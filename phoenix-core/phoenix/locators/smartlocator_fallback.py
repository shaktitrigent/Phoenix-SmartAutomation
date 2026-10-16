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
from phoenix_shared.locator_policy import acceptance_reasons, locator_accepted


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
    re.compile(r"\.(?:first|last)\b", re.IGNORECASE),
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
    if locator_accepted(bundle.primary, bundle.metadata):
        return []

    records = _raw_records(bundle)
    reasons: List[str] = acceptance_reasons(bundle.primary, bundle.metadata)
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

    # CRITICAL FIX: Use a stable identifier for page names, not human-readable text
    # Priority: element_identity > id > hash of bundle element_name
    # Never use error messages, visible text, or labels as filesystem identifiers
    import re
    import hashlib
    element_identity = metadata.get("element_identity")
    if element_identity and isinstance(element_identity, str):
        # Use the identity if available (stable unique identifier)
        safe_element_name = re.sub(r'[^\w\-]', '_', str(element_identity)[:50]).lower()
    elif element_data.get("id"):
        # Use the DOM id if available
        safe_element_name = re.sub(r'[^\w\-]', '_', str(element_data["id"])[:50]).lower()
    else:
        # Fallback to hash of element_name to avoid Windows path issues
        safe_element_name = hashlib.md5(bundle.element_name.encode()).hexdigest()[:16]

    return {
        "element_identity": metadata.get("element_identity"),
        "custom_name": _first_present(
            (metadata, "custom_name"), (first_record, "custom_name")
        ),
        "element_name": safe_element_name,  # Use sanitized identifier instead of bundle.element_name
        "original_element_name": bundle.element_name,  # Preserve original for reference
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
        "candidate_elements": metadata.get("candidate_elements", []),
        "requested_label": metadata.get("requested_label", bundle.element_name),
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
    patterns = _POSITIONAL_PATTERNS if value.strip().startswith(("page.", "locator(", "get_by_")) else _POSITIONAL_PATTERNS[1:]
    return any(pattern.search(value) for pattern in patterns)


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
        try:
            candidate = Locator(
            element_name=payload["element_name"],
            strategy=strategy,
            value=value,
            confidence=raw.get("confidence", 0.5),
            fallback=True,
            description=raw.get("description"),
            verified_in_snapshot=None,
            metadata={key: value for key, value in metadata.items() if value is not None},
            )
        except (ValueError, TypeError):
            continue
        candidates.append(candidate)
    return candidates


def merge_validated_fallback(
    bundle: LocatorBundle,
    candidate: Locator,
    validation: Dict[str, Any],
) -> LocatorBundle:
    """Merge a LocatorExpert candidate only after unique live validation."""
    match_count = validation.get("match_count")
    if type(match_count) is not int or match_count != 1 or validation.get("identity_matches") is not True:
        raise ValueError("LocatorExpert candidate requires live match_count == 1 and identity_matches == True")

    candidate_metadata = dict(candidate.metadata or {})
    candidate_metadata.update(validation)
    candidate_metadata.update({
        "source": "locator_expert",
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
    if locator_accepted(bundle.primary, bundle.metadata):
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
    bundle_metadata.pop("unresolved", None)
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
    capture: Optional[Callable] = None,
    max_rounds: int = 1,
    max_candidates: int = 5,
) -> Dict[str, Any]:
    """Resolve eligible bundles while guaranteeing zero calls for resolved ones."""
    if not 1 <= max_rounds <= 3 or not 1 <= max_candidates <= 10:
        raise ValueError("Fallback budget requires 1–3 rounds and 1–10 candidates")
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

    for original in payloads:
        original_name = original.get("original_element_name") or original["element_name"]
        identity = str(original.get("element_identity") or f"name:{original_name}")
        bundle = by_identity[identity]
        payload = dict(original)
        merged = None
        rejected = []
        fingerprints = set()
        error = None
        discovery_calls = 0
        capture_attempts = 0
        for round_number in range(1, max_rounds + 1):
            if capture is not None:
                capture_attempts += 1
                try:
                    evidence = capture(payload, round_number)
                except Exception as exc:
                    error = "scoped_capture_failed:" + type(exc).__name__
                    break
                payload.update(evidence)
                if evidence.get("capture_status") != "captured":
                    error = "insufficient_live_context"
                    break
                fingerprint = evidence.get("context_fingerprint")
                if round_number > 1 and fingerprint in fingerprints:
                    error = "context_unchanged_after_rejection"
                    break
                fingerprints.add(fingerprint)
            payload["round_number"] = round_number
            payload["previous_rejections"] = list(rejected)
            llm_calls += 1
            discovery_calls += 1
            try:
                response = discover(payload)
                metadata = response.get("metadata", {}) if isinstance(response, dict) else {}
                tokens = (response.get("tokens_used") or metadata.get("tokens_used") or 0) if isinstance(response, dict) else 0
                if isinstance(tokens, int):
                    total_tokens += tokens
            except Exception as exc:
                cause=getattr(exc,'__cause__',None)
                timed_out=isinstance(exc,TimeoutError) or type(cause).__name__ in {'Timeout','ReadTimeout','ConnectTimeout'}
                error = 'locator_expert_timeout_completion_unknown' if timed_out else "locator_expert_failed: " + type(exc).__name__
                break
            candidates = parse_locator_expert_candidates(response, payload)[:max_candidates]
            for candidate in candidates:
                attempt_number = len(rejected) + 1
                try:
                    validation = dict(validate(candidate, payload) or {})
                except Exception as exc:
                    validation = {"match_count": None, "error": "validation_failed:" + type(exc).__name__}
                validation.update(attempt_number=attempt_number, round_number=round_number)
                count = validation.get("match_count")
                same_identity = not (payload.get("element_identity") and validation.get("element_identity") and
                    payload["element_identity"] != validation["element_identity"])
                if type(count) is int and count == 1 and validation.get("identity_matches") is True and same_identity:
                    merged = merge_validated_fallback(bundle, candidate, validation)
                    break
                reason = (validation.get("validation_reason") or "browser_validation_error" if validation.get("error") and count is None else
                          "not_found" if count == 0 else "ambiguous" if isinstance(count, int) and count > 1 else
                          "wrong_element_identity" if count == 1 and (validation.get("identity_matches") is False or not same_identity) else
                          "missing_identity_evidence" if count == 1 else "invalid_validation_result")
                rejected.append({"strategy":candidate.strategy.value,"value":candidate.value,
                    "match_count":count,"error":validation.get("error"),"attempt_number":attempt_number,
                    "identity_matches": validation.get("identity_matches"),
                    "validation_url": validation.get("validation_url"), "state_name": validation.get("state_name"),
                    "capture_status": payload.get("capture_status"), "anchor_count": payload.get("anchor_count"),
                    "round_number":round_number,"rejection_reason":reason})
            if merged is not None:
                break
            if not candidates:
                error = "no_valid_locator_expert_candidates"
                break
        if merged is not None:
            resolved.append(merged)
        else:
            unresolved.append({**payload,"rejected_candidates":rejected,
                "fallback_attempted":discovery_calls > 0, "discovery_calls":discovery_calls,
                "capture_attempts":capture_attempts,
                "final_failure_reason":error or "all_locator_expert_candidates_rejected",
                **({"error":error} if error else {})})

    untouched = [bundle for bundle in bundles if build_unresolved_payload(bundle, page_url=page_url) is None]
    return {
        "resolved_bundles": untouched + resolved,
        "unresolved_elements": unresolved,
        "llm_calls": llm_calls,
        "tokens_used": total_tokens,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
    }


def intelligence_discoverer(
    client: Any,
    project_context: object | None = None,
) -> DiscoveryCallable:
    """Adapt ``IntelligenceClient`` to the scoped fallback discovery contract."""
    def discover(payload: Dict[str, Any]) -> Dict[str, Any]:
        kwargs = {
            "page_url": payload.get("page_url", ""),
            "elements": [],
            "element_contexts": [payload],
            "require_llm": True,
        }
        if project_context is not None:
            kwargs["project_context"] = project_context
        return client.discover_locators(**kwargs)

    return discover
