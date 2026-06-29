"""RegressionSuite — compare current T2/T3 results against a saved golden snapshot.

Workflow
--------
1. After a known-good run, call ``save_golden(results, path)`` to persist the
   snapshot.  The CI "bless" job does this after the acceptance gate passes.
2. On every subsequent run, call ``compare_against_golden(current_results, path)``
   to get a list of regressions (checks that used to pass but now fail).

Usage::

    # Save a golden snapshot from the most recent report:
    python -m preflight.suites.regression save --report preflight/reports/<ts>_report.md

    # Compare the latest run against the golden:
    python -m preflight.suites.regression compare --report preflight/reports/<ts>_report.md
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from preflight.assertions.result import AssertionResult

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent.parent          # preflight/
_DEFAULT_GOLDEN = _HERE / "golden_snapshot.json"


# ---------------------------------------------------------------------------
# Snapshot serialisation
# ---------------------------------------------------------------------------

def save_golden(results: List[AssertionResult], path: Path = _DEFAULT_GOLDEN) -> None:
    """Persist *results* as the golden baseline.

    Only T2 and T3 results are saved (T1 contract checks are fast-fail and
    generally do not exhibit non-determinism between runs).
    """
    snapshot = [
        asdict(r)
        for r in results
        if r.tier in ("T2", "T3")
    ]
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Golden snapshot saved to %s (%d entries)", path, len(snapshot))


def load_golden(path: Path = _DEFAULT_GOLDEN) -> List[dict]:
    """Load and return the golden snapshot as a list of dicts."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not load golden snapshot from %s: %s", path, exc)
        return []


# ---------------------------------------------------------------------------
# Regression comparison
# ---------------------------------------------------------------------------

@dataclass
class Regression:
    """A check that passed in the golden run but failed in the current run."""
    tier: str
    name: str
    golden_passed: bool
    current_passed: bool
    current_detail: str


def compare_against_golden(
    current_results: List[AssertionResult],
    golden_path: Path = _DEFAULT_GOLDEN,
) -> List[Regression]:
    """Return regressions: checks that passed in golden but fail now.

    A check that is *new* (not in golden) is not a regression.
    A check that was failing in golden and still fails is not a regression.
    """
    golden = {entry["name"]: entry for entry in load_golden(golden_path)}
    if not golden:
        logger.warning("No golden snapshot found at %s — skipping regression check", golden_path)
        return []

    regressions: List[Regression] = []
    current_by_name = {r.name: r for r in current_results}

    for name, golden_entry in golden.items():
        if not golden_entry.get("passed", False):
            continue  # wasn't passing in golden — not a regression if it fails now
        current = current_by_name.get(name)
        if current is None:
            regressions.append(Regression(
                tier=golden_entry.get("tier", "?"),
                name=name,
                golden_passed=True,
                current_passed=False,
                current_detail="Check no longer present in current run (possible rename/removal)",
            ))
        elif not current.passed:
            regressions.append(Regression(
                tier=current.tier,
                name=name,
                golden_passed=True,
                current_passed=False,
                current_detail=current.detail,
            ))

    return regressions


def regressions_to_assertion_results(regressions: List[Regression]) -> List[AssertionResult]:
    """Convert regressions to AssertionResult objects for integration with Gate/Reporter."""
    return [
        AssertionResult(
            tier=r.tier,
            name=f"regression:{r.name}",
            passed=False,
            detail=(
                f"REGRESSION — was passing in golden, now failing.\n"
                f"Current detail: {r.current_detail}"
            ),
        )
        for r in regressions
    ]


# ---------------------------------------------------------------------------
# Report parser (extract AssertionResults from a Markdown report)
# ---------------------------------------------------------------------------

def parse_results_from_report(report_path: Path) -> List[AssertionResult]:
    """Best-effort extraction of AssertionResult names+pass from a report .md file.

    This is used by the CLI to load results when a live run is unavailable.
    """
    results: List[AssertionResult] = []
    if not report_path.exists():
        return results

    import re
    content = report_path.read_text(encoding="utf-8")

    # Match table rows from T1/T2 Results sections: "- [T1] **name** — detail"
    for m in re.finditer(
        r"-\s+\[(T[123])\]\s+\*\*([^*]+)\*\*(?:\s+—\s+(.*))?",
        content,
    ):
        tier = m.group(1)
        name = m.group(2).strip()
        detail = (m.group(3) or "").strip()
        results.append(AssertionResult(tier=tier, name=name, passed=True, detail=detail))

    # Extract failures from "### Failed" section
    in_failed = False
    for line in content.splitlines():
        if line.strip().startswith("### Failed"):
            in_failed = True
            continue
        if line.strip().startswith("### ") and in_failed:
            in_failed = False
        if in_failed:
            m = re.match(r"-\s+\[(T[123])\]\s+\*\*([^*]+)\*\*", line)
            if m:
                tier = m.group(1)
                name = m.group(2).strip()
                # Update the previously added entry to failed, or add new
                existing = next((r for r in results if r.name == name), None)
                if existing:
                    existing.passed = False
                else:
                    results.append(AssertionResult(tier=tier, name=name, passed=False))

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Regression suite — golden snapshot comparison")
    sub = parser.add_subparsers(dest="command", required=True)

    save_p = sub.add_parser("save", help="Save current report as golden baseline")
    save_p.add_argument("--report", required=True, help="Path to a _report.md file")
    save_p.add_argument("--golden", default=str(_DEFAULT_GOLDEN), help="Output golden JSON path")

    cmp_p = sub.add_parser("compare", help="Compare current report against golden")
    cmp_p.add_argument("--report", required=True, help="Path to a _report.md file")
    cmp_p.add_argument("--golden", default=str(_DEFAULT_GOLDEN), help="Golden JSON path")

    args = parser.parse_args(argv)

    report_path = Path(args.report)
    golden_path = Path(args.golden)
    results = parse_results_from_report(report_path)

    if not results:
        print(f"No results could be parsed from {report_path}")
        return 2

    if args.command == "save":
        save_golden(results, golden_path)
        print(f"Golden snapshot saved to {golden_path} ({len(results)} checks)")
        return 0

    # compare
    regressions = compare_against_golden(results, golden_path)
    if not regressions:
        print("No regressions detected vs golden snapshot.")
        return 0

    print(f"\n{len(regressions)} REGRESSION(S) DETECTED:\n")
    for r in regressions:
        print(f"  [{r.tier}] {r.name}")
        print(f"        {r.current_detail[:120]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
