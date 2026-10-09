"""One fail-closed acceptance policy for serialized and runtime locators."""
from __future__ import annotations

from typing import Any
import math


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else value.model_dump() if hasattr(value, "model_dump") else {}


def acceptance_reasons(locator: Any, bundle_metadata: dict | None = None,
                       *, stability_threshold: float = 0.8) -> list[str]:
    data = _dict(locator)
    meta = data.get("metadata") or {}
    bundle = bundle_metadata or {}
    reasons = []
    if not str(data.get("value") or data.get("selector") or "").strip():
        reasons.append("empty_selector")
    if any(m.get("broken") or m.get("unresolved") or str(m.get("status", "")).lower() in
           {"broken", "unresolved", "invalid"} for m in (meta, bundle)):
        reasons.append("unresolved")
    if data.get("verified_in_snapshot") is not True or type(meta.get("match_count")) is not int or meta.get("match_count") != 1:
        reasons.append("missing_unique_live_validation")
    if meta.get("identity_matches") is not True:
        reasons.append("missing_target_identity_validation")
    if meta.get("source") != "locator_expert":
        stability = meta.get("stability_category") or meta.get("stability")
        if isinstance(stability, dict):
            stability = stability.get("category")
        if str(stability or "").casefold() != "high":
            reasons.append("stability_not_high")
        score = meta.get("stability_score")
        if score is not None:
            try:
                score = float(score)
                if score > 1:
                    score /= 10
                if not math.isfinite(score) or not 0 <= score <= 1:
                    reasons.append("invalid_stability_score")
                elif score < stability_threshold:
                    reasons.append("below_stability_threshold")
            except (TypeError, ValueError):
                reasons.append("invalid_stability_score")
        if meta.get("dynamic") is True or meta.get("duplicate") is True:
            reasons.append("unstable_attribute")
    return list(dict.fromkeys(reasons))


def locator_accepted(locator: Any, bundle_metadata: dict | None = None,
                     *, stability_threshold: float = 0.8) -> bool:
    return not acceptance_reasons(locator, bundle_metadata, stability_threshold=stability_threshold)
