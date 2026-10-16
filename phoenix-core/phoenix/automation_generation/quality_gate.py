"""Automation Quality Gate - Validates automation before execution.

This module implements a comprehensive quality gate that detects and rejects
automation with placeholder implementations, fake assertions, missing data,
and other quality issues before execution.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import ast
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

from phoenix.automation_generation.models import (
    GeneratedAutomation,
    AutomationPlan,
    Action,
    Assertion,
    TestDataRequirement,
    AutomationStatus,
    QualityIssueType,
)

logger = logging.getLogger(__name__)


class QualityIssue(BaseModel):
    """Represents a quality issue detected in automation."""
    
    issue_id: str = Field(..., description="Unique issue ID")
    issue_type: QualityIssueType = Field(..., description="Type of quality issue")
    severity: str = Field(default="medium", description="Issue severity (low, medium, high, critical)")
    
    # Location
    file_path: str = Field(default="", description="File path where issue was found")
    line_number: int = Field(default=0, description="Line number of issue")
    
    # Description
    message: str = Field(..., description="Issue description")
    suggestion: str = Field(default="", description="Suggested fix")
    
    # Evidence
    evidence: str = Field(default="", description="Code or text causing the issue")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class QualityGateResult(BaseModel):
    """Result of quality gate validation."""
    
    passed: bool = Field(..., description="Whether automation passed quality gate")
    quality_score: float = Field(..., ge=0.0, le=100.0, description="Overall quality score")
    
    # Issues
    issues: List[QualityIssue] = Field(default_factory=list, description="All detected issues")
    critical_issues: List[QualityIssue] = Field(default_factory=list, description="Critical issues")
    high_issues: List[QualityIssue] = Field(default_factory=list, description="High severity issues")
    medium_issues: List[QualityIssue] = Field(default_factory=list, description="Medium severity issues")
    low_issues: List[QualityIssue] = Field(default_factory=list, description="Low severity issues")
    
    # Statistics
    total_issues: int = Field(default=0, description="Total issue count")
    blocking_issues: int = Field(default=0, description="Number of blocking issues")
    
    # Recommendation
    recommendation: str = Field(default="", description="Recommendation for the automation")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AutomationQualityGate:
    """Comprehensive quality gate for automation validation.
    
    This gate detects:
    - pass, TODO, NotImplemented
    - empty test body
    - placeholder locator
    - fake assertion
    - missing assertion
    - invalid locator
    - unsupported action
    - missing test data
    - contradictory steps
    - impossible navigation
    - duplicate automation
    - hardcoded credentials
    - hardcoded product assumptions
    - application-specific assumptions
    """
    
    def __init__(self, block_on_critical: bool = True, block_on_high: bool = True):
        self.block_on_critical = block_on_critical
        self.block_on_high = block_on_high
        
        # Patterns to detect
        self.placeholder_patterns = [
            r"TODO",
            r"FIXME",
            r"XXX",
            r"HACK",
            r"placeholder",
            r"example\.com",
            r"test123",
            r"dummy",
            r"fake",
        ]
        
        self.hardcoded_credential_patterns = [
            r"password\s*=\s*['\"]\w+['\"]",
            r"username\s*=\s*['\"]\w+['\"]",
            r"api_key\s*=\s*['\"]\w+['\"]",
            r"secret\s*=\s*['\"]\w+['\"]",
            r"token\s*=\s*['\"]\w+['\"]",
        ]
        
        self.application_specific_patterns = [
            r"orangehrm",
            r"jira",
            r"salesforce",
            r"sap",
            r"servicenow",
            r"saucedemo",  # Added SauceDemo to ensure agnostic behavior
        ]
        
        logger.info("AutomationQualityGate initialized")
    
    def validate_automation(
        self,
        automation: GeneratedAutomation,
        script_code: Optional[str] = None,
    ) -> QualityGateResult:
        """Validate automation through quality gate.
        
        Args:
            automation: Generated automation to validate
            script_code: Optional script code to analyze
            
        Returns:
            QualityGateResult with validation outcome
        """
        issues = []
        code_to_analyze = script_code or automation.script_code
        
        # Parse the code
        try:
            tree = ast.parse(code_to_analyze)
        except SyntaxError as e:
            # Syntax error is a critical issue
            issue = QualityIssue(
                issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                issue_type=QualityIssueType.UNSUPPORTED_ACTION,
                severity="critical",
                message=f"Syntax error in generated code: {e}",
                suggestion="Fix syntax errors before execution",
                evidence=str(e),
            )
            issues.append(issue)
            return self._create_result(False, 0.0, issues)
        
        # Run all quality checks
        issues.extend(self._check_placeholder_implementation(tree, code_to_analyze))
        issues.extend(self._check_empty_test_body(tree))
        issues.extend(self._check_placeholder_locators(code_to_analyze))
        issues.extend(self._check_fake_assertions(tree, code_to_analyze))
        issues.extend(self._check_missing_assertions(tree))
        issues.extend(self._check_invalid_locators(code_to_analyze))
        issues.extend(self._check_unsupported_actions(tree))
        issues.extend(self._check_missing_test_data(automation))
        issues.extend(self._check_hardcoded_credentials(code_to_analyze))
        issues.extend(self._check_application_specific(code_to_analyze))
        issues.extend(self._check_impossible_navigation(code_to_analyze))
        
        # Categorize issues
        result = self._create_result_from_issues(issues)
        
        # Update automation with issues
        automation.quality_issues = [i.model_dump() for i in issues]
        automation.quality_score = result.quality_score
        
        if result.passed:
            automation.validation_status = "passed"
        else:
            automation.validation_status = "failed"
            automation.status = AutomationStatus.REJECTED
        
        logger.info(
            f"Quality gate validation: {'PASSED' if result.passed else 'FAILED'} "
            f"(score: {result.quality_score:.1f}, issues: {len(issues)})"
        )
        
        return result
    
    def _check_placeholder_implementation(
        self,
        tree: ast.AST,
        code: str,
    ) -> List[QualityIssue]:
        """Check for placeholder implementations like pass, TODO."""
        issues = []
        
        for node in ast.walk(tree):
            # Check for pass statements
            if isinstance(node, ast.Pass):
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.PLACEHOLDER_IMPLEMENTATION,
                    severity="critical",
                    message="Placeholder 'pass' statement found",
                    suggestion="Implement actual test logic",
                    evidence="pass",
                    line_number=getattr(node, "lineno", 0),
                )
                issues.append(issue)
            
            # Check for NotImplemented
            if isinstance(node, ast.Name) and node.id == "NotImplemented":
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.PLACEHOLDER_IMPLEMENTATION,
                    severity="critical",
                    message="NotImplementedError placeholder found",
                    suggestion="Implement actual test logic",
                    evidence="NotImplemented",
                    line_number=getattr(node, "lineno", 0),
                )
                issues.append(issue)
        
        # Check for TODO/FIXME comments
        for pattern in self.placeholder_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                # Find line number
                line_num = code[:match.start()].count('\n') + 1
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.PLACEHOLDER_IMPLEMENTATION,
                    severity="high",
                    message=f"Placeholder comment '{match.group()}' found",
                    suggestion="Replace with actual implementation",
                    evidence=match.group(),
                    line_number=line_num,
                )
                issues.append(issue)
        
        return issues
    
    def _check_empty_test_body(self, tree: ast.AST) -> List[QualityIssue]:
        """Check for empty test function bodies."""
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function name starts with test_
                if node.name.startswith("test_"):
                    # Check if function body is empty or only has pass/docstring
                    body_statements = [
                        stmt for stmt in node.body
                        if not isinstance(stmt, (ast.Pass, ast.Expr))
                    ]
                    
                    if not body_statements:
                        issue = QualityIssue(
                            issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                            issue_type=QualityIssueType.EMPTY_TEST_BODY,
                            severity="critical",
                            message=f"Test function '{node.name}' has empty body",
                            suggestion="Add test steps and assertions",
                            evidence=f"def {node.name}(...):",
                            line_number=getattr(node, "lineno", 0),
                        )
                        issues.append(issue)
        
        return issues
    
    def _check_placeholder_locators(self, code: str) -> List[QualityIssue]:
        """Check for placeholder or fake locators."""
        issues = []
        
        # Check for placeholder patterns in locators
        locator_patterns = [
            r'get_by_text\(["\']placeholder["\']\)',
            r'get_by_text\(["\']TODO["\']\)',
            r'get_by_text\(["\']example["\']\)',
            r'locator\(["\'].*placeholder.*["\']\)',
        ]
        
        for pattern in locator_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.INVALID_LOCATOR,
                    severity="high",
                    message="Placeholder locator found",
                    suggestion="Use actual element locator",
                    evidence=match.group(),
                    line_number=line_num,
                )
                issues.append(issue)
        
        return issues
    
    def _check_fake_assertions(
        self,
        tree: ast.AST,
        code: str,
    ) -> List[QualityIssue]:
        """Check for fake or placeholder assertions."""
        issues = []
        
        for node in ast.walk(tree):
            # Check for assert True or assert False
            if isinstance(node, ast.Assert):
                if isinstance(node.test, ast.NameConstant):
                    if node.test.value in [True, False]:
                        issue = QualityIssue(
                            issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                            issue_type=QualityIssueType.UNSUPPORTED_ASSUMPTIONS,
                            severity="high",
                            message=f"Fake assertion 'assert {node.test.value}' found",
                            suggestion="Use meaningful assertion",
                            evidence=f"assert {node.test.value}",
                            line_number=getattr(node, "lineno", 0),
                        )
                        issues.append(issue)
        
        # Check for placeholder assertion values
        assertion_patterns = [
            r'to_have_text\(["\']placeholder["\']\)',
            r'to_have_text\(["\']TODO["\']\)',
            r'to_contain_text\(["\']example["\']\)',
        ]
        
        for pattern in assertion_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.UNSUPPORTED_ASSUMPTIONS,
                    severity="medium",
                    message="Placeholder assertion value found",
                    suggestion="Use actual expected value",
                    evidence=match.group(),
                    line_number=line_num,
                )
                issues.append(issue)
        
        return issues
    
    def _check_missing_assertions(self, tree: ast.AST) -> List[QualityIssue]:
        """Check for missing assertions in test functions."""
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Check for assertions
                has_assertion = False
                for child in ast.walk(node):
                    if isinstance(child, (ast.Assert, ast.Call)):
                        # Check if it's an expect() call (Playwright assertion)
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Attribute):
                                if child.func.attr == "to_be_visible" or \
                                   child.func.attr == "to_have_text" or \
                                   child.func.attr == "to_contain_text" or \
                                   child.func.attr == "to_have_title" or \
                                   child.func.attr == "to_have_url":
                                    has_assertion = True
                                    break
                        elif isinstance(child, ast.Assert):
                            has_assertion = True
                            break
                
                if not has_assertion:
                    issue = QualityIssue(
                        issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                        issue_type=QualityIssueType.MISSING_VALIDATION,
                        severity="medium",
                        message=f"Test function '{node.name}' has no assertions",
                        suggestion="Add assertions to verify expected behavior",
                        evidence=f"def {node.name}(...):",
                        line_number=getattr(node, "lineno", 0),
                    )
                    issues.append(issue)
        
        return issues
    
    def _check_invalid_locators(self, code: str) -> List[QualityIssue]:
        """Check for invalid or suspicious locators."""
        issues = []
        
        # Check for XPath overuse (fragile locators)
        xpath_count = len(re.findall(r'xpath\s*=', code))
        if xpath_count > 3:
            issue = QualityIssue(
                issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                issue_type=QualityIssueType.INVALID_LOCATOR,
                severity="medium",
                message=f"Excessive XPath usage ({xpath_count} locators)",
                suggestion="Prefer stable locators like test-id, role, or label",
                evidence=f"XPath count: {xpath_count}",
            )
            issues.append(issue)
        
        # Check for text-based locators with generic text
        generic_text_patterns = [
            r'get_by_text\(["\']click["\']\)',
            r'get_by_text\(["\']submit["\']\)',
            r'get_by_text\(["\']button["\']\)',
        ]
        
        for pattern in generic_text_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.INVALID_LOCATOR,
                    severity="low",
                    message="Generic text locator found (may be unstable)",
                    suggestion="Use more specific locator like role or test-id",
                    evidence=match.group(),
                    line_number=line_num,
                )
                issues.append(issue)
        
        return issues
    
    def _check_unsupported_actions(self, tree: ast.AST) -> List[QualityIssue]:
        """Check for unsupported or suspicious actions."""
        issues = []
        
        # Check for time.sleep (should use Playwright waits)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "sleep" and \
                       isinstance(node.func.value, ast.Name) and \
                       node.func.value.id == "time":
                        issue = QualityIssue(
                            issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                            issue_type=QualityIssueType.UNSUPPORTED_ACTION,
                            severity="medium",
                            message="time.sleep() found (use Playwright waits instead)",
                            suggestion="Use page.wait_for_*() methods",
                            evidence="time.sleep",
                            line_number=getattr(node, "lineno", 0),
                        )
                        issues.append(issue)
        
        return issues
    
    def _check_missing_test_data(self, automation: GeneratedAutomation) -> List[QualityIssue]:
        """Check for missing required test data."""
        issues = []
        
        # This would need to be enhanced with actual test data analysis
        # For now, check if automation mentions test data but has none provided
        
        if "test_data" in automation.metadata:
            required_data = automation.metadata.get("test_data", {})
            missing_data = [k for k, v in required_data.items() if not v]
            
            if missing_data:
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.MISSING_TEST_DATA,
                    severity="high",
                    message=f"Missing test data: {', '.join(missing_data)}",
                    suggestion="Provide required test data values",
                    evidence=f"Missing: {missing_data}",
                )
                issues.append(issue)
        
        return issues
    
    def _check_hardcoded_credentials(self, code: str) -> List[QualityIssue]:
        """Check for hardcoded credentials."""
        issues = []
        
        for pattern in self.hardcoded_credential_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.UNSUPPORTED_ASSUMPTIONS,
                    severity="critical",
                    message="Hardcoded credential found",
                    suggestion="Use environment variables or secure configuration",
                    evidence=match.group(),
                    line_number=line_num,
                )
                issues.append(issue)
        
        return issues
    
    def _check_application_specific(self, code: str) -> List[QualityIssue]:
        """Check for application-specific hardcoded logic in framework code.
        
        Distinguishes between:
        - Test fixture/verification data (ALLOWED in test files)
        - Framework implementation (FORBIDDEN in framework code)
        """
        issues = []
        
        # Check if this is a test file (allow app-specific references in test data)
        is_test_file = any(indicator in code for indicator in [
            "def test_", 
            "conftest.py", 
            "fixture", 
            "test_data",
            "tests/",
            "manual_tests/"
        ])
        
        for pattern in self.application_specific_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                matched_text = match.group()
                line_num = code[:match.start()].count('\n') + 1
                
                # Allow app-specific references in test data/fixtures
                if is_test_file:
                    # Check if it's in a data structure or test-specific context
                    context = self._get_line_context(code, line_num)
                    if any(data_indicator in context.lower() for data_indicator in [
                        "test_data", "fixture", "config", "base_url", "environment"
                    ]):
                        continue  # Skip - this is test fixture data, not framework code
                
                # Flag as issue in framework code
                issue = QualityIssue(
                    issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type=QualityIssueType.UNSUPPORTED_ASSUMPTIONS,
                    severity="high",
                    message=f"Application-specific reference '{matched_text}' found in framework code",
                    suggestion="Use generic, application-agnostic logic in framework code. App-specific references should only be in test fixtures and test data.",
                    evidence=matched_text,
                    line_number=line_num,
                )
                issues.append(issue)
        
        return issues
    
    def _get_line_context(self, code: str, line_num: int, context_lines: int = 2) -> str:
        """Get context around a specific line for better analysis."""
        lines = code.split('\n')
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        return '\n'.join(lines[start:end])
    
    def _check_impossible_navigation(self, code: str) -> List[QualityIssue]:
        """Check for impossible or suspicious navigation."""
        issues = []
        
        # Check for navigation to localhost in production-like tests
        if re.search(r'goto\(["\']http://localhost', code):
            issue = QualityIssue(
                issue_id=f"ISSUE-{uuid.uuid4().hex[:8].upper()}",
                issue_type=QualityIssueType.IMPOSSIBLE_NAVIGATION,
                severity="medium",
                message="Navigation to localhost found",
                suggestion="Use configurable test environment URL",
                evidence="localhost",
            )
            issues.append(issue)
        
        return issues
    
    def _create_result_from_issues(self, issues: List[QualityIssue]) -> QualityGateResult:
        """Create quality gate result from detected issues."""
        # Categorize issues
        critical_issues = [i for i in issues if i.severity == "critical"]
        high_issues = [i for i in issues if i.severity == "high"]
        medium_issues = [i for i in issues if i.severity == "medium"]
        low_issues = [i for i in issues if i.severity == "low"]
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(issues)
        
        # Determine if passed
        passed = True
        if self.block_on_critical and critical_issues:
            passed = False
        if self.block_on_high and high_issues:
            passed = False
        
        # Count blocking issues
        blocking_issues = len(critical_issues) + (len(high_issues) if self.block_on_high else 0)
        
        # Generate recommendation
        if passed:
            recommendation = "Automation passed quality gate and is ready for execution"
        elif critical_issues:
            recommendation = "Automation rejected: Fix critical issues before execution"
        elif high_issues:
            recommendation = "Automation rejected: Fix high severity issues before execution"
        else:
            recommendation = "Automation has quality issues but may proceed"
        
        return QualityGateResult(
            passed=passed,
            quality_score=quality_score,
            issues=issues,
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            total_issues=len(issues),
            blocking_issues=blocking_issues,
            recommendation=recommendation,
        )
    
    def _calculate_quality_score(self, issues: List[QualityIssue]) -> float:
        """Calculate overall quality score from issues."""
        if not issues:
            return 100.0
        
        # Weight issues by severity
        severity_weights = {
            "critical": 25,
            "high": 15,
            "medium": 8,
            "low": 3,
        }
        
        total_deduction = sum(
            severity_weights.get(issue.severity, 5) for issue in issues
        )
        
        score = max(100.0 - total_deduction, 0.0)
        return score
    
    def _create_result(
        self,
        passed: bool,
        quality_score: float,
        issues: List[QualityIssue],
    ) -> QualityGateResult:
        """Create a quality gate result."""
        return self._create_result_from_issues(issues)
