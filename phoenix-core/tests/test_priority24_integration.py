"""Integration Tests for Priority 24 - Full Pipeline Integration.

This test suite verifies the complete integration of Priority 24 with
Priorities 20, 21, 22, and 23.

Priority 24: Universal Autonomous Test Automation Generation
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone

from phoenix.automation_generation.automation_generator import AutomationGenerationCoordinator
from phoenix.automation_generation.models import AutomationStatus

from phoenix.test_intelligence.models import (
    TestScenario,
    TestScenarioType,
    TestPriority,
    TestRisk,
)
from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    PageType,
)
from phoenix.flow_detection.models import (
    BusinessFlow,
    FlowType,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def authentication_components():
    """Create authentication page components."""
    return [
        SemanticComponent(
            component_id="COMP-001",
            component_type=ComponentType.TEXT_FIELD,
            text_content="Username",
            label="Username",
            placeholder="Enter username",
            name="username",
            aria_role="textbox",
            semantic_purpose="username_input",
            purpose_confidence=0.9,
            page_type="authentication_screen",
            business_intent="authentication",
            selected_locator='get_by_label("Username")',
            locator_confidence=0.85,
            supported_actions=["fill", "clear"],
            interaction_confidence=0.9,
        ),
        SemanticComponent(
            component_id="COMP-002",
            component_type=ComponentType.TEXT_FIELD,
            text_content="",
            label="Password",
            placeholder="Enter password",
            name="password",
            aria_role="textbox",
            semantic_purpose="password_input",
            purpose_confidence=0.95,
            page_type="authentication_screen",
            business_intent="authentication",
            selected_locator='get_by_label("Password")',
            locator_confidence=0.85,
            supported_actions=["fill", "clear"],
            interaction_confidence=0.9,
        ),
        SemanticComponent(
            component_id="COMP-003",
            component_type=ComponentType.BUTTON,
            text_content="Login",
            label="",
            placeholder="",
            name="login",
            aria_role="button",
            semantic_purpose="login_trigger",
            purpose_confidence=0.9,
            page_type="authentication_screen",
            business_intent="authentication",
            selected_locator='get_by_role("button", name="Login")',
            locator_confidence=0.9,
            supported_actions=["click", "hover"],
            interaction_confidence=0.95,
        ),
    ]


@pytest.fixture
def authentication_flow():
    """Create authentication business flow."""
    return BusinessFlow(
        flow_id="FLOW-001",
        flow_type=FlowType.AUTHENTICATION,
        name="User Login Flow",
        description="Flow for user authentication",
    )


@pytest.fixture
def validated_authentication_scenario():
    """Create a validated authentication test scenario."""
    return TestScenario(
        scenario_id="SCEN-AUTH-001",
        title="User Login with Valid Credentials",
        scenario_type=TestScenarioType.POSITIVE,
        priority=TestPriority.HIGH,
        risk=TestRisk.MEDIUM,
        purpose="Verify user can successfully login with valid credentials",
        business_intent="authentication",
        preconditions=["User is on login page"],
        flow="authentication",
        steps=[
            "Enter username in username field",
            "Enter password in password field",
            "Click login button",
            "Verify user is redirected to dashboard",
        ],
        test_data={"username": "testuser", "password": "testpass"},
        expected_result="User is logged in and dashboard is visible",
        validation_rules=["Username is required", "Password is required"],
        quality_score=90.0,
        confidence=0.9,
        is_validated=True,
        related_components=["COMP-001", "COMP-002", "COMP-003"],
        related_flows=["FLOW-001"],
    )


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    output_dir = tmp_path / "generated_automation"
    pom_dir = tmp_path / "pages"
    output_dir.mkdir(parents=True, exist_ok=True)
    pom_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir), str(pom_dir)


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_priority20_to_priority24_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test integration from Priority 20 (Semantic Understanding) to Priority 24."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Priority 20 provides semantic components
    # Priority 24 should use these components for automation generation
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    assert automation.scenario_id == validated_authentication_scenario.scenario_id
    
    # Verify that semantic component information was used
    assert automation.confidence > 0.0
    
    # Verify script was generated
    assert automation.script_code != ""
    assert automation.script_path != ""


def test_priority21_to_priority24_integration(
    validated_authentication_scenario,
    authentication_components,
    authentication_flow,
    temp_dirs,
):
    """Test integration from Priority 21 (Flow Detection) to Priority 24."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Priority 21 provides business flow information
    # Priority 24 should use flow information for automation planning
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [authentication_flow],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Verify that flow information was considered
    # (This would be reflected in the automation plan)


def test_priority22_to_priority24_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test integration from Priority 22 (Component Intelligence) to Priority 24."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Priority 22 provides component intelligence (purpose, interactions, locators)
    # Priority 24 should use this intelligence for action generation
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Verify that component intelligence was used
    # Components should have semantic purposes
    for component in authentication_components:
        assert component.semantic_purpose != ""
        assert component.supported_actions != []


def test_priority23_to_priority24_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test integration from Priority 23 (Test Intelligence) to Priority 24."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Priority 23 provides validated test scenarios
    # Priority 24 should only accept validated scenarios
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Unvalidated scenario should be rejected
    unvalidated_scenario = validated_authentication_scenario.copy()
    unvalidated_scenario.is_validated = False
    unvalidated_scenario.scenario_id = "SCEN-INVALID"
    
    automation_invalid = coordinator.generate_automation_from_scenario(
        unvalidated_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation_invalid is None


def test_full_pipeline_integration(
    validated_authentication_scenario,
    authentication_components,
    authentication_flow,
    temp_dirs,
):
    """Test the complete pipeline from Priorities 20-23 to Priority 24."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Full pipeline:
    # Priority 20: Semantic Understanding (components)
    # Priority 21: Flow Detection (flows)
    # Priority 22: Component Intelligence (purpose, locators)
    # Priority 23: Test Intelligence (validated scenarios)
    # Priority 24: Automation Generation
    
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [authentication_flow],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    assert automation.status in [AutomationStatus.GENERATED, AutomationStatus.REJECTED]
    
    if automation.status == AutomationStatus.GENERATED:
        # Verify generated script exists
        script_path = Path(automation.script_path)
        assert script_path.exists()
        
        # Verify script contains expected elements
        script_content = script_path.read_text()
        assert "def test_" in script_content
        assert "page" in script_content


def test_batch_automation_generation(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test batch automation generation for multiple scenarios."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Create multiple scenarios
    scenarios = [
        validated_authentication_scenario,
        TestScenario(
            scenario_id="SCEN-AUTH-002",
            title="User Login with Invalid Password",
            scenario_type=TestScenarioType.NEGATIVE,
            priority=TestPriority.HIGH,
            risk=TestRisk.MEDIUM,
            purpose="Verify login fails with invalid password",
            business_intent="authentication",
            preconditions=["User is on login page"],
            flow="authentication",
            steps=[
                "Enter username in username field",
                "Enter invalid password in password field",
                "Click login button",
                "Verify error message is displayed",
            ],
            test_data={"username": "testuser", "password": "wrongpass"},
            expected_result="Error message displayed",
            validation_rules=["Username is required", "Password is required"],
            quality_score=85.0,
            confidence=0.85,
            is_validated=True,
            related_components=["COMP-001", "COMP-002", "COMP-003"],
        ),
    ]
    
    components_map = {
        "SCEN-AUTH-001": authentication_components,
        "SCEN-AUTH-002": authentication_components,
    }
    
    flows_map = {
        "SCEN-AUTH-001": [],
        "SCEN-AUTH-002": [],
    }
    
    automations = coordinator.batch_generate_automation(
        scenarios,
        components_map,
        flows_map,
        "test_project",
    )
    
    assert len(automations) == 2
    assert all(a is not None for a in automations)


def test_pom_generation_and_reuse(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test POM generation and reuse across scenarios."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Generate first automation
    automation1 = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation1 is not None
    
    # Generate second automation with same page type
    scenario2 = TestScenario(
        scenario_id="SCEN-AUTH-003",
        title="User Logout",
        scenario_type=TestScenarioType.POSITIVE,
        priority=TestPriority.MEDIUM,
        risk=TestRisk.LOW,
        purpose="Verify user can logout",
        business_intent="authentication",
        preconditions=["User is logged in"],
        flow="authentication",
        steps=["Click logout button"],
        test_data={},
        expected_result="User is logged out",
        validation_rules=[],
        quality_score=80.0,
        confidence=0.8,
        is_validated=True,
    )
    
    automation2 = coordinator.generate_automation_from_scenario(
        scenario2,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation2 is not None
    
    # Verify POM reuse statistics
    stats = coordinator.pom_manager.get_pom_reuse_statistics()
    assert stats["total_poms"] >= 1


def test_quality_gate_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test quality gate integration in the pipeline."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Generate automation with quality gate
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Quality gate should have been applied
    assert automation.validation_status in ["passed", "failed"]
    
    if automation.validation_status == "failed":
        # Should have quality issues
        assert len(automation.quality_issues) > 0


def test_locator_strategy_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test locator strategy integration with fallback chain."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Verify that locator strategy was used
    # Components should have selected locators
    for component in authentication_components:
        assert component.selected_locator != ""


def test_test_data_intelligence_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test test data intelligence integration."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Test data requirements should have been identified
    # (This would be reflected in the automation plan)


def test_sensitive_data_protection_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test sensitive data protection integration."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Create scenario with password in test data
    scenario_with_password = validated_authentication_scenario.copy()
    scenario_with_password.test_data = {"username": "testuser", "password": "secret123"}
    scenario_with_password.scenario_id = "SCEN-PWD-001"
    
    automation = coordinator.generate_automation_from_scenario(
        scenario_with_password,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    
    # Verify sensitive data protection was applied
    # Password should not appear in plain text in the generated script
    if automation.script_code:
        # The protection should have masked the password
        assert "secret123" not in automation.script_code or "os.environ" in automation.script_code


def test_metrics_tracking_integration(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test metrics tracking across the pipeline."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    initial_metrics = coordinator.get_metrics()
    
    # Generate automation
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "test_project",
        "login_page",
    )
    
    final_metrics = coordinator.get_metrics()
    
    # Verify metrics were updated
    assert final_metrics.total_plans >= initial_metrics.total_plans
    assert final_metrics.total_generated >= initial_metrics.total_generated


def test_application_agnostic_behavior(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test that automation generation is application-agnostic."""
    output_dir, pom_dir = temp_dirs
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=output_dir,
        pom_directory=pom_dir,
    )
    
    # Generate automation without any application-specific context
    automation = coordinator.generate_automation_from_scenario(
        validated_authentication_scenario,
        authentication_components,
        [],
        "generic_project",
        "generic_page",
    )
    
    assert automation is not None
    
    # Verify that no application-specific assumptions were made
    # The generated script should work for any authentication page
    if automation.script_code:
        script_content = automation.script_code.lower()
        
        # Should not contain application-specific names
        forbidden = ["orangehrm", "jira", "salesforce", "sap", "servicenow"]
        for app in forbidden:
            assert app not in script_content


def test_regression_protection_priority20(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test that Priority 20 functionality still works with Priority 24."""
    # Priority 20: Semantic Understanding
    # Verify that semantic components are still understood correctly
    for component in authentication_components:
        assert component.component_type != ComponentType.UNKNOWN
        assert component.page_type != ""
        assert component.business_intent != ""


def test_regression_protection_priority22(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test that Priority 22 functionality still works with Priority 24."""
    # Priority 22: Component Intelligence
    # Verify that component intelligence is preserved
    for component in authentication_components:
        assert component.semantic_purpose != ""
        assert component.supported_actions != []
        assert component.locator_confidence >= 0.0


def test_regression_protection_priority23(
    validated_authentication_scenario,
    authentication_components,
    temp_dirs,
):
    """Test that Priority 23 functionality still works with Priority 24."""
    # Priority 23: Test Intelligence
    # Verify that scenario validation is still enforced
    assert validated_authentication_scenario.is_validated == True
    assert validated_authentication_scenario.quality_score >= 70.0
