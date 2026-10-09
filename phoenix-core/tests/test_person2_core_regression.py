"""Person 2 regression tests for phoenix-core.

Covers:
- Markdown table parsing with >4 columns and test data preservation
- Step action extraction fallback
- Fixture selection with word-boundary regexes
- CLI automate non-zero exit behavior
"""

import os
from pathlib import Path
import pytest
import click

from phoenix.generators.manual_parser import parse_manual_test_file, load_manual_tests_from_file
from phoenix.generators.automation import _needs_authenticated_page, _swap_fixtures_by_preconditions


def test_markdown_table_parsing_with_more_than_four_columns(tmp_path):
    content = """# Test Case: Form Submission with Multiple Columns

## Preconditions
User is logged in

## Test Steps
| Step | Action | Expected Result | Data Col 1 | Data Col 2 |
|---|---|---|---|---|
| 1 | Enter username | Field contains username | tomsmith | extra_meta |
| 2 | Enter password | Field contains password | secret | extra_pass |
| 3 | Click submit | Dashboard is displayed | btn_primary | click |
"""
    test_file = tmp_path / "manual_test_001_form.md"
    test_file.write_text(content, encoding="utf-8")
    
    parsed = parse_manual_test_file(test_file)
    assert parsed is not None
    steps = parsed["steps"]
    assert len(steps) == 3
    assert "tomsmith | extra_meta" in steps[0]["test_data"]
    assert "secret | extra_pass" in steps[1]["test_data"]
    assert "btn_primary | click" in steps[2]["test_data"]


def test_markdown_table_does_not_get_overwritten_by_description_steps(tmp_path):
    content = """# Test Case: Mixed Format Test

## Description
1. First description step
2. Second description step

## Test Steps
| Step | Action | Expected Result | Test Data |
|---|---|---|---|
| 1 | Real table step 1 | Real result 1 | data1 |
| 2 | Real table step 2 | Real result 2 | data2 |
"""
    test_file = tmp_path / "manual_test_002.md"
    test_file.write_text(content, encoding="utf-8")
    
    parsed = parse_manual_test_file(test_file)
    assert parsed is not None
    steps = parsed["steps"]
    assert len(steps) == 2
    assert steps[0]["action"] == "Real table step 1"
    assert steps[1]["action"] == "Real table step 2"


def test_fixture_selection_login_and_unauthenticated_scenarios():
    # Login scenario in name or description -> False
    assert not _needs_authenticated_page(
        preconditions="User is on login page",
        name="Valid Login Test",
        description="Test login with valid credentials",
    )
    assert not _needs_authenticated_page(
        preconditions="User is on login page",
        name="Invalid Login",
        description="Test login with invalid password",
    )
    assert not _needs_authenticated_page(
        preconditions="User is on login page",
        name="Empty Credentials",
        description="Test empty username and password",
    )

    # Negation in preconditions -> False
    assert not _needs_authenticated_page(
        preconditions="User is not logged in",
        name="View Landing Page",
        description="Public landing page",
    )
    assert not _needs_authenticated_page(
        preconditions="User is unauthenticated",
        name="Guest Checkout",
        description="Checkout without login",
    )

    # Authenticated preconditions -> True
    assert _needs_authenticated_page(
        preconditions="User is logged in",
        name="Apply for Leave",
        description="Submit leave application",
    )
    assert _needs_authenticated_page(
        preconditions="User is on the dashboard",
        name="Update Profile",
        description="Edit user settings",
    )
    assert _needs_authenticated_page(
        preconditions="Active session with valid credentials",
        name="View Reports",
        description="Generate analytics",
    )


def test_fixture_swapping_in_script_signature():
    auth_code = """
def test_apply_leave(page: Page) -> None:
    page.goto("https://example.com")
"""
    swapped_auth = _swap_fixtures_by_preconditions(
        auth_code,
        preconditions="User is logged in",
        name="Apply Leave",
        description="Submit leave",
    )
    assert "def test_apply_leave(authenticated_page: Page)" in swapped_auth

    unauth_code = """
def test_login(authenticated_page: Page) -> None:
    page.goto("https://example.com/login")
"""
    swapped_unauth = _swap_fixtures_by_preconditions(
        unauth_code,
        preconditions="User is on login page",
        name="Login Test",
        description="Login scenario",
    )
    assert "def test_login(page: Page)" in swapped_unauth


def test_bdd_given_when_then_and_parsing(tmp_path):
    """Test that Given/When/Then/And are parsed with correct semantic interpretation."""
    content = """# Test Case: BDD Login Flow

## Test Steps
Given I am on the login page
When I enter username "standard_user"
And I enter password "secret_sauce"
And I click the Login button
Then I should see the dashboard
And I should see the products list
"""
    test_file = tmp_path / "manual_test_bdd.md"
    test_file.write_text(content, encoding="utf-8")
    
    parsed = parse_manual_test_file(test_file)
    assert parsed is not None
    steps = parsed["steps"]
    
    # Should have 5 steps: Given, When, And(action), And(action), Then+And(assertion combined)
    assert len(steps) == 5
    
    # Step 1: Given -> action
    assert steps[0]["action"] == "I am on the login page"
    assert steps[0]["expected_result"] == ""
    
    # Step 2: When -> action
    assert steps[1]["action"] == 'I enter username "standard_user"'
    assert steps[1]["expected_result"] == ""
    
    # Step 3: And (extends When) -> action (new step)
    assert steps[2]["action"] == 'I enter password "secret_sauce"'
    assert steps[2]["expected_result"] == ""
    
    # Step 4: And (extends When) -> action (new step)
    assert steps[3]["action"] == "I click the Login button"
    assert steps[3]["expected_result"] == ""
    
    # Step 5: Then -> expected_result (And after Then appends to this)
    assert steps[4]["action"] == ""
    assert steps[4]["expected_result"] == "I should see the dashboard I should see the products list"


def test_bdd_and_never_becomes_field_or_selector(tmp_path):
    """Test that 'And' lines never become fields, selectors, or standalone UI actions."""
    content = """# Test Case: BDD Form Submission

## Test Steps
Given I am on the registration page
When I enter my personal details
And I enter my address
And I submit the form
Then I should see a success message
"""
    test_file = tmp_path / "manual_test_bdd_and.md"
    test_file.write_text(content, encoding="utf-8")
    
    parsed = parse_manual_test_file(test_file)
    assert parsed is not None
    steps = parsed["steps"]
    
    # All 'And' lines should be part of actions, not test_data
    for step in steps:
        # 'And' content should be in action, not test_data
        if "And" in step["action"]:
            assert step["test_data"] == ""
            # Verify it's not being treated as a selector/field
            assert not step["action"].startswith("#")
            assert not step["action"].startswith(".")


def test_bdd_then_becomes_expected_result(tmp_path):
    """Test that 'Then' lines become expected_result assertions."""
    content = """# Test Case: BDD Assertions

## Test Steps
Given I am logged in
When I navigate to the profile page
Then I should see my username
And I should see my email address
"""
    test_file = tmp_path / "manual_test_bdd_then.md"
    test_file.write_text(content, encoding="utf-8")
    
    parsed = parse_manual_test_file(test_file)
    assert parsed is not None
    steps = parsed["steps"]
    
    # Step 1: Given -> action
    assert steps[0]["action"] == "I am logged in"
    assert steps[0]["expected_result"] == ""
    
    # Step 2: When -> action
    assert steps[1]["action"] == "I navigate to the profile page"
    assert steps[1]["expected_result"] == ""
    
    # Step 3: Then -> expected_result (And after Then appends to this)
    assert steps[2]["action"] == ""
    assert steps[2]["expected_result"] == "I should see my username I should see my email address"


def test_truncated_generation_detection():
    """Test that truncated/incomplete generation is detected."""
    # Import the function from phoenix-intelligence
    import sys
    from pathlib import Path
    # Add phoenix-intelligence to path
    intelligence_path = Path(__file__).parent.parent.parent / "phoenix-intelligence"
    if str(intelligence_path) not in sys.path:
        sys.path.insert(0, str(intelligence_path))
    
    from services.agents.test_generator import _detect_truncated_generation
    
    # Empty script
    warnings = _detect_truncated_generation("", [])
    assert "Generated script is empty" in warnings
    
    # Script with truncation marker
    script_with_marker = """
def test_example(page):
    page.goto("https://example.com")
    # TODO: complete this step
    ...
"""
    warnings = _detect_truncated_generation(script_with_marker, [])
    assert any("truncation marker" in w.lower() for w in warnings)
    
    # Script with missing imports
    script_missing_imports = """
def test_example(page):
    page.goto("https://example.com")
    page.click("button")
"""
    warnings = _detect_truncated_generation(script_missing_imports, [])
    assert "missing imports" in " ".join(warnings).lower()
    
    # Script with undefined helpers
    script_undefined_helpers = """
def test_example(page):
    fill_ready(page, page.locator("#username"), "user", "Username")
    click_ready(page, page.locator("#submit"), "Submit button")
"""
    warnings = _detect_truncated_generation(script_undefined_helpers, [])
    assert "helper functions" in " ".join(warnings).lower()
    
    # Low step coverage
    manual_steps = [
        {"step_number": 1, "action": "Navigate to page", "expected_result": "", "test_data": ""},
        {"step_number": 2, "action": "Enter username", "expected_result": "", "test_data": ""},
        {"step_number": 3, "action": "Enter password", "expected_result": "", "test_data": ""},
        {"step_number": 4, "action": "Click submit", "expected_result": "", "test_data": ""},
    ]
    incomplete_script = """
def test_example(page):
    page.goto("https://example.com")
"""
    warnings = _detect_truncated_generation(incomplete_script, manual_steps)
    assert any("coverage" in w.lower() or "unresolved" in w.lower() for w in warnings)


def test_cart_arithmetic_generates_numerical_assertion():
    """Test that cart arithmetic expected results generate real numerical assertions, not visibility checks."""
    from phoenix_shared.automation_translation import assertion_lines
    
    # Cart arithmetic requires explicit locator from validated locator system
    locator = 'page.locator("#cart-total")'
    
    # Cart total calculation with locator
    expected = "Cart total equals 150.00"
    lines = assertion_lines(expected, locator=locator)
    
    # Should generate numerical comparison, not visibility check
    assert len(lines) > 0
    assert any("assert" in line and "displayed_value" in line for line in lines)
    assert not any("to_be_visible" in line for line in lines)
    
    # Without locator, should return empty (requires validated locator)
    expected = "Cart total is 200.00"
    lines = assertion_lines(expected)
    assert len(lines) == 0  # No locator = no unsafe hardcoded selectors
    
    # Price × quantity calculation with locator
    expected = "Subtotal is calculated as price × quantity"
    lines = assertion_lines(expected, locator=locator)
    assert len(lines) > 0
    assert any("calculated_value" in line for line in lines)
    
    # Sum of cart items with locator
    expected = "Total should match sum of all cart items"
    lines = assertion_lines(expected, locator=locator)
    assert len(lines) > 0
    assert any("sum" in line.lower() for line in lines)


def test_address_comparison_generates_value_comparison():
    """Test that address validation generates real value/content comparison, not visibility checks."""
    from phoenix_shared.automation_translation import assertion_lines
    
    # Address comparison requires explicit locator from validated locator system
    locator = 'page.locator("#billing-address")'
    
    # Single address comparison with locator
    expected = "Address matches '123 Main St, City, State 12345'"
    lines = assertion_lines(expected, locator=locator)
    
    # Should generate address comparison, not visibility check
    assert len(lines) > 0
    assert any("assert" in line and "displayed_address" in line for line in lines)
    assert not any("to_be_visible" in line for line in lines)
    
    # Without locator, should return empty (requires validated locator)
    expected = "Address equals '789 Pine Rd, Third City, Third State 11111'"
    lines = assertion_lines(expected)
    assert len(lines) == 0  # No locator = no unsafe hardcoded selectors
    
    # Multiline address with locator
    expected = "Shipping address equals '456 Oak Ave, Another City, Another State 67890'"
    lines = assertion_lines(expected, locator=locator)
    assert len(lines) > 0
    assert any("expected_address" in line for line in lines)
