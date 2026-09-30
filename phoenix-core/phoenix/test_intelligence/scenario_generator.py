"""Test Scenario Generator - Universal AI Test Scenario Generation (Priority 23).

This module generates test scenarios for ANY web application using generic
patterns based on semantic understanding, component intelligence, and
business flow detection.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestScenario,
    TestScenarioType,
    TestPriority,
    TestRisk,
    TestGenerationRequest,
    TestGenerationResponse,
)
from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    PageType,
    BusinessIntentType,
    ValidationRule,
)
from phoenix.flow_detection.models import (
    BusinessFlow,
    FlowType,
    ActionType,
)

logger = logging.getLogger(__name__)


class TestScenarioGenerator:
    """Universal test scenario generator for ANY web application.
    
    This generator creates test scenarios based on:
    - Semantic page understanding
    - Component intelligence
    - Business flow detection
    - Validation rules
    - Generic test patterns
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the test scenario generator."""
        self.scenario_patterns = self._initialize_scenario_patterns()
        logger.info(f"[TEST SCENARIO GENERATOR] Initialized with {len(self.scenario_patterns)} patterns")
    
    def _initialize_scenario_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize generic test scenario patterns."""
        patterns = {}
        
        # Positive scenario patterns
        patterns["positive_happy_path"] = {
            "scenario_type": TestScenarioType.POSITIVE,
            "description": "Happy path - everything works correctly",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["positive_valid_data"] = {
            "scenario_type": TestScenarioType.POSITIVE,
            "description": "Test with valid data",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.15,
        }
        
        patterns["positive_successful_submission"] = {
            "scenario_type": TestScenarioType.POSITIVE,
            "description": "Successful form submission",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["positive_successful_navigation"] = {
            "scenario_type": TestScenarioType.NAVIGATION,
            "description": "Successful navigation between pages",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["positive_successful_search"] = {
            "scenario_type": TestScenarioType.SEARCH,
            "description": "Successful search operation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.15,
        }
        
        patterns["positive_crud_create"] = {
            "scenario_type": TestScenarioType.CRUD,
            "description": "Successful CRUD create operation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["positive_crud_read"] = {
            "scenario_type": TestScenarioType.CRUD,
            "description": "Successful CRUD read operation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.15,
        }
        
        patterns["positive_crud_update"] = {
            "scenario_type": TestScenarioType.CRUD,
            "description": "Successful CRUD update operation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["positive_crud_delete"] = {
            "scenario_type": TestScenarioType.CRUD,
            "description": "Successful CRUD delete operation",
            "priority": TestPriority.CRITICAL,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.2,
        }
        
        # Negative scenario patterns
        patterns["negative_invalid_data"] = {
            "scenario_type": TestScenarioType.NEGATIVE,
            "description": "Test with invalid data",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["negative_missing_required"] = {
            "scenario_type": TestScenarioType.NEGATIVE,
            "description": "Test with missing required fields",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["negative_invalid_format"] = {
            "scenario_type": TestScenarioType.NEGATIVE,
            "description": "Test with invalid format (email, phone, etc.)",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["negative_incorrect_credentials"] = {
            "scenario_type": TestScenarioType.AUTHENTICATION,
            "description": "Test with incorrect credentials",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["negative_invalid_search"] = {
            "scenario_type": TestScenarioType.SEARCH,
            "description": "Test with invalid search criteria",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["negative_failed_submission"] = {
            "scenario_type": TestScenarioType.NEGATIVE,
            "description": "Test failed form submission",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["negative_unauthorized_action"] = {
            "scenario_type": TestScenarioType.AUTHORIZATION,
            "description": "Test unauthorized action attempt",
            "priority": TestPriority.CRITICAL,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.2,
        }
        
        # Boundary scenario patterns
        patterns["boundary_minimum_value"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with minimum value",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_maximum_value"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with maximum value",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_minimum_length"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with minimum length",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_maximum_length"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with maximum length",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_empty_value"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with empty value",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_zero_value"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with zero value",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_large_value"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with large value",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["boundary_boundary_date"] = {
            "scenario_type": TestScenarioType.BOUNDARY,
            "description": "Test with boundary date values",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        # Validation scenario patterns
        patterns["validation_required_field"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test required field validation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["validation_format_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test format validation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["validation_length_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test length validation",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["validation_range_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test range validation",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.1,
        }
        
        patterns["validation_cross_field_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test cross-field validation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["validation_duplicate_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test duplicate validation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        patterns["validation_error_message"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test error message display",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["validation_inline_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test inline validation",
            "priority": TestPriority.MEDIUM,
            "risk": TestRisk.LOW,
            "confidence_boost": 0.1,
        }
        
        patterns["validation_form_level_validation"] = {
            "scenario_type": TestScenarioType.VALIDATION,
            "description": "Test form-level validation",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
        }
        
        # Security scenario patterns (only when evidence exists)
        patterns["security_authentication"] = {
            "scenario_type": TestScenarioType.SECURITY,
            "description": "Test authentication mechanism",
            "priority": TestPriority.CRITICAL,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.2,
            "requires_evidence": ["authentication_screen", "login_trigger", "password_input"],
        }
        
        patterns["security_authorization"] = {
            "scenario_type": TestScenarioType.SECURITY,
            "description": "Test authorization controls",
            "priority": TestPriority.CRITICAL,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.2,
            "requires_evidence": ["authorization", "access_control", "restricted"],
        }
        
        patterns["security_session_handling"] = {
            "scenario_type": TestScenarioType.SECURITY,
            "description": "Test session handling",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.15,
            "requires_evidence": ["session", "logout_trigger", "authentication"],
        }
        
        patterns["security_restricted_actions"] = {
            "scenario_type": TestScenarioType.SECURITY,
            "description": "Test restricted action access",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.2,
            "requires_evidence": ["restricted", "authorized", "permission"],
        }
        
        patterns["security_input_validation"] = {
            "scenario_type": TestScenarioType.SECURITY,
            "description": "Test input validation for security",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.MEDIUM,
            "confidence_boost": 0.15,
            "requires_evidence": ["validation", "sanitization", "escape"],
        }
        
        patterns["security_file_upload_restrictions"] = {
            "scenario_type": TestScenarioType.SECURITY,
            "description": "Test file upload restrictions",
            "priority": TestPriority.HIGH,
            "risk": TestRisk.HIGH,
            "confidence_boost": 0.2,
            "requires_evidence": ["file_upload", "upload", "attachment"],
        }
        
        return patterns
    
    def generate_scenarios(
        self,
        request: TestGenerationRequest,
        semantic_components: List[SemanticComponent] = None,
        business_flows: List[BusinessFlow] = None,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
    ) -> TestGenerationResponse:
        """Generate test scenarios based on the request and context.
        
        Args:
            request: Test generation request
            semantic_components: List of semantic components
            business_flows: List of business flows
            page_type: Current page type
            business_intent: Current business intent
            
        Returns:
            Test generation response with generated scenarios
        """
        semantic_components = semantic_components or []
        business_flows = business_flows or []
        
        start_time = datetime.now(timezone.utc)
        scenarios = []
        
        logger.info(f"[TEST SCENARIO GENERATOR] Starting scenario generation")
        logger.info(f"[TEST SCENARIO GENERATOR] Components: {len(semantic_components)}, Flows: {len(business_flows)}")
        
        # Generate scenarios based on context
        if business_flows:
            scenarios.extend(self._generate_flow_scenarios(
                business_flows,
                request,
                semantic_components,
            ))
        
        if semantic_components:
            scenarios.extend(self._generate_component_scenarios(
                semantic_components,
                request,
                page_type,
                business_intent,
            ))
        
        # Filter by requested scenario types
        if request.scenario_types:
            scenarios = [s for s in scenarios if s.scenario_type in request.scenario_types]
        
        # Limit by max scenarios
        if len(scenarios) > request.max_scenarios:
            scenarios = scenarios[:request.max_scenarios]
        
        # Calculate generation time
        generation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        # Create response
        response = TestGenerationResponse(
            request_id=request.request_id,
            scenarios=scenarios,
            total_generated=len(scenarios),
            generation_time_ms=generation_time,
        )
        
        logger.info(f"[TEST SCENARIO GENERATOR] Generated {len(scenarios)} scenarios in {generation_time:.2f}ms")
        
        return response
    
    def _generate_flow_scenarios(
        self,
        business_flows: List[BusinessFlow],
        request: TestGenerationRequest,
        components: List[SemanticComponent],
    ) -> List[TestScenario]:
        """Generate scenarios based on business flows."""
        scenarios = []
        
        for flow in business_flows:
            flow_scenarios = self._generate_scenarios_for_flow(flow, components, request)
            scenarios.extend(flow_scenarios)
        
        return scenarios
    
    def _generate_scenarios_for_flow(
        self,
        flow: BusinessFlow,
        components: List[SemanticComponent],
        request: TestGenerationRequest,
    ) -> List[TestScenario]:
        """Generate scenarios for a specific business flow."""
        scenarios = []
        
        # Generate scenarios based on flow type
        if flow.flow_type == FlowType.AUTHENTICATION:
            scenarios.extend(self._generate_authentication_scenarios(flow, components))
        elif flow.flow_type == FlowType.SEARCH_FLOW:
            scenarios.extend(self._generate_search_scenarios(flow, components))
        elif flow.flow_type in [FlowType.CRUD_CREATE, FlowType.CRUD_READ, 
                                FlowType.CRUD_UPDATE, FlowType.CRUD_DELETE]:
            scenarios.extend(self._generate_crud_scenarios(flow, components))
        elif flow.flow_type == FlowType.FILE_UPLOAD_FLOW:
            scenarios.extend(self._generate_upload_scenarios(flow, components))
        
        return scenarios
    
    def _generate_authentication_scenarios(
        self,
        flow: BusinessFlow,
        components: List[SemanticComponent],
    ) -> List[TestScenario]:
        """Generate authentication test scenarios."""
        scenarios = []
        
        # Find authentication components
        username_field = self._find_component_by_purpose(components, "username_input")
        password_field = self._find_component_by_purpose(components, "password_input")
        login_button = self._find_component_by_purpose(components, "login_trigger")
        
        if username_field and password_field and login_button:
            # Positive: Valid credentials
            scenarios.append(TestScenario(
                scenario_id=f"auth_valid_{flow.flow_id}",
                title="Verify user can login with valid credentials",
                scenario_type=TestScenarioType.POSITIVE,
                priority=TestPriority.CRITICAL,
                risk=TestRisk.HIGH,
                purpose="Verify successful authentication with valid credentials",
                business_intent="authentication",
                flow=flow.flow_name,
                preconditions=["User is on login page", "User has valid credentials"],
                steps=[
                    "Navigate to login page",
                    f"Enter valid username in {username_field.name or 'username field'}",
                    f"Enter valid password in {password_field.name or 'password field'}",
                    f"Click {login_button.text_content or 'login button'}",
                ],
                test_data={"username": "valid_user", "password": "valid_password"},
                expected_result="User is successfully logged in and redirected to dashboard",
                validation_rules=["User is authenticated", "Dashboard is displayed"],
                confidence=0.9,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [username_field.component_id, password_field.component_id, login_button.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.4,
                    "component_evidence": 0.4,
                    "pattern_evidence": 0.2,
                },
                related_flows=[flow.flow_id],
                related_components=[username_field.component_id, password_field.component_id, login_button.component_id],
            ))
            
            # Negative: Invalid credentials
            scenarios.append(TestScenario(
                scenario_id=f"auth_invalid_{flow.flow_id}",
                title="Verify login fails with invalid credentials",
                scenario_type=TestScenarioType.NEGATIVE,
                priority=TestPriority.HIGH,
                risk=TestRisk.MEDIUM,
                purpose="Verify authentication fails with invalid credentials",
                business_intent="authentication",
                flow=flow.flow_name,
                preconditions=["User is on login page"],
                steps=[
                    "Navigate to login page",
                    f"Enter invalid username in {username_field.name or 'username field'}",
                    f"Enter invalid password in {password_field.name or 'password field'}",
                    f"Click {login_button.text_content or 'login button'}",
                ],
                test_data={"username": "invalid_user", "password": "invalid_password"},
                expected_result="Login fails with appropriate error message",
                validation_rules=["Error message is displayed", "User remains on login page"],
                confidence=0.85,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [username_field.component_id, password_field.component_id, login_button.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.4,
                    "component_evidence": 0.4,
                    "pattern_evidence": 0.2,
                },
                related_flows=[flow.flow_id],
                related_components=[username_field.component_id, password_field.component_id, login_button.component_id],
            ))
            
            # Negative: Missing credentials
            scenarios.append(TestScenario(
                scenario_id=f"auth_missing_{flow.flow_id}",
                title="Verify login fails with missing credentials",
                scenario_type=TestScenarioType.VALIDATION,
                priority=TestPriority.HIGH,
                risk=TestRisk.MEDIUM,
                purpose="Verify authentication fails when credentials are missing",
                business_intent="authentication",
                flow=flow.flow_name,
                preconditions=["User is on login page"],
                steps=[
                    "Navigate to login page",
                    "Leave username field empty",
                    "Leave password field empty",
                    f"Click {login_button.text_content or 'login button'}",
                ],
                test_data={"username": "", "password": ""},
                expected_result="Login fails with validation error",
                validation_rules=["Required field validation triggered", "Error message displayed"],
                confidence=0.8,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [username_field.component_id, password_field.component_id, login_button.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.3,
                    "component_evidence": 0.3,
                    "pattern_evidence": 0.4,
                },
                related_flows=[flow.flow_id],
                related_components=[username_field.component_id, password_field.component_id, login_button.component_id],
            ))
        
        return scenarios
    
    def _generate_search_scenarios(
        self,
        flow: BusinessFlow,
        components: List[SemanticComponent],
    ) -> List[TestScenario]:
        """Generate search test scenarios."""
        scenarios = []
        
        # Find search components
        search_input = self._find_component_by_purpose(components, "search_input")
        search_button = self._find_component_by_purpose(components, "search_trigger")
        
        if search_input:
            # Positive: Valid search
            scenarios.append(TestScenario(
                scenario_id=f"search_valid_{flow.flow_id}",
                title="Verify search returns results for valid query",
                scenario_type=TestScenarioType.SEARCH,
                priority=TestPriority.HIGH,
                risk=TestRisk.LOW,
                purpose="Verify search functionality with valid query",
                business_intent="search",
                flow=flow.flow_name,
                preconditions=["User is on search page", "Searchable data exists"],
                steps=[
                    "Navigate to search page",
                    f"Enter valid search term in {search_input.name or 'search field'}",
                    "Submit search",
                ],
                test_data={"search_term": "valid_query"},
                expected_result="Search results are displayed",
                validation_rules=["Results are displayed", "Results match search criteria"],
                confidence=0.85,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [search_input.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.4,
                    "component_evidence": 0.4,
                    "pattern_evidence": 0.2,
                },
                related_flows=[flow.flow_id],
                related_components=[search_input.component_id],
            ))
            
            # Negative: Empty search
            scenarios.append(TestScenario(
                scenario_id=f"search_empty_{flow.flow_id}",
                title="Verify search behavior with empty query",
                scenario_type=TestScenarioType.BOUNDARY,
                priority=TestPriority.MEDIUM,
                risk=TestRisk.LOW,
                purpose="Verify search behavior when query is empty",
                business_intent="search",
                flow=flow.flow_name,
                preconditions=["User is on search page"],
                steps=[
                    "Navigate to search page",
                    "Leave search field empty",
                    "Submit search",
                ],
                test_data={"search_term": ""},
                expected_result="Appropriate behavior (no results or all results)",
                validation_rules=["System handles empty query gracefully"],
                confidence=0.75,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [search_input.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.3,
                    "component_evidence": 0.3,
                    "pattern_evidence": 0.4,
                },
                related_flows=[flow.flow_id],
                related_components=[search_input.component_id],
            ))
        
        return scenarios
    
    def _generate_crud_scenarios(
        self,
        flow: BusinessFlow,
        components: List[SemanticComponent],
    ) -> List[TestScenario]:
        """Generate CRUD test scenarios."""
        scenarios = []
        
        # Find CRUD components
        create_button = self._find_component_by_purpose(components, "create_trigger")
        edit_button = self._find_component_by_purpose(components, "edit_trigger")
        delete_button = self._find_component_by_purpose(components, "delete_trigger")
        submit_button = self._find_component_by_purpose(components, "form_submit")
        
        if flow.flow_type == FlowType.CRUD_CREATE:
            if create_button and submit_button:
                scenarios.append(TestScenario(
                    scenario_id=f"crud_create_valid_{flow.flow_id}",
                    title="Verify successful record creation",
                    scenario_type=TestScenarioType.CRUD,
                    priority=TestPriority.HIGH,
                    risk=TestRisk.MEDIUM,
                    purpose="Verify successful creation of new record",
                    business_intent="data_entry",
                    flow=flow.flow_name,
                    preconditions=["User has create permissions", "User is on create page"],
                    steps=[
                        "Navigate to create page",
                        "Fill in all required fields with valid data",
                        f"Click {submit_button.text_content or 'submit button'}",
                    ],
                    test_data={"field_values": "valid_data"},
                    expected_result="Record is created successfully",
                    validation_rules=["Record appears in list", "Success message displayed"],
                    confidence=0.85,
                    source_evidence={
                        "flow": flow.flow_id,
                        "components": [create_button.component_id, submit_button.component_id],
                    },
                    confidence_breakdown={
                        "flow_evidence": 0.4,
                        "component_evidence": 0.4,
                        "pattern_evidence": 0.2,
                    },
                    related_flows=[flow.flow_id],
                    related_components=[create_button.component_id, submit_button.component_id],
                ))
        
        if flow.flow_type == FlowType.CRUD_DELETE:
            if delete_button:
                scenarios.append(TestScenario(
                    scenario_id=f"crud_delete_{flow.flow_id}",
                    title="Verify successful record deletion",
                    scenario_type=TestScenarioType.CRUD,
                    priority=TestPriority.CRITICAL,
                    risk=TestRisk.HIGH,
                    purpose="Verify successful deletion of record",
                    business_intent="data_deletion",
                    flow=flow.flow_name,
                    preconditions=["User has delete permissions", "Record exists"],
                    steps=[
                        "Navigate to record list",
                        "Select record to delete",
                        f"Click {delete_button.text_content or 'delete button'}",
                        "Confirm deletion",
                    ],
                    test_data={},
                    expected_result="Record is deleted successfully",
                    validation_rules=["Record no longer appears in list", "Success message displayed"],
                    confidence=0.85,
                    source_evidence={
                        "flow": flow.flow_id,
                        "components": [delete_button.component_id],
                    },
                    confidence_breakdown={
                        "flow_evidence": 0.4,
                        "component_evidence": 0.4,
                        "pattern_evidence": 0.2,
                    },
                    related_flows=[flow.flow_id],
                    related_components=[delete_button.component_id],
                ))
        
        return scenarios
    
    def _generate_upload_scenarios(
        self,
        flow: BusinessFlow,
        components: List[SemanticComponent],
    ) -> List[TestScenario]:
        """Generate file upload test scenarios."""
        scenarios = []
        
        # Find upload components
        upload_component = self._find_component_by_type(components, ComponentType.FILE_UPLOAD)
        
        if upload_component:
            # Positive: Valid file upload
            scenarios.append(TestScenario(
                scenario_id=f"upload_valid_{flow.flow_id}",
                title="Verify successful file upload",
                scenario_type=TestScenarioType.UPLOAD,
                priority=TestPriority.HIGH,
                risk=TestRisk.MEDIUM,
                purpose="Verify successful file upload",
                business_intent="file_management",
                flow=flow.flow_name,
                preconditions=["User has upload permissions", "Valid file exists"],
                steps=[
                    "Navigate to upload page",
                    "Select valid file",
                    "Submit upload",
                ],
                test_data={"file": "valid_file.pdf"},
                expected_result="File is uploaded successfully",
                validation_rules=["File appears in list", "Success message displayed"],
                confidence=0.8,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [upload_component.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.4,
                    "component_evidence": 0.4,
                    "pattern_evidence": 0.2,
                },
                related_flows=[flow.flow_id],
                related_components=[upload_component.component_id],
            ))
            
            # Negative: Invalid file type
            scenarios.append(TestScenario(
                scenario_id=f"upload_invalid_{flow.flow_id}",
                title="Verify upload fails with invalid file type",
                scenario_type=TestScenarioType.VALIDATION,
                priority=TestPriority.HIGH,
                risk=TestRisk.MEDIUM,
                purpose="Verify upload validation for file types",
                business_intent="file_management",
                flow=flow.flow_name,
                preconditions=["User is on upload page"],
                steps=[
                    "Navigate to upload page",
                    "Select invalid file type",
                    "Submit upload",
                ],
                test_data={"file": "invalid_file.exe"},
                expected_result="Upload fails with validation error",
                validation_rules=["Error message displayed", "File not uploaded"],
                confidence=0.75,
                source_evidence={
                    "flow": flow.flow_id,
                    "components": [upload_component.component_id],
                },
                confidence_breakdown={
                    "flow_evidence": 0.3,
                    "component_evidence": 0.3,
                    "pattern_evidence": 0.4,
                },
                related_flows=[flow.flow_id],
                related_components=[upload_component.component_id],
            ))
        
        return scenarios
    
    def _generate_component_scenarios(
        self,
        components: List[SemanticComponent],
        request: TestGenerationRequest,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
    ) -> List[TestScenario]:
        """Generate scenarios based on components."""
        scenarios = []
        
        for component in components:
            component_scenarios = self._generate_scenarios_for_component(
                component,
                request,
                page_type,
                business_intent,
            )
            scenarios.extend(component_scenarios)
        
        return scenarios
    
    def _generate_scenarios_for_component(
        self,
        component: SemanticComponent,
        request: TestGenerationRequest,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
    ) -> List[TestScenario]:
        """Generate scenarios for a specific component."""
        scenarios = []
        
        # Generate validation scenarios based on component validation rules
        if component.validation_rules:
            scenarios.extend(self._generate_validation_scenarios_for_component(
                component,
                page_type,
                business_intent,
            ))
        
        # Generate boundary scenarios for input components
        if component.component_type in [ComponentType.TEXT_FIELD, ComponentType.DROPDOWN]:
            scenarios.extend(self._generate_boundary_scenarios_for_component(
                component,
                page_type,
                business_intent,
            ))
        
        return scenarios
    
    def _generate_validation_scenarios_for_component(
        self,
        component: SemanticComponent,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
    ) -> List[TestScenario]:
        """Generate validation scenarios for a component."""
        scenarios = []
        
        for rule in component.validation_rules:
            rule_type = rule.get("validation_type", "")
            
            if rule_type == "required":
                scenarios.append(TestScenario(
                    scenario_id=f"val_required_{component.component_id}",
                    title=f"Verify required field validation for {component.name or component.component_id}",
                    scenario_type=TestScenarioType.VALIDATION,
                    priority=TestPriority.HIGH,
                    risk=TestRisk.MEDIUM,
                    purpose=f"Verify required field validation for {component.name or 'field'}",
                    business_intent=business_intent.value if business_intent else "",
                    steps=[
                        f"Navigate to form containing {component.name or 'field'}",
                        f"Leave {component.name or 'field'} empty",
                        "Submit form",
                    ],
                    test_data={component.name or "field": ""},
                    expected_result="Validation error is displayed",
                    validation_rules=["Required field validation triggered"],
                    confidence=0.85,
                    source_evidence={
                        "component": component.component_id,
                        "validation_rule": rule,
                    },
                    confidence_breakdown={
                        "component_evidence": 0.5,
                        "validation_evidence": 0.5,
                    },
                    related_components=[component.component_id],
                ))
            
            elif rule_type == "email_format":
                scenarios.append(TestScenario(
                    scenario_id=f"val_email_{component.component_id}",
                    title=f"Verify email format validation for {component.name or component.component_id}",
                    scenario_type=TestScenarioType.VALIDATION,
                    priority=TestPriority.HIGH,
                    risk=TestRisk.MEDIUM,
                    purpose=f"Verify email format validation for {component.name or 'field'}",
                    business_intent=business_intent.value if business_intent else "",
                    steps=[
                        f"Navigate to form containing {component.name or 'field'}",
                        f"Enter invalid email in {component.name or 'field'}",
                        "Submit form",
                    ],
                    test_data={component.name or "field": "invalid_email"},
                    expected_result="Email format validation error is displayed",
                    validation_rules=["Email format validation triggered"],
                    confidence=0.9,
                    source_evidence={
                        "component": component.component_id,
                        "validation_rule": rule,
                    },
                    confidence_breakdown={
                        "component_evidence": 0.5,
                        "validation_evidence": 0.5,
                    },
                    related_components=[component.component_id],
                ))
        
        return scenarios
    
    def _generate_boundary_scenarios_for_component(
        self,
        component: SemanticComponent,
        page_type: PageType = None,
        business_intent: BusinessIntentType = None,
    ) -> List[TestScenario]:
        """Generate boundary scenarios for a component."""
        scenarios = []
        
        # Check for length validation
        for rule in component.validation_rules:
            rule_type = rule.get("validation_type", "")
            rule_value = rule.get("rule_value")
            
            if rule_type == "min_length" and rule_value:
                scenarios.append(TestScenario(
                    scenario_id=f"bound_minlen_{component.component_id}",
                    title=f"Verify minimum length boundary for {component.name or component.component_id}",
                    scenario_type=TestScenarioType.BOUNDARY,
                    priority=TestPriority.MEDIUM,
                    risk=TestRisk.MEDIUM,
                    purpose=f"Verify minimum length boundary for {component.name or 'field'}",
                    business_intent=business_intent.value if business_intent else "",
                    steps=[
                        f"Navigate to form containing {component.name or 'field'}",
                        f"Enter text with length exactly {rule_value} in {component.name or 'field'}",
                        "Submit form",
                    ],
                    test_data={component.name or "field": "a" * int(rule_value)},
                    expected_result="Form is accepted (at minimum boundary)",
                    validation_rules=["Minimum length boundary accepted"],
                    confidence=0.8,
                    source_evidence={
                        "component": component.component_id,
                        "validation_rule": rule,
                    },
                    confidence_breakdown={
                        "component_evidence": 0.5,
                        "validation_evidence": 0.5,
                    },
                    related_components=[component.component_id],
                ))
            
            elif rule_type == "max_length" and rule_value:
                scenarios.append(TestScenario(
                    scenario_id=f"bound_maxlen_{component.component_id}",
                    title=f"Verify maximum length boundary for {component.name or component.component_id}",
                    scenario_type=TestScenarioType.BOUNDARY,
                    priority=TestPriority.MEDIUM,
                    risk=TestRisk.MEDIUM,
                    purpose=f"Verify maximum length boundary for {component.name or 'field'}",
                    business_intent=business_intent.value if business_intent else "",
                    steps=[
                        f"Navigate to form containing {component.name or 'field'}",
                        f"Enter text with length exactly {rule_value} in {component.name or 'field'}",
                        "Submit form",
                    ],
                    test_data={component.name or "field": "a" * int(rule_value)},
                    expected_result="Form is accepted (at maximum boundary)",
                    validation_rules=["Maximum length boundary accepted"],
                    confidence=0.8,
                    source_evidence={
                        "component": component.component_id,
                        "validation_rule": rule,
                    },
                    confidence_breakdown={
                        "component_evidence": 0.5,
                        "validation_evidence": 0.5,
                    },
                    related_components=[component.component_id],
                ))
        
        return scenarios
    
    def _find_component_by_purpose(
        self,
        components: List[SemanticComponent],
        purpose: str,
    ) -> Optional[SemanticComponent]:
        """Find a component by its semantic purpose."""
        for component in components:
            if component.semantic_purpose == purpose:
                return component
        return None
    
    def _find_component_by_type(
        self,
        components: List[SemanticComponent],
        component_type: ComponentType,
    ) -> Optional[SemanticComponent]:
        """Find a component by its type."""
        for component in components:
            if component.component_type == component_type:
                return component
        return None
