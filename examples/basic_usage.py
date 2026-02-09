"""Basic usage example for Phoenix SDK"""

from phoenix import PhoenixClient


def main():
    """Basic example of using Phoenix SDK"""
    
    # Initialize Phoenix client
    print("Initializing Phoenix client...")
    client = PhoenixClient()
    
    # Set project
    client.set_project("example-project")
    print(f"Using project: {client.get_project()}")
    
    # Generate tests from user story
    print("\nGenerating tests...")
    result = client.generate_tests(
        user_story="As a user, I want to login to the application",
        acceptance_criteria=[
            "User can enter email and password",
            "User can click login button",
            "User is redirected to dashboard after successful login",
            "Error message is shown for invalid credentials"
        ],
        test_type="both",
        risk_level="smoke"
    )
    
    print(f"Generated {len(result['manual_tests'])} manual test(s)")
    print(f"Generated {len(result['automation_tests'])} automation test(s)")
    
    # Display generated tests
    print("\nManual Tests:")
    for test in result['manual_tests']:
        print(f"  - {test['name']}")
        print(f"    Steps: {len(test.get('steps', []))} steps")
    
    print("\nAutomation Tests:")
    for test in result['automation_tests']:
        print(f"  - {test['name']}")
        if test.get('script_path'):
            print(f"    Script: {test['script_path']}")
    
    # Get test cases
    print("\nRetrieving test cases...")
    test_cases = client.get_test_cases()
    print(f"Found {len(test_cases)} test case(s) in project")
    
    # Execute tests (if automation tests exist)
    automation_tests = [tc for tc in test_cases if tc['test_type'] == 'automation']
    if automation_tests:
        print("\nExecuting automation tests...")
        execution_result = client.execute_tests()
        print(f"Execution status: {execution_result.get('status')}")
        print(f"Passed: {execution_result.get('passed_tests', 0)}")
        print(f"Failed: {execution_result.get('failed_tests', 0)}")
        if execution_result.get('report_path'):
            print(f"Report: {execution_result['report_path']}")
    
    # Get execution results
    print("\nRetrieving execution results...")
    execution_results = client.get_execution_results()
    if execution_results:
        print(f"Latest execution status: {execution_results.get('status')}")
        print(f"Total tests: {execution_results.get('total_tests', 0)}")
        if execution_results.get('report_path'):
            print(f"Report: {execution_results['report_path']}")


if __name__ == "__main__":
    main()
