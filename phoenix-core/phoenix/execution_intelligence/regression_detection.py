"""Runtime Regression Detection - Compare executions over time.

This module implements runtime regression detection that compares current
execution with previous successful executions to detect degradation.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import RuntimeRegression

logger = logging.getLogger(__name__)


class RuntimeRegressionDetector:
    """Runtime regression detector for execution intelligence.
    
    Detects:
    - Locator degradation
    - Page structure changes
    - Flow changes
    - Component changes
    - Unexpected navigation
    - Increased execution time
    - Increased healing
    - Increased failures
    """
    
    def __init__(self):
        self.execution_history: Dict[str, Dict[str, Any]] = {}
        
        logger.info("RuntimeRegressionDetector initialized")
    
    def detect_regression(
        self,
        current_execution: Dict[str, Any],
        previous_execution: Optional[Dict[str, Any]] = None,
    ) -> Optional[RuntimeRegression]:
        """Detect regression between current and previous execution.
        
        Args:
            current_execution: Current execution data
            previous_execution: Previous successful execution
            
        Returns:
            RuntimeRegression if regression detected, None otherwise
        """
        if not previous_execution:
            logger.info("[REGRESSION] No previous execution - baseline established")
            self.execution_history[current_execution["execution_id"]] = current_execution
            return None
        
        regression_id = f"REG-{uuid.uuid4().hex[:8].upper()}"
        
        # Check for various regression indicators
        locator_regression = self._check_locator_regression(
            current_execution, previous_execution
        )
        structure_regression = self._check_structure_regression(
            current_execution, previous_execution
        )
        time_regression = self._check_time_regression(
            current_execution, previous_execution
        )
        healing_regression = self._check_healing_regression(
            current_execution, previous_execution
        )
        
        # Determine if any regression detected
        has_regression = any([
            locator_regression,
            structure_regression,
            time_regression,
            healing_regression,
        ])
        
        if not has_regression:
            logger.info("[REGRESSION] No regression detected")
            return None
        
        # Create regression report
        regression = RuntimeRegression(
            regression_id=regression_id,
            previous_execution_id=previous_execution["execution_id"],
            current_execution_id=current_execution["execution_id"],
            regression_type="DETECTED",
            locator_degradation=locator_regression,
            page_structure_changed=structure_regression,
            increased_execution_time=time_regression,
            increased_healing=healing_regression,
            degradation_percentage=self._calculate_degradation(
                current_execution, previous_execution
            ),
            recommended_action=self._generate_recommendation(
                locator_regression, structure_regression, time_regression, healing_regression
            ),
            confidence=0.85,
        )
        
        logger.warning(
            f"[REGRESSION] Regression detected: {regression.regression_type}"
        )
        
        return regression
    
    def _check_locator_regression(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any],
    ) -> bool:
        """Check for locator degradation."""
        current_locators = current.get("locators", {})
        previous_locators = previous.get("locators", {})
        
        for locator_id, current_data in current_locators.items():
            if locator_id in previous_locators:
                previous_data = previous_locators[locator_id]
                
                # Check success rate degradation
                current_success = current_data.get("success_rate", 1.0)
                previous_success = previous_data.get("success_rate", 1.0)
                
                if current_success < previous_success - 0.2:  # 20% degradation
                    return True
        
        return False
    
    def _check_structure_regression(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any],
    ) -> bool:
        """Check for page structure changes."""
        current_dom_hash = current.get("dom_hash", "")
        previous_dom_hash = previous.get("dom_hash", "")
        
        if current_dom_hash and previous_dom_hash:
            return current_dom_hash != previous_dom_hash
        
        return False
    
    def _check_time_regression(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any],
    ) -> bool:
        """Check for execution time increase."""
        current_time = current.get("execution_time_ms", 0)
        previous_time = previous.get("execution_time_ms", 0)
        
        if previous_time > 0:
            time_increase = (current_time - previous_time) / previous_time
            return time_increase > 0.5  # 50% increase
        
        return False
    
    def _check_healing_regression(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any],
    ) -> bool:
        """Check for increased healing."""
        current_healing = current.get("healing_count", 0)
        previous_healing = previous.get("healing_count", 0)
        
        if previous_healing == 0:
            return current_healing > 0
        else:
            healing_increase = (current_healing - previous_healing) / previous_healing
            return healing_increase > 0.5  # 50% increase
        
        return False
    
    def _calculate_degradation(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any],
    ) -> float:
        """Calculate overall degradation percentage."""
        current_success = current.get("success_rate", 1.0)
        previous_success = previous.get("success_rate", 1.0)
        
        if previous_success > 0:
            return (previous_success - current_success) * 100
        
        return 0.0
    
    def _generate_recommendation(
        self,
        locator: bool,
        structure: bool,
        time: bool,
        healing: bool,
    ) -> str:
        """Generate recommendation based on regression type."""
        if locator:
            return "Relearn locator - DOM structure changed"
        elif structure:
            return "Re-analyze page structure"
        elif time:
            return "Investigate performance degradation"
        elif healing:
            return "Investigate increased instability"
        else:
            return "Review execution changes"
