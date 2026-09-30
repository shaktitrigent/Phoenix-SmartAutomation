"""Real Browser Verification Test for Priority 32 Audit.

This test performs actual browser execution with example.com to verify:
- Browser launch
- Page navigation
- DOM capture
- Element interaction
- Evidence collection
"""

import pytest
from playwright.sync_api import sync_playwright


def test_real_browser_launch_headless():
    """Test real browser launch in headless mode."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to example.com
        page.goto("https://example.com")
        
        # Verify page loaded
        title = page.title()
        assert title == "Example Domain"
        
        # Capture DOM
        dom_content = page.content()
        assert "<h1>Example Domain</h1>" in dom_content
        
        # Find elements
        h1 = page.query_selector("h1")
        assert h1 is not None
        assert h1.inner_text() == "Example Domain"
        
        # Get page URL
        url = page.url
        assert url == "https://example.com/"
        
        browser.close()
        
    print("[VERIFIED] Real browser headless execution")


def test_real_browser_launch_headed():
    """Test real browser launch in headed mode."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Navigate to example.com
        page.goto("https://example.com")
        
        # Verify page loaded
        title = page.title()
        assert title == "Example Domain"
        
        # Capture DOM
        dom_content = page.content()
        assert "<h1>Example Domain</h1>" in dom_content
        
        # Find elements
        h1 = page.query_selector("h1")
        assert h1 is not None
        assert h1.inner_text() == "Example Domain"
        
        # Screenshot for visual verification
        page.screenshot(path="headed_browser_verification.png")
        
        browser.close()
        
    print("[VERIFIED] Real browser headed execution")


def test_dom_capture_and_evidence():
    """Test DOM capture and evidence collection."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto("https://example.com")
        
        # Collect DOM evidence
        evidence = {
            "url": page.url,
            "title": page.title(),
            "dom_content": page.content(),
            "text_content": page.inner_text("body"),
            "elements": [],
        }
        
        # Extract key elements
        for selector in ["h1", "p", "a"]:
            elements = page.query_selector_all(selector)
            for el in elements:
                evidence["elements"].append({
                    "tag": selector,
                    "text": el.inner_text()[:50],
                    "href": el.get_attribute("href") if selector == "a" else None,
                })
        
        browser.close()
        
        # Verify evidence
        assert evidence["url"] == "https://example.com/"
        assert evidence["title"] == "Example Domain"
        assert len(evidence["elements"]) > 0
        assert any(el["tag"] == "h1" for el in evidence["elements"])
        
        print("[VERIFIED] DOM capture and evidence collection")


def test_element_interaction():
    """Test actual element interaction."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto("https://example.com")
        
        # Find and click the link
        link = page.query_selector("a")
        assert link is not None
        
        # Get link text and href
        link_text = link.inner_text()
        link_href = link.get_attribute("href")
        
        # The link text might vary, just verify it exists
        assert link_text is not None and len(link_text) > 0
        assert link_href is not None and "iana.org" in link_href
        
        # Click the link
        with page.expect_navigation():
            link.click()
        
        # Verify navigation
        assert "iana.org" in page.url
        
        browser.close()
        
    print("[VERIFIED] Element interaction")


if __name__ == "__main__":
    print("Running Real Browser Verification Tests...")
    print("=" * 60)
    
    try:
        test_real_browser_launch_headless()
        test_dom_capture_and_evidence()
        test_element_interaction()
        print("\nNote: headed test requires visual verification")
        print("Run: pytest test_real_browser_verification.py::test_real_browser_launch_headed -v -s")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] ALL REAL BROWSER TESTS PASSED")
    except Exception as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        raise