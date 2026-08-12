"""Universal Assertion Generator - Generates evidence-based assertions for automation.

This module implements a generic assertion generator that creates assertions based
on actual application evidence from semantic understanding and component intelligence.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.automation_generation.models import (
    Assertion,
    AssertionType,
)
from phoenix.semantic.models import SemanticComponent
from phoenix.test_intelligence.models import TestScenario

logger = logging.getLogger(__name__)


class AssertionGenerator:
    """Universal assertion generator for evidence-based test assertions.
    
    This generator:
    - Generates assertions from application evidence
    - Maps semantic expectations to Playwright assertions
    - Validates assertion feasibility
    - Calculates assertion confidence
    - Prevents fake/invented assertions
    """
    
    def __init__(self):
        self.assertion_templates = self._initialize_assertion_templates()
        logger.info("AssertionGenerator initialized")
    
    def generate_assertions(
        self,
        scenario: TestScenario,
        components: Optional[List[SemanticComponent]] = None,
        page_evidence: Optional[Dict[str, Any]] = None,
    ) -> List[Assertion]:
        """Generate assertions from scenario and application evidence.
        
        Args:
            scenario: Test scenario with expected results
            components: Available semantic components
            page_evidence: Page-level evidence (title, URL, etc.)
            
        Returns:
            List of generated assertions
        """
        assertions = []
        components = components or []
        page_evidence = page_evidence or {}
        
        # Generate from expected result
        if scenario.expected_result:
            expected_assertions = self._generate_from_expected_result(
                scenario.expected_result,
                components,
                page_evidence,
            )
            assertions.extend(expected_assertions)
        
        # Generate from validation rules
        for rule in scenario.validation_rules:
            rule_assertions = self._generate_from_validation_rule(rule, components)
            assertions.extend(rule_assertions)
        
        # Generate from business intent
        intent_assertions = self._generate_from_business_intent(
            scenario.business_intent,
            page_evidence,
        )
        assertions.extend(intent_assertions)
        
        # Generate from page evidence if available
        if page_evidence:
            evidence_assertions = self._generate_from_page_evidence(page_evidence)
            assertions.extend(evidence_assertions)
        
        # Validate and score assertions
        validated_assertions = []
        for assertion in assertions:
            if self._validate_assertion(assertion, components):
                assertion.confidence = self._calculate_assertion_confidence(assertion)
                validated_assertions.append(assertion)
        
        logger.info(f"Generated {len(validated_assertions)} assertions from scenario")
        return validated_assertions
    
    def _initialize_assertion_templates(self) -> Dict[AssertionType, str]:
        """Initialize Playwright assertion templates."""
        return {
            AssertionType.PAGE_TITLE: 'expect(page).to_have_title("{value}")',
            AssertionType.URL: 'expect(page).to_have_url("{value}")',
            AssertionType.VISIBLE_TEXT: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.ELEMENT_VISIBILITY: 'expect({locator}).to_be_visible()',
            AssertionType.ELEMENT_STATE: 'expect({locator}).to_have_attribute("{attr}", "{value}")',
            AssertionType.ELEMENT_VALUE: 'expect({locator}).to_have_value("{value}")',
            AssertionType.ELEMENT_COUNT: 'expect({locator}).to_have_count({count})',
            AssertionType.TABLE_CONTENTS: 'expect({locator}).to_contain_text("{value}")',
            AssertionType.SUCCESS_MESSAGE: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.ERROR_MESSAGE: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.VALIDATION_MESSAGE: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.NAVIGATION_RESULT: 'expect(page).to_have_url(re.compile("{pattern}"))',
            AssertionType.CREATED_RECORD: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.UPDATED_RECORD: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.DELETED_RECORD: 'expect(page.get_by_text("{value}").not).to_be_visible()',
            AssertionType.SEARCH_RESULT: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.UPLOAD_RESULT: 'expect(page.get_by_text("{value}")).to_be_visible()',
            AssertionType.DOWNLOAD_RESULT: 'expect(page).to_have_download()',
        }
    
    def _generate_from_expected_result(
        self,
        expected_result: str,
        components: List[SemanticComponent],
        page_evidence: Dict[str, Any],
    ) -> List[Assertion]:
        """Generate assertions from expected result text."""
        assertions = []
        result_lower = expected_result.lower()
        
        # Success indicators
        if any(word in result_lower for word in ["success", "successful", "completed", "saved"]):
            assertion = Assertion(
                assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                assertion_type=AssertionType.SUCCESS_MESSAGE,
                expected_value=expected_result,
                comparison_type="contains",
                page_context=page_evidence.get("page_type", ""),
                evidence=["Expected result indicates success"],
            )
            assertions.append(assertion)
        
        # Error indicators
        elif any(word in result_lower for word in ["error", "failed", "invalid", "rejected"]):
            assertion = Assertion(
                assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                assertion_type=AssertionType.ERROR_MESSAGE,
                expected_value=expected_result,
                comparison_type="contains",
                page_context=page_evidence.get("page_type", ""),
                evidence=["Expected result indicates error"],
            )
            assertions.append(assertion)
        
        # Navigation indicators
        elif any(word in result_lower for word in ["navigate", "redirect", "go to", "page"]):
            assertion = Assertion(
                assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                assertion_type=AssertionType.NAVIGATION_RESULT,
                expected_value=self._extract_url_pattern(expected_result),
                comparison_type="matches",
                page_context=page_evidence.get("page_type", ""),
                evidence=["Expected result indicates navigation"],
            )
            assertions.append(assertion)
        
        # Default to visible text assertion
        else:
            assertion = Assertion(
                assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                assertion_type=AssertionType.VISIBLE_TEXT,
                expected_value=expected_result,
                comparison_type="contains",
                page_context=page_evidence.get("page_type", ""),
                evidence=["Default visible text assertion"],
            )
            assertions.append(assertion)
        
        return assertions
    
    def _generate_from_validation_rule(
        self,
        rule: str,
        components: List[SemanticComponent],
    ) -> List[Assertion]:
        """Generate assertions from validation rules."""
        assertions = []
        rule_lower = rule.lower()
        
        # Validation message assertion
        assertion = Assertion(
            assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
            assertion_type=AssertionType.VALIDATION_MESSAGE,
            expected_value=rule,
            comparison_type="contains",
            evidence=["From validation rule"],
        )
        assertions.append(assertion)
        
        return assertions
    
    def _generate_from_business_intent(
        self,
        business_intent: str,
        page_evidence: Dict[str, Any],
    ) -> List[Assertion]:
        """Generate assertions from business intent."""
        assertions = []
        intent_lower = business_intent.lower()
        
        # Authentication assertions
        if "authentication" in intent_lower or "login" in intent_lower:
            if page_evidence.get("expected_title"):
                assertion = Assertion(
                    assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                    assertion_type=AssertionType.PAGE_TITLE,
                    expected_value=page_evidence["expected_title"],
                    comparison_type="contains",
                    page_context=page_evidence.get("page_type", ""),
                    evidence=["Authentication intent with expected title"],
                )
                assertions.append(assertion)
        
        # Dashboard assertions
        elif "dashboard" in intent_lower:
            if page_evidence.get("expected_title"):
                assertion = Assertion(
                    assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                    assertion_type=AssertionType.PAGE_TITLE,
                    expected_value=page_evidence["expected_title"],
                    comparison_type="contains",
                    page_context=page_evidence.get("page_type", ""),
                    evidence=["Dashboard intent with expected title"],
                )
                assertions.append(assertion)
        
        return assertions
    
    def _generate_from_page_evidence(
        self,
        page_evidence: Dict[str, Any],
    ) -> List[Assertion]:
        """Generate assertions from page-level evidence."""
        assertions = []
        
        # Page title assertion
        if page_evidence.get("title"):
            assertion = Assertion(
                assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                assertion_type=AssertionType.PAGE_TITLE,
                expected_value=page_evidence["title"],
                comparison_type="equals",
                page_context=page_evidence.get("page_type", ""),
                evidence=["From page evidence"],
            )
            assertions.append(assertion)
        
        # URL assertion
        if page_evidence.get("url"):
            assertion = Assertion(
                assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
                assertion_type=AssertionType.URL,
                expected_value=page_evidence["url"],
                comparison_type="contains",
                page_context=page_evidence.get("page_type", ""),
                evidence=["From page evidence"],
            )
            assertions.append(assertion)
        
        return assertions
    
    def _extract_url_pattern(self, text: str) -> str:
        """Extract URL pattern from text."""
        # Look for URL-like patterns
        url_pattern = re.search(r'/[\w\-]+', text)
        if url_pattern:
            return url_pattern.group(0)
        return ".*"  # Default pattern
    
    def _validate_assertion(
        self,
        assertion: Assertion,
        components: List[SemanticComponent],
    ) -> bool:
        """Validate that assertion is feasible and evidence-based."""
        # Reject assertions without expected values
        if not assertion.expected_value and assertion.assertion_type not in [
            AssertionType.ELEMENT_VISIBILITY,
            AssertionType.DOWNLOAD_RESULT,
        ]:
            logger.warning(f"Assertion {assertion.assertion_id} missing expected value")
            return False
        
        # Reject assertions targeting non-existent components
        if assertion.target_component_id:
            component_exists = any(
                c.component_id == assertion.target_component_id for c in components
            )
            if not component_exists:
                logger.warning(
                    f"Assertion {assertion.assertion_id} targets non-existent component "
                    f"{assertion.target_component_id}"
                )
                return False
        
        # Reject assertions with fake/placeholder values
        if assertion.expected_value:
            value_str = str(assertion.expected_value).lower()
            if any(
                placeholder in value_str
                for placeholder in ["placeholder", "todo", "fixme", "example", "test"]
            ):
                logger.warning(
                    f"Assertion {assertion.assertion_id} contains placeholder value"
                )
                return False
        
        return True
    
    def _calculate_assertion_confidence(self, assertion: Assertion) -> float:
        """Calculate confidence score for an assertion."""
        base_confidence = 0.7
        
        # Boost if evidence exists
        if assertion.evidence:
            base_confidence += 0.1 * min(len(assertion.evidence), 3)
        
        # Boost if locator is provided
        if assertion.target_locator:
            base_confidence += 0.1
        
        # Boost if expected value is specific
        if assertion.expected_value and len(str(assertion.expected_value)) > 3:
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def generate_playwright_assertion(self, assertion: Assertion) -> str:
        """Generate Playwright assertion code."""
        # Handle both enum and string assertion_type
        assertion_type = assertion.assertion_type
        if isinstance(assertion_type, str):
            try:
                assertion_type = AssertionType(assertion_type)
            except ValueError:
                logger.warning(f"Invalid assertion type: {assertion_type}")
                return "# TODO: Invalid assertion type"
        
        template = self.assertion_templates.get(assertion_type)
        
        if not template:
            logger.warning(f"No template for assertion type {assertion_type}")
            return "# TODO: Assertion not implemented"
        
        # Substitute values
        code = template
        
        if assertion.expected_value:
            code = code.replace("{value}", str(assertion.expected_value))
            code = code.replace("{pattern}", str(assertion.expected_value))
        
        if assertion.target_locator:
            code = code.replace("{locator}", assertion.target_locator)
        
        if assertion_type == AssertionType.ELEMENT_COUNT:
            code = code.replace("{count}", str(assertion.expected_value or 1))
        
        if assertion_type == AssertionType.ELEMENT_STATE:
            code = code.replace("{attr}", "value")
            code = code.replace("{value}", str(assertion.expected_value or ""))
        
        return code
    
    def generate_assertion_for_component(
        self,
        component: SemanticComponent,
        assertion_type: AssertionType,
        expected_value: Any = None,
    ) -> Assertion:
        """Generate an assertion for a specific component."""
        assertion = Assertion(
            assertion_id=f"ASSERT-{uuid.uuid4().hex[:8].upper()}",
            assertion_type=assertion_type,
            target_component_id=component.component_id,
            target_locator=component.selected_locator,
            expected_value=expected_value,
            page_context=component.page_type,
            evidence=[f"Component: {component.component_type.value}"],
        )
        
        assertion.confidence = self._calculate_assertion_confidence(assertion)
        
        return assertion
    
    def batch_generate_assertions(
        self,
        scenarios: List[TestScenario],
        components_map: Optional[Dict[str, List[SemanticComponent]]] = None,
        page_evidence_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, List[Assertion]]:
        """Generate assertions for multiple scenarios."""
        all_assertions = {}
        components_map = components_map or {}
        page_evidence_map = page_evidence_map or {}
        
        for scenario in scenarios:
            components = components_map.get(scenario.scenario_id, [])
            page_evidence = page_evidence_map.get(scenario.scenario_id, {})
            
            assertions = self.generate_assertions(scenario, components, page_evidence)
            all_assertions[scenario.scenario_id] = assertions
        
        logger.info(f"Generated assertions for {len(all_assertions)} scenarios")
        return all_assertions
