"""Jira integration configuration.

Non-sensitive settings live in .phoenixrc under [jira].
Secrets are read exclusively from environment variables — never from config files.

Environment variables (always take precedence over config file values):
    JIRA_URL          — Jira instance base URL
    JIRA_EMAIL        — account email used for Basic auth
    JIRA_API_TOKEN    — API token from https://id.atlassian.com/manage-profile/security/api-tokens
"""

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field


class JiraConfig(BaseModel):
    """Jira integration settings loaded from .phoenixrc [jira] section."""

    # Non-sensitive — can live in .phoenixrc
    url: Optional[str] = Field(
        default=None,
        description="Jira instance base URL, e.g. https://yourcompany.atlassian.net",
    )
    project_key: Optional[str] = Field(
        default=None,
        description="Default project key, e.g. PROJ (used when issue key has no prefix)",
    )
    board_id: Optional[str] = Field(
        default=None,
        description="Board ID for sprint queries (optional)",
    )
    acceptance_criteria_field: str = Field(
        default="description",
        description=(
            "Jira field that holds acceptance criteria. "
            "Use 'description' to parse AC from the description body, "
            "or a custom field ID like 'customfield_10016'."
        ),
    )
    download_attachments: bool = Field(
        default=True,
        description="Download issue attachments and pass them as supporting documents",
    )
    max_attachment_size_kb: int = Field(
        default=5120,
        description="Maximum attachment size to download in KB (default 5 MB)",
    )
    timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds",
    )

    # ------------------------------------------------------------------ #
    # Secrets — read from environment only, never stored in config files  #
    # ------------------------------------------------------------------ #

    @property
    def resolved_url(self) -> Optional[str]:
        """Env JIRA_URL overrides config file value."""
        return (os.environ.get("JIRA_URL") or self.url or "").rstrip("/") or None

    @property
    def resolved_email(self) -> Optional[str]:
        """Env JIRA_EMAIL overrides config file value."""
        return os.environ.get("JIRA_EMAIL") or None

    @property
    def api_token(self) -> Optional[str]:
        """API token — only from environment, never from config file."""
        return os.environ.get("JIRA_API_TOKEN") or None

    # ------------------------------------------------------------------ #
    # Validation helpers                                                  #
    # ------------------------------------------------------------------ #

    @property
    def is_configured(self) -> bool:
        """True when all required credentials are present."""
        return bool(self.resolved_url and self.resolved_email and self.api_token)

    def missing_fields(self) -> list[str]:
        """Return list of missing required fields (empty when fully configured)."""
        missing = []
        if not self.resolved_url:
            missing.append("JIRA_URL (env) or url (config)")
        if not self.resolved_email:
            missing.append("JIRA_EMAIL (env)")
        if not self.api_token:
            missing.append("JIRA_API_TOKEN (env)")
        return missing
