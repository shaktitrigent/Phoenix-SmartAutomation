"""Phase 1 project metadata propagation, without browsers or LLM calls."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, create_autospec

from click.testing import CliRunner
import pytest

from phoenix.cli.main import main
from phoenix.sdk.config import PhoenixConfig, resolve_config_path
from phoenix.sdk.intelligence_client import IntelligenceClient
from phoenix_shared.contracts.project_context import ProjectContext


@pytest.fixture
def api_models(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "phoenix-intelligence"))
    from api.models import AutomateRequest

    return AutomateRequest


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("source", ["directory", "file"])
@pytest.mark.parametrize("override_url", [False, True])
def test_cli_context_reaches_sdk_and_api_model(
    tmp_path, monkeypatch, api_models, nested, source, override_url
):
    root = tmp_path / "Phoenix Project"
    manual = root / "manual_tests"
    manual.mkdir(parents=True)
    (root / ".phoenixrc").write_text(
        '[project]\nbase_url = "https://configured.example/login"\n', encoding="utf-8"
    )
    login = manual / "manual_test_Login Page.md"
    login.write_text("# Login\n\n## Test Steps\n1. Open login\n", encoding="utf-8")
    # Context must not cause environment loading or leak its contents.
    secret = "phase-one-secret-sentinel"
    (root / ".env.local").write_text(f"PHASE_ONE_SECRET={secret}\n", encoding="utf-8")
    monkeypatch.delenv("PHASE_ONE_SECRET", raising=False)
    cwd = root / "tests" / "deep" if nested else root
    cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        lambda *args, **kwargs: [],
    )
    captured = {}

    def post(url, *, json, timeout):
        captured.update(json)
        # Validate the actual SDK JSON against the actual API schema.
        request = api_models.model_validate(json)
        assert request.project_context is not None
        return Mock(status_code=200, json=lambda: {"automation_tests": []})

    monkeypatch.setattr("phoenix.sdk.intelligence_client.requests.post", post)
    args = ["automate"]
    if source == "file":
        args += ["--file", os.path.relpath(login, cwd)]
    if override_url:
        args += ["--url", "https://override.example/login"]
    result = CliRunner().invoke(main, args)
    # The mocked API returns no automation; the CLI must report failure.
    assert result.exit_code == 1, result.output
    expected_url = "https://override.example/login" if override_url else "https://configured.example/login"
    assert captured["application_url"] == expected_url
    assert captured["project_context"] == {
        "project_root": str(root.resolve()),
        "application_url": expected_url,
        "page_name": "manual_test_login_page" if source == "file" else "manual_tests",
        "locator_directory": str(root / "locators"),
        "environment_file": str(root / ".env.local"),
    }
    assert secret not in result.output
    assert secret not in json.dumps(captured)
    assert "PHASE_ONE_SECRET" not in os.environ


def test_cli_locator_expert_discovery_reuses_project_context(tmp_path, monkeypatch):
    root = tmp_path / "Phoenix Project"
    manual = root / "manual_tests"
    manual.mkdir(parents=True)
    (root / ".phoenixrc").write_text(
        '[project]\nbase_url = "https://configured.example/login"\nlayout = "pom-v1"\n',
        encoding="utf-8",
    )
    (manual / "manual_test_Login.md").write_text(
        "# Login\n\n## Test Steps\n1. Enter the login email field\n", encoding="utf-8"
    )
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        lambda *args, **kwargs: [],
    )
    captured_requests = []

    def post(url, *, json, timeout):
        captured_requests.append((url, json))
        if url.endswith("/api/v1/locators/discover"):
            return Mock(status_code=200, json=lambda: {
                "locators": [], "metadata": {},
            })
        return Mock(status_code=200, json=lambda: {
            "automation_tests": [{
                "name": "login",
                "script_template": "pom",
                "script_code": "",
                "locators": [],
                "pom_bundle": {
                    "page_objects": [{
                        "action": "extend",
                        "file": "pages/login_page.py",
                        "class_name": "LoginPage",
                        "code": "class LoginPage:\n    def login(self):\n        pass\n",
                    }],
                    "tests": [], "locators": [], "test_data": [],
                },
            }],
        })

    monkeypatch.setattr("phoenix.sdk.intelligence_client.requests.post", post)
    def resolve_with_discovery(tests, bundles, **kwargs):
        kwargs["discover"]({
            "page_url": "https://configured.example/login",
            "element_name": "Email field",
            "element_context": {},
        })
        return {
            "stored_count": 0,
            "scanned_count": 0,
            "fresh_count": 0,
            "locator_expert_calls": 1,
            "unresolved": ["Email field"],
        }

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.resolve_automation_locator_evidence",
        resolve_with_discovery,
    )
    monkeypatch.setattr(
        "phoenix.output.coordinator.OutputManager.apply",
        lambda self, bundle: [str(self.root / "pages" / "login_page.py")],
    )

    result = CliRunner().invoke(main, ["automate", "--url", "https://configured.example/login"])

    assert result.exit_code != 0, result.output
    assert "Aborted!" in result.output
    discovery = next(
        payload for url, payload in captured_requests
        if url.endswith("/api/v1/locators/discover")
    )
    assert discovery["project_context"] == {
        "project_root": str(root.resolve()),
        "application_url": "https://configured.example/login",
        "page_name": "manual_tests",
        "locator_directory": str(root / "locators"),
        "environment_file": str(root / ".env.local"),
    }


def test_explicit_relative_config_and_nearest_project(tmp_path, monkeypatch):
    outer = tmp_path / "outer"
    inner = outer / "inner"
    nested = inner / "tests" / "deep"
    nested.mkdir(parents=True)
    for root in (outer, inner):
        (root / ".phoenixrc").write_text("[project]\n", encoding="utf-8")
    monkeypatch.chdir(nested)
    assert resolve_config_path(search_parents=True) == inner / ".phoenixrc"
    assert resolve_config_path("../../../.phoenixrc", search_parents=True) == outer / ".phoenixrc"
    # Other commands retain their existing discovery scope.
    assert resolve_config_path() is None


@pytest.mark.parametrize("root", [r"C:\QA Projects\Phoenix", r"\\server\QA Projects\Phoenix"])
@pytest.mark.parametrize("as_model", [False, True])
def test_windows_paths_survive_sdk_json_and_api(root, as_model, monkeypatch, api_models):
    context = {
        "project_root": root,
        "application_url": "https://app.example/login",
        "page_name": "login",
        "locator_directory": root + r"\locators",
        "environment_file": root + r"\.env.local",
    }
    client = IntelligenceClient(PhoenixConfig())
    captured = {}

    def post(path, payload):
        captured.update(json.loads(json.dumps(payload)))
        return {"automation_tests": []}

    monkeypatch.setattr(client, "_post", post)
    client.automate_from_manual([], project_context=ProjectContext(**context) if as_model else context)
    request = api_models.model_validate(captured)
    assert request.project_context.model_dump() == context


@pytest.mark.parametrize("explicit_none", [False, True])
def test_sdk_and_model_keep_legacy_payload(monkeypatch, api_models, explicit_none):
    client = IntelligenceClient(PhoenixConfig())
    post = Mock(return_value={"automation_tests": []})
    monkeypatch.setattr(client, "_post", post)
    kwargs = {"project_context": None} if explicit_none else {}
    client.automate_from_manual([], application_url="https://legacy.example", **kwargs)
    path, payload = post.call_args.args
    assert path == "/api/v1/tests/automate"
    assert "project_context" not in payload
    assert api_models.model_validate(payload).project_context is None


@pytest.mark.parametrize("context_mode", ["present", "absent", "null"])
def test_api_route_forwards_context_without_changing_legacy_calls(
    tmp_path, monkeypatch, api_models, context_mode
):
    # Import startup services in an empty directory without external clients.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PHOENIX_MCP_ENABLED", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from api import server
    from services.agents.registry import AgentRegistry

    registry = create_autospec(AgentRegistry, instance=True, spec_set=True)
    registry.automate_from_manual.return_value = {"automation_tests": []}
    monkeypatch.setattr(server, "_agent_registry", registry)
    locator_evidence = [{
        "element_name": "LoginButton",
        "primary": {"strategy": "css", "value": "#login", "verified_in_snapshot": True},
        "metadata": {"locator_source": "stored_primary"},
    }]
    payload = {
        "manual_tests": [],
        "application_url": "https://app.example/login",
        "locator_bundles": locator_evidence,
    }
    context = {
        "project_root": r"C:\QA Projects\Phoenix",
        "application_url": payload["application_url"],
        "page_name": "login",
        "locator_directory": r"C:\QA Projects\Phoenix\locators",
        "environment_file": r"C:\QA Projects\Phoenix\.env.local",
    }
    if context_mode != "absent":
        payload["project_context"] = context if context_mode == "present" else None
    response = TestClient(server.app).post("/api/v1/tests/automate", json=payload)
    assert response.status_code == 200, response.text
    kwargs = registry.automate_from_manual.call_args.kwargs
    assert kwargs["application_url"] == payload["application_url"]
    assert kwargs["locator_bundles"] == locator_evidence
    if context_mode == "present":
        assert kwargs["project_context"] == context
    else:
        assert "project_context" not in kwargs
