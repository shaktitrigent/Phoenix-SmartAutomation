"""Plain-English BDD Failure Reporter.

Translates pytest-bdd step failures into a human-readable Markdown report
that a non-technical user can act on — no stack traces, no selector strings.

The raw traceback is preserved in logs/ for engineering support.
The user-facing report lives in reports/failures/<run_id>.md.
"""

from __future__ import annotations

import re
import traceback as _tb
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Error → plain English translation
# ---------------------------------------------------------------------------

_TIMEOUT_RE = re.compile(r"timeout.*waiting for", re.IGNORECASE)
_LOCATOR_RE = re.compile(r"locator.*not found|element.*not found|no.*element", re.IGNORECASE)
_TEXT_ASSERT_RE = re.compile(r"expected.*to (contain|have|equal|match).*but (got|received|was)", re.IGNORECASE)
_NAV_TIMEOUT_RE = re.compile(r"navigation.*timeout|page.*did not load|net::ERR", re.IGNORECASE)
_STRICT_MODE_RE = re.compile(r"strict mode violation|resolved to \d+ elements", re.IGNORECASE)


def _extract_element_description(error_msg: str) -> str:
    """Try to pull a human-readable element name from the error message."""
    patterns = [
        r'get_by_role\(["\']([^"\']+)["\'],\s*name=["\']([^"\']+)["\']',
        r'get_by_label\(["\']([^"\']+)["\']',
        r'get_by_placeholder\(["\']([^"\']+)["\']',
        r'get_by_text\(["\']([^"\']+)["\']',
        r'\[data-testid=["\']([^"\']+)["\']',
        r'#([\w-]+)',
        r'\[name=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, error_msg)
        if m:
            parts = [g for g in m.groups() if g]
            return " ".join(parts)
    return "an element"


def _extract_text_mismatch(error_msg: str) -> tuple[str, str]:
    """Return (expected_text, actual_text) from an assertion error, or ("", "")."""
    m = re.search(r"expected.*?[\"'](.+?)[\"'].*?(?:but|was|got).*?[\"'](.+?)[\"']", error_msg, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def translate_error(exception: Exception) -> str:
    """Return a one-sentence plain-English explanation of *exception*."""
    msg = str(exception)

    if _NAV_TIMEOUT_RE.search(msg):
        return "The page didn't finish loading in time."

    if _TIMEOUT_RE.search(msg):
        elem = _extract_element_description(msg)
        return f'The "{elem}" could not be found or wasn\'t ready in time.'

    if _LOCATOR_RE.search(msg):
        elem = _extract_element_description(msg)
        return f'The "{elem}" could not be found on the page.'

    if _STRICT_MODE_RE.search(msg):
        elem = _extract_element_description(msg)
        return f'Multiple elements matched "{elem}" — the locator needs to be more specific.'

    if _TEXT_ASSERT_RE.search(msg):
        expected, actual = _extract_text_mismatch(msg)
        if expected and actual:
            return f'Expected to see "{expected}" but the page showed "{actual}".'
        return "The text on the page didn't match what was expected."

    # Generic fallback — trim to first sentence, remove Python identifiers
    first = msg.split("\n")[0][:200]
    first = re.sub(r"\bplaywright\b|\bpage\b|\blocator\b", "", first, flags=re.IGNORECASE).strip()
    return first or "An unexpected error occurred on this step."


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def record_step_failure(
    feature,
    scenario,
    step,
    exception: Exception,
    page=None,
    run_id: Optional[str] = None,
    reports_dir: str | Path = "reports",
) -> None:
    """Write a plain-English failure entry to reports/failures/<run_id>.md.

    Args:
        feature:     pytest-bdd Feature object.
        scenario:    pytest-bdd Scenario object.
        step:        pytest-bdd Step object.
        exception:   The exception that caused the failure.
        page:        Playwright Page fixture (optional; used for screenshot).
        run_id:      String run identifier; defaults to current UTC timestamp.
        reports_dir: Base reports directory (default: "reports/").
    """
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = Path(reports_dir)

    # Screenshot
    screenshot_rel = ""
    if page is not None:
        screenshots_dir = base / "failures" / run_id
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        safe_step = re.sub(r"[^\w\-]", "_", str(getattr(step, "name", "step")))[:40]
        screenshot_path = screenshots_dir / f"{safe_step}.png"
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
            screenshot_rel = str(screenshot_path)
        except Exception:
            pass

    # Plain-English explanation
    plain_reason = translate_error(exception)

    # Feature / scenario names
    feature_name = getattr(feature, "name", str(feature))
    scenario_name = getattr(scenario, "name", str(scenario))
    feature_path = getattr(getattr(feature, "rel_filename", None), "__str__", lambda: "")() or ""
    step_name = getattr(step, "name", str(step))

    # Build Markdown entry
    entry_lines = [
        f"### Scenario: {scenario_name}",
        f"> Source: `{feature_path}`" if feature_path else "",
        "",
        f"**Step that failed:** `{step_name}`",
        f"**What happened:** {plain_reason}",
    ]
    if screenshot_rel:
        entry_lines.append(f"**Screenshot:** `{screenshot_rel}`")
    entry_lines += [
        "",
        "> Full technical detail (for engineering support) is saved in `logs/`.",
        "",
        "---",
        "",
    ]
    entry = "\n".join(l for l in entry_lines if l is not None)

    # Write to the run-specific failure report
    failure_report = base / "failures" / f"{run_id}.md"
    failure_report.parent.mkdir(parents=True, exist_ok=True)

    header = ""
    if not failure_report.exists():
        header = (
            f"# Test Failure Report — {run_id}\n\n"
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"---\n\n"
        )

    with failure_report.open("a", encoding="utf-8") as fh:
        fh.write(header + entry)

    # Also append raw traceback to logs/ — never shown to the user directly
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    trace_log = logs_dir / f"failure_trace_{run_id}.txt"
    with trace_log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n--- {scenario_name} / {step_name} ---\n")
        fh.write(_tb.format_exc())
        fh.write("\n")
