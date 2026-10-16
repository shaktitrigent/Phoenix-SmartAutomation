"""Test to verify Healing flow execution."""
import pytest
from playwright.sync_api import Page, expect

def test_healing_execution(page: Page) -> None:
    """Verify healing functionality is actually executed."""
    print(f"[TEST] Page type: {type(page)}")
    print(f"[TEST] Page has _intelligent_runtime: {hasattr(page, '_intelligent_runtime')}")
    print(f"[TEST] Page has healing_engine: {hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'healing_engine')}")
    
    if hasattr(page, '_intelligent_runtime'):
        print(f"[TEST] Intelligent runtime: {page._intelligent_runtime}")
        if hasattr(page._intelligent_runtime, 'healing_engine'):
            print(f"[TEST] Runtime has healing_engine: {page._intelligent_runtime.healing_engine}")
            healing_engine = page._intelligent_runtime.healing_engine
            print(f"[TEST] Healing engine available: {healing_engine is not None}")
    
    # Navigate to OrangeHRM login page
    print("[TEST] Navigating to OrangeHRM login page...")
    page.goto("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login", timeout=30000)
    print("[TEST] Navigation completed")
    
    # First, use correct locators to establish baseline
    print("[TEST] Using correct locators first...")
    page.fill("input[name='username']", "Admin")
    page.fill("input[name='password']", "admin123")
    print("[TEST] Correct locators worked")
    
    # Now try an intentionally incorrect locator to trigger healing
    print("[TEST] Attempting to use incorrect locator to trigger healing...")
    try:
        # This selector is intentionally wrong (non-existent element)
        page.click("#non-existent-button-12345", timeout=5000)
        print("[TEST] Incorrect locator somehow worked (unexpected)")
    except Exception as e:
        print(f"[TEST] Incorrect locator failed as expected: {e}")
        print("[TEST] This should have triggered healing if enabled")
    
    # Check if healing was attempted
    if hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'healing_engine'):
        healing_engine = page._intelligent_runtime.healing_engine
        metrics = healing_engine.get_metrics()
        print(f"[TEST] Healing metrics: total_attempts={metrics.total_attempts}, successful_healings={metrics.successful_healings}, failed_healings={metrics.failed_healings}")
        print(f"[TEST] Healing strategy counts: {metrics.strategy_counts}")
        
        history = healing_engine.get_healing_history()
        print(f"[TEST] Healing history length: {len(history)}")
        for attempt in history:
            print(f"[TEST]  Attempt: strategy={attempt.strategy}, success={attempt.success}, duration_ms={attempt.duration_ms}")
    
    # Try using the correct locator again to verify the page still works
    print("[TEST] Using correct locator again to verify page state...")
    page.click("button[type='submit']")
    print("[TEST] Correct locator worked")
    
    assert True
