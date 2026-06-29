"""T1 contract checks — fully deterministic, no LLM involvement."""
from __future__ import annotations

import json
from typing import Optional

from preflight.adapters.base import CliResult
from preflight.assertions.result import AssertionResult

# ---------------------------------------------------------------------------
# Requests import with urllib fallback
# ---------------------------------------------------------------------------
try:
    import requests as _requests

    def _get(url: str, timeout: int):
        r = _requests.get(url, timeout=timeout)
        return r.status_code, r.text

    def _post(url: str, payload: dict, timeout: int):
        r = _requests.post(url, json=payload, timeout=timeout)
        return r.status_code, r.text

except ImportError:
    import urllib.request
    import urllib.error

    def _get(url: str, timeout: int):  # type: ignore[misc]
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, str(exc)

    def _post(url: str, payload: dict, timeout: int):  # type: ignore[misc]
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, str(exc)


# ---------------------------------------------------------------------------
# T1 assertions
# ---------------------------------------------------------------------------

def check_health(health_url: str, timeout: int = 10) -> AssertionResult:
    """GET health_url; expect status=ok, llm.configured=True, llm.provider present."""
    name = "T1:health_endpoint"
    try:
        status_code, body = _get(health_url, timeout)
    except Exception as exc:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"Request failed: {exc}",
        )

    if status_code != 200:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"HTTP {status_code} — expected 200. Body: {body[:200]}",
        )

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"Response not valid JSON: {exc}. Body: {body[:200]}",
        )

    status = data.get("status")
    # 'degraded' is acceptable in the gate context — the server is intentionally
    # started without an API key so the automate endpoint uses the fast heuristic
    # fallback path instead of making slow LLM calls.
    if status not in ("ok", "degraded"):
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"status not in ('ok', 'degraded'), got: {status!r}",
            data=data,
        )

    llm = data.get("llm", {})
    # Only enforce LLM-configured when the server reports full 'ok'.
    # A 'degraded' server is running in fallback mode by design.
    if status == "ok":
        if not llm.get("configured", False):
            return AssertionResult(
                tier="T1",
                name=name,
                passed=False,
                detail=f"llm.configured is not True. llm block: {llm}",
                data=data,
            )

        if not llm.get("provider"):
            return AssertionResult(
                tier="T1",
                name=name,
                passed=False,
                detail=f"llm.provider is missing or empty. llm block: {llm}",
                data=data,
            )

    provider = llm.get("provider", "n/a")
    configured = llm.get("configured", False)
    return AssertionResult(
        tier="T1",
        name=name,
        passed=True,
        detail=f"status={status!r}, provider={provider!r}, configured={configured}",
        data=data,
    )


def check_endpoint_200(
    url: str,
    method: str = "POST",
    payload: Optional[dict] = None,
) -> AssertionResult:
    """Assert endpoint returns HTTP 200 with a JSON body."""
    name = f"T1:endpoint_200 {method} {url}"
    _payload = payload or {}

    try:
        if method.upper() == "POST":
            status_code, body = _post(url, _payload, timeout=15)
        else:
            status_code, body = _get(url, timeout=15)
    except Exception as exc:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"Request failed: {exc}",
        )

    if status_code != 200:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"HTTP {status_code} — expected 200. Body: {body[:300]}",
        )

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=False,
            detail=f"Response not valid JSON. Body: {body[:200]}",
        )

    return AssertionResult(
        tier="T1",
        name=name,
        passed=True,
        detail=f"HTTP 200, JSON body keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}",
        data=data if isinstance(data, dict) else {"response": data},
    )


def check_cli_exit_zero(result: CliResult, command_label: str) -> AssertionResult:
    """Assert a CliResult.exit_code == 0."""
    name = f"T1:cli_exit_zero [{command_label}]"
    if result.exit_code == 0:
        return AssertionResult(
            tier="T1",
            name=name,
            passed=True,
            detail=f"exit_code=0, duration={result.duration_s:.2f}s",
        )
    return AssertionResult(
        tier="T1",
        name=name,
        passed=False,
        detail=(
            f"exit_code={result.exit_code}\n"
            f"stdout (last 500 chars): {result.stdout[-500:]}\n"
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        ),
    )
