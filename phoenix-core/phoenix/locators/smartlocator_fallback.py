"""Conditional LocatorExpert fallback for unresolved SmartLocatorAI bundles.

This module intentionally contains no HTTP or browser implementation.  Its
callers provide discovery and validation callables, keeping the decision and
merge contract independently testable while guaranteeing that an LLM result
is never accepted without a live ``match_count == 1`` result.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy


DiscoveryCallable = Callable[[Dict[str, Any]], Dict[str, Any]]
ValidationCallable = Callable[[Locator, Dict[str, Any]], Dict[str, Any]]

_STRATEGIES = {
    "role": LocatorStrategy.ROLE,
    "role selector": LocatorStrategy.ROLE,
    "label": LocatorStrategy.LABEL,
    "placeholder": LocatorStrategy.PLACEHOLDER,
    "test-id": LocatorStrategy.TEST_ID,
    "testid": LocatorStrategy.TEST_ID,
    "text": LocatorStrategy.TEXT,
    "text selector": LocatorStrategy.TEXT,
    "css": LocatorStrategy.CSS,
    "css selector": LocatorStrategy.CSS,
    "xpath": LocatorStrategy.XPATH,
    "context": LocatorStrategy.CONTEXT,
    "context selector": LocatorStrategy.CONTEXT,
    "alt-text": LocatorStrategy.ALT_TEXT,
    "title": LocatorStrategy.TITLE,
}

_POSITIONAL_PATTERNS = (
    re.compile(r"\.(?:first|last)\s*\(", re.IGNORECASE),
    re.compile(r"\.nth\s*\(", re.IGNORECASE),
    re.compile(r":nth-(?:child|of-type)\s*\(", re.IGNORECASE),
    re.compile(r"//[^\n]*\[\s*\d+\s*\]"),
)


def _raw_records(bundle: LocatorBundle) -> List[Dict[str, Any]]:
    metadata = bundle.metadata or {}
    records = metadata.get("smartlocator_raw_records", [])
    return [record for record in records if isinstance(record, dict)]


def _stability(record: Dict[str, Any]) -> str:
    value = record.get("stability") or record.get("stability_category") or ""
    if isinstance(value, dict):
        value = value.get("category", "")
    return str(value).strip().lower()


def fallback_reasons(bundle: LocatorBundle) -> List[str]:
    """Return deterministic fallback reasons, or an empty list when resolved.

    A uniquely browser-verified primary is terminal even when a lower-quality
    alternate carries warnings. This invariant prevents unnecessary LLM calls.
    """
    if bundle.primary.verified_in_snapshot is True:
        return []

    records = _raw_records(bundle)
    reasons: List[str] = []
    match_counts = [record.get("match_count") for record in records]
    if any(count == 0 for count in match_counts):
        reasons.append("not_found")
    if any(isinstance(count, int) and count > 1 for count in match_counts):
        reasons.append("ambiguous")

    has_working = any(
        record.get("element_has_working_locator") is True
        and record.get("working_locator_type")
        and record.get("working_locator_value")
        for record in records
    )
    if not has_working:
        reasons.append("no_validated_working_locator")

    if any(_stability(record) == "low" for record in records):
        reasons.append("low_stability")

    for record in records:
        warnings = " ".join(str(item).lower() for item in record.get("warnings", []) or [])
        if _stability(record) == "medium" and (
            record.get("dynamic") is True
            or record.get("duplicate") is True
            or "ambigu" in warnings
            or "dynamic" in warnings
            or "duplicate" in warnings
        ):
            reasons.append("unstable_medium_locator")
            break

    if not records:
        reasons.append("missing_validation_evidence")
    return list(dict.fromkeys(reasons))


def build_unresolved_payload(
    bundle: LocatorBundle,
    *,
    page_url: str,
) -> Optional[Dict[str, Any]]:
    """Build the scoped evidence sent to LocatorExpert for one element."""
    reasons = fallback_reasons(bundle)
    if not reasons:
        return None

    metadata = bundle.metadata or {}
    records = _raw_records(bundle)
    element_data = metadata.get("element_data")
    if not isinstance(element_data, dict):
        element_data = next(
            (
                record.get("element_data")
                for record in records
                if isinstance(record.get("element_data"), dict)
            ),
            {},
        )

    attempted = []
    for record in records:
        locator_type = record.get("locator_type") or record.get("strategy")
        locator_value = (
            record.get("locator_value")
            or record.get("selector")
            or record.get("value")
        )
        if locator_type and locator_value:
            attempted.append({
                "locator_type": locator_type,
                "locator_value": locator_value,
                "validated": record.get("validated"),
                "match_count": record.get("match_count"),
                "stability": record.get("stability"),
                "stability_score": record.get("stability_score"),
                "warnings": record.get("warnings", []),
            })

    return {
        "element_identity": metadata.get("element_identity"),
        "element_name": bundle.element_name,
        "page": bundle.page,
        "page_url": page_url,
        "element_data": element_data,
        "ancestor_context": element_data.get("ancestor_context", {}),
        "attempted_locators": attempted,
        "fallback_reasons": reasons,
    }


def build_unresolved_payloads(
    bundles: Iterable[LocatorBundle],
    *,
    page_url: str,
) -> List[Dict[str, Any]]:
    """Build one payload per unresolved physical element identity."""
    payloads: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for bundle in bundles:
        payload = build_unresolved_payload(bundle, page_url=page_url)
        if payload is None:
            continue
        identity = str(payload.get("element_identity") or f"name:{bundle.element_name}")
        if identity not in seen:
            seen.add(identity)
            payloads.append(payload)
    return payloads


def has_positional_selector(value: str) -> bool:
    """Reject selectors that force a result by arbitrary position."""
    return any(pattern.search(value) for pattern in _POSITIONAL_PATTERNS)


def parse_locator_expert_candidates(
    response: Dict[str, Any],
    payload: Dict[str, Any],
) -> List[Locator]:
    """Parse supported, non-positional LocatorExpert response candidates."""
    raw_candidates = response.get("locators", []) if isinstance(response, dict) else []
    candidates: List[Locator] = []
    seen: set[tuple[str, str]] = set()
    response_metadata = response.get("metadata", {}) if isinstance(response, dict) else {}
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        raw_strategy = str(raw.get("strategy") or raw.get("locator_type") or "").lower()
        strategy = _STRATEGIES.get(raw_strategy)
        value = str(raw.get("value") or raw.get("locator_value") or "").strip()
        if strategy is None or not value or has_positional_selector(value):
            continue
        key = (strategy.value, value)
        if key in seen:
            continue
        seen.add(key)
        metadata = {
            "source": "locator_expert",
            "provider": response_metadata.get("provider"),
            "model": response_metadata.get("model"),
            "fallback_reasons": payload.get("fallback_reasons", []),
            "validation_result": "pending",
            "element_identity": payload.get("element_identity"),
        }
        candidates.append(Locator(
            element_name=payload["element_name"],
            strategy=strategy,
            value=value,
            confidence=raw.get("confidence", 0.5),
            fallback=True,
            description=raw.get("description"),
            verified_in_snapshot=None,
            metadata={key: value for key, value in metadata.items() if value is not None},
        ))
    return candidates


def merge_validated_fallback(
    bundle: LocatorBundle,
    candidate: Locator,
    validation: Dict[str, Any],
) -> LocatorBundle:
    """Merge a LocatorExpert candidate only after unique live validation."""
    match_count = validation.get("match_count")
    if match_count != 1:
        raise ValueError("LocatorExpert candidate must have live match_count == 1")

    candidate_metadata = dict(candidate.metadata or {})
    candidate_metadata.update({
        "validation_result": "unique",
        "match_count": 1,
    })
    validated = candidate.model_copy(update={
        "verified_in_snapshot": True,
        "metadata": candidate_metadata,
    })

    existing = [bundle.primary] + list(bundle.alternates)
    if bundle.primary.verified_in_snapshot is True:
        primary = bundle.primary
        alternatives = existing[1:] + [validated]
    else:
        primary = validated.model_copy(update={"fallback": False})
        alternatives = existing

    primary_key = (primary.strategy.value, primary.value)
    deduplicated: Dict[tuple[str, str], Locator] = {}
    for locator in alternatives:
        key = (locator.strategy.value, locator.value)
        if key != primary_key and key not in deduplicated:
            deduplicated[key] = locator.model_copy(update={"fallback": True})

    bundle_metadata = dict(bundle.metadata or {})
    bundle_metadata["locator_expert_fallback"] = {
        "resolved": True,
        "fallback_reasons": candidate_metadata.get("fallback_reasons", []),
        "match_count": 1,
    }
    return bundle.model_copy(update={
        "primary": primary,
        "alternates": list(deduplicated.values()),
        "metadata": bundle_metadata,
    })


def resolve_with_locator_expert(
    bundles: List[LocatorBundle],
    *,
    page_url: str,
    discover: DiscoveryCallable,
    validate: ValidationCallable,
) -> Dict[str, Any]:
    """Resolve eligible bundles while guaranteeing zero calls for resolved ones."""
    by_identity: Dict[str, LocatorBundle] = {}
    for bundle in bundles:
        identity = str((bundle.metadata or {}).get("element_identity") or f"name:{bundle.element_name}")
        by_identity[identity] = bundle

    payloads = build_unresolved_payloads(bundles, page_url=page_url)
    resolved: List[LocatorBundle] = []
    unresolved: List[Dict[str, Any]] = []
    llm_calls = 0
    total_tokens = 0
    started_at = time.perf_counter()

    for payload in payloads:
        identity = str(payload.get("element_identity") or f"name:{payload['element_name']}")
        bundle = by_identity[identity]
        llm_calls += 1
        try:
            response = discover(payload)
            if isinstance(response, dict):
                metadata = response.get("metadata", {})
                tokens = (
                    response.get("tokens_used")
                    or metadata.get("tokens_used")
                    or metadata.get("usage", {}).get("total_tokens")
                    or 0
                )
                if isinstance(tokens, int):
                    total_tokens += tokens
        except Exception as exc:
            unresolved.append({**payload, "error": f"locator_expert_failed: {exc}"})
            continue
        merged = None
        rejected = []
        for candidate in parse_locator_expert_candidates(response, payload):
            try:
                validation = validate(candidate, payload)
            except Exception as exc:
                rejected.append({
                    "strategy": candidate.strategy.value,
                    "value": candidate.value,
                    "match_count": None,
                    "error": f"validation_failed: {exc}",
                })
                continue
            if validation.get("match_count") == 1:
                merged = merge_validated_fallback(bundle, candidate, validation)
                break
            rejected.append({
                "strategy": candidate.strategy.value,
                "value": candidate.value,
                "match_count": validation.get("match_count"),
                "error": validation.get("error"),
            })
        if merged is not None:
            resolved.append(merged)
        else:
            unresolved.append({**payload, "rejected_candidates": rejected})

    untouched = [bundle for bundle in bundles if build_unresolved_payload(bundle, page_url=page_url) is None]
    return {
        "resolved_bundles": untouched + resolved,
        "unresolved_elements": unresolved,
        "llm_calls": llm_calls,
        "tokens_used": total_tokens,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
    }

