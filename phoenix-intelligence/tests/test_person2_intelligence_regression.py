"""Person 2 regression tests for phoenix-intelligence.

Covers:
- Locator generation correctness (_semantic_locator_expr)
- Environment variable expression resolution (_resolve_fill_value_expr)
- Compound action splitting (_split_compound_actions)
- Fallback Playwright script building and syntax validation
- Step counting correctness (_count_implemented_steps)
- Fixture selection matching (_needs_authenticated_page)
- Request-scoped MCP client propagation on AgentRegistry
- Server metadata decoration (status, accepted/rejected counts)
- MCP client reliability (isError handling, redaction, evaluate format)
"""

import ast
import json
import pytest
from unittest.mock import MagicMock, patch

from services.agents.test_generator import (
    _semantic_locator_expr,
    _resolve_fill_value_expr,
    _split_compound_actions,
    _needs_authenticated_page,
    _criterion_to_playwright_lines,
    TestGeneratorAgent,
)
from services.agents.registry import AgentRegistry
from services.knowledge.base import KnowledgeBase
from services.cache import Cache
from services.mcp.client import MCPClient, InspectionFailedError, _redact_and_bound, _check_tool_result
from api.server import _decorate_metadata


def test_semantic_locator_expr_does_not_generate_hash_for_plain_labels():
    # Plain field labels should NOT produce page.locator('#Password') or page.locator('#Username')
    pass_expr = _semantic_locator_expr("Password")
    assert 'page.locator("#Password")' not in pass_expr
    assert 'get_by_placeholder("Password"' in pass_expr or 'get_by_label("Password"' in pass_expr or 'get_by_test_id("password")' in pass_expr

    user_expr = _semantic_locator_expr("Username")
    assert 'page.locator("#Username")' not in user_expr
    assert 'get_by_placeholder("Username"' in user_expr or 'get_by_label("Username"' in user_expr or 'get_by_test_id("username")' in user_expr

    # Explicit CSS / ID selectors starting with #, ., [ should be preserved
    explicit_id = _semantic_locator_expr("#user-name")
    assert explicit_id == 'page.locator("#user-name")'

    explicit_class = _semantic_locator_expr(".btn-primary")
    assert explicit_class == 'page.locator(".btn-primary")'

    explicit_attr = _semantic_locator_expr("[data-testid='custom-field']")
    assert explicit_attr == 'page.locator("[data-testid=\'custom-field\']")'


def test_resolve_fill_value_expr():
    # Environment variable tokens
    assert _resolve_fill_value_expr("Username", "TEST_USERNAME") == "os.environ['TEST_USERNAME']"
    assert _resolve_fill_value_expr("Password", "$TEST_PASSWORD") == "os.environ['TEST_PASSWORD']"
    assert _resolve_fill_value_expr("Username", "from environment") == repr("from environment")
    assert _resolve_fill_value_expr("Password", "valid credentials") == repr("valid credentials")

    # Plain string literals
    assert _resolve_fill_value_expr("Email", "user@example.com") == repr("user@example.com")
    assert _resolve_fill_value_expr("Search", "laptop") == repr("laptop")


def test_split_compound_actions():
    compound = "Enter username 'tomsmith' and enter password 'SuperSecretPassword!' and click Login"
    parts = _split_compound_actions(compound)
    assert len(parts) == 3
    assert "Enter username 'tomsmith'" in parts[0]
    assert "enter password 'SuperSecretPassword!'" in parts[1]
    assert "click Login" in parts[2]

    single = "Enter username 'tomsmith'"
    single_parts = _split_compound_actions(single)
    assert len(single_parts) == 1
    assert single_parts[0] == single


def test_criterion_to_playwright_lines_handles_compound_and_env():
    compound = "Enter username TEST_USERNAME and enter password TEST_PASSWORD and click the Login button"
    lines = _criterion_to_playwright_lines(compound, 1, "https://example.com")
    joined = "\n".join(lines)
    assert "os.environ['TEST_USERNAME']" in joined
    assert "os.environ['TEST_PASSWORD']" in joined
    assert "click_ready" in joined


def test_fallback_script_generation_is_valid_python():
    agent = TestGeneratorAgent(
        knowledge_base=MagicMock(spec=KnowledgeBase),
        cache=MagicMock(spec=Cache),
        llm_client=None,
        mcp_client=None,
    )
    manual_test = {
        "name": "Valid Login",
        "description": "User logs into the application",
        "steps": [
            {
                "step_number": 1,
                "action": "Enter username 'standard_user'",
                "expected_result": "Username field contains the value 'standard_user'",
            },
            {
                "step_number": 2,
                "action": "Enter password 'secret_sauce'",
                "expected_result": "Password field contains the value 'secret_sauce'",
            },
            {
                "step_number": 3,
                "action": "Click the Login button",
                "expected_result": "User is redirected to Dashboard and heading is displayed",
            },
        ],
        "expected_result": "User is logged in successfully",
    }
    script = agent._build_fallback_script_from_manual_test(manual_test, "https://example.com/login")
    assert "def test_valid_login" in script
    # Assert it compiles cleanly as valid Python
    compiled = compile(script, "<test>", "exec")
    assert compiled is not None


def test_count_implemented_steps():
    agent = TestGeneratorAgent(
        knowledge_base=MagicMock(spec=KnowledgeBase),
        cache=MagicMock(spec=Cache),
        llm_client=None,
        mcp_client=None,
    )
    script = """
def test_login(page: Page) -> None:
    page.goto("https://example.com")
    fill_ready(page, page.locator("#username"), "user", "username")
    fill_ready(page, page.locator("#password"), "pass", "password")
    click_ready(page, page.locator("#login-btn"), "login")
    expect(page.locator("body")).to_be_visible()
"""
    manual_steps = [
        {"step_number": 1, "action": "Fill in username"},
        {"step_number": 2, "action": "Type in password"},
        {"step_number": 3, "action": "Click login button"},
    ]
    count = agent._count_implemented_steps(script, manual_steps)
    assert count == 3


def test_needs_authenticated_page_intelligence_matching():
    # Login scenario -> False
    assert not _needs_authenticated_page(
        preconditions="User is on login page",
        name="Valid Login",
        description="Login with credentials",
    )
    # Negation -> False
    assert not _needs_authenticated_page(
        preconditions="User is not logged in",
        name="View Landing",
        description="Homepage",
    )
    # Authenticated -> True
    assert _needs_authenticated_page(
        preconditions="User is already logged in",
        name="View Dashboard",
        description="Dashboard view",
    )


def test_agent_registry_mcp_client_property_propagation():
    registry = AgentRegistry(
        knowledge_base=MagicMock(spec=KnowledgeBase),
        cache=MagicMock(spec=Cache),
    )
    mock_mcp = MagicMock(spec=MCPClient)
    registry.mcp_client = mock_mcp
    assert registry.mcp_client == mock_mcp
    assert registry.get_agent("test_generator").mcp_client == mock_mcp
    assert registry.get_agent("locator_expert").mcp_client == mock_mcp


def test_server_decorate_metadata_status_and_counts():
    raw_result = {
        "automation_tests": [
            {
                "script_code": "def test_ok(): pass",
                "warnings": ["Sample warning"],
                "recommendations": ["Invalid locators rejected: - old_btn: Not found in DOM"],
            }
        ],
        "metadata": {},
    }
    decorated = _decorate_metadata(raw_result)
    meta = decorated["metadata"]
    assert meta["accepted_count"] == 1
    assert meta["rejected_count"] == 1
    assert meta["status"] == "partial"
    assert any("Not found in DOM" in r for r in meta["rejection_reasons"])

    # All accepted -> success
    all_accepted = _decorate_metadata({
        "automation_tests": [{"script_code": "def test_ok(): pass", "recommendations": []}],
        "metadata": {},
    })
    assert all_accepted["metadata"]["status"] == "success"
    assert all_accepted["metadata"]["accepted_count"] == 1
    assert all_accepted["metadata"]["rejected_count"] == 0

    # All rejected -> failed
    all_rejected = _decorate_metadata({
        "automation_tests": [],
        "manual_tests": [],
        "metadata": {},
    })
    assert all_rejected["metadata"]["status"] == "failed"
    assert all_rejected["metadata"]["accepted_count"] == 0
    assert all_rejected["metadata"]["rejected_count"] == 0


def test_mcp_client_check_tool_result_and_redact():
    # Redaction
    redacted = _redact_and_bound("Secret token: sk-ant-api03-abcdef1234567890 and password=super_secret")
    assert "sk-ant-api03" not in redacted
    assert "super_secret" not in redacted

    # Tool error result detection
    mock_res = MagicMock()
    mock_res.isError = True
    mock_res.content = [MagicMock(text="Navigation timeout")]
    with pytest.raises(InspectionFailedError, match="Navigation timeout"):
        _check_tool_result(mock_res, "browser_navigate")
