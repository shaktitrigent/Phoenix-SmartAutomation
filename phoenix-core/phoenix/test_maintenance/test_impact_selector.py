"""Test Impact Selector - Priority 30.

This module determines exactly which tests are affected by detected application changes,
ensuring minimal disruption by avoiding regeneration of unaffected tests.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.test_maintenance.models import TestImpact

# Priority 29 Change Intelligence
try:
    from phoenix.change_intelligence.models import SemanticChange
    PRIORITY29_AVAILABLE = True
except ImportError:
    PRIORITY29_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestImpactSelector:
    """Determines which tests are affected by application changes.
    
    This selector:
    - Maps changes to affected tests
    - Identifies affected test steps
    - Identifies affected locators
    - Identifies affected assertions
    - Calculates impact severity
    - Determines regeneration scope
    - Avoids regenerating unaffected tests
    """
    
    def __init__(self):
        """Initialize test impact selector."""
        self.test_registry: Dict[str, Dict[str, Any]] = {}
        self.component_test_mapping: Dict[str, List[str]] = {}
        self.flow_test_mapping: Dict[str, List[str]] = {}
        
        logger.info("[TEST IMPACT SELECTOR] Initialized")
    
    def register_test(
        self,
        test_id: str,
        test_data: Dict[str, Any],
    ):
        """Register a test for impact analysis.
        
        Args:
            test_id: Test identifier
            test_data: Test metadata including components, flows, steps
        """
        self.test_registry[test_id] = test_data
        
        # Build component to test mapping
        for component_id in test_data.get("components", []):
            if component_id not in self.component_test_mapping:
                self.component_test_mapping[component_id] = []
            self.component_test_mapping[component_id].append(test_id)
        
        # Build flow to test mapping
        for flow_id in test_data.get("flows", []):
            if flow_id not in self.flow_test_mapping:
                self.flow_test_mapping[flow_id] = []
            self.flow_test_mapping[flow_id].append(test_id)
        
        logger.debug(f"[TEST IMPACT SELECTOR] Registered test: {test_id}")
    
    def select_affected_tests(
        self,
        changes: List[SemanticChange],
        all_tests: List[Dict[str, Any]],
    ) -> List[TestImpact]:
        """Select tests affected by detected changes.
        
        Args:
            changes: List of detected semantic changes
            all_tests: All registered tests
            
        Returns:
            List of test impacts
        """
        logger.info(f"[TEST IMPACT SELECTOR] Analyzing {len(changes)} changes against {len(all_tests)} tests")
        
        impacts = []
        
        for change in changes:
            # Find tests affected by this change
            affected_tests = self._find_tests_for_change(change, all_tests)
            
            for test in affected_tests:
                impact = self._analyze_test_impact(change, test)
                impacts.append(impact)
        
        logger.info(f"[TEST IMPACT SELECTOR] Found {len(impacts)} test impacts")
        
        return impacts
    
    def _find_tests_for_change(
        self,
        change: SemanticChange,
        all_tests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Find tests affected by a specific change.
        
        Args:
            change: Semantic change
            all_tests: All tests to check
            
        Returns:
            List of affected tests
        """
        affected = []
        
        change_component_id = change.current_state.get("id", "")
        change_component_tag = change.current_state.get("tag", "")
        
        for test in all_tests:
            test_id = test.get("test_id", "")
            test_components = test.get("components", [])
            test_flows = test.get("flows", [])
            test_steps = test.get("steps", [])
            
            # Check if test uses changed component
            if change_component_id in test_components:
                affected.append(test)
                continue
            
            # Check if test uses changed flow
            change_flow_id = change.current_state.get("flow_id", "")
            if change_flow_id and change_flow_id in test_flows:
                affected.append(test)
                continue
            
            # Check if any test step uses changed component
            for step in test_steps:
                step_target = step.get("target", "")
                if step_target == change_component_id:
                    affected.append(test)
                    break
        
        return affected
    
    def _analyze_test_impact(
        self,
        change: SemanticChange,
        test: Dict[str, Any],
    ) -> TestImpact:
        """Analyze impact of change on a specific test.
        
        Args:
            change: Semantic change
            test: Test data
            
        Returns:
            Test impact analysis
        """
        test_id = test.get("test_id", "")
        test_steps = test.get("steps", [])
        
        # Identify affected steps
        affected_steps = self._find_affected_steps(change, test_steps)
        
        # Identify affected locators
        affected_locators = self._find_affected_locators(change, test_steps)
        
        # Identify affected assertions
        affected_assertions = self._find_affected_assertions(change, test_steps)
        
        # Determine severity
        severity = self._assess_severity(change, affected_steps, affected_locators)
        
        # Determine if regeneration is required
        requires_regeneration = self._requires_regeneration(change, affected_steps)
        
        # Determine regeneration scope
        regeneration_scope = self._determine_regeneration_scope(
            change,
            affected_steps,
            affected_locators,
            affected_assertions,
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(change, affected_steps)
        
        impact = TestImpact(
            impact_id=f"IMPACT-{uuid4().hex[:8]}",
            test_id=test_id,
            change_id=change.change_id,
            affected_steps=affected_steps,
            affected_locators=affected_locators,
            affected_assertions=affected_assertions,
            severity=severity,
            confidence=confidence,
            requires_regeneration=requires_regeneration,
            regeneration_scope=regeneration_scope,
        )
        
        logger.debug(
            f"[TEST IMPACT SELECTOR] Impact for {test_id}: "
            f"severity={severity}, scope={regeneration_scope}"
        )
        
        return impact
    
    def _find_affected_steps(
        self,
        change: SemanticChange,
        test_steps: List[Dict[str, Any]],
    ) -> List[str]:
        """Find test steps affected by change.
        
        Args:
            change: Semantic change
            test_steps: Test steps
            
        Returns:
            List of affected step IDs
        """
        affected = []
        change_component_id = change.current_state.get("id", "")
        
        for step in test_steps:
            step_id = step.get("step_id", "")
            step_target = step.get("target", "")
            
            if step_target == change_component_id:
                affected.append(step_id)
        
        return affected
    
    def _find_affected_locators(
        self,
        change: SemanticChange,
        test_steps: List[Dict[str, Any]],
    ) -> List[str]:
        """Find locators affected by change.
        
        Args:
            change: Semantic change
            test_steps: Test steps
            
        Returns:
            List of affected locator IDs
        """
        affected = []
        
        # If change is a locator change, find all steps using that locator
        if change.change_type.value in ["locator_changed", "locator_invalidated"]:
            change_locator = change.current_state.get("locator", "")
            
            for step in test_steps:
                step_locator = step.get("locator", "")
                if step_locator == change_locator:
                    affected.append(step.get("step_id", ""))
        
        return affected
    
    def _find_affected_assertions(
        self,
        change: SemanticChange,
        test_steps: List[Dict[str, Any]],
    ) -> List[str]:
        """Find assertions affected by change.
        
        Args:
            change: Semantic change
            test_steps: Test steps
            
        Returns:
            List of affected assertion IDs
        """
        affected = []
        change_component_id = change.current_state.get("id", "")
        
        for step in test_steps:
            step_assertions = step.get("assertions", [])
            
            for assertion in step_assertions:
                assertion_target = assertion.get("target", "")
                if assertion_target == change_component_id:
                    affected.append(assertion.get("assertion_id", ""))
        
        return affected
    
    def _assess_severity(
        self,
        change: SemanticChange,
        affected_steps: List[str],
        affected_locators: List[str],
    ) -> str:
        """Assess severity of impact.
        
        Args:
            change: Semantic change
            affected_steps: Affected steps
            affected_locators: Affected locators
            
        Returns:
            Severity level (low, medium, high, critical)
        """
        # Critical changes
        if change.severity.value == "critical":
            return "critical"
        
        # High severity changes
        if change.severity.value == "significant":
            return "high"
        
        # Many affected steps
        if len(affected_steps) > 5:
            return "high"
        
        # Many affected locators
        if len(affected_locators) > 3:
            return "medium"
        
        # Some affected steps
        if len(affected_steps) > 0:
            return "medium"
        
        # Minor impact
        return "low"
    
    def _requires_regeneration(
        self,
        change: SemanticChange,
        affected_steps: List[str],
    ) -> bool:
        """Determine if regeneration is required.
        
        Args:
            change: Semantic change
            affected_steps: Affected steps
            
        Returns:
            True if regeneration required
        """
        # Component removed - requires regeneration
        if change.change_type.value == "component_removed":
            return True
        
        # Locator changed - requires regeneration
        if change.change_type.value in ["locator_changed", "locator_invalidated"]:
            return True
        
        # Affected steps exist - requires regeneration
        if len(affected_steps) > 0:
            return True
        
        return False
    
    def _determine_regeneration_scope(
        self,
        change: SemanticChange,
        affected_steps: List[str],
        affected_locators: List[str],
        affected_assertions: List[str],
    ) -> str:
        """Determine scope of regeneration needed.
        
        Args:
            change: Semantic change
            affected_steps: Affected steps
            affected_locators: Affected locators
            affected_assertions: Affected assertions
            
        Returns:
            Regeneration scope (locator_only, step_only, assertion_only, test_section, full_test)
        """
        # Locator only change
        if change.change_type.value in ["locator_changed", "locator_invalidated"]:
            if len(affected_locators) > 0 and len(affected_steps) == 0:
                return "locator_only"
        
        # Assertion only change
        if change.change_type.value in ["validation_added", "validation_removed", "validation_modified"]:
            if len(affected_assertions) > 0 and len(affected_steps) == 0:
                return "assertion_only"
        
        # Step level change
        if len(affected_steps) > 0 and len(affected_steps) < 3:
            return "step_only"
        
        # Test section change
        if len(affected_steps) >= 3 and len(affected_steps) < len(affected_steps) / 2:
            return "test_section"
        
        # Full test change
        if len(affected_steps) >= len(affected_steps) / 2:
            return "full_test"
        
        return "minimal"
    
    def _calculate_confidence(
        self,
        change: SemanticChange,
        affected_steps: List[str],
    ) -> float:
        """Calculate confidence in impact analysis.
        
        Args:
            change: Semantic change
            affected_steps: Affected steps
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        base_confidence = change.confidence
        
        # Reduce confidence if no clear steps affected
        if len(affected_steps) == 0:
            return base_confidence * 0.7
        
        # High confidence if clear mapping
        if len(affected_steps) > 0:
            return min(base_confidence + 0.1, 1.0)
        
        return base_confidence
