"""Request-scoped LLM and persisted locator evidence tests."""

from types import MappingProxyType
from unittest.mock import Mock, patch

from services.agents.registry import AgentRegistry
from services.agents.test_generator import TestGeneratorAgent as GeneratorAgent
from services.request_config import ConfigDiagnostics, RequestConfig
from services.request_llm import build_request_llm


def test_request_llm_uses_snapshot_without_mutating_environment(monkeypatch):
    process_key = "sk" + "-ant-" + "p" * 32
    project_key = "sk" + "-ant-" + "q" * 32
    monkeypatch.setenv("ANTHROPIC_API_KEY", process_key)
    result = build_request_llm(MappingProxyType({
        "ANTHROPIC_API_KEY": project_key,
        "PHOENIX_LLM_MODEL": "project-model",
    }))
    assert result.available is True
    assert result.client.settings.api_key == project_key
    assert result.client.settings.model == "project-model"
    assert __import__("os").environ["ANTHROPIC_API_KEY"] != project_key


def test_missing_and_invalid_key_have_safe_reason():
    assert build_request_llm({}).reason == "anthropic_key_missing"
    assert build_request_llm({"ANTHROPIC_API_KEY": "bad"}).reason == "anthropic_key_invalid"


def test_registry_passes_exact_stored_evidence_and_uses_request_agent():
    generator = Mock()
    generator.automate_from_manual_tests.return_value = {"automation_tests": []}
    registry = AgentRegistry(Mock(), Mock(), llm_client=Mock(name="shared_client"))
    request_config = RequestConfig(
        {"ANTHROPIC_API_KEY": ""}, ConfigDiagnostics()
    )
    bundles = [{
        "element_name": "LoginButton",
        "primary": {"strategy": "css", "value": "#login"},
        "metadata": {"locator_source": "stored_primary"},
    }]
    with patch("services.agents.registry.TestGeneratorAgent", return_value=generator), \
         patch("services.agents.registry.LocatorExpertAgent") as expert:
        result = registry.automate_from_manual(
            [{"name": "login"}], project_context={"project_root": "x"},
            request_config=request_config, locator_bundles=bundles,
        )
    assert generator.automate_from_manual_tests.call_args.kwargs["domain_knowledge"] == ""
    assert result["metadata"]["locator_sources"] == ["stored_primary"]
    assert result["metadata"]["locator_expert_scope"] == "unresolved_elements_only"
    assert generator.automate_from_manual_tests.call_args.kwargs["locator_bundles"] == bundles
    expert.assert_called_once()


def test_registry_requests_do_not_reuse_project_client():
    registry = AgentRegistry(Mock(), Mock(), llm_client=None)
    configs = [
        RequestConfig(
            {"ANTHROPIC_API_KEY": "sk" + "-ant-" + suffix * 16},
            ConfigDiagnostics(),
        )
        for suffix in ("one", "two")
    ]
    clients = []
    with patch("services.agents.registry.TestGeneratorAgent") as generator, \
         patch("services.agents.registry.LocatorExpertAgent"):
        generator.return_value.automate_from_manual_tests.return_value = {"automation_tests": []}
        for config in configs:
            registry.automate_from_manual([], request_config=config)
            clients.append(generator.call_args.kwargs["llm_client"])
    assert clients[0] is not clients[1]
    assert registry._llm_client is None


def test_locator_expert_uses_request_local_client_and_cache():
    registry = AgentRegistry(Mock(), Mock(), llm_client=None)
    configs = [
        RequestConfig({"ANTHROPIC_API_KEY": "sk-ant-" + suffix * 32}, ConfigDiagnostics())
        for suffix in ("a", "b")
    ]
    clients, caches = [], []
    with patch("services.agents.registry.LocatorExpertAgent") as expert:
        expert.return_value.process.return_value = {"locators": []}
        for config in configs:
            registry.discover_locators(
                "https://app.example",
                "Username input",
                request_config=config,
            )
            clients.append(expert.call_args.kwargs["llm_client"])
            caches.append(expert.call_args.args[1])
    assert clients[0] is not clients[1]
    assert caches[0] is not caches[1]
    assert registry._llm_client is None


def test_test_generator_consumes_structured_locator_evidence():
    agent = GeneratorAgent(Mock(), Mock(), llm_client=None)
    agent.get_knowledge_context = Mock(return_value="")
    generator = Mock(return_value={
        "script_code": "def test_login():\n    pass\n",
        "locators": [],
        "recommendations": [],
    })
    agent._generate_script_for_manual_test = generator
    evidence = [{
        "element_name": "UsernameInput",
        "primary": {"strategy": "css", "value": "#user-name"},
        "metadata": {"locator_source": "stored_primary"},
    }]

    agent.automate_from_manual_tests(
        [{"name": "login", "steps": []}],
        use_pom=False,
        locator_bundles=evidence,
    )

    context = generator.call_args.kwargs["domain_knowledge"]
    assert '"value":"#user-name"' in context
    assert '"locator_source":"stored_primary"' in context
