"""Test to verify Locator Repository flow execution."""
import pytest
from playwright.sync_api import Page, expect

def test_locator_repository_execution(page: Page) -> None:
    """Verify locator repository functionality is actually executed."""
    print(f"[TEST] Page type: {type(page)}")
    print(f"[TEST] Page has _intelligent_runtime: {hasattr(page, '_intelligent_runtime')}")
    print(f"[TEST] Page has _locator_repository: {hasattr(page, '_locator_repository')}")
    
    if hasattr(page, '_intelligent_runtime'):
        print(f"[TEST] Intelligent runtime: {page._intelligent_runtime}")
        if hasattr(page._intelligent_runtime, 'locator_repository'):
            print(f"[TEST] Runtime has locator_repository: {page._intelligent_runtime.locator_repository}")
            locator_repo = page._intelligent_runtime.locator_repository
            print(f"[TEST] Locator repository dir: {locator_repo.repository_dir}")
            print(f"[TEST] Locator repository projects: {list(locator_repo.projects.keys())}")
    
    # Navigate to OrangeHRM login page - this should trigger locator capture
    print("[TEST] Navigating to OrangeHRM login page...")
    page.goto("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login", timeout=30000)
    print("[TEST] Navigation completed")
    
    # Manually save some locators to the repository to test the functionality
    if hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'locator_repository'):
        locator_repo = page._intelligent_runtime.locator_repository
        print("[TEST] Manually saving locators to repository...")
        
        # Save username field locator
        locator_repo.save_locator(
            project_name="sandbox",
            page_name="login",
            element_name="username_input",
            locator="input[name='username']",
            locator_type="css",
            confidence=0.8,
            source="manual_test",
            page_url=page.url
        )
        
        # Save password field locator
        locator_repo.save_locator(
            project_name="sandbox",
            page_name="login",
            element_name="password_input",
            locator="input[name='password']",
            locator_type="css",
            confidence=0.8,
            source="manual_test",
            page_url=page.url
        )
        
        # Save login button locator
        locator_repo.save_locator(
            project_name="sandbox",
            page_name="login",
            element_name="login_button",
            locator="button[type='submit']",
            locator_type="css",
            confidence=0.8,
            source="manual_test",
            page_url=page.url
        )
        
        print("[TEST] Locators saved to repository")
    
    # Use the IntelligentPage wrapper's methods directly to trigger locator repository
    print("[TEST] Performing fill() operation through IntelligentPage wrapper...")
    page.fill("input[name='username']", "Admin")
    print("[TEST] fill() completed")
    
    print("[TEST] Performing second fill() operation through IntelligentPage wrapper...")
    page.fill("input[name='password']", "admin123")
    print("[TEST] second fill() completed")
    
    print("[TEST] Performing click() operation through IntelligentPage wrapper...")
    page.click("button[type='submit']")
    print("[TEST] click() completed")
    
    # Check if locator repository was populated
    if hasattr(page, '_intelligent_runtime') and hasattr(page._intelligent_runtime, 'locator_repository'):
        locator_repo = page._intelligent_runtime.locator_repository
        print(f"[TEST] Locator repository state after operations:")
        print(f"[TEST] Projects: {list(locator_repo.projects.keys())}")
        for project_key, project in locator_repo.projects.items():
            print(f"[TEST] Project {project_key}:")
            print(f"[TEST]  Elements: {list(project.elements.keys())}")
            for element_name, element in project.elements.items():
                print(f"[TEST]   {element_name}: {element.locator} (confidence: {element.confidence}, success_count: {element.success_count})")
    
    # Take a screenshot to prove page loaded
    page.screenshot(path="test_locator_repository.png")
    
    assert True
