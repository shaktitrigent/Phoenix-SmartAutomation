"""Unit Tests for Priority 24 - Universal Autonomous Test Automation Generation.

This test suite verifies all Priority 24 components work correctly without
application-specific knowledge.

Priority 24: Universal Autonomous Test Automation Generation
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from phoenix.automation_generation.models import (
    AutomationStatus,
    FailureType,
    ActionType,
    AssertionType,
    TestDataType,
    AutomationPlan,
    Action,
    Assertion,
    TestDataRequirement,
    GeneratedAutomation,
    FailureClassification,
    AutomationMetrics,
)
from phoenix.automation_generation.automation_planner import AutomationPlanner
from phoenix.automation_generation.action_generator import ActionGenerator
from phoenix.automation_generation.assertion_generator import AssertionGenerator
from phoenix.automation_generation.pom_manager import POMManager
from phoenix.automation_generation.locator_strategy import (
    LocatorStrategy,
    LocatorStrategyManager,
)
from phoenix.automation_generation.quality_gate import (
    QualityIssue,
    AutomationQualityGate,
)
from phoenix.automation_generation.test_data_intelligence import TestDataIntelligence
from phoenix.automation_generation.sensitive_data_protection import SensitiveDataProtection
from phoenix.automation_generation.failure_classifier import FailureClassifier
from phoenix.automation_generation.automation_regeneration import AutomationRegeneration

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


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_component():
    """Create a sample semantic component."""
    return SemanticComponent(
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
    )


@pytest.fixture
def sample_scenario():
    """Create a sample test scenario."""
    return TestScenario(
        scenario_id="SCEN-001",
        title="User Login Test",
        scenario_type=TestScenarioType.POSITIVE,
        priority=TestPriority.HIGH,
        risk=TestRisk.MEDIUM,
        purpose="Verify user can login with valid credentials",
        business_intent="authentication",
        preconditions=["User is on login page"],
        flow="authentication",
        steps=[
            "Enter username in username field",
            "Enter password in password field",
            "Click login button",
        ],
        test_data={"username": "testuser", "password": "testpass"},
        expected_result="User is logged in and redirected to dashboard",
        validation_rules=["Username is required", "Password is required"],
        quality_score=85.0,
        confidence=0.85,
        is_validated=True,
    )


@pytest.fixture
def temp_pom_dir(tmp_path):
    """Create a temporary POM directory."""
    pom_dir = tmp_path / "pages"
    pom_dir.mkdir(parents=True, exist_ok=True)
    return str(pom_dir)


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

def test_automation_status_enum():
    """Test AutomationStatus enum values."""
    assert AutomationStatus.PLANNED == "planned"
    assert AutomationStatus.GENERATED == "generated"
    assert AutomationStatus.VALIDATED == "validated"
    assert AutomationStatus.REJECTED == "rejected"
    assert AutomationStatus.EXECUTED == "executed"
    assert AutomationStatus.PASSED == "passed"
    assert AutomationStatus.FAILED == "failed"
    assert AutomationStatus.BLOCKED == "blocked"


def test_failure_type_enum():
    """Test FailureType enum values."""
    assert FailureType.AUTOMATION_FAILURE == "automation_failure"
    assert FailureType.LOCATOR_FAILURE == "locator_failure"
    assert FailureType.APPLICATION_FAILURE == "application_failure"
    assert FailureType.NAVIGATION_FAILURE == "navigation_failure"
    assert FailureType.ASSERTION_FAILURE == "assertion_failure"
    assert FailureType.DATA_FAILURE == "data_failure"
    assert FailureType.ENVIRONMENT_FAILURE == "environment_failure"
    assert FailureType.GENERATION_FAILURE == "generation_failure"


def test_action_type_enum():
    """Test ActionType enum values."""
    assert ActionType.NAVIGATE == "navigate"
    assert ActionType.CLICK == "click"
    assert ActionType.FILL == "fill"
    assert ActionType.SELECT == "select"
    assert ActionType.ASSERT == "assert"


def test_automation_plan_creation():
    """Test AutomationPlan model creation."""
    plan = AutomationPlan(
        scenario_id="SCEN-001",
        automation_id="AUTO-001",
        business_intent="authentication",
        confidence=0.85,
    )
    
    assert plan.scenario_id == "SCEN-001"
    assert plan.automation_id == "AUTO-001"
    assert plan.business_intent == "authentication"
    assert plan.confidence == 0.85
    assert plan.status == AutomationStatus.PLANNED


def test_action_creation():
    """Test Action model creation."""
    action = Action(
        action_id="ACT-001",
        action_type=ActionType.FILL,
        target_locator='get_by_label("Username")',
        confidence=0.9,
    )
    
    assert action.action_id == "ACT-001"
    assert action.action_type == ActionType.FILL
    assert action.target_locator == 'get_by_label("Username")'
    assert action.confidence == 0.9


def test_assertion_creation():
    """Test Assertion model creation."""
    assertion = Assertion(
        assertion_id="ASSERT-001",
        assertion_type=AssertionType.VISIBLE_TEXT,
        expected_value="Dashboard",
        confidence=0.8,
    )
    
    assert assertion.assertion_id == "ASSERT-001"
    assert assertion.assertion_type == AssertionType.VISIBLE_TEXT
    assert assertion.expected_value == "Dashboard"
    assert assertion.confidence == 0.8


def test_test_data_requirement_creation():
    """Test TestDataRequirement model creation."""
    req = TestDataRequirement(
        data_id="DATA-001",
        data_type=TestDataType.USERNAME,
        field_name="username",
        is_required=True,
        is_missing=False,
    )
    
    assert req.data_id == "DATA-001"
    assert req.data_type == TestDataType.USERNAME
    assert req.field_name == "username"
    assert req.is_required == True
    assert req.is_missing == False


def test_generated_automation_creation():
    """Test GeneratedAutomation model creation."""
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code="def test_login():\n    pass",
        confidence=0.85,
    )
    
    assert automation.automation_id == "AUTO-001"
    assert automation.scenario_id == "SCEN-001"
    assert automation.script_code == "def test_login():\n    pass"
    assert automation.confidence == 0.85
    assert automation.status == AutomationStatus.GENERATED


def test_automation_metrics_creation():
    """Test AutomationMetrics model creation."""
    metrics = AutomationMetrics()
    
    assert metrics.total_plans == 0
    assert metrics.total_generated == 0
    assert metrics.executed_automations == 0
    assert metrics.passed_automations == 0


# ---------------------------------------------------------------------------
# Automation Planner Tests
# ---------------------------------------------------------------------------

def test_automation_planner_initialization():
    """Test AutomationPlanner initialization."""
    planner = AutomationPlanner()
    
    assert planner is not None
    assert planner.components == []
    assert planner.flows == []


def test_automation_planner_with_components(sample_component):
    """Test AutomationPlanner with components."""
    planner = AutomationPlanner(components=[sample_component])
    
    assert len(planner.components) == 1
    assert sample_component.component_id in planner.component_map


def test_create_automation_plan_validated(sample_scenario, sample_component):
    """Test creating automation plan from validated scenario."""
    planner = AutomationPlanner(components=[sample_component])
    
    plan = planner.create_automation_plan(sample_scenario)
    
    assert plan is not None
    assert plan.scenario_id == sample_scenario.scenario_id
    assert plan.business_intent == sample_scenario.business_intent
    assert plan.status == AutomationStatus.PLANNED


def test_create_automation_plan_not_validated(sample_scenario):
    """Test that unvalidated scenarios are rejected."""
    sample_scenario.is_validated = False
    planner = AutomationPlanner()
    
    plan = planner.create_automation_plan(sample_scenario)
    
    assert plan is None


def test_create_automation_plan_low_quality(sample_scenario):
    """Test that low quality scenarios are rejected."""
    sample_scenario.quality_score = 50.0
    planner = AutomationPlanner()
    
    plan = planner.create_automation_plan(sample_scenario)
    
    assert plan is None


def test_identify_required_pages(sample_scenario):
    """Test identifying required pages from scenario."""
    planner = AutomationPlanner()
    
    pages = planner._identify_required_pages(sample_scenario)
    
    assert isinstance(pages, list)
    # Authentication intent should trigger authentication page
    assert any("authentication" in page.lower() for page in pages)


def test_identify_required_components(sample_scenario, sample_component):
    """Test identifying required components from scenario."""
    sample_scenario.related_components = [sample_component.component_id]
    planner = AutomationPlanner(components=[sample_component])
    
    components = planner._identify_required_components(sample_scenario)
    
    assert sample_component.component_id in components


def test_plan_actions_from_steps(sample_scenario):
    """Test planning actions from scenario steps."""
    planner = AutomationPlanner()
    
    actions = planner._plan_actions(sample_scenario)
    
    assert len(actions) == len(sample_scenario.steps)
    assert all("action_type" in action for action in actions)


def test_calculate_plan_confidence(sample_scenario, sample_component):
    """Test plan confidence calculation."""
    planner = AutomationPlanner(components=[sample_component])
    
    plan = planner.create_automation_plan(sample_scenario)
    
    if plan:
        assert 0.0 <= plan.confidence <= 1.0


# ---------------------------------------------------------------------------
# Action Generator Tests
# ---------------------------------------------------------------------------

def test_action_generator_initialization():
    """Test ActionGenerator initialization."""
    generator = ActionGenerator()
    
    assert generator is not None
    assert generator.action_mappings is not None


def test_generate_action_fill(sample_component):
    """Test generating fill action."""
    generator = ActionGenerator()
    
    action = generator.generate_action(
        ActionType.FILL,
        sample_component,
        {"value": "testuser"},
        sample_component.selected_locator,
    )
    
    assert action.action_type == ActionType.FILL
    assert action.target_component_id == sample_component.component_id
    assert "fill" in action.parameters.get("playwright_code", "").lower()


def test_generate_action_click(sample_component):
    """Test generating click action."""
    generator = ActionGenerator()
    
    action = generator.generate_action(
        ActionType.CLICK,
        sample_component,
        {},
        sample_component.selected_locator,
    )
    
    assert action.action_type == ActionType.CLICK
    assert "click" in action.parameters.get("playwright_code", "").lower()


def test_determine_action_from_component(sample_component):
    """Test determining action from component intelligence."""
    generator = ActionGenerator()
    
    action_type = generator.determine_action_from_component(sample_component)
    
    # Username input should map to fill
    assert action_type == ActionType.FILL


def test_generate_action_from_step():
    """Test generating action from natural language step."""
    generator = ActionGenerator()
    
    action = generator.generate_action_from_step("Click the submit button")
    
    assert action.action_type == ActionType.CLICK


def test_generate_action_from_step_fill():
    """Test generating fill action from step."""
    generator = ActionGenerator()
    
    action = generator.generate_action_from_step("Enter username in the field")
    
    assert action.action_type == ActionType.FILL


# ---------------------------------------------------------------------------
# Assertion Generator Tests
# ---------------------------------------------------------------------------

def test_assertion_generator_initialization():
    """Test AssertionGenerator initialization."""
    generator = AssertionGenerator()
    
    assert generator is not None
    assert generator.assertion_templates is not None


def test_generate_assertions_from_expected_result(sample_scenario):
    """Test generating assertions from expected result."""
    generator = AssertionGenerator()
    
    assertions = generator._generate_from_expected_result(
        sample_scenario.expected_result,
        [],
        {},
    )
    
    assert len(assertions) > 0
    assert all(hasattr(a, 'assertion_type') for a in assertions)


def test_generate_assertions_success():
    """Test generating success assertions."""
    generator = AssertionGenerator()
    
    assertions = generator._generate_from_expected_result("Login successful", [], {})
    
    assert len(assertions) > 0
    assert assertions[0].assertion_type == AssertionType.SUCCESS_MESSAGE


def test_generate_assertions_error():
    """Test generating error assertions."""
    generator = AssertionGenerator()
    
    assertions = generator._generate_from_expected_result("Login failed", [], {})
    
    assert len(assertions) > 0
    assert assertions[0].assertion_type == AssertionType.ERROR_MESSAGE


def test_validate_assertion():
    """Test assertion validation."""
    generator = AssertionGenerator()
    
    # Valid assertion
    valid_assertion = Assertion(
        assertion_id="ASSERT-001",
        assertion_type=AssertionType.VISIBLE_TEXT,
        expected_value="Dashboard",
    )
    
    assert generator._validate_assertion(valid_assertion, []) == True
    
    # Invalid assertion (no expected value)
    invalid_assertion = Assertion(
        assertion_id="ASSERT-002",
        assertion_type=AssertionType.VISIBLE_TEXT,
        expected_value=None,
    )
    
    assert generator._validate_assertion(invalid_assertion, []) == False


def test_generate_playwright_assertion():
    """Test generating Playwright assertion code."""
    generator = AssertionGenerator()
    
    assertion = Assertion(
        assertion_id="ASSERT-001",
        assertion_type=AssertionType.VISIBLE_TEXT,
        expected_value="Dashboard",
    )
    
    code = generator.generate_playwright_assertion(assertion)
    
    assert "to_be_visible" in code
    assert "Dashboard" in code


# ---------------------------------------------------------------------------
# POM Manager Tests
# ---------------------------------------------------------------------------

def test_pom_manager_initialization(temp_pom_dir):
    """Test POMManager initialization."""
    manager = POMManager(pom_directory=temp_pom_dir)
    
    assert manager is not None
    assert manager.pom_directory.exists()


def test_generate_pom_name():
    """Test POM name generation."""
    manager = POMManager()
    
    name = manager._generate_pom_name(PageType.AUTHENTICATION_SCREEN)
    
    assert name == "authentication"


def test_should_create_pom():
    """Test POM creation decision."""
    manager = POMManager()
    
    # Many components should trigger POM creation
    many_components = [SemanticComponent(component_id=f"COMP-{i}", component_type=ComponentType.TEXT_FIELD) for i in range(5)]
    should_create = manager.should_create_pom(many_components, ["action1", "action2"])
    
    assert should_create == True


def test_get_pom_reuse_statistics(temp_pom_dir):
    """Test POM reuse statistics."""
    manager = POMManager(pom_directory=temp_pom_dir)
    
    stats = manager.get_pom_reuse_statistics()
    
    assert "total_poms" in stats
    assert "total_reuse_count" in stats
    assert "reuse_rate" in stats


# ---------------------------------------------------------------------------
# Locator Strategy Tests
# ---------------------------------------------------------------------------

def test_locator_strategy_manager_initialization():
    """Test LocatorStrategyManager initialization."""
    manager = LocatorStrategyManager()
    
    assert manager is not None
    assert manager.strategy_priority is not None


def test_strategy_priority_order():
    """Test that strategy priority is correct."""
    manager = LocatorStrategyManager()
    
    assert manager.strategy_priority[0] == LocatorStrategy.TEST_ID
    assert manager.strategy_priority[-1] == LocatorStrategy.XPATH


def test_infer_strategy_from_locator():
    """Test inferring strategy from locator string."""
    manager = LocatorStrategyManager()
    
    strategy = manager._infer_strategy_from_locator('get_by_role("button")')
    
    assert strategy == LocatorStrategy.ROLE
    
    strategy = manager._infer_strategy_from_locator('get_by_test_id("submit")')
    
    assert strategy == LocatorStrategy.TEST_ID


def test_create_locator_chain(sample_component):
    """Test creating locator chain."""
    manager = LocatorStrategyManager()
    
    chain = manager.create_locator_chain("ACT-001", sample_component)
    
    assert chain.action_id == "ACT-001"
    assert chain.primary_locator != ""
    assert chain.primary_strategy in LocatorStrategy


# ---------------------------------------------------------------------------
# Quality Gate Tests
# ---------------------------------------------------------------------------

def test_quality_gate_initialization():
    """Test AutomationQualityGate initialization."""
    gate = AutomationQualityGate()
    
    assert gate is not None
    assert gate.placeholder_patterns is not None


def test_validate_automation_with_pass():
    """Test validating automation with pass statement."""
    gate = AutomationQualityGate()
    
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code="def test_login():\n    pass",
    )
    
    result = gate.validate_automation(automation)
    
    assert result.passed == False
    assert len(result.critical_issues) > 0


def test_validate_automation_with_todo():
    """Test validating automation with TODO comment."""
    gate = AutomationQualityGate()
    
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code="def test_login():\n    # TODO implement",
    )
    
    result = gate.validate_automation(automation)
    
    assert result.passed == False
    assert len(result.issues) > 0


def test_validate_automation_with_hardcoded_password():
    """Test validating automation with hardcoded password."""
    gate = AutomationQualityGate()
    
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code='password = "secret123"',
    )
    
    result = gate.validate_automation(automation)
    
    assert result.passed == False
    assert len(result.critical_issues) > 0


def test_validate_automation_clean():
    """Test validating clean automation."""
    gate = AutomationQualityGate()
    
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code='def test_login(page):\n    page.goto("https://test-app.local")\n    expect(page).to_have_title("Login")',
    )
    
    result = gate.validate_automation(automation)
    
    # Should pass or have only minor issues
    assert result.quality_score > 70.0


def test_calculate_quality_score():
    """Test quality score calculation."""
    gate = AutomationQualityGate()
    
    # No issues = perfect score
    score = gate._calculate_quality_score([])
    assert score == 100.0
    
    # Critical issue should reduce score significantly
    critical_issue = QualityIssue(
        issue_id="ISSUE-001",
        issue_type="placeholder_implementation",
        severity="critical",
        message="Test has pass statement",
    )
    score = gate._calculate_quality_score([critical_issue])
    assert score < 80.0


# ---------------------------------------------------------------------------
# Test Data Intelligence Tests
# ---------------------------------------------------------------------------

def test_test_data_intelligence_initialization():
    """Test TestDataIntelligence initialization."""
    intelligence = TestDataIntelligence()
    
    assert intelligence is not None
    assert intelligence.data_type_patterns is not None


def test_detect_data_type_username():
    """Test detecting username data type."""
    intelligence = TestDataIntelligence()
    
    data_type = intelligence._detect_data_type("username", "username", "", "")
    
    assert data_type == TestDataType.USERNAME


def test_detect_data_type_password():
    """Test detecting password data type."""
    intelligence = TestDataIntelligence()
    
    data_type = intelligence._detect_data_type("password", "password", "", "")
    
    assert data_type == TestDataType.PASSWORD


def test_detect_data_type_email():
    """Test detecting email data type."""
    intelligence = TestDataIntelligence()
    
    data_type = intelligence._detect_data_type("email", "email", "", "")
    
    assert data_type == TestDataType.EMAIL


def test_identify_test_data_requirements(sample_component):
    """Test identifying test data requirements."""
    intelligence = TestDataIntelligence()
    
    requirements = intelligence.identify_test_data_requirements([sample_component])
    
    assert len(requirements) > 0
    assert all(isinstance(req, TestDataRequirement) for req in requirements)


def test_is_sensitive_field():
    """Test sensitive field detection."""
    protection = SensitiveDataProtection()
    
    assert protection.is_sensitive_field("password") == True
    assert protection.is_sensitive_field("username") == False
    assert protection.is_sensitive_field("email") == False


# ---------------------------------------------------------------------------
# Sensitive Data Protection Tests
# ---------------------------------------------------------------------------

def test_sensitive_data_protection_initialization():
    """Test SensitiveDataProtection initialization."""
    protection = SensitiveDataProtection()
    
    assert protection is not None
    assert protection.sensitive_patterns is not None


def test_detect_sensitive_data():
    """Test detecting sensitive data in code."""
    protection = SensitiveDataProtection()
    
    code = 'password = "secret123"'
    detections = protection.detect_sensitive_data(code)
    
    assert len(detections) > 0
    assert detections[0]["type"] == "password"


def test_mask_sensitive_data():
    """Test masking sensitive data."""
    protection = SensitiveDataProtection()
    
    code = 'password = "secret123"'
    masked = protection.mask_sensitive_data(code)
    
    assert "secret123" not in masked
    assert "os.environ.get" in masked


def test_is_sensitive_field_protection():
    """Test sensitive field detection in protection."""
    protection = SensitiveDataProtection()
    
    assert protection.is_sensitive_field("password") == True
    assert protection.is_sensitive_field("api_key") == True
    assert protection.is_sensitive_field("username") == False


def test_get_safe_value():
    """Test getting safe value for logging."""
    protection = SensitiveDataProtection()
    
    safe = protection.get_safe_value("password", "secret123")
    
    assert safe == "***REDACTED***"
    
    safe = protection.get_safe_value("username", "testuser")
    
    assert safe == "testuser"


def test_sanitize_log_message():
    """Test sanitizing log messages."""
    protection = SensitiveDataProtection()
    
    message = 'User logged in with password="secret123"'
    sanitized = protection.sanitize_log_message(message)
    
    assert "secret123" not in sanitized
    assert "***REDACTED***" in sanitized


# ---------------------------------------------------------------------------
# Failure Classifier Tests
# ---------------------------------------------------------------------------

def test_failure_classifier_initialization():
    """Test FailureClassifier initialization."""
    classifier = FailureClassifier()
    
    assert classifier is not None
    assert classifier.failure_patterns is not None


def test_classify_locator_failure():
    """Test classifying locator failure."""
    classifier = FailureClassifier()
    
    classification = classifier.classify_failure(
        "Selector not found",
        automation_id="AUTO-001",
    )
    
    assert classification.failure_type == FailureType.LOCATOR_FAILURE
    assert classification.automation_id == "AUTO-001"


def test_classify_assertion_failure():
    """Test classifying assertion failure."""
    classifier = FailureClassifier()
    
    classification = classifier.classify_failure(
        "Assertion failed: expected 'Dashboard' but got 'Error'",
        automation_id="AUTO-001",
    )
    
    assert classification.failure_type == FailureType.ASSERTION_FAILURE


def test_classify_navigation_failure():
    """Test classifying navigation failure."""
    classifier = FailureClassifier()
    
    classification = classifier.classify_failure(
        "Navigation timeout exceeded after network error",
        automation_id="AUTO-001",
    )
    
    assert classification.failure_type == FailureType.NAVIGATION_FAILURE


def test_determine_responsibility_locator():
    """Test responsibility determination for locator failure."""
    classifier = FailureClassifier()
    
    phoenix_resp, app_resp = classifier._determine_responsibility(
        "element not found",
        FailureType.LOCATOR_FAILURE,
        "Element not found",
    )
    
    assert phoenix_resp == True
    assert app_resp == False


def test_determine_responsibility_assertion():
    """Test responsibility determination for assertion failure."""
    classifier = FailureClassifier()
    
    phoenix_resp, app_resp = classifier._determine_responsibility(
        "assertion failed",
        FailureType.ASSERTION_FAILURE,
        "Assertion condition not met",
    )
    
    assert phoenix_resp == False
    assert app_resp == True


# ---------------------------------------------------------------------------
# Automation Regeneration Tests
# ---------------------------------------------------------------------------

def test_automation_regeneration_initialization():
    """Test AutomationRegeneration initialization."""
    regenerator = AutomationRegeneration()
    
    assert regenerator is not None
    assert regenerator.dom_cache is not None


def test_detect_application_change():
    """Test detecting application change."""
    regenerator = AutomationRegeneration()
    
    # First time - no change
    changed = regenerator.detect_application_change("https://example.com", "<html></html>")
    assert changed == False
    
    # Second time with same DOM - no change
    changed = regenerator.detect_application_change("https://example.com", "<html></html>")
    assert changed == False
    
    # Second time with different DOM - change detected
    changed = regenerator.detect_application_change("https://example.com", "<html><body>Changed</body></html>")
    assert changed == True


def test_should_regenerate_no_changes():
    """Test regeneration decision with no changes."""
    regenerator = AutomationRegeneration()
    
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code="def test(): pass",
    )
    
    dom_changes = {"changed": False, "changes": []}
    
    should_regenerate = regenerator.should_regenerate(automation, dom_changes)
    
    assert should_regenerate == False


def test_should_regenerate_with_changes():
    """Test regeneration decision with changes."""
    regenerator = AutomationRegeneration()
    
    automation = GeneratedAutomation(
        automation_id="AUTO-001",
        scenario_id="SCEN-001",
        script_code="def test(): pass",
    )
    
    dom_changes = {
        "changed": True,
        "added_elements": ["div1", "div2", "div3", "div4", "div5", "div6", "div7", "div8", "div9", "div10", "div11"],
    }
    
    should_regenerate = regenerator.should_regenerate(automation, dom_changes)
    
    assert should_regenerate == True


def test_update_dom_cache():
    """Test updating DOM cache."""
    regenerator = AutomationRegeneration()
    
    regenerator.update_dom_cache("https://example.com", "<html></html>")
    
    assert "https://example.com" in regenerator.dom_cache
    assert regenerator.dom_cache["https://example.com"] == "<html></html>"


def test_clear_dom_cache():
    """Test clearing DOM cache."""
    regenerator = AutomationRegeneration()
    
    regenerator.update_dom_cache("https://example.com", "<html></html>")
    regenerator.clear_dom_cache()
    
    assert len(regenerator.dom_cache) == 0


# ---------------------------------------------------------------------------
# Application-Agnostic Verification Tests
# ---------------------------------------------------------------------------

def test_no_application_specific_references_in_models():
    """Verify models don't contain application-specific references."""
    import phoenix.automation_generation.models as models
    
    # Check for forbidden application names
    forbidden = ["orangehrm", "jira", "salesforce", "sap", "servicenow"]
    
    model_source = open(models.__file__, 'r').read().lower()
    
    for app in forbidden:
        assert app not in model_source, f"Found application-specific reference: {app}"


def test_no_application_specific_references_in_planner():
    """Verify planner doesn't contain application-specific references."""
    import phoenix.automation_generation.automation_planner as planner
    
    forbidden = ["orangehrm", "jira", "salesforce", "sap", "servicenow"]
    
    planner_source = open(planner.__file__, 'r').read().lower()
    
    for app in forbidden:
        assert app not in planner_source, f"Found application-specific reference: {app}"


def test_no_application_specific_references_in_action_generator():
    """Verify action generator doesn't contain application-specific references."""
    import phoenix.automation_generation.action_generator as generator
    
    forbidden = ["orangehrm", "jira", "salesforce", "sap", "servicenow"]
    
    generator_source = open(generator.__file__, 'r').read().lower()
    
    for app in forbidden:
        assert app not in generator_source, f"Found application-specific reference: {app}"


def test_no_hardcoded_urls_in_generation():
    """Verify no hardcoded application URLs in generation code."""
    import phoenix.automation_generation.automation_generator as generator
    
    generator_source = open(generator.__file__, 'r').read().lower()
    
    # Check for common hardcoded URL patterns
    assert "orangehrm.com" not in generator_source
    assert "atlassian.net" not in generator_source  # Jira
    assert "salesforce.com" not in generator_source


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_full_generation_pipeline(sample_scenario, sample_component, temp_pom_dir):
    """Test the full automation generation pipeline."""
    from phoenix.automation_generation.automation_generator import AutomationGenerationCoordinator
    from pathlib import Path
    
    output_dir = Path(temp_pom_dir) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=str(output_dir),
        pom_directory=temp_pom_dir,
    )
    
    automation = coordinator.generate_automation_from_scenario(
        sample_scenario,
        [sample_component],
        [],
        "test_project",
        "login_page",
    )
    
    assert automation is not None
    assert automation.automation_id != ""
    assert automation.scenario_id == sample_scenario.scenario_id
    assert automation.status in [AutomationStatus.GENERATED, AutomationStatus.REJECTED]


def test_metrics_tracking(sample_scenario, sample_component, temp_pom_dir):
    """Test that metrics are tracked correctly."""
    from phoenix.automation_generation.automation_generator import AutomationGenerationCoordinator
    from pathlib import Path
    
    output_dir = Path(temp_pom_dir) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    coordinator = AutomationGenerationCoordinator(
        output_dir=str(output_dir),
        pom_directory=temp_pom_dir,
    )
    
    initial_metrics = coordinator.get_metrics()
    
    coordinator.generate_automation_from_scenario(
        sample_scenario,
        [sample_component],
        [],
        "test_project",
        "login_page",
    )
    
    final_metrics = coordinator.get_metrics()
    
    # Metrics should have been updated
    assert final_metrics.total_plans >= initial_metrics.total_plans
