"""Conditional LocatorExpert fallback for unresolved SmartLocatorAI bundles.

This module intentionally contains no HTTP or browser implementation.  Its
callers provide discovery and validation callables, keeping the decision and
merge contract independently testable while guaranteeing that an LLM result
is never accepted without a live ``match_count == 1`` result.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
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

    has_validated_candidate = any(
        record.get("validated") is True or record.get("match_count") == 1
        for record in records
    )
    if records and not has_validated_candidate:
        reasons.append("no_validated_candidate")

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


def _first_present(*sources_and_keys: Any) -> Any:
    """Return the first non-empty value from ``(mapping, key)`` pairs."""
    for source, key in sources_and_keys:
        if isinstance(source, dict) and source.get(key) not in (None, "", [], {}):
            return source[key]
    return None


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
                "dynamic": record.get("dynamic"),
                "duplicate": record.get("duplicate"),
                "context_strategy": record.get("context_strategy"),
            })

    ancestor_context = element_data.get("ancestor_context", {})
    if not isinstance(ancestor_context, dict):
        ancestor_context = {}
    first_record = records[0] if records else {}
    stable_attributes = element_data.get("stable_attributes")
    if not isinstance(stable_attributes, dict):
        stable_attributes = {
            key: element_data[key]
            for key in ("id", "name", "role", "aria-label", "data-testid")
            if element_data.get(key)
        }

    return {
        "element_identity": metadata.get("element_identity"),
        "custom_name": _first_present(
            (metadata, "custom_name"), (first_record, "custom_name")
        ),
        "element_name": bundle.element_name,
        "page": bundle.page,
        "page_url": page_url,
        "element_data": element_data,
        "tag": _first_present((element_data, "tag"), (element_data, "tag_name")),
        "id": element_data.get("id"),
        "name": element_data.get("name"),
        "role": element_data.get("role"),
        "label": _first_present((element_data, "label"), (element_data, "accessible_name")),
        "placeholder": element_data.get("placeholder"),
        "visible_text": _first_present(
            (element_data, "visible_text"), (element_data, "text")
        ),
        "stable_attributes": stable_attributes,
        "dom_path": _first_present((element_data, "dom_path"), (element_data, "xpath")),
        "ancestor_context": ancestor_context,
        "container_context": {
            key: value for key, value in ancestor_context.items()
            if key.startswith("container_") and value not in (None, "", [], {})
        },
        "section_context": _first_present(
            (ancestor_context, "section_context"), (element_data, "section_context")
        ),
        "row_context": _first_present(
            (ancestor_context, "row_context"), (element_data, "row_context")
        ),
        "distinguishing_text": _first_present(
            (ancestor_context, "distinguishing_text"),
            (element_data, "distinguishing_text"),
        ),
        "attempted_locators": attempted,
        "working_locator": {
            "available": first_record.get("element_has_working_locator"),
            "type": first_record.get("working_locator_type"),
            "value": first_record.get("working_locator_value"),
        },
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
            "reason": raw.get("reason") or raw.get("description"),
            "context_strategy": raw.get("context_strategy"),
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
        "resolution_timestamp": datetime.now(timezone.utc).isoformat(),
        "attempt_number": validation.get("attempt_number"),
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
        "source": "locator_expert",
        "provider": candidate_metadata.get("provider"),
        "model": candidate_metadata.get("model"),
        "resolution_timestamp": candidate_metadata["resolution_timestamp"],
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
        candidates = parse_locator_expert_candidates(response, payload)
        for attempt_number, candidate in enumerate(candidates, start=1):
            try:
                validation = validate(candidate, payload)
            except Exception as exc:
                rejected.append({
                    "strategy": candidate.strategy.value,
                    "value": candidate.value,
                    "match_count": None,
                    "error": f"validation_failed: {exc}",
                    "attempt_number": attempt_number,
                    "rejection_reason": "browser_validation_error",
                })
                continue
            validation = dict(validation or {})
            validation["attempt_number"] = attempt_number
            expected_identity = payload.get("element_identity")
            actual_identity = validation.get("element_identity")
            identity_matches = validation.get("identity_matches")
            wrong_identity = identity_matches is False or (
                expected_identity and actual_identity and expected_identity != actual_identity
            )
            if validation.get("match_count") == 1 and not wrong_identity:
                merged = merge_validated_fallback(bundle, candidate, validation)
                break
            match_count = validation.get("match_count")
            if wrong_identity:
                rejection_reason = "wrong_element_identity"
            elif match_count == 0:
                rejection_reason = "not_found"
            elif isinstance(match_count, int) and match_count > 1:
                rejection_reason = "ambiguous"
            else:
                rejection_reason = "invalid_validation_result"
            rejected.append({
                "strategy": candidate.strategy.value,
                "value": candidate.value,
                "match_count": match_count,
                "error": validation.get("error"),
                "attempt_number": attempt_number,
                "rejection_reason": rejection_reason,
            })
        if merged is not None:
            resolved.append(merged)
        else:
            unresolved.append({
                **payload,
                "rejected_candidates": rejected,
                "final_failure_reason": (
                    "no_valid_locator_expert_candidates" if not candidates
                    else "all_locator_expert_candidates_rejected"
                ),
            })

    untouched = [bundle for bundle in bundles if build_unresolved_payload(bundle, page_url=page_url) is None]
    return {
        "resolved_bundles": untouched + resolved,
        "unresolved_elements": unresolved,
        "llm_calls": llm_calls,
        "tokens_used": total_tokens,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
    }


def intelligence_discoverer(client: Any) -> DiscoveryCallable:
    """Adapt ``IntelligenceClient`` to the scoped fallback discovery contract."""
    def discover(payload: Dict[str, Any]) -> Dict[str, Any]:
        return client.discover_locators(
            page_url=payload.get("page_url", ""),
            elements=[],
            element_contexts=[payload],
            require_llm=True,
        )

    return discover
