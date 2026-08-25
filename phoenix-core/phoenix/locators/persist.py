
"""Locator persistence - extracts and saves locators from generated scripts."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    """Merge locators by element_id/element_name, combining strategies."""
    merged: Dict[str, Dict[str, Any]] = {}
    
    for loc in locators:
        element_id = loc.get("element_id") or loc.get("element_name")
        if not element_id:
            continue
        
        if element_id not in merged:
            merged[element_id] = {
                "element_id": element_id,
                "element_name": loc.get("element_name", element_id),
                "strategies": [],
            }
        
        # Add strategies
        if "strategies" in loc:
            for strat in loc["strategies"]:
                if not any(
                    s.get("value") == strat.get("value") 
                    for s in merged[element_id]["strategies"]
                ):
                    merged[element_id]["strategies"].append(strat)
        elif "primary" in loc:
            # Legacy format with primary/alternates
            primary = loc["primary"]
            if primary:
                merged[element_id]["strategies"].append({
                    "strategy": primary.get("strategy", "css"),
                    "value": primary.get("value", ""),
                    "confidence": primary.get("confidence", 0.8),
                })
            for alt in loc.get("alternates", []):
                if not any(
                    s.get("value") == alt.get("value") 
                    for s in merged[element_id]["strategies"]
                ):
                    merged[element_id]["strategies"].append({
                        "strategy": alt.get("strategy", "css"),
                        "value": alt.get("value", ""),
                        "confidence": alt.get("confidence", 0.6),
                    })
        elif "selector" in loc:
            # Simple format with just selector
            merged[element_id]["strategies"].append({
                "strategy": "css",
                "value": loc["selector"],
                "confidence": 0.7,
            })
    
    # Sort strategies by confidence (highest first)
    for loc in merged.values():
        loc["strategies"].sort(key=lambda s: s.get("confidence", 0), reverse=True)
    
    return list(merged.values())
