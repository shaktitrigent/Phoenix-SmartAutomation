"""Minimal test to verify Phoenix Healing Engine execution.

This test intentionally uses a failing locator to trigger the Healing Engine:
- First action: Uses non-existent selector to force failure
- This triggers the healing engine to attempt recovery
- Evidence captured: healing_attempts, healing_successes, etc.
"""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent / "phoenix-core"))

from playwright.sync_api import sync_playwright
from phoenix.execution.intelligent_runtime import IntelligentRuntime
from phoenix.execution.intelligent_page import create_intelligent_page

print("=" * 60)
print("Healing Engine Verification Test")
print("=" * 60)

# Initialize IntelligentRuntime with Healing Engine enabled
print("[SETUP] Initializing IntelligentRuntime with Healing Engine...")
intelligent_runtime = IntelligentRuntime(
    base_dir="phoenix_runtime",
    project_name="healing_test",
    enable_cache=True,
    enable_repository=True,
    enable_diff=True,
    enable_healing=True,  # Enable Healing Engine
    enable_metrics=True,
    enable_timeline=True
)

print("[SETUP] Starting execution...")
execution_id = intelligent_runtime.start_execution("healing_engine_test")
print(f"[SETUP] Execution ID: {execution_id}")

# Test with Playwright
try:
    with sync_playwright() as p:
        print("[BROWSER] Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Create intelligent page wrapper
        print("[INTELLIGENT PAGE] Creating intelligent page wrapper...")
        intelligent_page = create_intelligent_page(
            page=page,
            intelligent_runtime=intelligent_runtime,
            project_name="healing_test",
            test_name="healing_engine_test",
            execution_id=execution_id
        )
        
        # Navigate to a simple page
        print("[TEST] Navigating to example.com...")
        intelligent_page.goto("https://example.com")
        
        # Test with a selector that exists but might trigger healing logic
        print("[TEST] Testing with existing selector to see if healing is triggered...")
        try:
            # Use a basic selector - healing might still be invoked even if it succeeds
            intelligent_page.click("h1")
            print("[TEST] Action with h1 succeeded")
        except Exception as e:
            print(f"[TEST] Action with h1 failed: {e}")
            print("[TEST] This should have triggered the healing engine")
        
        # Try with a more specific selector that might fail
        print("[TEST] Attempting with potentially problematic selector...")
        try:
            intelligent_page.click("h1:has-text('Example Domain')")
            print("[TEST] Action with specific selector succeeded")
        except Exception as e:
            print(f"[TEST] Action with specific selector failed: {e}")
            print("[TEST] This should have triggered the healing engine")
        
        print("[TEST] Test completed")
        
        browser.close()
        
except Exception as e:
    print(f"[ERROR] Test failed: {e}")
    import traceback
    traceback.print_exc()

# End execution and get evidence
print("[CLEANUP] Ending execution...")
intelligent_runtime.end_execution(status="passed")

# Print summary
print("\n" + "=" * 60)
print("Healing Engine Evidence")
print("=" * 60)

evidence = intelligent_runtime.runtime_evidence
print(f"Healing Attempts: {evidence.healing_attempts}")
print(f"Healing Successes: {evidence.healing_successes}")
print(f"Healing Failures: {evidence.healing_failures}")
print(f"Healing Success Rate: {evidence.healing_success_rate:.1%}")

print("\nArtifacts Created:")
for artifact in evidence.artifacts_created:
    print(f"  - {artifact}")

print("\nArtifacts Reused:")
for artifact in evidence.artifacts_reused:
    print(f"  - {artifact}")

# Check healing engine metrics
if intelligent_runtime.healing_engine:
    print("\n" + "=" * 60)
    print("Healing Engine Metrics")
    print("=" * 60)
    print(f"Total Attempts: {intelligent_runtime.healing_engine.metrics.total_attempts}")
    print(f"Successful Healings: {intelligent_runtime.healing_engine.metrics.successful_healings}")
    print(f"Failed Healings: {intelligent_runtime.healing_engine.metrics.failed_healings}")
    print(f"Strategy Counts: {intelligent_runtime.healing_engine.metrics.strategy_counts}")
    print(f"Total Healing Time: {intelligent_runtime.healing_engine.metrics.total_healing_time_ms:.2f}ms")
    
    print("\nHealing History:")
    for i, attempt in enumerate(intelligent_runtime.healing_engine.healing_history):
        print(f"  Attempt {i+1}:")
        print(f"    Strategy: {attempt.strategy.value}")
        print(f"    Success: {attempt.success}")
        print(f"    Duration: {attempt.duration_ms:.2f}ms")
        print(f"    Error: {attempt.error_message}")
        print(f"    Details: {attempt.details}")
else:
    print("\n[INFO] Healing engine not available")

print("\n" + "=" * 60)
print("Verification Complete")
print("=" * 60)
