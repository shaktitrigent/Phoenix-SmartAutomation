"""Test Maintenance - Priority 30.

This module provides universal autonomous test maintenance and continuous validation,
closing the loop between change detection, impact analysis, selective regeneration,
validation, and baseline updates.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from phoenix.test_maintenance.models import (
    MaintenanceDecisionType,
    ValidationStatus,
    MaintenanceOutcome,
    TestImpact,
    MaintenancePlan,
    RegenerationResult,
    ValidationResult,
    ContinuousValidationResult,
    BaselineUpdate,
    MaintenanceSession,
)
from phoenix.test_maintenance.test_impact_selector import TestImpactSelector
from phoenix.test_maintenance.selective_regeneration_engine import SelectiveRegenerationEngine
from phoenix.test_maintenance.test_maintenance_planner import TestMaintenancePlanner
from phoenix.test_maintenance.maintenance_validation_engine import MaintenanceValidationEngine
from phoenix.test_maintenance.continuous_validation_engine import ContinuousValidationEngine
from phoenix.test_maintenance.baseline_update_manager import BaselineUpdateManager
from phoenix.test_maintenance.maintenance_learning import MaintenanceLearning

# Priority 29: Change Intelligence
try:
    from phoenix.change_intelligence import ChangeIntelligence
    from phoenix.change_intelligence.models import SemanticChange, ChangeIntelligenceSession
    PRIORITY29_AVAILABLE = True
except ImportError:
    PRIORITY29_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestMaintenanceCoordinator:
    """Main coordinator for test maintenance.
    
    This coordinator:
    - Integrates with Priority 29 Change Intelligence
    - Selects affected tests
    - Creates maintenance plans
    - Executes selective regeneration
    - Validates regenerated automation
    - Executes continuous validation
    - Updates baselines on success
    - Preserves baselines on failure
    - Tracks metrics
    """
    
    def __init__(
        self,
        base_dir: str = "phoenix_test_maintenance",
        change_intelligence: Optional[ChangeIntelligence] = None,
    ):
        """Initialize test maintenance coordinator.
        
        Args:
            base_dir: Base directory for storage
            change_intelligence: Optional ChangeIntelligence from Priority 29
        """
        self.base_dir = base_dir
        
        # Priority 29 integration
        self.change_intelligence = change_intelligence
        
        # Priority 30 components
        self.test_impact_selector = TestImpactSelector()
        self.selective_regeneration_engine = SelectiveRegenerationEngine()
        self.test_maintenance_planner = TestMaintenancePlanner()
        self.maintenance_validation_engine = MaintenanceValidationEngine()
        self.continuous_validation_engine = ContinuousValidationEngine()
        self.baseline_update_manager = BaselineUpdateManager(
            baseline_manager=change_intelligence.baseline_manager if change_intelligence else None
        )
        self.maintenance_learning = MaintenanceLearning()
        
        # Session tracking
        self.current_session: Optional[MaintenanceSession] = None
        
        # Metrics
        self.metrics = {
            "sessions": 0,
            "total_tests": 0,
            "affected_tests": 0,
            "preserved_tests": 0,
            "regenerated_tests": 0,
            "successful_maintenance": 0,
            "failed_maintenance": 0,
            "human_reviews": 0,
            "baseline_updates": 0,
        }
        
        logger.info("[TEST MAINTENANCE COORDINATOR] Initialized")
        logger.info(f"[TEST MAINTENANCE COORDINATOR] Priority 29 available: {PRIORITY29_AVAILABLE}")
    
    def execute_maintenance(
        self,
        change_intelligence_session: ChangeIntelligenceSession,
        all_tests: List[Dict[str, Any]],
        current_dom: str,
        current_page_type: str,
        current_components: List[Dict[str, Any]],
        current_locators: List[Dict[str, Any]],
        current_flows: List[Dict[str, Any]],
        headed: bool = False,
    ) -> MaintenanceSession:
        """Execute complete maintenance cycle.
        
        Args:
            change_intelligence_session: Change intelligence session from Priority 29
            all_tests: All registered tests
            current_dom: Current DOM snapshot
            current_page_type: Current page type
            current_components: Current components
            current_locators: Current locators
            current_flows: Current flows
            headed: Run browser in headed mode
            
        Returns:
            Complete maintenance session
        """
        logger.info("[TEST MAINTENANCE COORDINATOR] Starting maintenance cycle")
        
        # Create session
        session = MaintenanceSession(
            session_id=f"MAINT-{change_intelligence_session.session_id}",
            url=change_intelligence_session.url,
            change_intelligence_session_id=change_intelligence_session.session_id,
            maintenance_plan=None,  # Will be set
            regeneration_results=[],
            validation_results=[],
            continuous_validation_results=[],
            baseline_update=None,
            overall_outcome=MaintenanceOutcome.SKIPPED,
            total_tests=len(all_tests),
            affected_tests=0,
            preserved_tests=0,
            regenerated_tests=0,
            successful_maintenance=0,
            failed_maintenance=0,
            human_reviews=0,
            metrics={},
        )
        
        self.current_session = session
        self.metrics["sessions"] += 1
        
        # Register tests
        for test in all_tests:
            self.test_impact_selector.register_test(
                test.get("test_id", ""),
                test,
            )
        
        # Select affected tests
        logger.info("[TEST MAINTENANCE COORDINATOR] Selecting affected tests...")
        test_impacts = self.test_impact_selector.select_affected_tests(
            changes=change_intelligence_session.detected_changes,
            all_tests=all_tests,
        )
        
        session.affected_tests = len(test_impacts)
        session.preserved_tests = len(all_tests) - len(test_impacts)
        self.metrics["affected_tests"] += len(test_impacts)
        self.metrics["preserved_tests"] += session.preserved_tests
        
        logger.info(f"[TEST MAINTENANCE COORDINATOR] Affected tests: {len(test_impacts)}")
        logger.info(f"[TEST MAINTENANCE COORDINATOR] Preserved tests: {session.preserved_tests}")
        
        # If no affected tests, skip maintenance
        if not test_impacts:
            logger.info("[TEST MAINTENANCE COORDINATOR] No affected tests - maintenance skipped")
            session.overall_outcome = MaintenanceOutcome.SKIPPED
            return session
        
        # Create maintenance plan
        logger.info("[TEST MAINTENANCE COORDINATOR] Creating maintenance plan...")
        maintenance_plan = self.test_maintenance_planner.create_maintenance_plan(
            session_id=change_intelligence_session.session_id,
            changes=change_intelligence_session.detected_changes,
            test_impacts=test_impacts,
            all_tests=all_tests,
        )
        session.maintenance_plan = maintenance_plan
        
        session.human_reviews = len(maintenance_plan.human_review_triggers)
        self.metrics["human_reviews"] += session.human_reviews
        
        # Execute maintenance for each affected test
        for impact in test_impacts:
            # Get test data
            test_data = next(
                (t for t in all_tests if t.get("test_id", "") == impact.test_id),
                None,
            )
            
            if not test_data:
                logger.warning(f"[TEST MAINTENANCE COORDINATOR] Test data not found: {impact.test_id}")
                continue
            
            # Regenerate test
            logger.info(f"[TEST MAINTENANCE COORDINATOR] Regenerating test: {impact.test_id}")
            regeneration_result = self.selective_regeneration_engine.regenerate_test(
                test_impact=impact,
                current_test=test_data,
                new_components=current_components,
                new_locators=current_locators,
            )
            session.regeneration_results.append(regeneration_result)
            
            # Learn from regeneration
            self.maintenance_learning.learn_from_regeneration(regeneration_result)
            
            if regeneration_result.success:
                session.regenerated_tests += 1
                self.metrics["regenerated_tests"] += 1
            
            # Validate regeneration
            logger.info(f"[TEST MAINTENANCE COORDINATOR] Validating regeneration: {impact.test_id}")
            validation_result = self.maintenance_validation_engine.validate_regeneration(
                regeneration_result=regeneration_result,
                regenerated_code=None,  # Would be actual regenerated code
            )
            session.validation_results.append(validation_result)
            
            # Learn from validation
            self.maintenance_learning.learn_from_validation(validation_result)
            
            # Continuous validation
            if validation_result.status.value in ["passed", "partial"]:
                logger.info(f"[TEST MAINTENANCE COORDINATOR] Continuous validation: {impact.test_id}")
                continuous_validation_result = self.continuous_validation_engine.validate_maintenance(
                    validation_result=validation_result,
                    test_data=test_data,
                    url=change_intelligence_session.url,
                    headed=headed,
                )
                session.continuous_validation_results.append(continuous_validation_result)
                
                # Learn from execution
                self.maintenance_learning.learn_from_execution(continuous_validation_result)
                
                if continuous_validation_result.outcome == MaintenanceOutcome.SUCCESS:
                    session.successful_maintenance += 1
                    self.metrics["successful_maintenance"] += 1
                else:
                    session.failed_maintenance += 1
                    self.metrics["failed_maintenance"] += 1
            else:
                session.failed_maintenance += 1
                self.metrics["failed_maintenance"] += 1
        
        # Update baseline if all maintenance successful
        if session.successful_maintenance == session.affected_tests:
            logger.info("[TEST MAINTENANCE COORDINATOR] All maintenance successful - updating baseline")
            baseline_update = self.baseline_update_manager.update_baseline(
                url=change_intelligence_session.url,
                validation_results=session.continuous_validation_results,
                current_dom=current_dom,
                current_page_type=current_page_type,
                components=current_components,
                locators=current_locators,
                flows=current_flows,
            )
            session.baseline_update = baseline_update
            
            if baseline_update and baseline_update.success:
                self.metrics["baseline_updates"] += 1
                session.overall_outcome = MaintenanceOutcome.SUCCESS
            else:
                session.overall_outcome = MaintenanceOutcome.PARTIAL_SUCCESS
        else:
            logger.warning("[TEST MAINTENANCE COORDINATOR] Some maintenance failed - baseline NOT updated")
            session.overall_outcome = MaintenanceOutcome.PARTIAL_SUCCESS
        
        # Update session metrics
        session.metrics = self.metrics.copy()
        session.metrics["learning"] = self.maintenance_learning.get_learning_metrics()
        session.end_time = datetime.now()
        
        logger.info(
            f"[TEST MAINTENANCE COORDINATOR] Maintenance complete: "
            f"outcome={session.overall_outcome.value}, "
            f"affected={session.affected_tests}, "
            f"successful={session.successful_maintenance}, "
            f"failed={session.failed_maintenance}"
        )
        
        return session
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get maintenance metrics.
        
        Returns:
            Metrics dictionary
        """
        return self.metrics.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get maintenance status.
        
        Returns:
            Status dictionary
        """
        return {
            "current_session": self.current_session.session_id if self.current_session else None,
            "metrics": self.metrics,
            "priority_29_available": PRIORITY29_AVAILABLE,
        }


__all__ = [
    "TestMaintenanceCoordinator",
    "TestImpactSelector",
    "SelectiveRegenerationEngine",
    "TestMaintenancePlanner",
    "MaintenanceValidationEngine",
    "ContinuousValidationEngine",
    "BaselineUpdateManager",
    "MaintenanceLearning",
    "MaintenanceDecisionType",
    "ValidationStatus",
    "MaintenanceOutcome",
    "TestImpact",
    "MaintenancePlan",
    "RegenerationResult",
    "ValidationResult",
    "ContinuousValidationResult",
    "BaselineUpdate",
    "MaintenanceSession",
]
