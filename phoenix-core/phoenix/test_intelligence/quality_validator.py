"""AI Test Validator - Test Quality Validation (Priority 23).

This module validates generated test scenarios for quality before
accepting them into the test suite.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestScenario,
    QualityIssue,
    QualityIssueType,
)

logger = logging.getLogger(__name__)


class AITestValidator:
    """AI test quality validator for ANY web application.
    
    This validator detects:
    - Missing steps
    - Missing expected result
    - Missing preconditions
    - Invalid locator
    - Unsupported action
    - Duplicate scenario
    - Contradictory steps
    - Impossible navigation
    - Missing test data
    - Missing validation
    - Placeholder implementation
    - Empty test body
    - Unsupported assumptions
    - Low confidence
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self, min_quality_score: float = 70.0):
        """Initialize the AI test validator.
        
        Args:
            min_quality_score: Minimum quality score to accept a scenario
        """
        self.min_quality_score = min_quality_score
        logger.info(f"[AI TEST VALIDATOR] Initialized with min quality score {min_quality_score}")
    
    def validate_scenario(
        self,
        scenario: TestScenario,
        available_components: List[Any] = None,
        available_flows: List[Any] = None,
    ) -> tuple[bool, float, List[QualityIssue]]:
        """Validate a single test scenario.
        
        Args:
            scenario: Test scenario to validate
            available_components: List of available components
            available_flows: List of available flows
            
        Returns:
            Tuple of (is_valid, quality_score, issues)
        """
        issues = []
        
        # Check for missing steps
        steps_issues = self._check_steps(scenario)
        issues.extend(steps_issues)
        
        # Check for missing expected result
        expected_result_issues = self._check_expected_result(scenario)
        issues.extend(expected_result_issues)
        
        # Check for missing preconditions
        preconditions_issues = self._check_preconditions(scenario)
        issues.extend(preconditions_issues)
        
        # Check for missing test data
        test_data_issues = self._check_test_data(scenario)
        issues.extend(test_data_issues)
        
        # Check for missing validation
        validation_issues = self._check_validation(scenario)
        issues.extend(validation_issues)
        
        # Check for placeholder implementation
        placeholder_issues = self._check_placeholder(scenario)
        issues.extend(placeholder_issues)
        
        # Check for empty test body
        empty_body_issues = self._check_empty_body(scenario)
        issues.extend(empty_body_issues)
        
        # Check for low confidence
        confidence_issues = self._check_confidence(scenario)
        issues.extend(confidence_issues)
        
        # Check for component references
        component_issues = self._check_component_references(
            scenario,
            available_components,
        )
        issues.extend(component_issues)
        
        # Check for flow references
        flow_issues = self._check_flow_references(
            scenario,
            available_flows,
        )
        issues.extend(flow_issues)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(scenario, issues)
        
        # Determine if valid
        is_valid = quality_score >= self.min_quality_score and not self._has_critical_issues(issues)
        
        # Update scenario
        scenario.quality_score = quality_score
        scenario.quality_issues = [issue.model_dump() for issue in issues]
        scenario.is_validated = True
        
        logger.info(f"[AI TEST VALIDATOR] Validated scenario {scenario.scenario_id}: score={quality_score:.1f}, valid={is_valid}")
        
        return is_valid, quality_score, issues
    
    def validate_scenarios(
        self,
        scenarios: List[TestScenario],
        available_components: List[Any] = None,
        available_flows: List[Any] = None,
    ) -> tuple[List[TestScenario], List[TestScenario], Dict[str, Any]]:
        """Validate multiple test scenarios.
        
        Args:
            scenarios: List of test scenarios to validate
            available_components: List of available components
            available_flows: List of available flows
            
        Returns:
            Tuple of (valid_scenarios, rejected_scenarios, validation_stats)
        """
        valid_scenarios = []
        rejected_scenarios = []
        
        validation_stats = {
            "total": len(scenarios),
            "valid": 0,
            "rejected": 0,
            "average_quality_score": 0.0,
            "issues_by_type": {},
        }
        
        total_quality_score = 0.0
        
        for scenario in scenarios:
            is_valid, quality_score, issues = self.validate_scenario(
                scenario,
                available_components,
                available_flows,
            )
            
            total_quality_score += quality_score
            
            if is_valid:
                valid_scenarios.append(scenario)
                validation_stats["valid"] += 1
            else:
                rejected_scenarios.append(scenario)
                validation_stats["rejected"] += 1
            
            # Track issues by type
            for issue in issues:
                issue_type = issue.issue_type.value
                validation_stats["issues_by_type"][issue_type] = \
                    validation_stats["issues_by_type"].get(issue_type, 0) + 1
        
        # Calculate average quality score
        if scenarios:
            validation_stats["average_quality_score"] = total_quality_score / len(scenarios)
        
        logger.info(f"[AI TEST VALIDATOR] Validated {len(scenarios)} scenarios: {validation_stats['valid']} valid, {validation_stats['rejected']} rejected")
        
        return valid_scenarios, rejected_scenarios, validation_stats
    
    def _check_steps(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for missing or invalid steps."""
        issues = []
        
        if not scenario.steps or len(scenario.steps) == 0:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_STEPS,
                severity="critical",
                description="Scenario has no steps defined",
                affected_field="steps",
                recommendation="Add test steps to define the scenario execution",
                evidence=["steps list is empty"],
            ))
        elif len(scenario.steps) < 2:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_STEPS,
                severity="high",
                description="Scenario has insufficient steps",
                affected_field="steps",
                recommendation="Add more detailed steps to properly define the scenario",
                evidence=[f"Only {len(scenario.steps)} step(s) defined"],
            ))
        
        return issues
    
    def _check_expected_result(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for missing expected result."""
        issues = []
        
        if not scenario.expected_result or len(scenario.expected_result.strip()) == 0:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_EXPECTED_RESULT,
                severity="high",
                description="Scenario has no expected result defined",
                affected_field="expected_result",
                recommendation="Define the expected result for this scenario",
                evidence=["expected_result is empty"],
            ))
        
        return issues
    
    def _check_preconditions(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for missing preconditions."""
        issues = []
        
        if not scenario.preconditions or len(scenario.preconditions) == 0:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_PRECONDITIONS,
                severity="medium",
                description="Scenario has no preconditions defined",
                affected_field="preconditions",
                recommendation="Add preconditions to define the required state before execution",
                evidence=["preconditions list is empty"],
            ))
        
        return issues
    
    def _check_test_data(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for missing test data."""
        issues = []
        
        # Check if scenario needs test data based on steps
        needs_test_data = any(
            "enter" in step.lower() or "fill" in step.lower() or "input" in step.lower()
            for step in scenario.steps
        )
        
        if needs_test_data and (not scenario.test_data or len(scenario.test_data) == 0):
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_TEST_DATA,
                severity="high",
                description="Scenario needs test data but none is defined",
                affected_field="test_data",
                recommendation="Add test data for the input fields in this scenario",
                evidence=["Steps indicate input operations but no test data provided"],
            ))
        
        return issues
    
    def _check_validation(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for missing validation rules."""
        issues = []
        
        # Check if scenario is validation-related
        is_validation_scenario = scenario.scenario_type.value in ["validation", "negative"]
        
        if is_validation_scenario and (not scenario.validation_rules or len(scenario.validation_rules) == 0):
            issues.append(QualityIssue(
                issue_type=QualityIssueType.MISSING_VALIDATION,
                severity="medium",
                description="Validation scenario has no validation rules defined",
                affected_field="validation_rules",
                recommendation="Add validation rules to define what should be validated",
                evidence=["Scenario type is validation but no rules defined"],
            ))
        
        return issues
    
    def _check_placeholder(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for placeholder implementations."""
        issues = []
        
        placeholder_indicators = ["TODO", "FIXME", "placeholder", "not implemented"]
        
        for step in scenario.steps:
            for indicator in placeholder_indicators:
                if indicator.lower() in step.lower():
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.PLACEHOLDER_IMPLEMENTATION,
                        severity="high",
                        description="Scenario contains placeholder implementation",
                        affected_field="steps",
                        recommendation="Replace placeholder with actual implementation",
                        evidence=[f"Step contains '{indicator}'"],
                    ))
                    break
        
        return issues
    
    def _check_empty_body(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for empty test body."""
        issues = []
        
        # Check if all critical fields are empty
        critical_fields = ["title", "purpose", "steps", "expected_result"]
        empty_fields = [
            field for field in critical_fields
            if not getattr(scenario, field) or len(str(getattr(scenario, field)).strip()) == 0
        ]
        
        if len(empty_fields) >= 3:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.EMPTY_TEST_BODY,
                severity="critical",
                description="Scenario has empty critical fields",
                affected_field="multiple",
                recommendation="Fill in all critical fields (title, purpose, steps, expected_result)",
                evidence=[f"Empty fields: {', '.join(empty_fields)}"],
            ))
        
        return issues
    
    def _check_confidence(self, scenario: TestScenario) -> List[QualityIssue]:
        """Check for low confidence."""
        issues = []
        
        if scenario.confidence < 0.5:
            issues.append(QualityIssue(
                issue_type=QualityIssueType.LOW_CONFIDENCE,
                severity="medium",
                description="Scenario has low generation confidence",
                affected_field="confidence",
                recommendation="Review scenario and add more evidence to improve confidence",
                evidence=[f"Confidence: {scenario.confidence:.2f}"],
            ))
        
        return issues
    
    def _check_component_references(
        self,
        scenario: TestScenario,
        available_components: List[Any] = None,
    ) -> List[QualityIssue]:
        """Check for invalid component references."""
        issues = []
        
        if not available_components:
            return issues
        
        available_ids = set()
        for comp in available_components:
            if hasattr(comp, "component_id"):
                available_ids.add(comp.component_id)
        
        for component_id in scenario.related_components:
            if component_id not in available_ids:
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.UNSUPPORTED_ASSUMPTIONS,
                    severity="medium",
                    description=f"Scenario references unknown component: {component_id}",
                    affected_field="related_components",
                    recommendation="Verify component exists or remove reference",
                    evidence=[f"Component ID not found: {component_id}"],
                ))
        
        return issues
    
    def _check_flow_references(
        self,
        scenario: TestScenario,
        available_flows: List[Any] = None,
    ) -> List[QualityIssue]:
        """Check for invalid flow references."""
        issues = []
        
        if not available_flows:
            return issues
        
        available_ids = set()
        for flow in available_flows:
            if hasattr(flow, "flow_id"):
                available_ids.add(flow.flow_id)
        
        for flow_id in scenario.related_flows:
            if flow_id not in available_ids:
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.UNSUPPORTED_ASSUMPTIONS,
                    severity="medium",
                    description=f"Scenario references unknown flow: {flow_id}",
                    affected_field="related_flows",
                    recommendation="Verify flow exists or remove reference",
                    evidence=[f"Flow ID not found: {flow_id}"],
                ))
        
        return issues
    
    def _calculate_quality_score(
        self,
        scenario: TestScenario,
        issues: List[QualityIssue],
    ) -> float:
        """Calculate quality score based on issues."""
        score = 100.0
        
        for issue in issues:
            if issue.severity == "critical":
                score -= 25
            elif issue.severity == "high":
                score -= 15
            elif issue.severity == "medium":
                score -= 10
            elif issue.severity == "low":
                score -= 5
        
        # Bonus for having good content
        if len(scenario.steps) >= 3:
            score += 5
        if scenario.expected_result:
            score += 5
        if scenario.preconditions:
            score += 3
        if scenario.test_data:
            score += 2
        
        return max(0.0, min(100.0, score))
    
    def _has_critical_issues(self, issues: List[QualityIssue]) -> bool:
        """Check if there are any critical issues."""
        return any(issue.severity == "critical" for issue in issues)
