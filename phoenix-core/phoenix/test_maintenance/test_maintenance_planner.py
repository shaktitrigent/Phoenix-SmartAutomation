"""Test Maintenance Planner - Priority 30.

This module creates evidence-based maintenance plans for affected tests,
determining exactly what needs to be changed and how.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.test_maintenance.models import (
    MaintenancePlan,
    TestImpact,
    MaintenanceDecisionType,
)

# Priority 29: Change Intelligence
try:
    from phoenix.change_intelligence.models import SemanticChange
    PRIORITY29_AVAILABLE = True
except ImportError:
    PRIORITY29_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestMaintenancePlanner:
    """Creates evidence-based maintenance plans.
    
    This planner:
    - Determines why tests are affected
    - Determines what changed
    - Determines which test step is affected
    - Determines which locator is affected
    - Determines whether POM changes are required
    - Determines whether test data changes are required
    - Determines whether assertion changes are required
    - Determines whether regeneration is required
    - Determines whether human review is required
    """
    
    def __init__(self):
        """Initialize test maintenance planner."""
        self.planning_history: List[Dict[str, Any]] = []
        
        logger.info("[TEST MAINTENANCE PLANNER] Initialized")
    
    def create_maintenance_plan(
        self,
        session_id: str,
        changes: List[SemanticChange],
        test_impacts: List[TestImpact],
        all_tests: List[Dict[str, Any]],
    ) -> MaintenancePlan:
        """Create evidence-based maintenance plan.
        
        Args:
            session_id: Change intelligence session ID
            changes: Detected changes
            test_impacts: Test impact analyses
            all_tests: All registered tests
            
        Returns:
            Maintenance plan
        """
        logger.info(f"[TEST MAINTENANCE PLANNER] Creating plan for {len(test_impacts)} impacted tests")
        
        plan_id = f"PLAN-{uuid4().hex[:8]}"
        
        # Create maintenance decisions for each impacted test
        maintenance_decisions = []
        for impact in test_impacts:
            decision = self._create_maintenance_decision(impact, changes)
            maintenance_decisions.append(decision)
        
        # Determine execution order
        execution_order = self._determine_execution_order(test_impacts)
        
        # Estimate duration
        estimated_duration = self._estimate_duration(test_impacts)
        
        # Assess risk
        risk_assessment = self._assess_risk(test_impacts, changes)
        
        # Identify human review triggers
        human_review_triggers = self._identify_human_review_triggers(
            test_impacts,
            maintenance_decisions,
        )
        
        plan = MaintenancePlan(
            plan_id=plan_id,
            session_id=session_id,
            impacted_tests=test_impacts,
            maintenance_decisions=maintenance_decisions,
            execution_order=execution_order,
            estimated_duration=estimated_duration,
            risk_assessment=risk_assessment,
            human_review_triggers=human_review_triggers,
        )
        
        # Record plan
        self._record_plan(plan)
        
        logger.info(
            f"[TEST MAINTENANCE PLANNER] Plan created: {plan_id}, "
            f"duration: {estimated_duration}s, human reviews: {len(human_review_triggers)}"
        )
        
        return plan
    
    def _create_maintenance_decision(
        self,
        impact: TestImpact,
        changes: List[SemanticChange],
    ) -> Dict[str, Any]:
        """Create maintenance decision for a test impact.
        
        Args:
            impact: Test impact analysis
            changes: Detected changes
            
        Returns:
            Maintenance decision
        """
        # Find the change for this impact
        change = next(
            (c for c in changes if c.change_id == impact.change_id),
            None,
        )
        
        # Determine decision type
        decision_type = self._map_scope_to_decision(impact.regeneration_scope)
        
        # Generate reason
        reason = self._generate_decision_reason(impact, change)
        
        # Determine if human review needed
        requires_human_review = self._requires_human_review(impact, change)
        
        decision = {
            "decision_id": f"DEC-{uuid4().hex[:8]}",
            "test_id": impact.test_id,
            "change_id": impact.change_id,
            "decision_type": decision_type.value,
            "reason": reason,
            "affected_steps": impact.affected_steps,
            "affected_locators": impact.affected_locators,
            "affected_assertions": impact.affected_assertions,
            "severity": impact.severity,
            "confidence": impact.confidence,
            "requires_human_review": requires_human_review,
            "regeneration_scope": impact.regeneration_scope,
        }
        
        return decision
    
    def _map_scope_to_decision(
        self,
        scope: str,
    ) -> MaintenanceDecisionType:
        """Map regeneration scope to decision type.
        
        Args:
            scope: Regeneration scope
            
        Returns:
            Maintenance decision type
        """
        mapping = {
            "locator_only": MaintenanceDecisionType.UPDATE_LOCATOR,
            "assertion_only": MaintenanceDecisionType.REGENERATE_ASSERTION,
            "step_only": MaintenanceDecisionType.UPDATE_TEST_STEP,
            "test_section": MaintenanceDecisionType.REGENERATE_TEST_SECTION,
            "full_test": MaintenanceDecisionType.REGENERATE_TEST,
            "minimal": MaintenanceDecisionType.NO_ACTION,
        }
        
        return mapping.get(scope, MaintenanceDecisionType.MONITOR)
    
    def _generate_decision_reason(
        self,
        impact: TestImpact,
        change: Optional[SemanticChange],
    ) -> str:
        """Generate reason for maintenance decision.
        
        Args:
            impact: Test impact analysis
            change: Semantic change
            
        Returns:
            Decision reason
        """
        if not change:
            return f"Test {impact.test_id} affected by unknown change"
        
        reasons = []
        
        # Add change type
        reasons.append(f"Change type: {change.change_type.value}")
        
        # Add affected components
        if impact.affected_steps:
            reasons.append(f"Affected {len(impact.affected_steps)} test steps")
        
        if impact.affected_locators:
            reasons.append(f"Affected {len(impact.affected_locators)} locators")
        
        if impact.affected_assertions:
            reasons.append(f"Affected {len(impact.affected_assertions)} assertions")
        
        # Add severity
        reasons.append(f"Severity: {impact.severity}")
        
        return "; ".join(reasons)
    
    def _requires_human_review(
        self,
        impact: TestImpact,
        change: Optional[SemanticChange],
    ) -> bool:
        """Determine if human review is required.
        
        Args:
            impact: Test impact analysis
            change: Semantic change
            
        Returns:
            True if human review required
        """
        # Low confidence requires review
        if impact.confidence < 0.7:
            return True
        
        # Critical severity requires review
        if impact.severity == "critical":
            return True
        
        # Full regeneration requires review
        if impact.regeneration_scope == "full_test":
            return True
        
        # Many affected steps requires review
        if len(impact.affected_steps) > 5:
            return True
        
        return False
    
    def _determine_execution_order(
        self,
        test_impacts: List[TestImpact],
    ) -> List[str]:
        """Determine optimal execution order for maintenance.
        
        Args:
            test_impacts: Test impact analyses
            
        Returns:
            Ordered list of test IDs
        """
        # Sort by severity (low severity first)
        sorted_impacts = sorted(
            test_impacts,
            key=lambda x: (
                self._severity_weight(x.severity),
                len(x.affected_steps),
            ),
        )
        
        return [impact.test_id for impact in sorted_impacts]
    
    def _severity_weight(
        self,
        severity: str,
    ) -> int:
        """Get weight for severity level.
        
        Args:
            severity: Severity level
            
        Returns:
            Weight (lower = execute first)
        """
        weights = {
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        
        return weights.get(severity, 2)
    
    def _estimate_duration(
        self,
        test_impacts: List[TestImpact],
    ) -> int:
        """Estimate maintenance duration in seconds.
        
        Args:
            test_impacts: Test impact analyses
            
        Returns:
            Estimated duration in seconds
        """
        total_duration = 0
        
        for impact in test_impacts:
            # Base time per test
            base_time = 30
            
            # Add time for affected steps
            step_time = len(impact.affected_steps) * 5
            
            # Add time for regeneration scope
            scope_multiplier = {
                "locator_only": 1.0,
                "assertion_only": 1.2,
                "step_only": 1.5,
                "test_section": 2.0,
                "full_test": 3.0,
                "minimal": 0.5,
            }
            
            multiplier = scope_multiplier.get(impact.regeneration_scope, 1.0)
            
            total_duration += int((base_time + step_time) * multiplier)
        
        return total_duration
    
    def _assess_risk(
        self,
        test_impacts: List[TestImpact],
        changes: List[SemanticChange],
    ) -> Dict[str, Any]:
        """Assess overall risk of maintenance.
        
        Args:
            test_impacts: Test impact analyses
            changes: Detected changes
            
        Returns:
            Risk assessment
        """
        # Count by severity
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for impact in test_impacts:
            severity_counts[impact.severity] += 1
        
        # Calculate overall risk score
        total_tests = len(test_impacts)
        if total_tests == 0:
            risk_score = 0.0
        else:
            weighted_sum = (
                severity_counts["low"] * 1 +
                severity_counts["medium"] * 2 +
                severity_counts["high"] * 3 +
                severity_counts["critical"] * 4
            )
            risk_score = weighted_sum / (total_tests * 4)
        
        # Determine risk level
        if risk_score < 0.25:
            risk_level = "low"
        elif risk_score < 0.5:
            risk_level = "medium"
        elif risk_score < 0.75:
            risk_level = "high"
        else:
            risk_level = "critical"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "severity_counts": severity_counts,
            "total_affected_tests": total_tests,
            "critical_changes": len([c for c in changes if c.severity.value == "critical"]),
        }
    
    def _identify_human_review_triggers(
        self,
        test_impacts: List[TestImpact],
        maintenance_decisions: List[Dict[str, Any]],
    ) -> List[str]:
        """Identify triggers that require human review.
        
        Args:
            test_impacts: Test impact analyses
            maintenance_decisions: Maintenance decisions
            
        Returns:
            List of human review triggers
        """
        triggers = []
        
        for decision in maintenance_decisions:
            if decision.get("requires_human_review", False):
                trigger = f"Test {decision['test_id']}: {decision['reason']}"
                triggers.append(trigger)
        
        return triggers
    
    def _record_plan(
        self,
        plan: MaintenancePlan,
    ):
        """Record maintenance plan for learning.
        
        Args:
            plan: Maintenance plan
        """
        self.planning_history.append({
            "plan_id": plan.plan_id,
            "session_id": plan.session_id,
            "impacted_tests": len(plan.impacted_tests),
            "estimated_duration": plan.estimated_duration,
            "risk_level": plan.risk_assessment.get("risk_level", "unknown"),
            "human_reviews": len(plan.human_review_triggers),
        })
