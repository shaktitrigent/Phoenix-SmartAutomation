"""Baseline Manager - Priority 29.

This module manages application baselines for change detection.
It creates, stores, and retrieves baselines that serve as comparison points
for detecting application changes.

Priority 29: Universal Autonomous Change Intelligence + Adaptive Test Maintenance
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from phoenix.change_intelligence.models import Baseline

logger = logging.getLogger(__name__)


class BaselineManager:
    """Manages application baselines for change detection.
    
    This manager:
    - Creates baselines from application state
    - Stores baselines with version tracking
    - Retrieves baselines for comparison
    - Manages baseline versions
    """
    
    def __init__(self, base_dir: str = "phoenix_baselines"):
        """Initialize baseline manager.
        
        Args:
            base_dir: Base directory for baseline storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Baseline storage
        self.baselines: Dict[str, Baseline] = {}
        
        logger.info(f"[BASELINE MANAGER] Initialized with storage: {self.base_dir}")
    
    def create_baseline(
        self,
        url: str,
        dom_snapshot: str,
        page_type: str,
        components: List[Dict[str, Any]],
        locators: List[Dict[str, Any]],
        flows: List[Dict[str, Any]],
    ) -> Baseline:
        """Create a new baseline.
        
        Args:
            url: Page URL
            dom_snapshot: DOM snapshot
            page_type: Page type
            components: List of components
            locators: List of locators
            flows: List of flows
            
        Returns:
            Created baseline
        """
        # Generate DOM hash
        dom_hash = self._generate_dom_hash(dom_snapshot)
        
        # Get next version for this URL
        version = self._get_next_version(url)
        
        # Create baseline
        baseline = Baseline(
            baseline_id=f"BASE-{url.replace('/', '-').replace(':', '-')}-V{version}",
            url=url,
            version=version,
            dom_snapshot=dom_snapshot,
            dom_hash=dom_hash,
            page_type=page_type,
            components=components,
            locators=locators,
            flows=flows,
        )
        
        # Store baseline
        self.baselines[baseline.baseline_id] = baseline
        
        # Persist to disk
        self._persist_baseline(baseline)
        
        logger.info(f"[BASELINE MANAGER] Created baseline: {baseline.baseline_id}")
        logger.info(f"[BASELINE MANAGER] URL: {url}, Version: {version}")
        
        return baseline
    
    def get_latest_baseline(self, url: str) -> Optional[Baseline]:
        """Get the latest baseline for a URL.
        
        Args:
            url: Page URL
            
        Returns:
            Latest baseline or None
        """
        # Find all baselines for this URL
        url_baselines = [
            b for b in self.baselines.values()
            if b.url == url
        ]
        
        if not url_baselines:
            return None
        
        # Return the one with highest version
        latest = max(url_baselines, key=lambda b: b.version)
        
        logger.info(f"[BASELINE MANAGER] Retrieved latest baseline: {latest.baseline_id}")
        
        return latest
    
    def get_baseline(self, baseline_id: str) -> Optional[Baseline]:
        """Get a specific baseline by ID.
        
        Args:
            baseline_id: Baseline ID
            
        Returns:
            Baseline or None
        """
        return self.baselines.get(baseline_id)
    
    def compare_baselines(
        self,
        old_baseline: Baseline,
        new_baseline: Baseline,
    ) -> Dict[str, Any]:
        """Compare two baselines to detect changes.
        
        Args:
            old_baseline: Previous baseline
            new_baseline: Current baseline
            
        Returns:
            Comparison results
        """
        logger.info(f"[BASELINE MANAGER] Comparing baselines:")
        logger.info(f"  Old: {old_baseline.baseline_id}")
        logger.info(f"  New: {new_baseline.baseline_id}")
        
        # Compare DOM hashes
        dom_changed = old_baseline.dom_hash != new_baseline.dom_hash
        
        # Compare page types
        page_type_changed = old_baseline.page_type != new_baseline.page_type
        
        # Compare component counts
        component_count_changed = len(old_baseline.components) != len(new_baseline.components)
        
        # Compare locator counts
        locator_count_changed = len(old_baseline.locators) != len(new_baseline.locators)
        
        # Compare flow counts
        flow_count_changed = len(old_baseline.flows) != len(new_baseline.flows)
        
        changes = {
            "dom_changed": dom_changed,
            "page_type_changed": page_type_changed,
            "component_count_changed": component_count_changed,
            "locator_count_changed": locator_count_changed,
            "flow_count_changed": flow_count_changed,
            "has_changes": any([
                dom_changed,
                page_type_changed,
                component_count_changed,
                locator_count_changed,
                flow_count_changed,
            ]),
        }
        
        logger.info(f"[BASELINE MANAGER] Comparison result: {changes['has_changes']}")
        
        return changes
    
    def _generate_dom_hash(self, dom_snapshot: str) -> str:
        """Generate hash for DOM snapshot.
        
        Args:
            dom_snapshot: DOM snapshot
            
        Returns:
            Hash string
        """
        return hashlib.sha256(dom_snapshot.encode()).hexdigest()
    
    def _get_next_version(self, url: str) -> int:
        """Get next version number for a URL.
        
        Args:
            url: Page URL
            
        Returns:
            Next version number
        """
        url_baselines = [
            b for b in self.baselines.values()
            if b.url == url
        ]
        
        if not url_baselines:
            return 1
        
        max_version = max(b.version for b in url_baselines)
        return max_version + 1
    
    def _persist_baseline(self, baseline: Baseline):
        """Persist baseline to disk.
        
        Args:
            baseline: Baseline to persist
        """
        baseline_file = self.base_dir / f"{baseline.baseline_id}.json"
        
        with open(baseline_file, 'w') as f:
            json.dump(baseline.to_dict(), f, indent=2)
        
        logger.info(f"[BASELINE MANAGER] Persisted baseline to: {baseline_file}")
    
    def load_baselines(self):
        """Load all baselines from disk."""
        for baseline_file in self.base_dir.glob("*.json"):
            try:
                with open(baseline_file, 'r') as f:
                    data = json.load(f)
                    
                baseline = Baseline(
                    baseline_id=data["baseline_id"],
                    url=data["url"],
                    version=data["version"],
                    dom_snapshot=data["dom_snapshot"],
                    dom_hash=data["dom_hash"],
                    page_type=data["page_type"],
                    components=data["components"],
                    locators=data["locators"],
                    flows=data["flows"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                )
                
                self.baselines[baseline.baseline_id] = baseline
                
            except Exception as e:
                logger.warning(f"[BASELINE MANAGER] Failed to load baseline: {e}")
        
        logger.info(f"[BASELINE MANAGER] Loaded {len(self.baselines)} baselines")
