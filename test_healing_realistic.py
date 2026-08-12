"""Realistic Healing Engine test with actual failure scenarios.

This test creates a realistic scenario where healing can actually work:
1. Save multiple locators for the same element to repository
2. Intentionally use a failing locator
3. Healing should find and try the alternative from repository
"""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent / "phoenix-core"))

from playwright.sync_api import sync_playwright
from phoenix.healing.engine import HealingEngine
from phoenix.execution.locator_repository import LocatorRepository

print("=" * 60)
print("Realistic Healing Engine Test")
print("=" * 60)

# Initialize components
print("[SETUP] Initializing Locator Repository...")
locator_repo = LocatorRepository(repository_dir="phoenix_runtime/locator_repository_realistic")

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
        
        # Save multiple locators for the same element to repository
        print("[TEST] Saving multiple locators for h1 element to repository...")
        locator_repo.save_locator(
            project_name="healing_test",
            page_name="example",
            element_name="main_heading",
            locator="h1",
            locator_type="css",
            confidence=0.9,
            source="manual",
            page_url="https://example.com"
        )
        
        # Save an alternative locator
        locator_repo.save_locator(
            project_name="healing_test", 
            page_name="example",
            element_name="main_heading_alt",
            locator="h1:has-text('Example Domain')",
            locator_type="css",
            confidence=0.95,
            source="manual",
            page_url="https://example.com"
        )
        
        print("[TEST] Multiple locators saved to repository")
        
        # Now try to heal using a failing locator
        print("[TEST] Attempting to heal with failing locator...")
        context = {
            "project_name": "healing_test",
            "page_name": "example", 
            "url": "https://example.com"
        }
        
        # Use a locator that will fail but has alternatives in repository
        healing_result = healing_engine.heal(
            element_name="main_heading",
            locator="#non-existent-id",  # This will fail
            page=page,
            context=context
        )
        
        print(f"[TEST] Healing result for failing locator: {healing_result}")
        
        # Try with a locator that exists to see if healing still tries alternatives
        print("[TEST] Attempting healing with existing locator...")
        healing_result = healing_engine.heal(
            element_name="main_heading",
            locator="h1",  # This exists
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
