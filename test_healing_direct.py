"""Direct Healing Engine test to verify healing functionality.

This test directly calls the healing engine to verify it works.
"""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent / "phoenix-core"))

from playwright.sync_api import sync_playwright
from phoenix.healing.engine import HealingEngine
from phoenix.execution.locator_repository import LocatorRepository

print("=" * 60)
print("Direct Healing Engine Test")
print("=" * 60)

# Initialize components
print("[SETUP] Initializing Locator Repository...")
locator_repo = LocatorRepository(repository_dir="phoenix_runtime/locator_repository_test")

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
        
        # Navigate to example.com
        print("[TEST] Navigating to example.com...")
        page.goto("https://example.com")
        
        # First, save a known good locator to the repository
        print("[TEST] Saving known good locator to repository...")
        locator_repo.save_locator(
            project_name="healing_test",
            page_name="example",
            element_name="main_heading",
            locator="h1",
            locator_type="css",
            confidence=0.95,
            source="manual",
            page_url="https://example.com"
        )
        print("[TEST] Known good locator saved")
        
        # Now try to heal a failed locator
        print("[TEST] Attempting to heal a failed locator...")
        context = {
            "project_name": "healing_test",
            "page_name": "example",
            "url": "https://example.com"
        }
        
        # Try healing with a locator that doesn't exist
        healing_result = healing_engine.heal(
            element_name="non_existent_button",
            locator="#non-existent-button",
            page=page,
            context=context
        )
        
        print(f"[TEST] Healing result: {healing_result}")
        
        # Try healing with a locator that exists in repository
        print("[TEST] Attempting to heal with repository lookup...")
        healing_result = healing_engine.heal(
            element_name="main_heading",
            locator="h1",  # This exists and is in repository
            page=page,
            context=context
        )
        
        print(f"[TEST] Healing result for existing locator: {healing_result}")
        
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
