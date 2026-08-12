"""Minimal test to verify Locator Repository execution.

This test uses the intelligent_page wrapper to trigger:
- locator generation (save new locators)
- locator repository lookup/reuse
- proper tracking of locator_generation_count and locator_reuse_count
"""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent / "phoenix-core"))

from playwright.sync_api import sync_playwright
from phoenix.execution.intelligent_runtime import IntelligentRuntime
from phoenix.execution.intelligent_page import create_intelligent_page

print("=" * 60)
print("Locator Repository Verification Test")
print("=" * 60)

# Initialize IntelligentRuntime with Locator Repository enabled
print("[SETUP] Initializing IntelligentRuntime with Locator Repository...")
intelligent_runtime = IntelligentRuntime(
    base_dir="phoenix_runtime",
    project_name="locator_repo_test",
    enable_cache=True,
    enable_repository=True,  # Enable Locator Repository
    enable_diff=True,
    enable_healing=True,
    enable_metrics=True,
    enable_timeline=True
)

print("[SETUP] Starting execution...")
execution_id = intelligent_runtime.start_execution("locator_repository_test")
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
            project_name="locator_repo_test",
            test_name="locator_repository_test",
            execution_id=execution_id
        )
        
        # Navigate to a simple page
        print("[TEST] Navigating to example.com...")
        intelligent_page.goto("https://example.com")
        
        # First click - should trigger locator generation
        print("[TEST] First click - should trigger locator generation...")
        intelligent_page.click("a")  # Click a link
        
        # Second click on same selector - should trigger locator reuse
        print("[TEST] Second click - should trigger locator reuse...")
        intelligent_page.click("a")  # Click another link with same selector pattern
        
        print("[TEST] Test completed successfully")
        
        browser.close()
        
except Exception as e:
    print(f"[ERROR] Test failed: {e}")
    raise

# End execution and get evidence
print("[CLEANUP] Ending execution...")
intelligent_runtime.end_execution(status="passed")

# Print summary
print("\n" + "=" * 60)
print("Locator Repository Evidence")
print("=" * 60)

evidence = intelligent_runtime.runtime_evidence
print(f"Locator Generation Count: {evidence.locator_generation_count}")
print(f"Locator Reuse Count: {evidence.locator_reuse_count}")
print(f"Locator Reuse Ratio: {evidence.locator_reuse_ratio:.1%}")

print("\nArtifacts Created:")
for artifact in evidence.artifacts_created:
    print(f"  - {artifact}")

print("\nArtifacts Reused:")
for artifact in evidence.artifacts_reused:
    print(f"  - {artifact}")

# Check repository files
print("\n" + "=" * 60)
print("Locator Repository Files")
print("=" * 60)
repo_dir = Path("phoenix_runtime/locators")
if repo_dir.exists():
    for project_dir in repo_dir.iterdir():
        if project_dir.is_dir():
            print(f"Project: {project_dir.name}")
            for locator_file in project_dir.glob("*.json"):
                print(f"  Page: {locator_file.stem}")
                print(f"  File: {locator_file}")
else:
    print("No locator repository files found")

print("\n" + "=" * 60)
print("Verification Complete")
print("=" * 60)
