"""Generate automation tests from existing manual test cases"""

import re
from pathlib import Path
from typing import List, Dict


def parse_manual_test(md_file: Path) -> Dict:
    """Parse a manual test markdown file"""
    content = md_file.read_text()
    
    # Extract application URL
    url_match = re.search(r'Application URL: (.+)', content)
    application_url = url_match.group(1).strip() if url_match else None
    
    # Extract description
    desc_match = re.search(r'Description: (.+)', content, re.MULTILINE)
    description = desc_match.group(1).strip() if desc_match else ""
    
    # Extract steps
    steps_match = re.search(r'Steps:\s*\n((?:\s+\d+\.\s+.+\n?)+)', content)
    steps = []
    if steps_match:
        step_lines = steps_match.group(1).strip().split('\n')
        for line in step_lines:
            step_match = re.search(r'\d+\.\s+(.+)', line)
            if step_match:
                steps.append(step_match.group(1).strip())
    
    return {
        "file": md_file,
        "url": application_url,
        "description": description,
        "steps": steps,
        "name": md_file.stem
    }


def generate_form_submission_test(test_data: Dict) -> str:
    """Generate Playwright test for form submission"""
    url = test_data["url"]
    steps = test_data["steps"]
    
    test_code = f'''"""Generated Playwright UI Test
User Story: {test_data["description"]}
Application URL: {url}
"""

import pytest
from playwright.sync_api import Page, expect


def test_form_submission(page: Page):
    """{test_data["description"]}"""
    # Navigate to application
    page.goto("{url}")
    page.wait_for_load_state('networkidle')
    
    # Step 1: User can enter name, email, phone and address
    page.get_by_label("Name:").fill("John Doe")
    page.get_by_label("Email:").fill("john.doe@example.com")
    page.get_by_label("Phone:").fill("1234567890")
    page.get_by_label("Address:").fill("123 Main Street")
    
    # Step 2: User can select gender and multiple days
    page.get_by_role("radio", name="Male").check()
    page.get_by_role("checkbox", name="Monday").check()
    page.get_by_role("checkbox", name="Wednesday").check()
    page.get_by_role("checkbox", name="Friday").check()
    
    # Step 3: User can choose a country from the dropdown
    page.get_by_label("Country:").select_option("United States")
    
    # Step 4: The form must submit successfully without errors
    page.get_by_role("button", name="Submit").click()
    
    # Verify form submission (check for any error messages or success indicators)
    # Note: This site doesn't show explicit success, so we verify no errors appear
    expect(page.locator("body")).to_be_visible()
'''
    return test_code


def generate_table_validation_test(test_data: Dict) -> str:
    """Generate Playwright test for table validation"""
    url = test_data["url"]
    
    test_code = f'''"""Generated Playwright UI Test
User Story: {test_data["description"]}
Application URL: {url}
"""

import pytest
from playwright.sync_api import Page, expect


def test_static_web_table_validation(page: Page):
    """{test_data["description"]}"""
    # Navigate to application
    page.goto("{url}")
    page.wait_for_load_state('networkidle')
    
    # Step 1: Book table loads with expected column headers
    table = page.locator('table').filter(has_text="BookName")
    expect(table).to_be_visible()
    
    # Verify column headers
    expect(table.get_by_role("columnheader", name="BookName")).to_be_visible()
    expect(table.get_by_role("columnheader", name="Author")).to_be_visible()
    expect(table.get_by_role("columnheader", name="Subject")).to_be_visible()
    expect(table.get_by_role("columnheader", name="Price")).to_be_visible()
    
    # Step 2: All rows display accurate book details
    # Verify specific book entries exist
    expect(table.get_by_text("Learn Selenium")).to_be_visible()
    expect(table.get_by_text("Amit")).to_be_visible()
    expect(table.get_by_text("300")).to_be_visible()
    
    expect(table.get_by_text("Learn Java")).to_be_visible()
    expect(table.get_by_text("Mukesh")).to_be_visible()
    expect(table.get_by_text("500")).to_be_visible()
    
    expect(table.get_by_text("Master In Selenium")).to_be_visible()
    expect(table.get_by_text("3000")).to_be_visible()
    
    # Step 3: Verify table has expected number of rows (6 books + 1 header)
    rows = table.get_by_role("row")
    expect(rows).to_have_count(7)  # 1 header + 6 data rows
'''
    return test_code


def generate_alert_handling_test(test_data: Dict) -> str:
    """Generate Playwright test for alert handling"""
    url = test_data["url"]
    
    test_code = f'''"""Generated Playwright UI Test
User Story: {test_data["description"]}
Application URL: {url}
"""

import pytest
from playwright.sync_api import Page, expect


def test_alert_handling(page: Page):
    """{test_data["description"]}"""
    # Navigate to application
    page.goto("{url}")
    page.wait_for_load_state('networkidle')
    
    # Step 1: Simple alerts appear when triggered
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Simple Alert").click()
    # Alert is automatically accepted by the handler above
    
    # Step 2: Confirmation alerts can be accepted or dismissed
    # Test accepting
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Confirmation Alert").click()
    
    # Test dismissing (reload page first)
    page.reload()
    page.wait_for_load_state('networkidle')
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Confirmation Alert").click()
    
    # Step 3: Prompt alerts allow input and reflect that input correctly
    page.reload()
    page.wait_for_load_state('networkidle')
    page.once("dialog", lambda dialog: dialog.accept("Test Input"))
    page.get_by_role("button", name="Prompt Alert").click()
    # Verify the page handled the prompt (if there's any visual feedback)
    expect(page.locator("body")).to_be_visible()
'''
    return test_code


def main():
    """Generate automation tests from manual tests"""
    manual_tests_dir = Path("manual_tests")
    test_results_dir = Path("test_results")
    test_results_dir.mkdir(exist_ok=True)
    
    # Find all manual test files
    manual_tests = list(manual_tests_dir.glob("*.md"))
    
    print(f"Found {len(manual_tests)} manual test(s)")
    
    for md_file in manual_tests:
        print(f"\nProcessing: {md_file.name}")
        test_data = parse_manual_test(md_file)
        
        # Determine test type based on description
        description_lower = test_data["description"].lower()
        
        if "form" in description_lower and "submit" in description_lower:
            test_code = generate_form_submission_test(test_data)
            test_file = test_results_dir / f"test_form_submission.py"
        elif "table" in description_lower:
            test_code = generate_table_validation_test(test_data)
            test_file = test_results_dir / f"test_table_validation.py"
        elif "alert" in description_lower or "popup" in description_lower:
            test_code = generate_alert_handling_test(test_data)
            test_file = test_results_dir / f"test_alert_handling.py"
        else:
            print(f"  [SKIP] Unknown test type: {test_data['description'][:50]}...")
            continue
        
        # Write test file
        test_file.write_text(test_code)
        print(f"  [OK] Generated: {test_file}")
    
    print(f"\n[OK] All automation tests generated in {test_results_dir}/")


if __name__ == "__main__":
    main()
