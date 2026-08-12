"""Test with hardcoded credentials using TestRunner with Intelligent Runtime."""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent / "phoenix-core"))

from phoenix.execution.runner import TestRunner

print("=" * 60)
print("Running hardcoded credentials test with Intelligent Runtime")
print("=" * 60)

# Create TestRunner with intelligent runtime enabled
runner = TestRunner(
    test_output_dir="./tests",
    reports_dir="./reports",
    headed=True,
    slow_mo=0,
    enable_healing=True,
    enable_intelligent_runtime=True,
    project_name="hardcoded_verification"
)

print("[TEST] TestRunner created with Intelligent Runtime enabled")

# Run the test
test_path = "test_hardcoded_login_verification.py"
print(f"[TEST] Running test: {test_path}")

results = runner.run_tests([test_path])

print("\n" + "=" * 60)
print("Test Execution Results")
print("=" * 60)
print(f"Status: {results.get('status')}")
print(f"Total Tests: {results.get('total_tests')}")
print(f"Passed: {results.get('passed_tests')}")
print(f"Failed: {results.get('failed_tests')}")
print(f"Skipped: {results.get('skipped_tests')}")

if runner.intelligent_runtime:
    print("\n" + "=" * 60)
    print("Intelligent Runtime Summary")
    print("=" * 60)
    runner.intelligent_runtime.print_summary()
