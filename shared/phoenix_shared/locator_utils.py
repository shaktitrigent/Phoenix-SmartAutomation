"""Shared locator utilities for bundle normalization and sufficiency checking."""

from typing import Any, Dict, List, Optional, Tuple


def _extract_fill_target_and_value(action: str) -> Tuple[str, str]:
    """Extract field name and value from a fill action text.
    
    Returns (field, value) tuple.
    """
    import re
    
    # Pattern: "Enter {value} in {field}" or "Fill {field} with {value}"
    enter_pattern = r"enter\s+(.+?)\s+in\s+(.+?)(?:\s+field)?$"
    fill_pattern = r"fill\s+(.+?)\s+with\s+(.+?)$"
    
    m = re.search(enter_pattern, action, re.IGNORECASE)
    if m:
        return m.group(2).strip(), m.group(1).strip()
    
    m = re.search(fill_pattern, action, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    
    return "", ""


def _extract_click_target(action: str) -> Tuple[str, str]:
    """Extract button name from a click action text.
    
    Returns (control_type, label) tuple.
    """
    import re
    action = action.lower()
    
    # Pattern: "Click {label}" or "Press {label}"
    click_pattern = r"(?:click|press|tap)\s+(.+?)(?:\s+button)?$"
    m = re.search(click_pattern, action)
    if m:
        return "button", m.group(1).strip()
    
    return "", ""


def _are_locator_bundles_sufficient(
    manual_test: Dict[str, Any],
    locator_bundles: Optional[List[Dict[str, Any]]],
) -> Tuple[bool, List[str]]:
    """Check if stored locator bundles are sufficient for the manual test.

    Returns (is_sufficient, missing_elements) where:
    - is_sufficient: True if every required element has a validated, non-rejected locator
    - missing_elements: List of element labels that don't have matching bundles

    Uses semantic matching from reconciliation.py to match manual test steps
    to locator bundles. Partial coverage is treated as insufficient.
    
    Note: Bundle normalization should be done before calling this function
    using normalize_locator_bundles().
    """
    # Ensure bundles are normalized to dicts
    locator_bundles = normalize_locator_bundles(locator_bundles or [])
    
    if not locator_bundles:
        return False, []

    # Filter to only validated, non-rejected bundles
    validated_bundles = []
    for bundle in locator_bundles:
        element_name = bundle.get("element_name") or bundle.get("element_id")
        if not element_name:
            continue

        metadata = bundle.get("metadata") or {}
        primary = bundle.get("primary") or {}
        primary_metadata = primary.get("metadata") or {}

        # Rejection flags at any level
        if (metadata.get("broken") or metadata.get("unresolved") or
            primary_metadata.get("broken") or primary_metadata.get("unresolved") or
            metadata.get("status") in {"broken", "unresolved", "invalid"} or
            primary_metadata.get("status") in {"broken", "unresolved", "invalid"}):
            continue

        # Must be verified in snapshot
        if not primary.get("verified_in_snapshot"):
            continue

        validated_bundles.append(bundle)

    if not validated_bundles:
        return False, []

    # Extract required elements from manual test steps
    required_elements = []
    for step in manual_test.get("steps", []):
        action = step.get("action", "")

        # Extract fill targets
        try:
            field, _ = _extract_fill_target_and_value(action)
            if field and field.lower() not in {"field", "valid", "invalid"}:
                required_elements.append(field)
        except Exception:
            pass

        # Extract click targets
        if any(k in action.lower() for k in ["click", "press", "tap"]):
            _, label = _extract_click_target(action)
            if label:
                required_elements.append(label)

    if not required_elements:
        # If we can't extract required elements but have validated bundles,
        # assume sufficient (better than skipping available bundles)
        return True, []

    # Use semantic matching from reconciliation.py
    try:
        from phoenix.locators.reconciliation import match_locator_bundle
    except ImportError:
        # Fallback to simple name matching if reconciliation not available
        available_names = {
            (bundle.get("element_name") or bundle.get("element_id", "")).lower()
            for bundle in validated_bundles
        }
        missing = [
            elem for elem in required_elements
            if elem.lower() not in available_names
        ]
        return len(missing) == 0, missing

    # Match each required element to a validated bundle
    missing_elements = []
    for element_label in required_elements:
        matched = match_locator_bundle(element_label, validated_bundles)
        if matched is None:
            missing_elements.append(element_label)

    is_sufficient = len(missing_elements) == 0
    return is_sufficient, missing_elements


def locator_bundle_to_dict(bundle: Any) -> Dict[str, Any]:
    """Convert a LocatorBundle object to a dict for sufficiency checking.
    
    Args:
        bundle: LocatorBundle object or dict
        
    Returns:
        Dict representation with keys: element_name, primary, metadata
    """
    if isinstance(bundle, dict):
        return bundle
    
    # Handle LocatorBundle object
    result = {
        "element_name": getattr(bundle, "element_name", ""),
        "primary": {},
        "metadata": getattr(bundle, "metadata", None) or {},
    }
    
    primary = getattr(bundle, "primary", None)
    if primary:
        # If primary is already a dict, use it directly
        if isinstance(primary, dict):
            result["primary"] = primary
        else:
            # Extract strategy value - handle both enum and string
            strategy = getattr(primary, "strategy", "css")
            if hasattr(strategy, "value"):
                strategy = strategy.value
            else:
                strategy = str(strategy)
            
            result["primary"] = {
                "strategy": strategy,
                "value": getattr(primary, "value", ""),
                "verified_in_snapshot": getattr(primary, "verified_in_snapshot", False),
            }
    
    return result


def normalize_locator_bundles(bundles: List[Any]) -> List[Dict[str, Any]]:
    """Normalize a list of LocatorBundle objects or dicts to dicts.
    
    Args:
        bundles: List of LocatorBundle objects or dicts
        
    Returns:
        List of dict representations
    """
    return [locator_bundle_to_dict(b) for b in bundles]
