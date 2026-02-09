"""Sample tests for Test Automation Practice website

Website: https://testautomationpractice.blogspot.com/
This script demonstrates Phoenix framework usage with real user stories.
"""

from phoenix import PhoenixClient


def generate_form_submission_tests():
    """User Story 1: Form Submission"""
    print("=" * 60)
    print("User Story 1: Form Submission")
    print("=" * 60)
    
    client = PhoenixClient()
    client.set_project("test-automation-practice")
    
    result = client.generate_tests(
        user_story="As a user, I want to fill in the form with my personal details and submit it, so that the system accepts and processes my registration correctly",
        application_url="https://testautomationpractice.blogspot.com/",
        acceptance_criteria=[
            "User can enter name, email, phone and address",
            "User can select gender and multiple days",
            "User can choose a country from the dropdown",
            "The form must submit successfully without errors"
        ],
        test_type="both",
        risk_level="smoke"
    )
    
    print(f"✓ Generated {len(result['manual_tests'])} manual test(s)")
    print(f"✓ Generated {len(result['automation_tests'])} automation test(s)")
    
    for test in result.get("manual_tests", []):
        if test.get("file_path"):
            print(f"  Manual test: {test['file_path']}")
    
    for test in result.get("automation_tests", []):
        if test.get("script_path"):
            print(f"  Automation script: {test['script_path']}")
    
    return result


def generate_table_validation_tests():
    """User Story 2: Table Data Validation"""
    print("\n" + "=" * 60)
    print("User Story 2: Table Data Validation")
    print("=" * 60)
    
    client = PhoenixClient()
    client.set_project("test-automation-practice")
    
    result = client.generate_tests(
        user_story="As a tester, I want to verify the static web table data for books (Book Name, Author, Subject, Price), so that I can ensure the table displays correct information and sorting behaves as expected",
        application_url="https://testautomationpractice.blogspot.com/",
        acceptance_criteria=[
            "Book table loads with expected column headers",
            "All rows display accurate book details",
            "Sorting or filtering functions work if provided"
        ],
        test_type="both",
        risk_level="regression"
    )
    
    print(f"✓ Generated {len(result['manual_tests'])} manual test(s)")
    print(f"✓ Generated {len(result['automation_tests'])} automation test(s)")
    
    for test in result.get("manual_tests", []):
        if test.get("file_path"):
            print(f"  Manual test: {test['file_path']}")
    
    for test in result.get("automation_tests", []):
        if test.get("script_path"):
            print(f"  Automation script: {test['script_path']}")
    
    return result


def generate_alert_handling_tests():
    """User Story 3: Alert Handling"""
    print("\n" + "=" * 60)
    print("User Story 3: Alert Handling")
    print("=" * 60)
    
    client = PhoenixClient()
    client.set_project("test-automation-practice")
    
    result = client.generate_tests(
        user_story="As a user, I want to interact with alerts and popup messages, so that the application displays and handles alert boxes appropriately (accept, cancel, input text)",
        application_url="https://testautomationpractice.blogspot.com/",
        acceptance_criteria=[
            "Simple alerts appear when triggered",
            "Confirmation alerts can be accepted or dismissed",
            "Prompt alerts allow input and reflect that input correctly"
        ],
        test_type="both",
        risk_level="regression"
    )
    
    print(f"✓ Generated {len(result['manual_tests'])} manual test(s)")
    print(f"✓ Generated {len(result['automation_tests'])} automation test(s)")
    
    for test in result.get("manual_tests", []):
        if test.get("file_path"):
            print(f"  Manual test: {test['file_path']}")
    
    for test in result.get("automation_tests", []):
        if test.get("script_path"):
            print(f"  Automation script: {test['script_path']}")
    
    return result


def main():
    """Generate all sample tests"""
    print("Phoenix Framework - Test Automation Practice Sample Tests")
    print("Website: https://testautomationpractice.blogspot.com/")
    print("\nGenerating tests for 3 user stories...\n")
    
    # Initialize project
    client = PhoenixClient()
    client.set_project("test-automation-practice")
    print(f"Using project: {client.get_project()}\n")
    
    # Generate tests for each user story
    form_result = generate_form_submission_tests()
    table_result = generate_table_validation_tests()
    alert_result = generate_alert_handling_tests()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    total_manual = len(form_result['manual_tests']) + len(table_result['manual_tests']) + len(alert_result['manual_tests'])
    total_automation = len(form_result['automation_tests']) + len(table_result['automation_tests']) + len(alert_result['automation_tests'])
    
    print(f"Total Manual Tests Generated: {total_manual}")
    print(f"Total Automation Tests Generated: {total_automation}")
    print(f"\nManual tests location: ./manual_tests/")
    print(f"Automation scripts location: ./test_results/")
    print(f"\nTo run automation tests:")
    print(f"  pytest -v test_results/")


if __name__ == "__main__":
    main()
