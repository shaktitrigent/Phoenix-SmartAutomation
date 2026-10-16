"""Attach concrete browser failure evidence to pytest JSON reports."""
import hashlib
from pathlib import Path
import pytest


@pytest.hookimpl(optionalhook=True)
def pytest_json_runtest_metadata(item, call):
    if call.excinfo is None: return {}
    page = item.funcargs.get("page") or item.funcargs.get("authenticated_page")
    if page is None: return {"failure_phase": call.when}
    destination = Path("test-results") / hashlib.sha256(item.nodeid.encode()).hexdigest()[:20]
    destination.mkdir(parents=True, exist_ok=True)
    image = destination / f"failure-{call.when}.png"
    try:
        page.screenshot(path=str(image))
    except Exception as exc:
        return {"failure_phase": call.when, "screenshot_error": type(exc).__name__}
    return {"failure_phase": call.when, "screenshot_path": str(image.resolve())}
