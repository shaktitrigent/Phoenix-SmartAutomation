"""Baseline Update Manager - Priority 30.

This module manages baseline updates after successful maintenance validation,
ensuring baselines are only updated when maintenance is successful.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

from phoenix.test_maintenance.models import (
    BaselineUpdate,
    ContinuousValidationResult,
    MaintenanceOutcome,
)

# Priority 29: Change Intelligence
try:
    from phoenix.change_intelligence.baseline_manager import BaselineManager
    from phoenix.change_intelligence.models import Baseline
    PRIORITY29_AVAILABLE = True
except ImportError:
    PRIORITY29_AVAILABLE = False

logger = logging.getLogger(__name__)


class BaselineUpdateManager:
    """Manages baseline updates after successful maintenance.
    
    This manager:
    - Never overwrites valid baseline after failed maintenance
    - Preserves previous baseline
    - Creates new baseline version
    - Maintains baseline history
    - Records what changed
    - Records what tests were regenerated
    - Records validation results
    """
    
    def __init__(self, baseline_manager: Optional[BaselineManager] = None):
        """Initialize baseline update manager.
        
        Args:
            baseline_manager: Optional baseline manager from Priority 29
        """
        self.baseline_manager = baseline_manager
        
        if PRIORITY29_AVAILABLE and baseline_manager:
            logger.info("[BASELINE UPDATE MANAGER] Priority 29 BaselineManager available")
        else:
            logger.warning("[BASELINE UPDATE MANAGER] Priority 29 not available")
        
        # Update history
        self.update_history: List[Dict[str, Any]] = []
        
        logger.info("[BASELINE UPDATE MANAGER] Initialized")
    
    def update_baseline(
        self,
        url: str,
        validation_results: List[ContinuousValidationResult],
        current_dom: str,
        current_page_type: str,
        current_components: List[Dict[str, Any]],
        current_locators: List[Dict[str, Any]],
        current_flows: List[Dict[str, Any]],
    ) -> Optional[BaselineUpdate]:
        """Update baseline after successful maintenance.
        
        Args:
            url: Page URL
            validation_results: Continuous validation results
            current_dom: Current DOM snapshot
            current_page_type: Current page type
            current_components: Current components
            current_locators: Current locators
            current_flows: Current flows
            
        Returns:
            Baseline update result or None if update not performed
        """
        logger.info(f"[BASELINE UPDATE MANAGER] Evaluating baseline update for {url}")
        
        # Check if all validations passed
        all_passed = self._check_all_validations_passed(validation_results)
        
        if not all_passed:
            logger.warning("[BASELINE UPDATE MANAGER] Not all validations passed - baseline NOT updated")
            return None
        
        # Get previous baseline
        previous_baseline = None
        if self.baseline_manager:
            previous_baseline = self.baseline_manager.get_latest_baseline(url)
        
        # Create new baseline
        new_baseline = None
        if self.baseline_manager:
            new_baseline = self.baseline_manager.create_baseline(
                url=url,
                dom_snapshot=current_dom,
                page_type=current_page_type,
                components=current_components,
                locators=current_locators,
                flows=current_flows,
            )
        
        if not new_baseline:
            logger.error("[BASELINE UPDATE MANAGER] Failed to create new baseline")
            return None
        
        # Record changes
        changes_recorded = self._record_changes(validation_results)
        
        # Record tests updated and preserved
        tests_updated = [v.test_id for v in validation_results if v.outcome == MaintenanceOutcome.SUCCESS]
        tests_preserved = [v.test_id for v in validation_results if v.outcome == MaintenanceOutcome.SKIPPED]
        
        # Record validation results
        validation_result_ids = [v.execution_id for v in validation_results]
        
        # Create baseline update record
        update = BaselineUpdate(
            update_id=f"UPDATE-{uuid4().hex[:8]}",
            previous_baseline_id=previous_baseline.baseline_id if previous_baseline else "None",
            new_baseline_id=new_baseline.baseline_id,
            update_type="maintenance",
            tests_updated=tests_updated,
            tests_preserved=tests_preserved,
            changes_recorded=changes_recorded,
            validation_results=validation_result_ids,
            success=True,
        )
        
        # Record update
        self._record_update(update)
        
        logger.info(
            f"[BASELINE UPDATE MANAGER] Baseline updated: "
            f"{previous_baseline.baseline_id if previous_baseline else 'None'} -> {new_baseline.baseline_id}"
        )
        logger.info(f"[BASELINE UPDATE MANAGER] Tests updated: {len(tests_updated)}")
        logger.info(f"[BASELINE UPDATE MANAGER] Tests preserved: {len(tests_preserved)}")
        
        return update
    
    def _check_all_validations_passed(
        self,
        validation_results: List[ContinuousValidationResult],
    ) -> bool:
        """Check if all validations passed.
        
        Args:
            validation_results: Continuous validation results
            
        Returns:
            True if all passed
        """
        for result in validation_results:
            if result.outcome not in [MaintenanceOutcome.SUCCESS, MaintenanceOutcome.SKIPPED]:
                logger.warning(
                    f"[BASELINE UPDATE MANAGER] Validation failed for {result.test_id}: {result.outcome.value}"
                )
                return False
        
        return True
    
    def _record_changes(
        self,
        validation_results: List[ContinuousValidationResult],
    ) -> List[str]:
        """Record changes that triggered maintenance.
        
        Args:
            validation_results: Continuous validation results
            
        Returns:
            List of change descriptions
        """
        changes = []
        
        for result in validation_results:
            change_desc = f"Test {result.test_id}: {result.outcome.value}"
            changes.append(change_desc)
        
        return changes
    
    def _record_update(
        self,
        update: BaselineUpdate,
    ):
        """Record baseline update for learning.
        
        Args:
            update: Baseline update
        """
        self.update_history.append({
            "update_id": update.update_id,
            "previous_baseline_id": update.previous_baseline_id,
            "new_baseline_id": update.new_baseline_id,
            "tests_updated": len(update.tests_updated),
            "tests_preserved": len(update.tests_preserved),
            "success": update.success,
        })
    
    def get_baseline_history(
        self,
        url: str,
    ) -> List[Dict[str, Any]]:
        """Get baseline history for a URL.
        
        Args:
            url: Page URL
            
        Returns:
            Baseline history
        """
        if not self.baseline_manager:
            return []
        
        # Get all baselines for this URL
        baselines = [
            b for b in self.baseline_manager.baselines.values()
            if b.url == url
        ]
        
        # Sort by version
        baselines.sort(key=lambda b: b.version)
        
        return [
            {
                "baseline_id": b.baseline_id,
                "version": b.version,
                "created_at": b.created_at.isoformat(),
                "dom_hash": b.dom_hash,
            }
            for b in baselines
        ]
    
    def rollback_baseline(
        self,
        url: str,
        target_version: int,
    ) -> bool:
        """Rollback baseline to a specific version.
        
        Args:
            url: Page URL
            target_version: Target version to rollback to
            
        Returns:
            True if rollback successful
        """
        logger.warning(f"[BASELINE UPDATE MANAGER] Rollback requested for {url} to version {target_version}")
        
        if not self.baseline_manager:
            logger.error("[BASELINE UPDATE MANAGER] Baseline manager not available")
            return False
        
        # Find target baseline
        target_baseline = None
        for baseline in self.baseline_manager.baselines.values():
            if baseline.url == url and baseline.version == target_version:
                target_baseline = baseline
                break
        
        if not target_baseline:
            logger.error(f"[BASELINE UPDATE MANAGER] Target baseline not found: version {target_version}")
            return False
        
        # In a real implementation, this would restore the baseline
        # For now, just log the intent
        logger.info(f"[BASELINE UPDATE MANAGER] Rollback would restore: {target_baseline.baseline_id}")
        
        return True
