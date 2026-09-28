"""Focused Phase 1 service-boundary and logging regressions."""

import copy
import logging
import os
from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from phoenix.sdk.config import PhoenixConfig, resolve_config_path
from phoenix.sdk.intelligence_client import IntelligenceClient


@pytest.mark.parametrize("mode", ["present", "absent", "null"])
def test_real_registry_boundary_has_no_context_side_effects(
    tmp_path, monkeypatch, capfd, caplog, mode
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "phoenix-intelligence"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PHOENIX_MCP_ENABLED", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from api import server
    from api.models import AutomateRequest
    from services.agents.registry import AgentRegistry
    from services.agents.test_generator import TestGeneratorAgent

    root = tmp_path / "private-project-root"
    root.mkdir()
    (root / ".phoenixrc").write_text("[project]\n", encoding="utf-8")
    secret = "phase1-test-only-credential"
    (root / ".env.local").write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")
    (root / "private.txt").write_text("private-root-content", encoding="utf-8")
    context = {
        "project_root": str(root), "application_url": "https://app.example/login",
        "page_name": "login", "locator_directory": str(root / "locators"),
        "environment_file": str(root / ".env.local"),
    }
    original_context = copy.deepcopy(context)
    generator = create_autospec(TestGeneratorAgent, instance=True, spec_set=True)
    generator.automate_from_manual_tests.return_value = {"automation_tests": []}
    # Run the real registry method while isolating normal generation and startup.
    registry = AgentRegistry.__new__(AgentRegistry)
    registry._agents = {"test_generator": generator}
    registry._llm_client = Mock(spec_set=[])
    registry._mcp_client = Mock(spec_set=[])
    original_state = registry.__dict__.copy()
    boundary = Mock(wraps=registry.automate_from_manual)
    monkeypatch.setattr(registry, "automate_from_manual", boundary)
    monkeypatch.setattr(server, "_agent_registry", registry)
    settings_before = vars(server._mcp_settings).copy()
    environment_before = dict(os.environ)

    # Start capture after pre-existing server startup/configuration behavior.
    capfd.readouterr()
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    assert resolve_config_path(str(root / ".phoenixrc")) == root / ".phoenixrc"
    payloads = []
    client = IntelligenceClient(PhoenixConfig())
    monkeypatch.setattr(client, "_post", lambda path, payload: payloads.append(payload))
    kwargs = {} if mode == "absent" else {"project_context": context if mode == "present" else None}
    client.automate_from_manual([], application_url=context["application_url"], **kwargs)
    # Existing MCP reconfiguration is outside the scope of this regression.
    payloads[0].pop("mcp_config")
    payload = AutomateRequest.model_validate(payloads[0])
    with monkeypatch.context() as guards:
        def unexpected_read(*args, **kwargs):
            pytest.fail("Phase 1 must not read client files or load an environment")

        guards.setattr("builtins.open", unexpected_read)
        guards.setattr(Path, "open", unexpected_read)
        guards.setattr("dotenv.load_dotenv", unexpected_read)
        server.automate_from_manual(payload)

    boundary.assert_called_once()
    if mode == "present":
        assert boundary.call_args.kwargs["project_context"] == original_context
    else:
        assert "project_context" not in boundary.call_args.kwargs
    assert context == original_context
    generator.automate_from_manual_tests.assert_called_once_with(
        manual_tests=[], application_url=context["application_url"],
        domain_knowledge="", manifest="", use_pom=True, use_bdd=False, keywords="",
    )
    assert len(generator.mock_calls) == 1
    registry._llm_client.assert_not_called()
    registry._mcp_client.assert_not_called()
    for name, value in original_state.items():
        assert registry.__dict__[name] is value
    assert vars(server._mcp_settings) == settings_before
    assert dict(os.environ) == environment_before
    output = capfd.readouterr()
    text = output.out + output.err + caplog.text
    for value in (str(root), secret, "private-root-content", "ANTHROPIC_API_KEY"):
        assert value not in text
