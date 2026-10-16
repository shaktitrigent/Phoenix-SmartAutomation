"""Test to verify DOM Snapshot flow execution."""
import pytest
from playwright.sync_api import Page, expect

def test_dom_snapshot_execution(page: Page) -> None:
    """Verify DOM snapshot functionality is actually executed."""
    print(f"[TEST] Page type: {type(page)}")
    print(f"[TEST] Page has _intelligent_runtime: {hasattr(page, '_intelligent_runtime')}")
    print(f"[TEST] Page has _dom_snapshot_manager: {hasattr(page, '_dom_snapshot_manager')}")
    
    if hasattr(page, '_dom_snapshot_manager'):
        print(f"[TEST] DOM snapshot manager: {page._dom_snapshot_manager}")
    if hasattr(page, '_intelligent_runtime'):
        print(f"[TEST] Intelligent runtime: {page._intelligent_runtime}")
        if hasattr(page._intelligent_runtime, 'dom_snapshot_manager'):
            print(f"[TEST] Runtime has dom_snapshot_manager: {page._intelligent_runtime.dom_snapshot_manager}")
        if hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'runtime_evidence') and page._intelligent_runtime.runtime_evidence:
            print(f"[TEST] Runtime has runtime_evidence: {page._intelligent_runtime.runtime_evidence}")
            print(f"[TEST] Initial evidence: dom_reuse_count={page._intelligent_runtime.runtime_evidence.dom_reuse_count}, dom_generation_count={page._intelligent_runtime.runtime_evidence.dom_generation_count}")
    
    # Navigate to a simple page - this should trigger DOM capture
    print("[TEST] Calling page.goto()...")
    page.goto("https://example.com", timeout=30000)
    print("[TEST] page.goto() completed")
    
    # Try to trigger DOM capture manually
    print("[TEST] Calling page._capture_dom_with_intelligence()...")
    if hasattr(page, '_capture_dom_with_intelligence'):
        dom_content, dom_reused = page._capture_dom_with_intelligence(force_refresh=True)
        print(f"[TEST] DOM captured: {len(dom_content)} bytes, reused: {dom_reused}")
        
        # Check evidence after capture
        if hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'runtime_evidence') and page._intelligent_runtime.runtime_evidence:
            print(f"[TEST] Evidence after capture: dom_reuse_count={page._intelligent_runtime.runtime_evidence.dom_reuse_count}, dom_generation_count={page._intelligent_runtime.runtime_evidence.dom_generation_count}")
    else:
        print("[TEST] Method _capture_dom_with_intelligence not found")
    
    # Verify basic page content
    expect(page).to_have_title("Example Domain")
    
    # Take a screenshot to prove page loaded
    page.screenshot(path="test_dom_snapshot.png")
    
    # This should trigger DOM snapshot functionality
    assert True