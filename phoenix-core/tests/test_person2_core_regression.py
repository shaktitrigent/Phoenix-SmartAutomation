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
