"""Adapter: SmartLocatorAI JSON -> Phoenix ``LocatorBundle`` objects.

This module only converts and reconciles SmartLocatorAI output. It does not
change locator generation, healing, or registry behavior.

Selection precedence for a bundle's primary locator:
1. Validated recommended locator.
2. Working locator reported by the validation rollup.
3. Existing adapter fallback behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy
except ImportError:  # pragma: no cover - import path fallback, mirrors registry.py
    from shared.phoenix_shared.models.locator import (  # type: ignore[no-redef]
        Locator,
        LocatorBundle,
        LocatorStrategy,
    )


_STRATEGY_MAP: Dict[str, LocatorStrategy] = {
    "css": LocatorStrategy.CSS,
    "css selector": LocatorStrategy.CSS,
    "xpath": LocatorStrategy.XPATH,
    "role": LocatorStrategy.ROLE,
    "role selector": LocatorStrategy.ROLE,
    "text": LocatorStrategy.TEXT,
    "text selector": LocatorStrategy.TEXT,
    "label": LocatorStrategy.LABEL,
    "label selector": LocatorStrategy.LABEL,
    "placeholder": LocatorStrategy.PLACEHOLDER,
    "placeholder selector": LocatorStrategy.PLACEHOLDER,
    "test id": LocatorStrategy.TEST_ID,
    "test-id": LocatorStrategy.TEST_ID,
    "testid": LocatorStrategy.TEST_ID,
    "alt text": LocatorStrategy.ALT_TEXT,
    "alt-text": LocatorStrategy.ALT_TEXT,
    "title": LocatorStrategy.TITLE,
}

_STABILITY_LABEL_TO_CONFIDENCE: Dict[str, float] = {
    "high": 0.9,
    "medium": 0.6,
    "low": 0.3,
}

_ROLE_CALL_RE = re.compile(
    r"""getByRole\(\s*['"](?P<role>[^'"]+)['"]\s*,\s*\{\s*name:\s*['"](?P<name>.*?)['"]\s*\}\s*\)"""
)
_TEXT_CALL_RE = re.compile(r"""getByText\(\s*['"](?P<text>.*?)['"]\s*\)""")
_LABEL_CALL_RE = re.compile(r"""getByLabel\(\s*['"](?P<label>.*?)['"]\s*\)""")
_PLACEHOLDER_CALL_RE = re.compile(r"""getByPlaceholder\(\s*['"](?P<placeholder>.*?)['"]\s*\)""")
_TESTID_CALL_RE = re.compile(r"""getByTestId\(\s*['"](?P<testid>.*?)['"]\s*\)""")
_ALT_TEXT_CALL_RE = re.compile(r"""getByAltText\(\s*['"](?P<alt_text>.*?)['"]\s*\)""")
_TITLE_CALL_RE = re.compile(r"""getByTitle\(\s*['"](?P<title>.*?)['"]\s*\)""")

_LEGACY_BLOCK_START_TYPE = "css selector"

_PRESERVED_METADATA_KEYS = {
    "recommended",
    "validated",
    "context_strategy",
    "stability",
    "stability_score",
    "stability_category",
    "stability_details",
    "estimated_unique",
    "warnings",
    "element_has_working_locator",
    "working_locator_type",
    "working_locator_value",
    "custom_name",
    "element_name",
    "element_data",
    "dom_path",
    "element_id",
    "page",
    "notes",
    "duplicate",
    "dynamic",
    "source",
}

_IDENTITY_KEYS = (
    "element_data",
    "dom_path",
    "domPath",
    "element_id",
    "elementId",
    "dom_id",
    "node_id",
    "stable_element_id",
    "element_uid",
    "uid",
)


def _coerce_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"}:
            return False
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _dedupe_list(values: List[Any]) -> List[Any]:
    result: List[Any] = []
    seen: set[str] = set()
    for value in values:
        if _is_empty(value):
            continue
        try:
            key = json.dumps(value, sort_keys=True, default=str)
        except TypeError:
            key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _merge_scalar(existing: Any, value: Any, *, prefer_max: bool = False) -> Any:
    if _is_empty(existing):
        return value
    if _is_empty(value):
        return existing
    if existing == value:
        return existing
    if prefer_max:
        existing_num = _coerce_float(existing)
        value_num = _coerce_float(value)
        if existing_num is not None and value_num is not None:
            return max(existing_num, value_num)
    merged = existing if isinstance(existing, list) else [existing]
    merged.append(value)
    return _dedupe_list(merged)


def _merge_metadata(existing: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, value in update.items():
        if _is_empty(value):
            continue
        if key == "warnings":
            merged[key] = _dedupe_list((merged.get(key, []) if isinstance(merged.get(key), list) else [merged.get(key)])
                                      + (value if isinstance(value, list) else [value]))
            continue
        if key in {"recommended", "validated", "element_has_working_locator"}:
            existing_bool = _coerce_bool(merged.get(key))
            value_bool = _coerce_bool(value)
            if existing_bool is True or value_bool is True:
                merged[key] = True
            elif existing_bool is False and value_bool is False:
                merged[key] = False
            else:
                merged[key] = value if not _is_empty(value) else merged.get(key)
            continue
        if key == "stability_score":
            merged[key] = _merge_scalar(merged.get(key), value, prefer_max=True)
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_metadata(merged[key], value)
            continue
        if isinstance(merged.get(key), list):
            merged[key] = _dedupe_list(list(merged.get(key)) + (value if isinstance(value, list) else [value]))
            continue
        if isinstance(value, list):
            merged[key] = _dedupe_list(([merged[key]] if key in merged and not isinstance(merged[key], list) else [])
                                      + value)
            continue
        merged[key] = _merge_scalar(merged.get(key), value)
    return merged


def _normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s_-]", "", name).strip()
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    cleaned = re.sub(r"(?<!^)(?=[A-Z])", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_").lower()


def _canonical_element_name(names: List[str]) -> str:
    cleaned = [name.strip() for name in names if isinstance(name, str) and name.strip()]
    if not cleaned:
        return ""
    unique = list(dict.fromkeys(cleaned))
    if len(unique) == 1:
        return unique[0]

    snake_case = [name for name in unique if re.fullmatch(r"[a-z][a-z0-9_]*", name)]
    if snake_case:
        return snake_case[0]
    return _normalize_name(unique[0]) or unique[0]


def _stability_to_confidence(entry: Dict[str, Any]) -> float:
    raw_score = entry.get("stability_score")
    score: Optional[float] = None
    if isinstance(raw_score, bool):
        score = None
    elif isinstance(raw_score, int):
        score = raw_score / 10.0
    elif isinstance(raw_score, float):
        score = raw_score if raw_score < 1.0 else raw_score / 10.0
    else:
        score = _coerce_float(raw_score)

    if score is None:
        stability = entry.get("stability")
        if isinstance(stability, dict):
            score = _coerce_float(stability.get("score"))
            if score is None:
                score = _coerce_float(stability.get("value"))
        elif isinstance(stability, (int, float, str)):
            score = _coerce_float(stability)
    if score is not None:
        if score > 1.0:
            if score <= 10.0:
                score /= 10.0
            else:
                score = 1.0
        return max(0.0, min(1.0, score))

    label = str(entry.get("stability", "")).strip().lower()
    return _STABILITY_LABEL_TO_CONFIDENCE.get(label, 0.5)


def _clean_value(strategy: LocatorStrategy, raw_value: str) -> str:
    if strategy == LocatorStrategy.ROLE:
        m = _ROLE_CALL_RE.search(raw_value)
        if m:
            return f'{m.group("role")}[name={m.group("name")}]'
        return raw_value
    if strategy == LocatorStrategy.TEXT:
        m = _TEXT_CALL_RE.search(raw_value)
        if m:
            return m.group("text")
        return raw_value
    if strategy == LocatorStrategy.LABEL:
        m = _LABEL_CALL_RE.search(raw_value)
        if m:
            return m.group("label")
        return raw_value
    if strategy == LocatorStrategy.PLACEHOLDER:
        m = _PLACEHOLDER_CALL_RE.search(raw_value)
        if m:
            return m.group("placeholder")
        return raw_value
    if strategy == LocatorStrategy.TEST_ID:
        m = _TESTID_CALL_RE.search(raw_value)
        if m:
            return m.group("testid")
        return raw_value
    if strategy == LocatorStrategy.ALT_TEXT:
        m = _ALT_TEXT_CALL_RE.search(raw_value)
        if m:
            return m.group("alt_text")
        return raw_value
    if strategy == LocatorStrategy.TITLE:
        m = _TITLE_CALL_RE.search(raw_value)
        if m:
            return m.group("title")
        return raw_value
    return raw_value


def _strategy_from_raw(raw_type: Any) -> Optional[LocatorStrategy]:
    raw = str(raw_type or "").strip().lower()
    return _STRATEGY_MAP.get(raw)


def _extract_identity_value(value: Any) -> Optional[str]:
    if _is_empty(value):
        return None
    if isinstance(value, dict):
        payload = {
            key: value[key]
            for key in sorted(value.keys())
            if not _is_empty(value[key])
        }
        if not payload:
            return None
        encoded = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha1(encoded.encode("utf-8")).hexdigest()
    if isinstance(value, list):
        encoded = json.dumps(value, sort_keys=True, default=str)
        return hashlib.sha1(encoded.encode("utf-8")).hexdigest()
    return str(value).strip()


def _get_element_identity(entry: Dict[str, Any]) -> Optional[str]:
    """Return a stable identity key based on DOM identity, not element name."""
    for key in _IDENTITY_KEYS:
        identity = _extract_identity_value(entry.get(key))
        if identity:
            return f"{key}:{identity}"
    return None


def _extract_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for key in _PRESERVED_METADATA_KEYS:
        if key in entry and not _is_empty(entry[key]):
            metadata[key] = entry[key]
    return metadata


def _build_locator(
    entry: Dict[str, Any],
    element_name: str,
    *,
    origin: str,
    fallback: bool = False,
    recommended: Optional[bool] = None,
    working_rollup: bool = False,
) -> Optional[Locator]:
    raw_type = entry.get("locator_type", entry.get("strategy"))
    strategy = _strategy_from_raw(raw_type)
    if strategy is None:
        return None

    raw_value = entry.get("locator_value", entry.get("selector", entry.get("value", "")))
    value = _clean_value(strategy, str(raw_value))
    if not value:
        return None

    metadata = _extract_metadata(entry)
    metadata["smartlocator_origin"] = origin
    if recommended is not None:
        metadata["smartlocator_recommended"] = recommended
    if working_rollup:
        metadata["smartlocator_working_rollup"] = True

    verified = entry.get("verified_in_snapshot")
    if verified is None:
        verified = entry.get("validated")
    verified_bool = _coerce_bool(verified)
    if working_rollup and verified_bool is None:
        verified_bool = True

    description = entry.get("description")
    warnings = entry.get("warnings")
    if isinstance(warnings, list) and warnings:
        warning_text = ", ".join(str(item) for item in warnings if not _is_empty(item))
        if warning_text:
            description = warning_text if not description else f"{description}; {warning_text}"

    return Locator(
        element_name=element_name,
        strategy=strategy,
        value=value,
        confidence=_stability_to_confidence(entry),
        fallback=fallback,
        description=description or None,
        verified_in_snapshot=verified_bool,
        metadata=metadata,
    )


def convert_entry(entry: Dict[str, Any]) -> Locator:
    """Convert a single SmartLocatorAI locator record into a Phoenix ``Locator``."""
    raw_type = entry.get("locator_type", entry.get("strategy"))
    strategy = _strategy_from_raw(raw_type)
    if strategy is None:
        raise ValueError(f"Unknown SmartLocatorAI locator_type: {entry.get('locator_type')!r}")

    element_name = str(entry.get("custom_name", entry.get("element_name", "")))
    locator = _build_locator(entry, element_name, origin="legacy_entry")
    if locator is None:
        raise ValueError(f"Invalid SmartLocatorAI locator_value for {entry.get('locator_type')!r}")
    return locator


def _split_into_blocks(raw_locators: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    blocks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    for entry in raw_locators:
        raw_type = str(entry.get("locator_type", "")).strip().lower()
        if raw_type == _LEGACY_BLOCK_START_TYPE and current:
            blocks.append(current)
            current = []
        current.append(entry)

    if current:
        blocks.append(current)

    if not blocks and raw_locators:
        blocks = [[entry] for entry in raw_locators]

    return blocks


def _looks_like_identity_aware_record(entry: Dict[str, Any]) -> bool:
    return any(
        key in entry
        for key in (
            "recommended",
            "recommended_locator",
            "working_locator_type",
            "working_locator_value",
            "element_has_working_locator",
            "element_data",
            "dom_path",
            "element_id",
            "context_strategy",
            "stability_category",
            "stability_details",
            "estimated_unique",
        )
    )


def _record_display_name(entry: Dict[str, Any]) -> str:
    for key in ("custom_name", "element_name", "name"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _candidate_locators_for_record(entry: Dict[str, Any], bundle_name: str) -> List[Locator]:
    candidates: List[Locator] = []

    recommended = entry.get("recommended_locator", entry.get("recommended"))
    if isinstance(recommended, dict):
        recommended_entry = dict(recommended)
        recommended_entry.setdefault("validated", recommended.get("validated"))
        locator = _build_locator(
            recommended_entry,
            bundle_name,
            origin="recommended",
            recommended=True,
        )
        if locator is not None:
            candidates.append(locator)

    if _coerce_bool(entry.get("element_has_working_locator")):
        working_type = entry.get("working_locator_type")
        working_value = entry.get("working_locator_value")
        if working_type and working_value:
            working_entry = {
                "locator_type": working_type,
                "locator_value": working_value,
                "validated": entry.get("validated"),
                "stability_score": entry.get("stability_score"),
                "stability": entry.get("stability"),
                "warnings": entry.get("warnings", []),
                "element_has_working_locator": True,
                "working_locator_type": working_type,
                "working_locator_value": working_value,
            }
            locator = _build_locator(
                working_entry,
                bundle_name,
                origin="working_rollup",
                working_rollup=True,
            )
            if locator is not None:
                candidates.append(locator)

    for key in ("primary", "locator", "current", "selector_record"):
        value = entry.get(key)
        if isinstance(value, dict):
            locator = _build_locator(value, bundle_name, origin=key)
            if locator is not None:
                candidates.append(locator)

    locators = entry.get("locators")
    if isinstance(locators, list):
        for candidate in locators:
            if isinstance(candidate, dict):
                locator = _build_locator(candidate, bundle_name, origin="locators")
                if locator is not None:
                    candidates.append(locator)

    alternates = entry.get("alternates") or entry.get("candidates")
    if isinstance(alternates, list):
        for candidate in alternates:
            if isinstance(candidate, dict):
                locator = _build_locator(candidate, bundle_name, origin="alternates", fallback=True)
                if locator is not None:
                    candidates.append(locator)

    if not candidates and any(
        key in entry for key in ("locator_type", "strategy", "locator_value", "selector", "value")
    ):
        locator = _build_locator(entry, bundle_name, origin="entry")
        if locator is not None:
            candidates.append(locator)

    return candidates


def _locator_rank(locator: Locator) -> Tuple[int, float, int]:
    metadata = locator.metadata or {}
    origin = metadata.get("smartlocator_origin")
    if metadata.get("smartlocator_recommended") and locator.verified_in_snapshot is True:
        tier = 3
    elif metadata.get("smartlocator_working_rollup"):
        tier = 2
    elif locator.verified_in_snapshot is True:
        tier = 1
    else:
        tier = 0
    if origin == "legacy_entry" and tier > 0:
        tier = 1
    order = metadata.get("smartlocator_order", 0)
    return tier, locator.confidence, -int(order)


def _merge_locator(existing: Locator, new: Locator) -> Locator:
    merged_metadata = _merge_metadata(existing.metadata, new.metadata)
    description = existing.description or new.description
    if existing.description and new.description and existing.description != new.description:
        description = f"{existing.description}; {new.description}"

    verified = existing.verified_in_snapshot
    new_verified = new.verified_in_snapshot
    if verified is True or new_verified is True:
        verified = True
    elif verified is False or new_verified is False:
        verified = False

    fallback = existing.fallback and new.fallback

    confidence = max(existing.confidence, new.confidence)
    preferred = existing if _locator_rank(existing) >= _locator_rank(new) else new
    return preferred.model_copy(
        update={
            "confidence": confidence,
            "fallback": fallback,
            "description": description,
            "verified_in_snapshot": verified,
            "metadata": merged_metadata,
        }
    )


def _best_locator(locators: List[Locator]) -> Locator:
    unique: Dict[Tuple[str, str], Locator] = {}
    for locator in locators:
        key = (locator.strategy.value, locator.value)
        if key in unique:
            unique[key] = _merge_locator(unique[key], locator)
        else:
            unique[key] = locator
    ordered = sorted(unique.values(), key=_locator_rank, reverse=True)
    return ordered[0]


def _merge_bundle_metadata(records: List[Dict[str, Any]], bundle_name: str, identity: Optional[str]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "element_identity": identity,
        "source_names": _dedupe_list([_record_display_name(record) for record in records]),
        "smartlocator_raw_records": records,
    }
    for record in records:
        metadata = _merge_metadata(metadata, _extract_metadata(record))
    metadata["bundle_element_name"] = bundle_name
    return metadata


def _convert_identity_aware_records(raw_locators: List[Dict[str, Any]], page: str) -> List[LocatorBundle]:
    groups: Dict[str, Dict[str, Any]] = {}
    for index, record in enumerate(raw_locators):
        identity = _get_element_identity(record) or f"__synthetic__:{index}"
        group = groups.setdefault(identity, {"records": [], "order": index})
        record_copy = dict(record)
        record_copy["_smartlocator_order"] = index
        group["records"].append(record_copy)

    bundles: List[LocatorBundle] = []
    for identity, group in groups.items():
        records = group["records"]
        names = [_record_display_name(record) for record in records]
        bundle_name = _canonical_element_name(names) or f"element_{group['order'] + 1}"

        candidates: List[Locator] = []
        for record in records:
            for candidate in _candidate_locators_for_record(record, bundle_name):
                candidate.metadata = dict(candidate.metadata)
                candidate.metadata["smartlocator_order"] = record.get("_smartlocator_order", 0)
                candidate.metadata["element_identity"] = identity
                candidates.append(candidate)

        if not candidates:
            continue

        primary = _best_locator(candidates)
        alternates = sorted(
            [locator for locator in candidates if locator is not primary],
            key=_locator_rank,
            reverse=True,
        )
        for locator in [primary] + alternates:
            locator.element_name = bundle_name

        bundles.append(
            LocatorBundle(
                element_name=bundle_name,
                page=page,
                primary=primary,
                alternates=alternates,
                metadata=_merge_bundle_metadata(records, bundle_name, identity),
            )
        )

    return bundles


def convert_locators(raw_locators: List[Dict[str, Any]], page: str = "global") -> List[LocatorBundle]:
    """Convert SmartLocatorAI records into Phoenix ``LocatorBundle`` objects."""
    if not raw_locators:
        return []

    if any(_looks_like_identity_aware_record(entry) for entry in raw_locators):
        return _convert_identity_aware_records(raw_locators, page)

    bundles: List[LocatorBundle] = []
    name_occurrences: Dict[str, int] = {}

    for block in _split_into_blocks(raw_locators):
        locators: List[Locator] = []
        for raw_entry in block:
            try:
                locator = convert_entry(raw_entry)
            except ValueError:
                continue
            locators.append(locator)

        if not locators:
            continue

        base_name = locators[0].element_name
        if not base_name:
            continue

        name_occurrences[base_name] = name_occurrences.get(base_name, 0) + 1
        occurrence = name_occurrences[base_name]
        element_name = base_name if occurrence == 1 else f"{base_name}_{occurrence}"

        for locator in locators:
            locator.element_name = element_name

        ordered = sorted(locators, key=lambda loc: loc.confidence, reverse=True)
        primary, *alternates = ordered
        bundles.append(
            LocatorBundle(
                element_name=element_name,
                page=page,
                primary=primary,
                alternates=alternates,
                metadata={
                    "source_names": [base_name],
                    "smartlocator_raw_records": block,
                },
            )
        )

    return bundles


def convert_file(smartlocator_json_path: Union[str, Path], page: str = "global") -> List[LocatorBundle]:
    """Read a SmartLocatorAI JSON file and convert it to ``LocatorBundle`` objects."""
    data = json.loads(Path(smartlocator_json_path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_locators: List[Dict[str, Any]] = []
        recommended = data.get("recommended_locator")
        if isinstance(recommended, dict):
            raw_locators.append(recommended)
        locators = data.get("locators", [])
        if isinstance(locators, list):
            raw_locators.extend([entry for entry in locators if isinstance(entry, dict)])
        if not raw_locators and isinstance(data.get("locators"), list):
            raw_locators = [entry for entry in data["locators"] if isinstance(entry, dict)]
    else:
        raw_locators = [entry for entry in data if isinstance(entry, dict)]
    return convert_locators(raw_locators, page=page)
