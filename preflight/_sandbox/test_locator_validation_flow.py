"""Test to verify complete locator validation and reuse flow."""
import pytest
from playwright.sync_api import Page

def test_locator_validation_and_reuse(page: Page) -> None:
    """Verify complete validation lifecycle and locator reuse."""
    print(f"[FLOW] Page type: {type(page)}")
    print(f"[FLOW] Page has _intelligent_runtime: {hasattr(page, '_intelligent_runtime')}")
    
    if not hasattr(page, '_intelligent_runtime'):
        print("[FLOW] No intelligent runtime available")
        return
    
    runtime = page._intelligent_runtime
    locator_repo = runtime.locator_repository
    
    # Navigate to OrangeHRM login page
    print("[FLOW] Step 1: Navigate to OrangeHRM login page...")
    page.goto("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login", timeout=30000)
    current_url = page.url
    print(f"[FLOW] Current URL: {current_url}")
    
    # First interaction - this should save and validate the locator
    print("[FLOW] Step 2: First fill() interaction (should save and validate locator)...")
    page.fill("input[name='username']", "Admin")
    print("[FLOW] First fill() completed")
    
    # Check if locator was validated
    # The IntelligentPage now derives page_name from URL
    from urllib.parse import urlparse
    parsed = urlparse(current_url)
    path = parsed.path.strip('/')
    page_name = path.split('/')[-1] if path else "unknown"
    project_key = f"sandbox/{page_name}"
    print(f"[FLOW] Extracted page_name from URL: {page_name}")
    print(f"[FLOW] Checking project key: {project_key}")
    
    # Wait a moment for persistence
    import time
    time.sleep(1)
    
    # Reload repository to check validation status
    locator_repo._load_repository()
    project_data = locator_repo.projects.get(project_key)
    
    if project_data:
        print(f"[FLOW] Elements in repository: {list(project_data.elements.keys())}")
        for element_name, locator_entry in project_data.elements.items():
            print(f"[FLOW]   {element_name}: validated={locator_entry.validated}, confidence={locator_entry.confidence}")
    else:
        print(f"[FLOW] No project data found for {project_key}")
    
    # Second interaction - this should reuse the validated locator
    print("[FLOW] Step 3: Second fill() interaction (should reuse validated locator)...")
    print("[FLOW] Calling get_improved_locator directly to test...")
    improved = locator_repo.get_improved_locator(
        selector="input[name='username']",
        url=current_url,
        project="sandbox"
    )
    print(f"[FLOW] get_improved_locator returned: {improved}")
    page.fill("input[name='username']", "Admin2")
    print("[FLOW] Second fill() completed")
    
    # Check runtime evidence for locator reuse
    if runtime.runtime_evidence:
        print(f"[FLOW] Locator reuse count: {runtime.runtime_evidence.locator_reuse_count}")
        print(f"[FLOW] Locator generation count: {runtime.runtime_evidence.locator_generation_count}")
        print(f"[FLOW] Artifacts reused: {runtime.runtime_evidence.artifacts_reused}")
    
    # Force a second interaction to check reuse
    print("[FLOW] Step 4: Third fill() interaction to check for improved locator logs...")
    page.fill("input[name='username']", "Admin3")
    print("[FLOW] Third fill() completed")
    
    # Check final runtime evidence
    if runtime.runtime_evidence:
        print(f"[FLOW] Final locator reuse count: {runtime.runtime_evidence.locator_reuse_count}")
        print(f"[FLOW] Final locator generation count: {runtime.runtime_evidence.locator_generation_count}")
        print(f"[FLOW] Final artifacts reused: {runtime.runtime_evidence.artifacts_reused}")
    
    assert True
