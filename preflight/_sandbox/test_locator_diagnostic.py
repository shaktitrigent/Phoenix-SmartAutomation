"""Diagnostic test to understand why get_improved_locator() returns None."""
import pytest
from playwright.sync_api import Page

def test_locator_repository_diagnostic(page: Page) -> None:
    """Diagnostic test to trace exactly why locator reuse fails."""
    print(f"[DIAG] Page type: {type(page)}")
    print(f"[DIAG] Page has _intelligent_runtime: {hasattr(page, '_intelligent_runtime')}")
    
    if not hasattr(page, '_intelligent_runtime'):
        print("[DIAG] No intelligent runtime available")
        return
    
    runtime = page._intelligent_runtime
    print(f"[DIAG] Runtime has locator_repository: {hasattr(runtime, 'locator_repository')}")
    
    if not hasattr(runtime, 'locator_repository'):
        print("[DIAG] No locator repository available")
        return
    
    locator_repo = runtime.locator_repository
    print(f"[DIAG] Locator repository projects: {list(locator_repo.projects.keys())}")
    
    # Navigate to OrangeHRM login page
    print("[DIAG] Navigating to OrangeHRM login page...")
    page.goto("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login", timeout=30000)
    current_url = page.url
    print(f"[DIAG] Current URL: {current_url}")
    
    # Save some locators manually
    print("[DIAG] Saving test locators...")
    locator_repo.save_locator(
        project_name="sandbox",
        page_name="login",
        element_name="username_input",
        locator="input[name='username']",
        locator_type="css",
        confidence=0.8,
        source="manual_test",
        page_url=current_url
    )
    
    # Now try to get improved locator
    print("[DIAG] Testing get_improved_locator()...")
    selector = "input[name='username']"
    
    # Call the function with diagnostic logging
    print(f"[DIAG] Calling get_improved_locator with:")
    print(f"[DIAG]   selector: {selector}")
    print(f"[DIAG]   url: {current_url}")
    print(f"[DIAG]   project: sandbox")
    
    # Manually trace through the logic
    print("[DIAG] Manual trace of get_improved_locator logic:")
    
    # Extract page name
    from urllib.parse import urlparse
    parsed = urlparse(current_url)
    path = parsed.path.strip('/')
    page_name = path.split('/')[-1] if path else "sandbox"
    print(f"[DIAG] Extracted page_name: {page_name}")
    
    # Get project key
    project_key = f"sandbox/{page_name}"
    print(f"[DIAG] Project key: {project_key}")
    
    # Get project data
    project_data = locator_repo.projects.get(project_key)
    print(f"[DIAG] Project data exists: {project_data is not None}")
    
    if project_data:
        print(f"[DIAG] Elements in project: {list(project_data.elements.keys())}")
        
        for element_name, locator_entry in project_data.elements.items():
            print(f"[DIAG] Checking element: {element_name}")
            print(f"[DIAG]   locator: {locator_entry.locator}")
            print(f"[DIAG]   confidence: {locator_entry.confidence}")
            print(f"[DIAG]   validated: {locator_entry.validated}")
            print(f"[DIAG]   page_url: {locator_entry.page_url}")
            print(f"[DIAG]   URL match: {locator_entry.page_url == current_url}")
            
            # Check the condition
            min_confidence = 0.7
            confidence_ok = locator_entry.confidence >= min_confidence
            validated_ok = locator_entry.validated
            url_match = locator_entry.page_url == current_url
            
            print(f"[DIAG]   Confidence >= 0.7: {confidence_ok}")
            print(f"[DIAG]   Validated: {validated_ok}")
            print(f"[DIAG]   URL match: {url_match}")
            
            if confidence_ok and validated_ok and url_match:
                print(f"[DIAG]   [SUCCESS] WOULD RETURN: {locator_entry.locator}")
            else:
                print(f"[DIAG]   [BLOCKED] BY: {'confidence' if not confidence_ok else 'validated' if not validated_ok else 'URL'}")
    
    # Actually call the function
    result = locator_repo.get_improved_locator(
        selector=selector,
        url=current_url,
        project="sandbox"
    )
    
    print(f"[DIAG] get_improved_locator() returned: {result}")
    
    assert True
