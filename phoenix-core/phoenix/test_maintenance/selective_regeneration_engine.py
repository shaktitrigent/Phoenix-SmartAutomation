"""Selective Regeneration Engine - Priority 30.

This module regenerates only the affected portions of tests, preserving unaffected
steps, locators, and assertions to minimize code churn.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.test_maintenance.models import (
    RegenerationResult,
    MaintenanceDecisionType,
    TestImpact,
)

# Priority 24: Automation Generation
try:
    from phoenix.automation_generation.automation_regeneration import AutomationRegeneration
    from phoenix.automation_generation.locator_strategy import LocatorStrategyManager
    PRIORITY24_AVAILABLE = True
except ImportError:
    PRIORITY24_AVAILABLE = False

# Priority 29: Change Intelligence
try:
    from phoenix.change_intelligence.models import SemanticChange
    PRIORITY29_AVAILABLE = True
except ImportError:
    PRIORITY29_AVAILABLE = False

logger = logging.getLogger(__name__)


class SelectiveRegenerationEngine:
    """Regenerates only affected portions of tests.
    
    This engine:
    - Preserves unaffected test steps
    - Preserves stable locators
    - Preserves reusable POM objects
    - Regenerates only impacted automation
    - Preserves test intent
    - Preserves business workflow meaning
    - Minimizes code churn
    - Prefers minimal change over full regeneration
    """
    
    def __init__(self):
        """Initialize selective regeneration engine."""
        # Priority 24 components
        self.automation_regenerator = None
        self.locator_strategy_manager = None
        
        if PRIORITY24_AVAILABLE:
            self.automation_regenerator = AutomationRegeneration()
            self.locator_strategy_manager = LocatorStrategyManager()
            logger.info("[SELECTIVE REGENERATION] Priority 24 components available")
        else:
            logger.warning("[SELECTIVE REGENERATION] Priority 24 not available")
        
        # Regeneration history for learning
        self.regeneration_history: List[Dict[str, Any]] = []
        
        logger.info("[SELECTIVE REGENERATION] Initialized")
    
    def regenerate_test(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_components: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Regenerate test based on impact analysis.
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_components: New component state
            new_locators: New locator state
            
        Returns:
            Regeneration result
        """
        logger.info(f"[SELECTIVE REGENERATION] Regenerating test: {test_impact.test_id}")
        logger.info(f"[SELECTIVE REGENERATION] Scope: {test_impact.regeneration_scope}")
        
        # Determine regeneration strategy
        decision_type = self._determine_decision_type(test_impact)
        
        # Execute regeneration based on scope
        if test_impact.regeneration_scope == "locator_only":
            result = self._regenerate_locators_only(
                test_impact,
                current_test,
                new_locators,
            )
        elif test_impact.regeneration_scope == "assertion_only":
            result = self._regenerate_assertions_only(
                test_impact,
                current_test,
                new_components,
            )
        elif test_impact.regeneration_scope == "step_only":
            result = self._regenerate_steps_only(
                test_impact,
                current_test,
                new_components,
                new_locators,
            )
        elif test_impact.regeneration_scope == "test_section":
            result = self._regenerate_test_section(
                test_impact,
                current_test,
                new_components,
                new_locators,
            )
        elif test_impact.regeneration_scope == "full_test":
            result = self._regenerate_full_test(
                test_impact,
                current_test,
                new_components,
                new_locators,
            )
        else:
            result = self._minimal_repair(
                test_impact,
                current_test,
                new_components,
                new_locators,
            )
        
        # Set decision type
        result.decision_type = decision_type
        
        # Record regeneration
        self._record_regeneration(result)
        
        logger.info(
            f"[SELECTIVE REGENERATION] Regeneration complete: "
            f"success={result.success}, confidence={result.confidence}"
        )
        
        return result
    
    def _determine_decision_type(
        self,
        test_impact: TestImpact,
    ) -> MaintenanceDecisionType:
        """Determine maintenance decision type.
        
        Args:
            test_impact: Test impact analysis
            
        Returns:
            Maintenance decision type
        """
        if test_impact.regeneration_scope == "locator_only":
            return MaintenanceDecisionType.UPDATE_LOCATOR
        elif test_impact.regeneration_scope == "assertion_only":
            return MaintenanceDecisionType.REGENERATE_ASSERTION
        elif test_impact.regeneration_scope == "step_only":
            return MaintenanceDecisionType.UPDATE_TEST_STEP
        elif test_impact.regeneration_scope == "test_section":
            return MaintenanceDecisionType.REGENERATE_TEST_SECTION
        elif test_impact.regeneration_scope == "full_test":
            return MaintenanceDecisionType.REGENERATE_TEST
        else:
            return MaintenanceDecisionType.NO_ACTION
    
    def _regenerate_locators_only(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_locators: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Regenerate only affected locators.
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_locators: New locator state
            
        Returns:
            Regeneration result
        """
        logger.info("[SELECTIVE REGENERATION] Locator-only regeneration")
        
        regenerated_steps = []
        preserved_steps = []
        new_locators_map = {}
        preserved_locators_map = {}
        new_assertions = []
        preserved_assertions = []
        
        test_steps = current_test.get("steps", [])
        
        for step in test_steps:
            step_id = step.get("step_id", "")
            
            if step_id in test_impact.affected_steps:
                # Regenerate locator for this step
                new_locator = self._find_new_locator(
                    step,
                    new_locators,
                )
                if new_locator:
                    new_locators_map[step_id] = new_locator
                    regenerated_steps.append(step_id)
                else:
                    preserved_locators_map[step_id] = step.get("locator", "")
                    preserved_steps.append(step_id)
            else:
                # Preserve this step
                preserved_steps.append(step_id)
                preserved_locators_map[step_id] = step.get("locator", "")
        
        # Preserve all assertions
        for step in test_steps:
            for assertion in step.get("assertions", []):
                preserved_assertions.append(assertion.get("assertion_id", ""))
        
        result = RegenerationResult(
            regeneration_id=f"REGEN-{uuid4().hex[:8]}",
            test_id=test_impact.test_id,
            decision_type=MaintenanceDecisionType.UPDATE_LOCATOR,
            regenerated_steps=regenerated_steps,
            preserved_steps=preserved_steps,
            new_locators=new_locators_map,
            preserved_locators=preserved_locators_map,
            new_assertions=new_assertions,
            preserved_assertions=preserved_assertions,
            success=len(regenerated_steps) > 0 or len(preserved_steps) > 0,
            confidence=0.9,
        )
        
        return result
    
    def _regenerate_assertions_only(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_components: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Regenerate only affected assertions.
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_components: New component state
            
        Returns:
            Regeneration result
        """
        logger.info("[SELECTIVE REGENERATION] Assertion-only regeneration")
        
        regenerated_steps = []
        preserved_steps = []
        new_locators_map = {}
        preserved_locators_map = {}
        new_assertions = []
        preserved_assertions = []
        
        test_steps = current_test.get("steps", [])
        
        for step in test_steps:
            step_id = step.get("step_id", "")
            step_assertions = step.get("assertions", [])
            
            # Check if any assertion is affected
            has_affected_assertion = any(
                assertion.get("assertion_id", "") in test_impact.affected_assertions
                for assertion in step_assertions
            )
            
            if has_affected_assertion:
                # Regenerate assertions for this step
                for assertion in step_assertions:
                    if assertion.get("assertion_id", "") in test_impact.affected_assertions:
                        new_assertion = self._regenerate_assertion(
                            assertion,
                            new_components,
                        )
                        if new_assertion:
                            new_assertions.append(new_assertion.get("assertion_id", ""))
                regenerated_steps.append(step_id)
            else:
                # Preserve assertions
                for assertion in step_assertions:
                    preserved_assertions.append(assertion.get("assertion_id", ""))
                preserved_steps.append(step_id)
            
            # Preserve all locators
            preserved_locators_map[step_id] = step.get("locator", "")
        
        result = RegenerationResult(
            regeneration_id=f"REGEN-{uuid4().hex[:8]}",
            test_id=test_impact.test_id,
            decision_type=MaintenanceDecisionType.REGENERATE_ASSERTION,
            regenerated_steps=regenerated_steps,
            preserved_steps=preserved_steps,
            new_locators=new_locators_map,
            preserved_locators=preserved_locators_map,
            new_assertions=new_assertions,
            preserved_assertions=preserved_assertions,
            success=len(new_assertions) > 0 or len(preserved_assertions) > 0,
            confidence=0.85,
        )
        
        return result
    
    def _regenerate_steps_only(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_components: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Regenerate only affected steps.
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_components: New component state
            new_locators: New locator state
            
        Returns:
            Regeneration result
        """
        logger.info("[SELECTIVE REGENERATION] Step-only regeneration")
        
        regenerated_steps = []
        preserved_steps = []
        new_locators_map = {}
        preserved_locators_map = {}
        new_assertions = []
        preserved_assertions = []
        
        test_steps = current_test.get("steps", [])
        
        for step in test_steps:
            step_id = step.get("step_id", "")
            
            if step_id in test_impact.affected_steps:
                # Regenerate this step
                new_step = self._regenerate_step(
                    step,
                    new_components,
                    new_locators,
                )
                if new_step:
                    regenerated_steps.append(step_id)
                    new_locators_map[step_id] = new_step.get("locator", "")
                    for assertion in new_step.get("assertions", []):
                        new_assertions.append(assertion.get("assertion_id", ""))
            else:
                # Preserve this step
                preserved_steps.append(step_id)
                preserved_locators_map[step_id] = step.get("locator", "")
                for assertion in step.get("assertions", []):
                    preserved_assertions.append(assertion.get("assertion_id", ""))
        
        result = RegenerationResult(
            regeneration_id=f"REGEN-{uuid4().hex[:8]}",
            test_id=test_impact.test_id,
            decision_type=MaintenanceDecisionType.UPDATE_TEST_STEP,
            regenerated_steps=regenerated_steps,
            preserved_steps=preserved_steps,
            new_locators=new_locators_map,
            preserved_locators=preserved_locators_map,
            new_assertions=new_assertions,
            preserved_assertions=preserved_assertions,
            success=len(regenerated_steps) > 0 or len(preserved_steps) > 0,
            confidence=0.8,
        )
        
        return result
    
    def _regenerate_test_section(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_components: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Regenerate affected test section.
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_components: New component state
            new_locators: New locator state
            
        Returns:
            Regeneration result
        """
        logger.info("[SELECTIVE REGENERATION] Test section regeneration")
        
        # Similar to step regeneration but for a larger section
        result = self._regenerate_steps_only(
            test_impact,
            current_test,
            new_components,
            new_locators,
        )
        
        result.decision_type = MaintenanceDecisionType.REGENERATE_TEST_SECTION
        result.confidence = 0.75
        
        return result
    
    def _regenerate_full_test(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_components: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Regenerate entire test (last resort).
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_components: New component state
            new_locators: New locator state
            
        Returns:
            Regeneration result
        """
        logger.warning("[SELECTIVE REGENERATION] Full test regeneration (last resort)")
        
        # In a real implementation, this would call Priority 24 automation generation
        # to regenerate the entire test from scratch
        
        test_steps = current_test.get("steps", [])
        
        regenerated_steps = [step.get("step_id", "") for step in test_steps]
        preserved_steps = []
        new_locators_map = {}
        preserved_locators_map = {}
        new_assertions = []
        preserved_assertions = []
        
        for step in test_steps:
            step_id = step.get("step_id", "")
            # Would regenerate from scratch
            new_locators_map[step_id] = step.get("locator", "")  # Placeholder
            for assertion in step.get("assertions", []):
                new_assertions.append(assertion.get("assertion_id", ""))
        
        result = RegenerationResult(
            regeneration_id=f"REGEN-{uuid4().hex[:8]}",
            test_id=test_impact.test_id,
            decision_type=MaintenanceDecisionType.FULL_REGENERATION,
            regenerated_steps=regenerated_steps,
            preserved_steps=preserved_steps,
            new_locators=new_locators_map,
            preserved_locators=preserved_locators_map,
            new_assertions=new_assertions,
            preserved_assertions=preserved_assertions,
            success=len(regenerated_steps) > 0,
            confidence=0.6,  # Lower confidence for full regeneration
        )
        
        return result
    
    def _minimal_repair(
        self,
        test_impact: TestImpact,
        current_test: Dict[str, Any],
        new_components: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> RegenerationResult:
        """Perform minimal repair.
        
        Args:
            test_impact: Test impact analysis
            current_test: Current test data
            new_components: New component state
            new_locators: New locator state
            
        Returns:
            Regeneration result
        """
        logger.info("[SELECTIVE REGENERATION] Minimal repair")
        
        test_steps = current_test.get("steps", [])
        
        preserved_steps = [step.get("step_id", "") for step in test_steps]
        preserved_locators_map = {
            step.get("step_id", ""): step.get("locator", "")
            for step in test_steps
        }
        preserved_assertions = [
            assertion.get("assertion_id", "")
            for step in test_steps
            for assertion in step.get("assertions", [])
        ]
        
        result = RegenerationResult(
            regeneration_id=f"REGEN-{uuid4().hex[:8]}",
            test_id=test_impact.test_id,
            decision_type=MaintenanceDecisionType.NO_ACTION,
            regenerated_steps=[],
            preserved_steps=preserved_steps,
            new_locators={},
            preserved_locators=preserved_locators_map,
            new_assertions=[],
            preserved_assertions=preserved_assertions,
            success=True,
            confidence=0.95,
        )
        
        return result
    
    def _find_new_locator(
        self,
        step: Dict[str, Any],
        new_locators: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Find new locator for a step.
        
        Args:
            step: Test step
            new_locators: New locator state
            
        Returns:
            New locator or None
        """
        old_locator = step.get("locator", "")
        old_target = step.get("target", "")
        
        # Try to find matching locator in new state
        for locator in new_locators:
            if locator.get("target", "") == old_target:
                return locator.get("locator", "")
        
        # Use locator strategy manager if available
        if self.locator_strategy_manager:
            # This would use the locator strategy to find a new locator
            pass
        
        return None
    
    def _regenerate_assertion(
        self,
        assertion: Dict[str, Any],
        new_components: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Regenerate an assertion.
        
        Args:
            assertion: Original assertion
            new_components: New component state
            
        Returns:
            New assertion or None
        """
        # In a real implementation, this would regenerate the assertion
        # based on the new component state
        return assertion.copy()
    
    def _regenerate_step(
        self,
        step: Dict[str, Any],
        new_components: List[Dict[str, Any]],
        new_locators: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Regenerate a test step.
        
        Args:
            step: Original step
            new_components: New component state
            new_locators: New locator state
            
        Returns:
            New step or None
        """
        # In a real implementation, this would regenerate the step
        # based on the new component and locator state
        return step.copy()
    
    def _record_regeneration(
        self,
        result: RegenerationResult,
    ):
        """Record regeneration for learning.
        
        Args:
            result: Regeneration result
        """
        self.regeneration_history.append({
            "regeneration_id": result.regeneration_id,
            "test_id": result.test_id,
            "decision_type": result.decision_type.value,
            "regenerated_steps": len(result.regenerated_steps),
            "preserved_steps": len(result.preserved_steps),
            "success": result.success,
            "confidence": result.confidence,
        })
