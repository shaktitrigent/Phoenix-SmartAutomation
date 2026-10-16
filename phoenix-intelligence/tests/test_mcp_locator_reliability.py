import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.config import MCPSettings
from services.mcp.client import MCPClient, InspectionFailedError, _check_tool_result
from services.agents.locator_expert import LocatorExpertAgent
from services.cache import Cache


def test_dictionary_protocol_errors_are_not_silently_accepted():
    with pytest.raises(InspectionFailedError):
        _check_tool_result({"isError":True,"content":[{"text":"failed"}]},"browser_snapshot")


def test_configured_timeout_cancels_capture():
    client=MCPClient(MCPSettings(enabled=True,timeout=0.01))
    closed=[]
    async def inspect(url):
        try: await asyncio.sleep(10)
        finally: closed.append(True)
    client._inspect_page_async=inspect
    with pytest.raises(InspectionFailedError): client.inspect_page("https://example.test")
    assert closed==[True]


def test_capture_failure_recovers_on_the_next_request():
    client=MCPClient(MCPSettings(enabled=True))
    responses=iter(["","current snapshot"])
    async def inspect(url): return next(responses)
    client._inspect_page_async=inspect
    with pytest.raises(InspectionFailedError): client.inspect_page("https://example.test")
    assert client.inspect_page("https://example.test")=="current snapshot"


def test_unobserved_cached_dom_is_not_reused():
    manager=Mock()
    client=MCPClient(MCPSettings(enabled=True),dom_snapshot_manager=manager)
    calls=[]
    async def inspect(url):
        calls.append(url)
        return "fresh state " + str(len(calls))
    client._inspect_page_async=inspect
    assert client.inspect_page("https://example.test",execution_id="first")=="fresh state 1"
    assert client.inspect_page("https://example.test",execution_id="second")=="fresh state 2"
    manager.get_dom_with_automatic_reuse.assert_not_called()


def test_scoped_fallback_does_not_navigate_another_mcp_browser():
    knowledge=Mock()
    knowledge.get_context_for_agent.return_value=""
    llm=Mock(settings=SimpleNamespace(provider="test",model="test"))
    llm.generate.return_value='{"locators":[{"strategy":"css","value":"#submit"}]}'
    mcp=Mock()
    agent=LocatorExpertAgent(knowledge,Cache(),llm_client=llm,mcp_client=mcp)
    result=agent.process({"element_name":"Submit","page_url":"https://example.test/secure",
        "require_llm":True,"element_context":{"scoped_dom":"current parent/sibling context",
            "element_identity":"submit","state_name":"secure"}})
    assert result["locators"]
    mcp.inspect_page.assert_not_called()
    assert "current parent/sibling context" in llm.generate.call_args.args[1]


def test_supplied_state_snapshot_skips_anonymous_mcp_generation():
    from services.agents.test_generator import TestGeneratorAgent
    agent=object.__new__(TestGeneratorAgent)
    agent.mcp_client=Mock()
    agent.get_knowledge_context=lambda **kw:""
    result=agent.automate_from_manual_tests([],application_url="https://example.test/secure",
        dom_snapshot="<body><button>Current state</button></body>")
    assert result["automation_tests"]==[]
    agent.mcp_client.inspect_page.assert_not_called()
