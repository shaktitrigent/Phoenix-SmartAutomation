"""Thin-slice usage example: Simple user story + URL → Manual + Automation tests"""

from phoenix import PhoenixClient


def main():
    """Simple thin-slice example"""
    
    # Initialize Phoenix client
    print("Initializing Phoenix...")
    client = PhoenixClient()
    client.set_project("demo")
    
    # Generate tests with user story and URL
    print("\nGenerating tests...")
    result = client.generate_tests(
        user_story="As a user, I want to login to the application",
        application_url="https://example.com/login",
        acceptance_criteria=[
            "User can enter email and password",
            "User can click login button",
            "User is redirected to dashboard after successful login"
        ],
        test_type="both"
    )
    
    print(f"\n✓ Generated {len(result['manual_tests'])} manual test(s)")
    print(f"✓ Generated {len(result['automation_tests'])} automation test(s)")
    
    # Show file paths
    for test in result.get("manual_tests", []):
        if test.get("file_path"):
            print(f"  Manual test: {test['file_path']}")
    
    for test in result.get("automation_tests", []):
        if test.get("script_path"):
            print(f"  Automation script: {test['script_path']}")
    
    print("\nTo run automation tests:")
    print("  pytest -v test_results/")


if __name__ == "__main__":
    main()
