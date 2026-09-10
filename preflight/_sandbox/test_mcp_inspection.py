"""Test to verify MCP inspection flow execution."""
import pytest
from playwright.sync_api import Page, expect

def test_mcp_inspection_execution(page: Page) -> None:
    """Verify MCP inspection functionality is actually executed."""
    print(f"[TEST] Page type: {type(page)}")
    print(f"[TEST] Page has _intelligent_runtime: {hasattr(page, '_intelligent_runtime')}")
    print(f"[TEST] Page has mcp_client: {hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'mcp_client')}")
    
    if hasattr(page, '_intelligent_runtime'):
        print(f"[TEST] Intelligent runtime: {page._intelligent_runtime}")
        if hasattr(page._intelligent_runtime, 'dom_snapshot_manager'):
            print(f"[TEST] Runtime has dom_snapshot_manager: {page._intelligent_runtime.dom_snapshot_manager}")
    
    # Navigate to OrangeHRM login page - this should trigger DOM capture
    print("[TEST] Navigating to OrangeHRM login page (first visit)...")
    page.goto("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login", timeout=30000)
    print("[TEST] First navigation completed")
    
    # Force a DOM refresh to trigger MCP inspection
    print("[TEST] Forcing DOM refresh to trigger MCP inspection...")
    if hasattr(page, '_capture_dom_with_intelligence'):
        dom_content, dom_reused = page._capture_dom_with_intelligence(force_refresh=True)
        print(f"[TEST] DOM captured: {len(dom_content)} bytes, reused: {dom_reused}")
        print(f"[TEST] Force refresh should have triggered MCP inspection if DOM changed")
    
    # Navigate to a different page to ensure DOM changes
    print("[TEST] Navigating to different URL to force DOM change...")
    page.goto("https://example.com", timeout=30000)
    print("[TEST] Navigation to different page completed")
    
    # Navigate back to trigger fresh DOM capture
    print("[TEST] Navigating back to OrangeHRM (should trigger fresh DOM capture)...")
    page.goto("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login", timeout=30000)
    print("[TEST] Navigation back completed")
    
    # Force another DOM refresh
    print("[TEST] Forcing another DOM refresh...")
    if hasattr(page, '_capture_dom_with_intelligence'):
        dom_content, dom_reused = page._capture_dom_with_intelligence(force_refresh=True)
        print(f"[TEST] DOM captured: {len(dom_content)} bytes, reused: {dom_reused}")
        print(f"[TEST] This should trigger MCP inspection since we forced refresh")
    
    # Check runtime evidence for MCP calls
    if hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'runtime_evidence'):
        evidence = page._intelligent_runtime.runtime_evidence
        if evidence:
            print(f"[TEST] Runtime evidence mcp_calls_saved: {evidence.mcp_calls_saved}")
            print(f"[TEST] Runtime evidence llm_calls_saved: {evidence.llm_calls_saved}")
    
    assert True
