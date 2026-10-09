"""
Pytest configuration for Phoenix Intelligence tests.
Disables browser password-manager prompts (e.g. "Change your password" after login)
so they do not block or interfere with test assertions.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def block_external_calls(monkeypatch):
    """Guard fixture to prevent any external API, LLM, MCP, or network calls during tests.
    
    This ensures tests run offline and fail immediately if any external call is attempted.
    """
    # Unset all API keys
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "OPENAI_ORGANIZATION"]:
        monkeypatch.delenv(key, raising=False)
    
    # Mock LLM client to raise
    def mock_llm_init(*args, **kwargs):
        raise RuntimeError("LLM client call blocked by test guard - use mocks for LLM-dependent tests")
    
    # Mock MCP client to raise
    def mock_mcp_init(*args, **kwargs):
        raise RuntimeError("MCP client call blocked by test guard - use mocks for MCP-dependent tests")
    
    # Mock HTTP requests to raise
    def mock_requests_post(*args, **kwargs):
        raise RuntimeError("HTTP request blocked by test guard - use mocks for network-dependent tests")
    
    # Apply monkeypatches
    try:
        import services.llm.client
        monkeypatch.setattr("services.llm.client.LLMClient", mock_llm_init)
    except ImportError:
        pass
    
    try:
        import services.mcp.client
        monkeypatch.setattr("services.mcp.client.MCPClient", mock_mcp_init)
    except ImportError:
        pass
    
    try:
        import requests
        monkeypatch.setattr("requests.post", mock_requests_post)
        monkeypatch.setattr("requests.get", mock_requests_post)
    except ImportError:
        pass
    
    yield


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Add Chromium launch args to suppress password save/breach dialogs."""
    opts = dict(browser_type_launch_args or {})
    args = list(opts.get("args", []))
    args.extend(
        [
            "--disable-save-password-bubble",
            "--disable-features=PasswordManager",
        ]
    )
    opts["args"] = args
    return opts
