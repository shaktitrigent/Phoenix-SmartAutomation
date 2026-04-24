"""HTTP client for phoenix-intelligence.

Uses requests with automatic retry / exponential back-off so transient errors
(connection reset, 5xx responses) are handled transparently.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from phoenix.sdk.config import PhoenixConfig

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_BASE_BACKOFF = 0.5  # seconds


class IntelligenceClient:
    """HTTP client for communicating with phoenix-intelligence."""

    def __init__(self, config: PhoenixConfig) -> None:
        self.config = config.intelligence
        self.base_url = self.config.base_url.rstrip("/")
        self.timeout = self.config.timeout
        self.retry_count = self.config.retry_count

    # ------------------------------------------------------------------
    def _build_url(self, path: str) -> str:
        """Join base URL and path without duplicating /api/v1 prefixes."""
        if self.base_url.endswith("/api/v1") and path.startswith("/api/v1/"):
            path = path[len("/api/v1") :]
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    # ------------------------------------------------------------------
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._build_url(path)
        last_error: Optional[Exception] = None

        for attempt in range(self.retry_count):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)

                if response.status_code in _RETRYABLE_STATUS:
                    logger.warning(
                        "Intelligence server returned %d on attempt %d/%d — retrying",
                        response.status_code,
                        attempt + 1,
                        self.retry_count,
                    )
                    last_error = requests.HTTPError(
                        f"HTTP {response.status_code}", response=response
                    )
                    time.sleep(_BASE_BACKOFF * (2**attempt))
                    continue

                response.raise_for_status()
                return response.json()

            except requests.ConnectionError as exc:
                logger.warning(
                    "Connection error on attempt %d/%d: %s",
                    attempt + 1,
                    self.retry_count,
                    exc,
                )
                last_error = exc
                time.sleep(_BASE_BACKOFF * (2**attempt))

            except requests.Timeout as exc:
                logger.warning(
                    "Timeout on attempt %d/%d: %s",
                    attempt + 1,
                    self.retry_count,
                    exc,
                )
                last_error = exc
                time.sleep(_BASE_BACKOFF * (2**attempt))

            except requests.HTTPError as exc:
                # Non-retryable 4xx — re-raise immediately
                raise RuntimeError(
                    f"Phoenix Intelligence request failed with "
                    f"{exc.response.status_code}: {exc.response.text[:200]}"
                ) from exc

        raise RuntimeError(
            f"Phoenix Intelligence request failed after {self.retry_count} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    def generate_tests(
        self,
        user_story: str,
        application_url: Optional[str],
        acceptance_criteria: List[str],
        test_type: str,
        risk_level: Optional[str],
    ) -> Dict[str, Any]:
        payload = {
            "user_story": user_story,
            "application_url": application_url,
            "acceptance_criteria": acceptance_criteria,
            "options": {
                "test_type": test_type,
                "risk_level": risk_level,
            },
        }
        return self._post("/api/v1/tests/generate", payload)

    def discover_locators(
        self,
        page_url: str,
        elements: List[str],
        dom_snapshot: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "page_url": page_url,
            "elements": elements,
            "dom_snapshot": dom_snapshot,
        }
        return self._post("/api/v1/locators/discover", payload)

    def analyze_failure(
        self,
        error_message: str,
        traceback: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "error_message": error_message,
            "traceback": traceback,
        }
        return self._post("/api/v1/failures/analyze", payload)
