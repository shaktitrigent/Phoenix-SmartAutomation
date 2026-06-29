"""T3 behavior checks — probabilistic, exercise the live generated project."""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class BehaviorResult:
    pass_count: int
    total: int
    rate: float
    raw_output: str


@dataclass
class HealResult:
    recovered: bool
    registry_updated: bool
    pass_rate_after: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_first_locator_bundle(sandbox: Path):
    """Return (json_path, element_name, bundle_index) for the first bundle found.

    Returns None if no locator files exist.
    """
    locators_dir = sandbox / "locators"
    if not locators_dir.exists():
        return None

    for jf in sorted(locators_dir.glob("*.json")):
        try:
            raw = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        bundles = raw if isinstance(raw, list) else [raw]
        for idx, bundle in enumerate(bundles):
            if isinstance(bundle, dict) and bundle.get("element_name"):
                return jf, bundle["element_name"], idx, raw
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_tests(
    sandbox: Path,
    python_exe: str,
    test_path: str = "tests/",
) -> BehaviorResult:
    """Run pytest on sandbox/tests/ and return pass/total counts."""
    tests_dir = sandbox / test_path
    if not tests_dir.exists():
        return BehaviorResult(pass_count=0, total=0, rate=0.0, raw_output="tests/ directory missing")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        report_path = tf.name

    try:
        result = subprocess.run(
            [
                python_exe, "-m", "pytest",
                str(tests_dir),
                f"--json-report",
                f"--json-report-file={report_path}",
                "-q",
                "--tb=short",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(sandbox),
        )
        raw_output = result.stdout + result.stderr

        # Try to read the JSON report
        try:
            report = json.loads(Path(report_path).read_text(encoding="utf-8"))
            summary = report.get("summary", {})
            passed = summary.get("passed", 0)
            total = summary.get("total", 0)
            rate = (passed / total) if total > 0 else 0.0
            return BehaviorResult(
                pass_count=passed,
                total=total,
                rate=rate,
                raw_output=raw_output,
            )
        except (OSError, json.JSONDecodeError):
            # Fall back to parsing pytest stdout
            pass

    except subprocess.TimeoutExpired:
        return BehaviorResult(
            pass_count=0,
            total=0,
            rate=0.0,
            raw_output="pytest timed out after 300s",
        )
    finally:
        try:
            Path(report_path).unlink(missing_ok=True)
        except OSError:
            pass

    # Fallback: parse "X passed, Y failed" from stdout
    import re
    stdout = raw_output
    passed = 0
    total = 0
    m = re.search(r"(\d+) passed", stdout)
    if m:
        passed = int(m.group(1))
    m_fail = re.search(r"(\d+) failed", stdout)
    failed = int(m_fail.group(1)) if m_fail else 0
    m_err = re.search(r"(\d+) error", stdout)
    errors = int(m_err.group(1)) if m_err else 0
    total = passed + failed + errors

    rate = (passed / total) if total > 0 else 0.0
    return BehaviorResult(
        pass_count=passed,
        total=total,
        rate=rate,
        raw_output=raw_output,
    )


def inject_stale_locator(
    sandbox: Path,
    page_name: str,
    element_name: str,
) -> dict:
    """Demote primary to a broken selector; keep original as secondary[0].

    Returns the original bundle dict so it can be restored.
    """
    locator_file = sandbox / "locators" / f"{page_name}.json"
    raw = json.loads(locator_file.read_text(encoding="utf-8"))
    is_list = isinstance(raw, list)
    bundles = raw if is_list else [raw]

    original_bundle: Optional[dict] = None
    original_index: int = 0

    for idx, bundle in enumerate(bundles):
        if isinstance(bundle, dict) and bundle.get("element_name") == element_name:
            original_bundle = json.loads(json.dumps(bundle))  # deep copy
            original_index = idx

            # Demote current primary to secondary[0]
            current_primary = bundle.get("primary", "")
            secondary = bundle.get("secondary", [])
            if current_primary:
                secondary = [current_primary] + [s for s in secondary if s != current_primary]

            bundle["primary"] = "#broken-selector-999"
            bundle["secondary"] = secondary
            break

    if original_bundle is None:
        raise ValueError(
            f"Element '{element_name}' not found in {locator_file}"
        )

    # Write back
    out = bundles if is_list else bundles[0]
    locator_file.write_text(json.dumps(out, indent=2), encoding="utf-8")

    return original_bundle


def restore_locator(
    sandbox: Path,
    page_name: str,
    element_name: str,
    original: dict,
) -> None:
    """Restore a locator bundle to its original state."""
    locator_file = sandbox / "locators" / f"{page_name}.json"
    raw = json.loads(locator_file.read_text(encoding="utf-8"))
    is_list = isinstance(raw, list)
    bundles = raw if is_list else [raw]

    for idx, bundle in enumerate(bundles):
        if isinstance(bundle, dict) and bundle.get("element_name") == element_name:
            bundles[idx] = original
            break

    out = bundles if is_list else bundles[0]
    locator_file.write_text(json.dumps(out, indent=2), encoding="utf-8")


def run_heal_cycle(
    sandbox: Path,
    python_exe: str,
    adapter,
) -> HealResult:
    """Inject a stale locator, run fix, re-run tests; assess recovery.

    Steps:
    1. Find the first available locator bundle.
    2. Inject a broken primary selector.
    3. Run `phoenix fix` via adapter.
    4. Re-run the test suite.
    5. Check if the primary was promoted back (registry_updated).
    6. Restore the locator to original state.
    7. Return HealResult.
    """
    found = _find_first_locator_bundle(sandbox)
    if found is None:
        return HealResult(recovered=False, registry_updated=False, pass_rate_after=0.0)

    jf, element_name, bundle_index, _ = found
    page_name = jf.stem  # filename without .json

    original_bundle = inject_stale_locator(sandbox, page_name, element_name)

    try:
        # Run phoenix fix
        adapter.run_cli(["fix"], cwd=str(sandbox))

        # Re-run tests
        behavior_after = run_tests(sandbox, python_exe)
        pass_rate_after = behavior_after.rate

        # Check if the registry was updated (primary is no longer the broken value)
        locator_file = sandbox / "locators" / f"{page_name}.json"
        try:
            raw = json.loads(locator_file.read_text(encoding="utf-8"))
            bundles = raw if isinstance(raw, list) else [raw]
            registry_updated = False
            for bundle in bundles:
                if isinstance(bundle, dict) and bundle.get("element_name") == element_name:
                    if bundle.get("primary") != "#broken-selector-999":
                        registry_updated = True
                    break
        except (OSError, json.JSONDecodeError):
            registry_updated = False

        recovered = registry_updated and pass_rate_after > 0.0

        return HealResult(
            recovered=recovered,
            registry_updated=registry_updated,
            pass_rate_after=pass_rate_after,
        )
    finally:
        # Always restore the original locator
        try:
            restore_locator(sandbox, page_name, element_name, original_bundle)
        except Exception:
            pass
