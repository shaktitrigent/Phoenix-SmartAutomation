"""ServerLifecycle — context manager that starts and health-polls the intelligence server."""
from __future__ import annotations

import time

from preflight.adapters.base import TargetAdapter

# ---------------------------------------------------------------------------
# Requests import with urllib fallback
# ---------------------------------------------------------------------------
try:
    import requests as _requests

    def _get_status(url: str, timeout: int) -> int:
        r = _requests.get(url, timeout=timeout)
        return r.status_code

except ImportError:
    import urllib.request
    import urllib.error

    def _get_status(url: str, timeout: int) -> int:  # type: ignore[misc]
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code


class ServerLifecycle:
    def __init__(self, adapter: TargetAdapter, health_timeout: int = 30) -> None:
        self._adapter = adapter
        self._health_timeout = health_timeout

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "ServerLifecycle":
        self._adapter.start_server()
        self.wait_ready()
        return self

    def __exit__(self, *_) -> None:
        """Stop server — ALWAYS runs, even if an exception was raised."""
        self._adapter.stop_server()

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def wait_ready(self) -> None:
        """Poll GET health_url() every 1 s up to health_timeout_seconds.

        Raises RuntimeError if the server does not become healthy in time.
        """
        url = self._adapter.health_url()
        deadline = time.monotonic() + self._health_timeout
        last_exc: Exception | None = None

        while time.monotonic() < deadline:
            try:
                status = _get_status(url, timeout=3)
                if status == 200:
                    return
            except Exception as exc:
                last_exc = exc
            time.sleep(1)

        raise RuntimeError(
            f"Intelligence server did not become healthy at {url} "
            f"within {self._health_timeout}s. "
            f"Last error: {last_exc}"
        )
