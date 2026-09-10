"""Root conftest.py for Phoenix runtime demo tests."""

import json
import os
from contextlib import suppress
from pathlib import Path

import pytest

# Phoenix runtime integration
try:
    from phoenix.execution.runtime_wrapper import get_runtime_integration, print_runtime_summary
    PHOENIX_RUNTIME_AVAILABLE = True
except ImportError:
    PHOENIX_RUNTIME_AVAILABLE = False

# Phoenix Intelligent Runtime integration
try:
    from phoenix.execution.intelligent_runtime import IntelligentRuntime
    from phoenix.execution.intelligent_page import create_intelligent_page
    INTELLIGENT_RUNTIME_AVAILABLE = True
except ImportError:
    INTELLIGENT_RUNTIME_AVAILABLE = False

# Phoenix Priority 25 Execution Intelligence integration
try:
    from phoenix.execution.runtime_intelligence_integration import (
        RuntimeIntelligenceIntegrator,
        create_intelligent_page_with_intelligence,
    )
    PRIORITY25_AVAILABLE = True
except ImportError:
    PRIORITY25_AVAILABLE = False

# Global variable to store intelligent_runtime instance for session finish hook
_intelligent_runtime_instance = None


# ---------------------------------------------------------------------------
# Base URL fixture for root tests
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url(request) -> str:
    return request.config.getoption("--base-url", default=None) or BASE_URL


# ---------------------------------------------------------------------------
# Page fixture override for automatic intelligent integration
# ---------------------------------------------------------------------------

@pytest.fixture
def page(context, intelligent_runtime, request):
    """Playwright Page fixture with automatic Phoenix Intelligent Runtime integration.

    This fixture overrides pytest-playwright's page fixture to automatically wrap
    with Phoenix intelligence when IntelligentRuntime is available.

    Note: This requires pytest-playwright to provide the 'context' fixture.
    """
    print("[PHOENIX] Page fixture: Starting creation")
    p = context.new_page()
    p.set_default_timeout(30000)
    p.set_default_navigation_timeout(60000)
    p.on("dialog", lambda dialog: dialog.dismiss())

    print(f"[PHOENIX] Page fixture type: {type(p).__name__}")
    print(f"[PHOENIX] IntelligentRuntime available: {intelligent_runtime is not None}")
    print(f"[PHOENIX] INTELLIGENT_RUNTIME_AVAILABLE: {INTELLIGENT_RUNTIME_AVAILABLE}")

    # Wrap with Phoenix intelligence if available
    if intelligent_runtime and INTELLIGENT_RUNTIME_AVAILABLE:
        try:
            test_name = request.node.name if hasattr(request, 'node') else "unknown"
            project_name = intelligent_runtime.project_name
            execution_id = intelligent_runtime.execution_id or "unknown"

            print(f"[PHOENIX] Creating IntelligentPage for test: {test_name}")
            print(f"[PHOENIX] Project: {project_name}")
            print(f"[PHOENIX] Execution ID: {execution_id}")

            wrapped_page = create_intelligent_page(
                page=p,
                intelligent_runtime=intelligent_runtime,
                project_name=project_name,
                test_name=test_name,
                execution_id=execution_id
            )

            print(f"[PHOENIX] Intelligent Page: ENABLED (automatic integration)")
            print(f"[PHOENIX] Wrapped page type: {type(wrapped_page).__name__}")
            yield wrapped_page
        except Exception as e:
            print(f"[PHOENIX] Failed to create intelligent page, using standard page: {e}")
            import traceback
            traceback.print_exc()
            yield p
    else:
        print("[PHOENIX] Using standard Playwright page (no intelligent runtime)")
        yield p

    with suppress(Exception):
        p.close()


# ---------------------------------------------------------------------------
# Phoenix Runtime fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def phoenix_runtime():
    """Phoenix runtime integration for enterprise subsystem visibility."""
    if PHOENIX_RUNTIME_AVAILABLE:
        return get_runtime_integration()
    return None


@pytest.fixture(scope="session")
def intelligent_runtime():
    """IntelligentRuntime instance for production test execution.
    
    This fixture loads the IntelligentRuntime state that was created by
    TestRunner before spawning the pytest subprocess. The state is stored
    in phoenix_runtime/.execution_context.json.
    
    This fixture is automatically available to all project-specific conftest.py files
    and ensures intelligent runtime integration happens transparently.
    """
    global _intelligent_runtime_instance
    
    if not INTELLIGENT_RUNTIME_AVAILABLE:
        print("[INTELLIGENT RUNTIME] Intelligent Runtime not available - imports failed")
        return None
    
    # Use absolute path to ensure consistent location
    import os
    current_dir = Path(os.getcwd())
    # Use the main project directory's phoenix_runtime for evidence tracking
    # This ensures that the evidence file is in the main phoenix_runtime directory
    # where TestRunner will look for it
    # Go up to find the main project directory (Phoenix-SmartAutomation)
    parent_dir = current_dir
    while parent_dir.name != "Phoenix-SmartAutomation" and parent_dir.parent != parent_dir:
        parent_dir = parent_dir.parent
    base_dir = parent_dir / "phoenix_runtime"
    
    print(f"[INTELLIGENT RUNTIME] Current working directory: {current_dir}")
    print(f"[INTELLIGENT RUNTIME] Base directory: {base_dir}")
    print(f"[INTELLIGENT RUNTIME] Base directory resolved to: {base_dir.absolute()}")
    
    # Try to load execution context from TestRunner
    execution_context_path = base_dir / ".execution_context.json"
    
    print(f"[INTELLIGENT RUNTIME] Execution context path: {execution_context_path}")
    print(f"[INTELLIGENT RUNTIME] Execution context exists: {execution_context_path.exists()}")
    
    if execution_context_path.exists():
        try:
            with open(execution_context_path, 'r', encoding='utf-8') as f:
                context = json.load(f)
            
            execution_id = context.get("execution_id")
            project_name = context.get("project_name", "default")
            enable_intelligent = context.get("enable_intelligent_runtime", True)
            enable_healing = context.get("enable_healing", True)
            
            if not enable_intelligent:
                print("[INTELLIGENT RUNTIME] Intelligent Runtime disabled in execution context")
                return None
            
            # Recreate IntelligentRuntime with the same configuration
            intelligent_runtime = IntelligentRuntime(
                base_dir=str(base_dir),
                project_name=project_name,
                enable_cache=True,
                enable_repository=True,
                enable_diff=True,
                enable_healing=enable_healing,
                enable_metrics=True,
                enable_timeline=True
            )
            
            # Restore execution state
            intelligent_runtime.execution_id = execution_id
            intelligent_runtime.test_name = context.get("test_name", "default")
            
            # Start execution tracking with the existing execution ID
            intelligent_runtime.start_execution(intelligent_runtime.test_name)
            
            # Store globally for session finish hook
            _intelligent_runtime_instance = intelligent_runtime
            
            print(f"[INTELLIGENT RUNTIME] Loaded from execution context: {execution_id}")
            print(f"[INTELLIGENT RUNTIME] Project: {project_name}")
            print(f"[INTELLIGENT RUNTIME] Intelligent Runtime enabled and ready")
            
            return intelligent_runtime
            
        except Exception as e:
            print(f"[INTELLIGENT RUNTIME] Failed to load execution context: {e}")
            return None
    
    # Fallback: create new IntelligentRuntime instance if phoenix_runtime exists
    if base_dir.exists():
        print("[INTELLIGENT RUNTIME] No execution context found, creating new instance")
        try:
            intelligent_runtime = IntelligentRuntime(
                base_dir=str(base_dir),
                project_name="default",
                enable_cache=True,
                enable_repository=True,
                enable_diff=True,
                enable_healing=True,
                enable_metrics=True,
                enable_timeline=True
            )
            
            # Start execution tracking
            intelligent_runtime.start_execution("default")
            
            # Store globally for session finish hook
            _intelligent_runtime_instance = intelligent_runtime
            
            print("[INTELLIGENT RUNTIME] Created new IntelligentRuntime instance")
            return intelligent_runtime
        except Exception as e:
            print(f"[INTELLIGENT RUNTIME] Failed to create IntelligentRuntime: {e}")
            return None
    
    print("[INTELLIGENT RUNTIME] No phoenix_runtime directory found, Intelligent Runtime disabled")
    return None


@pytest.fixture(scope="function")
def intelligent_page(page, intelligent_runtime, request):
    """Playwright Page wrapper with IntelligentRuntime integration.
    
    This fixture wraps the standard Playwright page with intelligent
    decision-making for DOM reuse, MCP calls, locator healing, and
    runtime evidence collection.
    
    Now includes Priority 25 execution intelligence integration.
    
    Usage in tests:
        def test_example(intelligent_page):
            intelligent_page.goto("https://example.com")
            intelligent_page.click("#submit")
    """
    if not intelligent_runtime:
        # If IntelligentRuntime is not available, return standard page
        return page
    
    # Get test name from request node
    test_name = request.node.name if hasattr(request, 'node') else "unknown"
    project_name = intelligent_runtime.project_name
    execution_id = intelligent_runtime.execution_id or "unknown"
    
    # Create intelligent page wrapper with Priority 25 integration
    if PRIORITY25_AVAILABLE:
        wrapped_page = create_intelligent_page_with_intelligence(
            page=page,
            intelligent_runtime=intelligent_runtime,
            project_name=project_name,
            test_name=test_name,
            execution_id=execution_id
        )
        print("[PHOENIX] Priority 25 Execution Intelligence: ENABLED")
    else:
        # Fallback to standard intelligent page
        wrapped_page = create_intelligent_page(
            page=page,
            intelligent_runtime=intelligent_runtime,
            project_name=project_name,
            test_name=test_name,
            execution_id=execution_id
        )
        print("[PHOENIX] Priority 25 Execution Intelligence: NOT AVAILABLE")
    
    return wrapped_page


# Note: The standard 'page' fixture is provided by pytest-playwright
# We override it here to provide automatic intelligent integration for all tests
# Projects can still provide their own page fixture in project-specific conftest.py


@pytest.fixture
def page(context, intelligent_runtime, request):
    """Playwright Page fixture with automatic Phoenix Intelligent Runtime integration.

    This fixture automatically wraps the standard Playwright page with Phoenix intelligence
    when IntelligentRuntime is available, ensuring DOM reuse, locator healing, and
    runtime evidence collection happen automatically for all tests.

    When IntelligentRuntime is not available, returns a standard Playwright page for
    backward compatibility.
    """
    print("[PHOENIX] Page fixture: Starting creation")
    p = context.new_page()
    p.set_default_timeout(30000)
    p.set_default_navigation_timeout(60000)
    p.on("dialog", lambda dialog: dialog.dismiss())

    print(f"[PHOENIX] Page fixture type: {type(p).__name__}")
    print(f"[PHOENIX] IntelligentRuntime available: {intelligent_runtime is not None}")
    print(f"[PHOENIX] INTELLIGENT_RUNTIME_AVAILABLE: {INTELLIGENT_RUNTIME_AVAILABLE}")

    # Wrap with Phoenix intelligence if available
    if intelligent_runtime and INTELLIGENT_RUNTIME_AVAILABLE:
        try:
            test_name = request.node.name if hasattr(request, 'node') else "unknown"
            project_name = intelligent_runtime.project_name
            execution_id = intelligent_runtime.execution_id or "unknown"

            print(f"[PHOENIX] Creating IntelligentPage for test: {test_name}")
            print(f"[PHOENIX] Project: {project_name}")
            print(f"[PHOENIX] Execution ID: {execution_id}")

            wrapped_page = create_intelligent_page(
                page=p,
                intelligent_runtime=intelligent_runtime,
                project_name=project_name,
                test_name=test_name,
                execution_id=execution_id
            )

            print(f"[PHOENIX] Intelligent Page: ENABLED (automatic integration)")
            print(f"[PHOENIX] Wrapped page type: {type(wrapped_page).__name__}")
            yield wrapped_page
        except Exception as e:
            print(f"[PHOENIX] Failed to create intelligent page, using standard page: {e}")
            import traceback
            traceback.print_exc()
            yield p
    else:
        print("[PHOENIX] Using standard Playwright page (no intelligent runtime)")
        yield p

    with suppress(Exception):
        p.close()


def pytest_sessionfinish(session, exitstatus):
    """Print Phoenix runtime summary at the end of test session."""
    print("[PHOENIX] pytest_sessionfinish invoked")
    print("[PHOENIX] Ending intelligent runtime")
    
    # Call IntelligentRuntime end_execution to save evidence
    global _intelligent_runtime_instance
    if _intelligent_runtime_instance:
        try:
            status = "passed" if exitstatus == 0 else "failed"
            print(f"[PHOENIX] Session status: {status}")
            _intelligent_runtime_instance.end_execution(status=status)
            print(f"[INTELLIGENT RUNTIME] Saved execution evidence with status: {status}")
            
            # Print final summary
            print("\n========== PHOENIX DOM INTELLIGENCE SUMMARY ==========")
            print(f"Session Status: {status}")
            print(f"Execution ID: {_intelligent_runtime_instance.execution_id}")
            print(f"Project: {_intelligent_runtime_instance.project_name}")
            print(f"Test: {_intelligent_runtime_instance.test_name}")
            
            if _intelligent_runtime_instance.runtime_evidence:
                print(f"\nDOM Snapshot: EXECUTED")
                print(f"DOM Cache: EXECUTED")
                print(f"DOM Generated: {_intelligent_runtime_instance.runtime_evidence.dom_generation_count}")
                print(f"DOM Reused: {_intelligent_runtime_instance.runtime_evidence.dom_reuse_count}")
                print(f"Cache Hits: {_intelligent_runtime_instance.runtime_evidence.cache_hits}")
                print(f"Cache Misses: {_intelligent_runtime_instance.runtime_evidence.cache_misses}")
                print(f"Cache Hit Ratio: {_intelligent_runtime_instance.runtime_evidence.cache_hit_ratio:.2f}")
                print(f"Time Saved: {_intelligent_runtime_instance.runtime_evidence.time_saved_ms:.2f}ms")
                print(f"MCP Calls Saved: {_intelligent_runtime_instance.runtime_evidence.mcp_calls_saved}")
            else:
                print(f"\nDOM Snapshot: NOT EXECUTED")
                print(f"DOM Cache: NOT EXECUTED")
            
            print("===================================================\n")
            
        except Exception as e:
            print(f"[INTELLIGENT RUNTIME] Failed to end execution: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[PHOENIX] No intelligent runtime instance to end")
    
    if PHOENIX_RUNTIME_AVAILABLE:
        print_runtime_summary()
