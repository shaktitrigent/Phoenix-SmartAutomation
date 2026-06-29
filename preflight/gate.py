"""Gate — compute GO / GO-WITH-WARNINGS / NO-GO verdicts from assertion results."""
from __future__ import annotations

from typing import List

from preflight.assertions.result import AssertionResult


# ---------------------------------------------------------------------------
# Pure function (unit-test friendly)
# ---------------------------------------------------------------------------

def _compute_verdict(
    results: List[AssertionResult],
    t3_first_run_green_min: float,
    t3_post_heal_green_min: float,
) -> str:
    """Pure verdict computation — no side effects.

    Rules
    -----
    * Any T1 or T2 failure                          → NO-GO
    * All T1/T2 pass, any T3 below threshold        → NO-GO
    * All T1/T2 pass, T3 ≥ threshold with warnings  → GO-WITH-WARNINGS
    * Everything green, no warnings                 → GO

    A *warning* is a T3 result that passed but ``data.get('warned') is True``.
    """
    if not results:
        return "NO-GO"

    # Split by tier
    t1_t2 = [r for r in results if r.tier in ("T1", "T2")]
    t3 = [r for r in results if r.tier == "T3"]

    # Rule 1 — any hard failure
    if any(not r.passed for r in t1_t2):
        return "NO-GO"

    # Rule 2 — T3 below threshold
    for r in t3:
        if not r.passed:
            return "NO-GO"

        # Check numeric threshold from data if present
        rate = r.data.get("rate")
        threshold = r.data.get("threshold")
        if rate is not None and threshold is not None:
            if float(rate) < float(threshold):
                return "NO-GO"

    # Rule 3 — all pass but some T3 warned
    has_warnings = any(r.data.get("warned") for r in t3 if r.passed)
    if has_warnings:
        return "GO-WITH-WARNINGS"

    return "GO"


# ---------------------------------------------------------------------------
# Gate class
# ---------------------------------------------------------------------------

class Gate:
    """Evaluate a collection of AssertionResults and return a verdict string."""

    def verdict(
        self,
        results: List[AssertionResult],
        t3_first_run_green_min: float,
        t3_post_heal_green_min: float,
    ) -> str:
        """Return 'GO', 'GO-WITH-WARNINGS', or 'NO-GO'.

        Parameters
        ----------
        results:
            All AssertionResult objects collected across every stage.
        t3_first_run_green_min:
            Minimum acceptable first-run green rate (0–1).
        t3_post_heal_green_min:
            Minimum acceptable post-heal green rate (0–1).
        """
        return _compute_verdict(results, t3_first_run_green_min, t3_post_heal_green_min)
