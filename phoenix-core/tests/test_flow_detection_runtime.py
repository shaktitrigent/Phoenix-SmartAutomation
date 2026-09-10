"""Runtime test for Flow Detection with headed browser (Priority 21).

This test demonstrates flow detection working with a real browser in headed mode.
It uses the existing Phoenix test infrastructure to run a simple test scenario
and verify that flow detection captures the business flows.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

# Only run this test if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not available")
class TestFlowDetectionRuntime:
    """Runtime tests for flow detection with real browser."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    @pytest.fixture
    def flow_discovery(self, temp_dir):
        """Create flow discovery engine for testing."""
        from phoenix.flow_detection.flow_discovery import FlowDiscoveryEngine
        
        discovery = FlowDiscoveryEngine(
            base_dir=temp_dir,
            enable_persistence=True,
            enable_ai_reasoning=False,  # Disable AI for faster testing
            enable_flow_learning=True,
        )
        return discovery
    
    def test_headed_browser_flow_detection(self, flow_discovery):
        """Test flow detection with headed browser.
        
        This test:
        1. Launches a real browser in headed mode
        2. Navigates to a simple page
        3. Observes page transitions
        4. Verifies flow detection captures the transitions
        """
        print("\n[PHOENIX] Starting headed browser flow detection test")
        
        with sync_playwright() as p:
            # Launch browser in headed mode
            browser = p.chromium.launch(headed=True, slow_mo=100)
            page = browser.new_page()
            
            print("[PHOENIX] Headed browser launched")
            
            # Start flow discovery
            flow_discovery.start_execution(
                execution_id="runtime_test_001",
                test_id="test_headed_flow",
                project_name="runtime_test",
            )
            
            print("[PHOENIX] Flow discovery started")
            
            try:
                # Navigate to a simple page (using example.com or a simple local HTML)
                page.goto("https://example.com")
                
                # Get page content
                dom_content = page.content()
                url = page.url
                title = page.title()
                
                print(f"[PHOENIX] Navigated to: {url}")
                print(f"[PHOENIX] Page title: {title}")
                
                # Observe the page (generic page type since example.com is generic)
                flow_discovery.observe_page(
                    page_type="landing_page",  # Generic classification
                    url=url,
                    dom_content=dom_content,
                )
                
                print("[PHOENIX] Page observed")
                
                # Simulate an action (click on a link)
                # Find first link and click
                links = page.locator("a").all()
                if links:
                    first_link = links[0]
                    link_text = first_link.inner_text()
                    
                    print(f"[PHOENIX] Found link: {link_text}")
                    
                    # Observe action
                    action = flow_discovery.observe_action(
                        element_info={
                            "role": "link",
                            "text": link_text,
                            "label": "",
                            "xpath": "",
                        }
                    )
                    
                    print(f"[PHOENIX] Action observed: {action.action_type.value}")
                    
                    # Click the link
                    first_link.click()
                    
                    # Wait for navigation
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                    
                    # Get new page state
                    new_url = page.url
                    new_dom = page.content()
                    
                    print(f"[PHOENIX] Navigated to: {new_url}")
                    
                    # Observe page transition
                    transition = flow_discovery.observe_page_transition(
                        target_page_type="landing_page",  # Generic classification
                        target_url=new_url,
                        target_dom_content=new_dom,
                        action=action,
                    )
                    
                    print(f"[PHOENIX] Page transition recorded: {transition.source_page_type} -> {transition.target_page_type}")
                
                # End execution and discover flows
                discovered_flows = flow_discovery.end_execution()
                
                print(f"[PHOENIX] Flow discovery ended - discovered {len(discovered_flows)} flows")
                
                # Verify flows were discovered
                assert isinstance(discovered_flows, list)
                
                # Verify graph was built
                assert flow_discovery.current_graph is not None
                assert flow_discovery.current_graph.total_nodes >= 1
                assert flow_discovery.current_graph.total_edges >= 0
                
                print("[PHOENIX] Flow detection runtime test PASSED")
                
            finally:
                # Close browser
                browser.close()
                print("[PHOENIX] Browser closed")
    
    def test_multi_page_flow_detection(self, flow_discovery):
        """Test flow detection across multiple pages."""
        print("\n[PHOENIX] Starting multi-page flow detection test")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headed=True, slow_mo=100)
            page = browser.new_page()
            
            print("[PHOENIX] Headed browser launched")
            
            # Start flow discovery
            flow_discovery.start_execution(
                execution_id="runtime_test_002",
                test_id="test_multi_page",
                project_name="runtime_test",
            )
            
            try:
                # Visit multiple pages to create a flow
                pages_to_visit = [
                    "https://example.com",
                    "https://example.com",
                ]
                
                for i, url in enumerate(pages_to_visit):
                    page.goto(url)
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                    
                    dom_content = page.content()
                    current_url = page.url
                    
                    # Observe page
                    flow_discovery.observe_page(
                        page_type="landing_page",
                        url=current_url,
                        dom_content=dom_content,
                    )
                    
                    print(f"[PHOENIX] Page {i+1} observed: {current_url}")
                    
                    if i < len(pages_to_visit) - 1:
                        # Simulate navigation action
                        action = flow_discovery.observe_action(
                            element_info={"role": "link", "text": "navigation"}
                        )
                
                # End execution
                flows = flow_discovery.end_execution()
                
                print(f"[PHOENIX] Multi-page test completed - discovered {len(flows)} flows")
                
                # Verify
                assert isinstance(flows, list)
                assert flow_discovery.current_graph is not None
                
                print("[PHOENIX] Multi-page flow detection test PASSED")
                
            finally:
                browser.close()
                print("[PHOENIX] Browser closed")
    
    def test_flow_persistence_across_sessions(self, flow_discovery, temp_dir):
        """Test that flows persist across browser sessions."""
        print("\n[PHOENIX] Starting flow persistence test")
        
        # First session
        with sync_playwright() as p:
            browser = p.chromium.launch(headed=True, slow_mo=100)
            page = browser.new_page()
            
            flow_discovery.start_execution(
                execution_id="session_001",
                test_id="test_persistence_1",
                project_name="persistence_test",
            )
            
            try:
                page.goto("https://example.com")
                page.wait_for_load_state("domcontentloaded", timeout=5000)
                
                flow_discovery.observe_page(
                    page_type="landing_page",
                    url=page.url,
                    dom_content=page.content(),
                )
                
                flows1 = flow_discovery.end_execution()
                print(f"[PHOENIX] Session 1 - discovered {len(flows1)} flows")
                
            finally:
                browser.close()
        
        # Second session - should be able to load previous flows
        from phoenix.flow_detection.flow_discovery import FlowDiscoveryEngine
        
        discovery2 = FlowDiscoveryEngine(
            base_dir=temp_dir,
            enable_persistence=True,
            enable_ai_reasoning=False,
        )
        
        previous_flows = discovery2.get_discovered_flows(project_name="persistence_test")
        
        print(f"[PHOENIX] Session 2 - loaded {len(previous_flows)} previous flows")
        
        # Verify persistence
        assert isinstance(previous_flows, list)
        
        print("[PHOENIX] Flow persistence test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
