"""Jira REST API client for Phoenix.

Communicates with Jira Cloud (v3 API) or Jira Server/Data Center (v2 API).
Authentication uses HTTP Basic Auth: email + API token (Cloud) or
username + API token/password (Server).

Usage::

    from phoenix.integrations.jira.config import JiraConfig
    from phoenix.integrations.jira.client import JiraClient

    config = JiraConfig(url="https://yourco.atlassian.net", project_key="PROJ")
    client = JiraClient(config)

    health = client.health_check()
    issue  = client.get_issue("PROJ-123")
    docs   = issue.as_supporting_documents()
"""

from __future__ import annotations

import logging
import mimetypes
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

from phoenix.integrations.jira.adf import adf_to_text, extract_acceptance_criteria
from phoenix.integrations.jira.config import JiraConfig

logger = logging.getLogger(__name__)

# Jira Cloud uses /rest/api/3  (ADF for rich text)
# Jira Server/DC uses /rest/api/2 (wiki markup, simpler text)
_CLOUD_API = "/rest/api/3"
_SERVER_API = "/rest/api/2"


class JiraAuthError(RuntimeError):
    """Raised when Jira returns 401 / 403."""


class JiraNotFoundError(RuntimeError):
    """Raised when the requested issue does not exist."""


class JiraConnectionError(RuntimeError):
    """Raised when the Jira server cannot be reached."""


# ---------------------------------------------------------------------------
# Data model for a fetched issue
# ---------------------------------------------------------------------------

@dataclass
class JiraIssue:
    """Represents a Jira issue with all data needed for test generation."""

    key: str
    summary: str
    description: str
    issue_type: str
    priority: str
    status: str
    labels: List[str]
    acceptance_criteria: List[str]
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    def as_user_story(self) -> str:
        """Format issue as a user story string for the LLM."""
        lines = [f"[{self.key}] {self.summary}"]
        if self.description.strip():
            lines += ["", self.description.strip()]
        return "\n".join(lines)

    def as_supporting_documents(
        self,
        client: "JiraClient",
    ) -> List[Dict[str, str]]:
        """Download attachments and return them as supporting document dicts.

        Each dict has keys: filename, format, content.
        Non-text attachments that cannot be parsed are skipped silently.
        """
        from phoenix.documents.loader import DocumentLoader

        docs: List[Dict[str, str]] = []
        loader = DocumentLoader()
        max_bytes = client.config.max_attachment_size_kb * 1024

        for att in self.attachments:
            filename = att.get("filename", "attachment")
            content_url = att.get("content", "")
            size = att.get("size", 0)
            mime = att.get("mimeType", "")

            # Skip binary formats we can't extract text from (images, videos, zip)
            ext = Path(filename).suffix.lower()
            if ext not in loader.SUPPORTED_EXTS:
                logger.debug("Skipping unsupported attachment format: %s", filename)
                continue

            if size > max_bytes:
                logger.warning(
                    "Skipping attachment %s — size %d KB exceeds limit %d KB",
                    filename,
                    size // 1024,
                    client.config.max_attachment_size_kb,
                )
                continue

            raw = client.download_attachment(content_url)
            if raw is None:
                continue

            # Write to a temp file so DocumentLoader can read it
            suffix = ext or mimetypes.guess_extension(mime) or ".bin"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw)
                tmp_path = Path(tmp.name)

            try:
                doc = loader.load_file(tmp_path)
                if doc:
                    doc["filename"] = filename  # restore original name
                    docs.append(doc)
                    logger.info("Loaded attachment: %s (%d chars)", filename, len(doc["content"]))
            finally:
                tmp_path.unlink(missing_ok=True)

        return docs


# ---------------------------------------------------------------------------
# Jira HTTP client
# ---------------------------------------------------------------------------

class JiraClient:
    """Thin HTTP client for the Jira REST API."""

    def __init__(self, config: JiraConfig) -> None:
        if not config.is_configured:
            missing = ", ".join(config.missing_fields())
            raise JiraAuthError(
                f"Jira integration is not fully configured. Missing: {missing}\n"
                "Set the required environment variables and ensure [jira] url is set in .phoenixrc."
            )
        self.config = config
        self._base = config.resolved_url
        self._auth = HTTPBasicAuth(config.resolved_email, config.api_token)
        self._session = requests.Session()
        self._session.auth = self._auth
        self._session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        # Detect Cloud vs Server to pick the right API version
        self._api_path = _CLOUD_API  # default; adjusted by health check

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _url(self, path: str) -> str:
        return f"{self._base}{self._api_path}{path}"

    def _get(self, path: str, **params) -> Dict[str, Any]:
        url = self._url(path)
        try:
            resp = self._session.get(url, params=params or None, timeout=self.config.timeout)
        except requests.ConnectionError as exc:
            raise JiraConnectionError(f"Cannot reach Jira at {self._base}: {exc}") from exc
        except requests.Timeout as exc:
            raise JiraConnectionError(f"Jira request timed out after {self.config.timeout}s") from exc

        if resp.status_code == 401:
            raise JiraAuthError(
                "Jira returned 401 Unauthorized. "
                "Check JIRA_EMAIL and JIRA_API_TOKEN are correct."
            )
        if resp.status_code == 403:
            raise JiraAuthError(
                f"Jira returned 403 Forbidden for {path}. "
                "The account may lack permission to read this resource."
            )
        if resp.status_code == 404:
            raise JiraNotFoundError(f"Jira resource not found: {path}")

        resp.raise_for_status()
        return resp.json()

    def _parse_description(self, fields: Dict[str, Any]) -> str:
        """Convert description field (ADF dict or plain string) to plain text."""
        desc = fields.get("description")
        if desc is None:
            return ""
        if isinstance(desc, dict):
            return adf_to_text(desc).strip()
        return str(desc).strip()

    def _parse_acceptance_criteria(self, fields: Dict[str, Any], description_text: str) -> List[str]:
        """Extract acceptance criteria from the configured field or description body."""
        ac_field = self.config.acceptance_criteria_field

        if ac_field and ac_field != "description":
            raw = fields.get(ac_field)
            if raw:
                text = adf_to_text(raw) if isinstance(raw, dict) else str(raw)
                # Split by newline / bullet
                import re
                items = [
                    re.sub(r"^[-*\d.]+\s*", "", line).strip()
                    for line in text.splitlines()
                    if line.strip()
                ]
                return [i for i in items if i]

        # Fall back to parsing "Acceptance Criteria" section from description
        return extract_acceptance_criteria(description_text)

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def health_check(self) -> Dict[str, Any]:
        """Verify connectivity and credentials.

        Returns a dict with status, account display name, and server info.
        Raises JiraAuthError or JiraConnectionError on failure.
        """
        try:
            # Try v3 (Cloud)
            myself = self._get("/myself")
            server_info = self._get("/serverInfo")
            return {
                "status": "ok",
                "account": myself.get("displayName") or myself.get("name", "unknown"),
                "email": myself.get("emailAddress", ""),
                "server_title": server_info.get("serverTitle", ""),
                "version": server_info.get("version", ""),
                "deployment_type": server_info.get("deploymentType", ""),
                "url": self._base,
                "api_version": self._api_path.split("/")[-1],
            }
        except JiraNotFoundError:
            # v3 /myself not found — try v2 (Server/DC)
            self._api_path = _SERVER_API
            myself = self._get("/myself")
            server_info = self._get("/serverInfo")
            return {
                "status": "ok",
                "account": myself.get("displayName") or myself.get("name", "unknown"),
                "email": myself.get("emailAddress", ""),
                "server_title": server_info.get("serverTitle", ""),
                "version": server_info.get("version", ""),
                "deployment_type": "server",
                "url": self._base,
                "api_version": self._api_path.split("/")[-1],
            }

    def get_issue(self, issue_key: str) -> JiraIssue:
        """Fetch a single Jira issue and return a structured JiraIssue.

        Args:
            issue_key: Issue key such as ``PROJ-123``.
        """
        # Expand attachment metadata
        data = self._get(f"/issue/{issue_key}", fields="*all", expand="renderedFields")
        fields = data.get("fields", {})

        description_text = self._parse_description(fields)
        acceptance_criteria = self._parse_acceptance_criteria(fields, description_text)

        attachments = []
        if self.config.download_attachments:
            for att in fields.get("attachment", []):
                attachments.append({
                    "filename": att.get("filename", ""),
                    "content": att.get("content", ""),
                    "size": att.get("size", 0),
                    "mimeType": att.get("mimeType", ""),
                })

        return JiraIssue(
            key=data.get("key", issue_key),
            summary=fields.get("summary", ""),
            description=description_text,
            issue_type=fields.get("issuetype", {}).get("name", "Story"),
            priority=fields.get("priority", {}).get("name", "Medium"),
            status=fields.get("status", {}).get("name", ""),
            labels=fields.get("labels", []),
            acceptance_criteria=acceptance_criteria,
            attachments=attachments,
        )

    def download_attachment(self, url: str) -> Optional[bytes]:
        """Download attachment bytes from a Jira content URL."""
        try:
            resp = self._session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.warning("Failed to download attachment from %s: %s", url, exc)
            return None

    def search_issues(self, jql: str, max_results: int = 20) -> List[JiraIssue]:
        """Search for issues using JQL.

        Args:
            jql: JQL query string, e.g. ``project = PROJ AND sprint in openSprints()``
            max_results: Maximum number of issues to return.
        """
        data = self._get(
            "/search",
            jql=jql,
            maxResults=max_results,
            fields="summary,description,issuetype,priority,status,labels,attachment",
        )
        issues = []
        for item in data.get("issues", []):
            fields = item.get("fields", {})
            description_text = self._parse_description(fields)
            issues.append(JiraIssue(
                key=item.get("key", ""),
                summary=fields.get("summary", ""),
                description=description_text,
                issue_type=fields.get("issuetype", {}).get("name", "Story"),
                priority=fields.get("priority", {}).get("name", "Medium"),
                status=fields.get("status", {}).get("name", ""),
                labels=fields.get("labels", []),
                acceptance_criteria=self._parse_acceptance_criteria(fields, description_text),
                attachments=[
                    {
                        "filename": a.get("filename", ""),
                        "content": a.get("content", ""),
                        "size": a.get("size", 0),
                        "mimeType": a.get("mimeType", ""),
                    }
                    for a in fields.get("attachment", [])
                ],
            ))
        return issues
