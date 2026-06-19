"""Plain-English Heal Confirmation — CB.5.

When the self-healing engine finds a candidate locator replacement but isn't
confident enough to apply it automatically, this module asks the user a simple
yes/no question — entirely in plain English, with no code or selectors shown.

Thresholds (configurable in .phoenixrc [bdd] section):
  auto_heal_threshold  (default 0.85) — apply silently, no prompt
  ask_threshold        (default 0.55) — ask the user; below this, mark as needs_human

In CI (non-interactive) mode, the question is skipped, the candidate is logged
to reports/needs_review.md, and the test fails softly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

AUTO_HEAL_THRESHOLD = 0.85
ASK_THRESHOLD = 0.55


# ---------------------------------------------------------------------------
# Candidate description builder
# ---------------------------------------------------------------------------

def _describe_candidate(element_id: str, candidate: Dict[str, Any]) -> str:
    """Return a one-sentence plain-English description of the candidate locator."""
    label = candidate.get("label") or candidate.get("element_id", "an element")
    selector = candidate.get("selector", "")
    # Avoid showing raw CSS/XPath to the user
    if selector.startswith("[data-testid"):
        location = f'with test ID "{selector}"'
    elif selector.startswith("#"):
        location = f'with ID "{selector.lstrip("#")}"'
    elif "role" in selector.lower() or "button" in selector.lower():
        location = "in the same area"
    else:
        location = "in a similar position on the page"
    return f'a {label} {location}'


def _describe_original(element_id: str) -> str:
    return element_id.replace("_", " ").strip()


# ---------------------------------------------------------------------------
# needs_human report
# ---------------------------------------------------------------------------

def _write_needs_review(
    element_id: str,
    candidate: Dict[str, Any],
    screenshot: Optional[str],
    reports_dir: Path,
    reason: str = "",
) -> None:
    out = reports_dir / "needs_review.md"
    reports_dir.mkdir(parents=True, exist_ok=True)

    entry = (
        f"\n### {element_id} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"**What happened:** {reason or 'Locator no longer works and could not be healed automatically.'}\n"
        f"**Candidate found:** {_describe_candidate(element_id, candidate)}\n"
    )
    if screenshot and Path(screenshot).exists():
        entry += f"**Screenshot:** `{screenshot}`\n"
    entry += "\n**Action needed:** Open the application and update the locator manually.\n\n---\n"

    with out.open("a", encoding="utf-8") as fh:
        fh.write(entry)


# ---------------------------------------------------------------------------
# Promotion — apply candidate as the new primary locator
# ---------------------------------------------------------------------------

def _promote_candidate(
    element_id: str,
    candidate: Dict[str, Any],
    locators_file: Path,
) -> None:
    """Write the candidate selector into locators/<page>.json as primary."""
    if not locators_file.exists():
        return
    try:
        bundles: list = json.loads(locators_file.read_text(encoding="utf-8"))
        if not isinstance(bundles, list):
            bundles = [bundles]
        for bundle in bundles:
            eid = bundle.get("element_id", bundle.get("element_name", ""))
            if eid == element_id:
                old_primary = bundle.get("primary", {})
                # Push old primary to alternates
                alts = bundle.setdefault("alternates", [])
                if old_primary:
                    alts.insert(0, {**old_primary, "fallback": True})
                # Set new primary
                bundle["primary"] = {
                    "element_name": element_id,
                    "strategy": candidate.get("strategy", "css"),
                    "value": candidate.get("selector", ""),
                    "confidence": min(candidate.get("confidence", 0.7) + 0.1, 1.0),
                    "fallback": False,
                }
                bundle["element_name"] = element_id
                break
        locators_file.write_text(json.dumps(bundles, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError, KeyError):
        pass


# ---------------------------------------------------------------------------
# Main confirmation function
# ---------------------------------------------------------------------------

def prompt_user(
    element_id: str,
    candidate: Dict[str, Any],
    locators_file: Optional[Path] = None,
    screenshot: Optional[str] = None,
    reports_dir: Path = Path("reports"),
    interactive: Optional[bool] = None,
) -> str:
    """Ask the user (in plain English) whether to accept a healing candidate.

    Returns:
        "accepted"  — user said yes; locator has been promoted.
        "rejected"  — user said no; element recorded in needs_review.md.
        "skipped"   — non-interactive / CI mode; recorded in needs_review.md.
    """
    _interactive = interactive if interactive is not None else sys.stdin.isatty()

    original_desc = _describe_original(element_id)
    candidate_desc = _describe_candidate(element_id, candidate)

    if not _interactive:
        _write_needs_review(
            element_id, candidate, screenshot, reports_dir,
            reason="Running in CI — could not ask for confirmation.",
        )
        return "skipped"

    # Print the plain-English question
    print(f'\n  The "{original_desc}" seems to have moved or changed.')
    print(f"  I found {candidate_desc}.")
    print("  Is that the same element?\n")

    while True:
        choice = input("    [Y] Yes, use it    [N] No    [S] Show screenshot  > ").strip().upper()

        if choice == "Y":
            if locators_file:
                _promote_candidate(element_id, candidate, locators_file)
            print(f'  ✓ Updated — "{original_desc}" will use the new locator going forward.\n')
            return "accepted"

        elif choice == "N":
            _write_needs_review(
                element_id, candidate, screenshot, reports_dir,
                reason="User indicated the candidate does not match the original element.",
            )
            print(f'  Noted — "{original_desc}" has been added to reports/needs_review.md.\n')
            return "rejected"

        elif choice == "S":
            if screenshot and Path(screenshot).exists():
                print(f"\n  Screenshot saved at: {screenshot}")
                # Try to open with the OS default viewer (best-effort)
                try:
                    import subprocess
                    subprocess.Popen(["start", "", str(screenshot)], shell=True)
                except Exception:
                    pass
            else:
                print("  (No screenshot available for this failure)")
            # Re-ask
            print()

        else:
            print("  Please type Y, N, or S.")


# ---------------------------------------------------------------------------
# HealingEngine integration helper
# ---------------------------------------------------------------------------

def maybe_confirm(
    element_id: str,
    candidates: list,
    locators_file: Optional[Path] = None,
    screenshot: Optional[str] = None,
    reports_dir: Path = Path("reports"),
    auto_heal_threshold: float = AUTO_HEAL_THRESHOLD,
    ask_threshold: float = ASK_THRESHOLD,
    interactive: Optional[bool] = None,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """Decide whether to auto-heal, ask the user, or mark as needs_human.

    Args:
        element_id:           The element that failed.
        candidates:           List of candidate dicts with "selector" and "confidence".
        locators_file:        Path to the locators JSON file to update on acceptance.
        screenshot:           Path to the failure screenshot (optional).
        reports_dir:          Base reports directory.
        auto_heal_threshold:  Confidence at or above this → apply silently.
        ask_threshold:        Confidence at or above this → ask the user.
        interactive:          Override for stdin.isatty() — useful in tests.

    Returns:
        (outcome, chosen_candidate) where outcome is one of:
            "auto_healed" — applied silently.
            "accepted"    — user confirmed.
            "rejected"    — user declined.
            "skipped"     — CI mode; written to needs_review.
            "below_threshold" — no good candidate; written to needs_review.
    """
    if not candidates:
        _write_needs_review(
            element_id, {}, screenshot, reports_dir,
            reason="No alternative locators were available.",
        )
        return "below_threshold", None

    best = max(candidates, key=lambda c: c.get("confidence", 0.0))
    confidence = best.get("confidence", 0.0)

    if confidence >= auto_heal_threshold:
        if locators_file:
            _promote_candidate(element_id, best, locators_file)
        return "auto_healed", best

    if confidence >= ask_threshold:
        outcome = prompt_user(
            element_id, best, locators_file, screenshot, reports_dir, interactive
        )
        return outcome, best if outcome == "accepted" else None

    # Below ask_threshold
    _write_needs_review(
        element_id, best, screenshot, reports_dir,
        reason=f"Best candidate confidence ({confidence:.0%}) was too low to suggest automatically.",
    )
    return "below_threshold", None
