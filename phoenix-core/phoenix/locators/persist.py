
"""Locator persistence - extracts and saves locators from generated scripts."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def locator_bundle_to_dict(bundle: "LocatorBundle") -> Dict[str, Any]:
    """Convert a LocatorBundle to the dict format expected by persist_locators.
    
    This preserves SmartLocatorAI metadata and maintains backward compatibility
    with the existing persistence format.
    """
    try:
        from phoenix_shared.models.locator import LocatorBundle
    except ImportError:
        from shared.phoenix_shared.models.locator import LocatorBundle
    
    result = {
        "element_id": bundle.element_name,
        "element_name": bundle.element_name,
        "primary": _locator_to_dict(bundle.primary),
        "alternates": [_locator_to_dict(alt) for alt in bundle.alternates],
    }
    
    # Preserve bundle-level metadata
    if bundle.metadata:
        result["metadata"] = bundle.metadata
    
    if bundle.page:
        result["page"] = bundle.page
    
    if bundle.notes:
        result["notes"] = bundle.notes
    
    return result


def _locator_to_dict(locator: "Locator") -> Dict[str, Any]:
    """Convert a Locator to dict format, preserving metadata."""
    result = {
        "strategy": locator.strategy.value,
        "value": locator.value,
        "confidence": locator.confidence,
        "fallback": locator.fallback,
    }
    
    if locator.description:
        result["description"] = locator.description
    
    if locator.verified_in_snapshot is not None:
        result["verified_in_snapshot"] = locator.verified_in_snapshot
    
    if locator.metadata:
        result["metadata"] = locator.metadata
    
    return result


def enrich_locators_with_smartlocator(
    existing_locators: List[Dict[str, Any]], 
    smartlocator_bundles: List["LocatorBundle"]
) -> List[Dict[str, Any]]:
    """Enrich existing locators with SmartLocatorAI data.
    
    This function merges SmartLocatorAI LocatorBundle data with existing
    locator data, preserving the working locator information and metadata.
    
    Args:
        existing_locators: List of existing locator dicts (from LLM/legacy)
        smartlocator_bundles: List of LocatorBundle objects from SmartLocatorAI adapter
    
    Returns:
        Enriched locator dicts with SmartLocatorAI metadata and working locators
    """
    if not smartlocator_bundles:
        return existing_locators
    
    try:
        from phoenix_shared.models.locator import LocatorBundle
    except ImportError:
        from shared.phoenix_shared.models.locator import LocatorBundle
    
    # Convert SmartLocatorAI bundles to dict format
    sl_dicts = [locator_bundle_to_dict(bundle) for bundle in smartlocator_bundles]
    
    # Merge with existing locators
    return _merge_locators(existing_locators + sl_dicts)


def persist_locators(scripts: List[Dict[str, Any]], locators_dir: Path) -> int:
    """Extract and save locators from generated automation scripts.
    
    Args:
        scripts: List of script dicts with keys: script_path, page, locators
        locators_dir: Directory to save locator bundles (e.g., locators/)
    
    Returns:
        Number of locator bundles saved
    """
    locators_dir = Path(locators_dir)
    locators_dir.mkdir(parents=True, exist_ok=True)
    
    # Group locators by page
    page_locators: Dict[str, List[Dict[str, Any]]] = {}
    
    for script in scripts:
        page = script.get("page", "global")
        script_locators = script.get("locators", [])
        
        # Handle LocatorBundle objects from SmartLocatorAI adapter
        if script_locators and isinstance(script_locators, list) and len(script_locators) > 0:
            # Check if we have LocatorBundle objects
            if hasattr(script_locators[0], 'primary'):
                # Convert LocatorBundle objects to dict format
                script_locators = [locator_bundle_to_dict(loc) for loc in script_locators if hasattr(loc, 'primary')]
        
        if not script_locators:
            # Try to extract locators from the script file
            script_path = script.get("script_path")
            if script_path and Path(script_path).exists():
                try:
                    from phoenix.locators.extractor import extract_locators_from_script
                    script_locators = extract_locators_from_script(script_path)
                except Exception as exc:
                    logger.debug("Failed to extract locators from %s: %s", script_path, exc)
        
        if script_locators:
            page_locators.setdefault(page, []).extend(script_locators)
    
    # Save locator bundles
    bundles_saved = 0
    for page, locators in page_locators.items():
        if not locators:
            continue
        
        # Merge locators by element_id/element_name
        merged = _merge_locators(locators)
        
        # Save to locators/<page>.json
        bundle_path = locators_dir / f"{page}.json"
        try:
            # Load existing if it exists
            if bundle_path.exists():
                existing = json.loads(bundle_path.read_text(encoding="utf-8"))
                if isinstance(existing, list):
                    existing_merged = _merge_locators(existing)
                    # Merge new locators into existing
                    for new_loc in merged:
                        element_id = new_loc.get("element_id") or new_loc.get("element_name")
                        found = False
                        for existing_loc in existing_merged:
                            existing_id = existing_loc.get("element_id") or existing_loc.get("element_name")
                            if existing_id == element_id:
                                # Merge strategies
                                existing_strategies = existing_loc.get("strategies", [])
                                new_strategies = new_loc.get("strategies", [])
                                # Add new strategies that dont exist
                                for new_strat in new_strategies:
                                    if not any(
                                        s.get("value") == new_strat.get("value") 
                                        for s in existing_strategies
                                    ):
                                        existing_strategies.append(new_strat)
                                existing_loc["strategies"] = existing_strategies
                                # Merge metadata
                                if "metadata" in new_loc:
                                    existing_meta = existing_loc.get("metadata", {})
                                    existing_meta.update(new_loc["metadata"])
                                    existing_loc["metadata"] = existing_meta
                                found = True
                                break
                        if not found:
                            existing_merged.append(new_loc)
                    merged = existing_merged
            
            # Write the bundle
            bundle_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
            bundles_saved += 1
            logger.info("Saved locator bundle: %s (%d locators)", bundle_path, len(merged))
        except Exception as exc:
            logger.error("Failed to save locator bundle %s: %s", bundle_path, exc)
    
    return bundles_saved


def _merge_locators(locators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge locators by element_id/element_name, combining strategies.
    
    This function handles both:
    1. Legacy strategies format: {element_id, element_name, strategies: [...]}
    2. LocatorBundle format: {element_id, element_name, primary: {...}, alternates: [...]}
    
    It preserves the LocatorBundle format when present to maintain SmartLocatorAI metadata.
    When merging different formats, it prefers LocatorBundle format for better metadata preservation.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    
    for loc in locators:
        element_id = loc.get("element_id") or loc.get("element_name")
        if not element_id:
            continue
        
        # If this is a LocatorBundle format (has primary), preserve that format
        if "primary" in loc and isinstance(loc["primary"], dict):
            if element_id not in merged:
                # First time seeing this element - copy the LocatorBundle format
                merged[element_id] = {
                    "element_id": element_id,
                    "element_name": loc.get("element_name", element_id),
                    "primary": dict(loc["primary"]),
                    "alternates": [dict(alt) for alt in loc.get("alternates", [])],
                    "metadata": {},
                }
                
                # Preserve bundle-level metadata
                for meta_key in [
                    "recommended", "recommended_locator", "element_has_working_locator",
                    "working_locator_type", "working_locator_value", "context_strategy",
                    "stability", "stability_score", "stability_category", "stability_details",
                    "estimated_unique", "warnings", "element_data", "dom_path", "element_id",
                    "custom_name", "element_name", "notes", "duplicate", "dynamic", "source",
                    "element_identity", "source_names", "smartlocator_raw_records", "bundle_element_name",
                    "page"
                ]:
                    if meta_key in loc and loc[meta_key]:
                        merged[element_id]["metadata"][meta_key] = loc[meta_key]
            else:
                # Element exists - merge strategies into existing LocatorBundle
                existing = merged[element_id]
                
                # If existing is in legacy format, convert to LocatorBundle format first
                if "strategies" in existing and "primary" not in existing:
                    # Convert legacy to LocatorBundle format
                    if existing["strategies"]:
                        existing["primary"] = existing["strategies"][0]
                        existing["alternates"] = existing["strategies"][1:] if len(existing["strategies"]) > 1 else []
                        del existing["strategies"]
                    else:
                        existing["primary"] = {"strategy": "css", "value": "", "confidence": 0.5}
                        existing["alternates"] = []
                    if "metadata" not in existing:
                        existing["metadata"] = {}
                
                # Now merge with LocatorBundle format
                if "primary" in existing:
                    # Merge primary if it has higher confidence
                    new_primary = loc["primary"]
                    existing_primary = existing["primary"]
                    if new_primary.get("confidence", 0) > existing_primary.get("confidence", 0):
                        existing["primary"] = dict(new_primary)
                    
                    # Add new alternates
                    for alt in loc.get("alternates", []):
                        if not any(
                            a.get("value") == alt.get("value") 
                            for a in existing["alternates"]
                        ):
                            existing["alternates"].append(dict(alt))
                    
                    # Merge metadata
                    for meta_key in [
                        "recommended", "recommended_locator", "element_has_working_locator",
                        "working_locator_type", "working_locator_value", "context_strategy",
                        "stability", "stability_score", "stability_category", "stability_details",
                        "estimated_unique", "warnings", "element_data", "dom_path", "element_id",
                        "custom_name", "element_name", "notes", "duplicate", "dynamic", "source",
                        "element_identity", "source_names", "smartlocator_raw_records", "bundle_element_name",
                        "page"
                    ]:
                        if meta_key in loc and loc[meta_key]:
                            existing["metadata"][meta_key] = loc[meta_key]
        else:
            # Legacy strategies format
            if element_id not in merged:
                merged[element_id] = {
                    "element_id": element_id,
                    "element_name": loc.get("element_name", element_id),
                    "strategies": [],
                    "metadata": {},
                }
            
            # Preserve SmartLocatorAI metadata at the element level
            for meta_key in [
                "recommended", "recommended_locator", "element_has_working_locator",
                "working_locator_type", "working_locator_value", "context_strategy",
                "stability", "stability_score", "stability_category", "stability_details",
                "estimated_unique", "warnings", "element_data", "dom_path", "element_id",
                "custom_name", "element_name", "notes", "duplicate", "dynamic", "source",
                "element_identity", "source_names", "smartlocator_raw_records", "bundle_element_name"
            ]:
                if meta_key in loc and loc[meta_key]:
                    merged[element_id]["metadata"][meta_key] = loc[meta_key]
            
            # Add strategies
            if "strategies" in loc:
                for strat in loc["strategies"]:
                    if not any(
                        s.get("value") == strat.get("value") 
                        for s in merged[element_id]["strategies"]
                    ):
                        # Preserve strategy-level metadata
                        strat_with_meta = dict(strat)
                        if "metadata" in strat:
                            strat_with_meta["metadata"] = strat["metadata"]
                        merged[element_id]["strategies"].append(strat_with_meta)
            elif "selector" in loc:
                # Simple format with just selector
                merged[element_id]["strategies"].append({
                    "strategy": "css",
                    "value": loc["selector"],
                    "confidence": 0.7,
                })
    
    # Sort strategies by confidence (highest first) for legacy format
    for loc in merged.values():
        if "strategies" in loc:
            loc["strategies"].sort(key=lambda s: s.get("confidence", 0), reverse=True)
        # For LocatorBundle format, ensure alternates are sorted by confidence
        if "alternates" in loc:
            loc["alternates"].sort(key=lambda s: s.get("confidence", 0), reverse=True)
    
    return list(merged.values())
