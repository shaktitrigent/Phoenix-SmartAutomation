"""Healing Engine test with proper context for healing to work.

This test provides the required context to make healing actually work:
1. Saves alternate locators in the context
2. Uses a failing locator that has alternatives
3. Healing should find and use the alternate locator
"""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent / "phoenix-core"))

from playwright.sync_api import sync_playwright
from phoenix.healing.engine import HealingEngine
from phoenix.execution.locator_repository import LocatorRepository

print("=" * 60)
print("Healing Engine Test with Context")
print("=" * 60)

# Initialize components
print("[SETUP] Initializing Locator Repository...")
locator_repo = LocatorRepository(repository_dir="phoenix_runtime/locator_repository_context")

print("[SETUP] Initializing Healing Engine...")
healing_engine = HealingEngine(
    max_retries=3,
    retry_delay_ms=1000,
    locator_repository=locator_repo
)

# Test with Playwright
try:
    with sync_playwright() as p:
        print("[BROWSER] Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to local test page
        print("[TEST] Navigating to local test page...")
        local_file = Path(__file__).parent / "test_healing_local.html"
        page.goto(f"file:///{local_file.as_posix()}")
        
        # Save an improved locator to repository
        print("[TEST] Saving improved locator to repository...")
        local_file = Path(__file__).parent / "test_healing_local.html"
        page_url = f"file:///{local_file.as_posix()}"
        
        locator_repo.save_locator(
            project_name="healing_test",
            page_name="test_page",
            element_name="#non-existent",  # Match the failing locator
            locator="h1:has-text('Example Domain')",  # Improved locator
            locator_type="css",
            confidence=0.95,
            source="manual",
            page_url=page_url
        )
        
        print("[TEST] Improved locator saved")
        
        # Create context with alternate locators
        print("[TEST] Creating context with alternate locators...")
        context = {
            "project_name": "healing_test",
            "page_name": "test_page",
            "url": page_url,
            "locators": [
                {
                    "element_name": "heading",
                    "alternate_locators": [
                        "h1",
                        "h1:has-text('Example Domain')",
                        "body > h1",
                        "#main-heading"
                    ]
                }
            ]
        }
        
        # Try healing with a basic locator that has alternatives
        print("[TEST] Attempting to heal with basic locator...")
        healing_result = healing_engine.heal(
            element_name="heading",
            locator="h1",  # Basic locator
            page=page,
            context=context
        )
        
        print(f"[TEST] Healing result: {healing_result}")
        
        # Try with a failing locator that has repository alternatives
        print("[TEST] Attempting to heal with failing locator using repository...")
        context_repo = {
            "project_name": "healing_test",
            "page_name": "test_page",
            "url": page_url
        }
        
        healing_result = healing_engine.heal(
            element_name="heading",
            locator="#non-existent",  # Failing locator
            page=page,
            context=context_repo
        )
        
        print(f"[TEST] Healing result for failing locator: {healing_result}")
        
        browser.close()
        
except Exception as e:
    print(f"[ERROR] Test failed: {e}")
    import traceback
    traceback.print_exc()

# Print healing metrics
print("\n" + "=" * 60)
print("Healing Engine Metrics")
print("=" * 60)
print(f"Total Attempts: {healing_engine.metrics.total_attempts}")
print(f"Successful Healings: {healing_engine.metrics.successful_healings}")
print(f"Failed Healings: {healing_engine.metrics.failed_healings}")
print(f"Strategy Counts: {healing_engine.metrics.strategy_counts}")
print(f"Total Healing Time: {healing_engine.metrics.total_healing_time_ms:.2f}ms")

print("\nHealing History:")
for i, attempt in enumerate(healing_engine.healing_history):
    print(f"  Attempt {i+1}:")
    print(f"    Strategy: {attempt.strategy.value}")
    print(f"    Success: {attempt.success}")
    print(f"    Duration: {attempt.duration_ms:.2f}ms")
    print(f"    Error: {attempt.error_message}")
    print(f"    Details: {attempt.details}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
