"""BootStage — verify intelligence server health and start AUT."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import List

from preflight.assertions.contract import check_health
from preflight.assertions.result import AssertionResult

# Requests / urllib fallback for AUT health check
try:
    import requests as _requests

    def _aut_ok(url: str, timeout: int = 10) -> bool:
        try:
            r = _requests.get(url, timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

except ImportError:
    import urllib.request
    import urllib.error

    def _aut_ok(url: str, timeout: int = 10) -> bool:  # type: ignore[misc]
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False


class BootStage:
    """Start the AUT (serve.py) or confirm an external AUT is reachable.

    When ``aut_url`` is set in config, the local serve.py is NOT started and the
    provided URL is used as the application-under-test for the whole gate run.
    """

    def run(self, context: dict) -> List[AssertionResult]:
        results: List[AssertionResult] = []
        config = context["config"]
        adapter = context["adapter"]

        external_aut_url: str | None = config.get("aut_url", "").strip() or None

        if external_aut_url:
            # ------------------------------------------------------------------
            # External AUT mode — skip local serve.py, verify connectivity only
            # ------------------------------------------------------------------
            context["aut_proc"] = None
            context["aut_url"] = external_aut_url

            aut_reachable = _aut_ok(external_aut_url, timeout=15)
            results.append(AssertionResult(
                tier="T1",
                name="T1:aut_serving",
                passed=aut_reachable,
                detail=(
                    f"External AUT at {external_aut_url} is reachable"
                    if aut_reachable
                    else f"External AUT at {external_aut_url} did not respond within 15s — "
                         "check network connectivity"
                ),
            ))
        else:
            # ------------------------------------------------------------------
            # Local AUT mode — start preflight/aut/serve.py
            # ------------------------------------------------------------------
            aut_port: int = int(config.get("aut_port", 9000))
            aut_dir = Path(__file__).parent.parent / "aut"
            serve_script = aut_dir / "serve.py"

            import sys
            aut_proc = subprocess.Popen(
                [sys.executable, str(serve_script), "--port", str(aut_port)],
                cwd=str(aut_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            context["aut_proc"] = aut_proc
            context["aut_port"] = aut_port

            local_aut_url = f"http://127.0.0.1:{aut_port}/"
            context["aut_url"] = local_aut_url

            deadline = time.monotonic() + 15
            aut_started = False
            while time.monotonic() < deadline:
                if _aut_ok(local_aut_url, timeout=2):
                    aut_started = True
                    break
                time.sleep(1)

            results.append(AssertionResult(
                tier="T1",
                name="T1:aut_serving",
                passed=aut_started,
                detail=(
                    f"AUT at {local_aut_url} responded HTTP 200"
                    if aut_started
                    else f"AUT at {local_aut_url} did not become available within 15s"
                ),
            ))

        # ------------------------------------------------------------------
        # T1: Start intelligence server (if the adapter manages it)
        # ------------------------------------------------------------------
        health_timeout: int = int(config.get("health_timeout_seconds", 30))

        if hasattr(adapter, "start_server"):
            adapter.start_server()

            # Poll until the server is ready or we time out
            health_url = adapter.health_url()
            deadline = time.monotonic() + health_timeout
            server_ready = False
            while time.monotonic() < deadline:
                if _aut_ok(health_url, timeout=2):
                    server_ready = True
                    break
                time.sleep(2)

            if not server_ready:
                results.append(AssertionResult(
                    tier="T1",
                    name="T1:health_endpoint",
                    passed=False,
                    detail=(
                        f"Intelligence server at {health_url} did not become available "
                        f"within {health_timeout}s — check uvicorn startup logs"
                    ),
                ))
                return results  # no point checking further

        # T1: Intelligence server health (always required)
        results.append(check_health(adapter.health_url(), timeout=10))

        # NOTE: We intentionally skip a live /tests/generate smoke test here.
        # That endpoint makes a real LLM call (10-30s) and would always time out
        # the 15-second contract check.  The health endpoint (above) already
        # confirms the server is up, LLM is configured, and the provider key is
        # present — that is sufficient for T1.

        return results
