"""Phase 2 isolated project configuration; all credentials here are synthetic."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phoenix_shared.contracts.project_context import ProjectContext
from services.request_config import RequestConfig, load_request_config


def context(root, environment_file=".env.local"):
    return ProjectContext(
        project_root=str(root), environment_file=str(environment_file),
        application_url="https://example.test", page_name="login",
        locator_directory=str(root / "locators"),
    )


def fingerprint_environment():
    # Failure output must not dump the actual server environment.
    return hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).digest()


def test_precedence_and_immutable_snapshot(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("PHASE2_A=base\nPHASE2_B=base\nPHASE2_C=base-only\n")
    (tmp_path / ".env.local").write_text("PHASE2_A=local\n")
    monkeypatch.setenv("PHASE2_A", "process")
    monkeypatch.setenv("PHASE2_B", "process")
    monkeypatch.delenv("PHASE2_C", raising=False)
    before = fingerprint_environment()
    result = load_request_config(context(tmp_path))
    assert [result.values[key] for key in ("PHASE2_A", "PHASE2_B", "PHASE2_C")] == [
        "local", "process", "base-only",
    ]
    assert result.diagnostics.sources == ("project_env", "process_environment", "project_env_local")
    assert fingerprint_environment() == before
    with pytest.raises(TypeError):
        result.values["PHASE2_A"] = "changed"
    with pytest.raises(FrozenInstanceError):
        result.values = {}
    monkeypatch.setenv("PHASE2_B", "changed-after-load")
    assert result.values["PHASE2_B"] == "process"


@pytest.mark.parametrize("base,local", [(True, False), (False, True), (False, False), (True, True)])
def test_missing_and_empty_files(tmp_path, monkeypatch, base, local):
    for filename, exists in ((".env", base), (".env.local", local)):
        if exists:
            (tmp_path / filename).write_text("")
    monkeypatch.setenv("PHASE2_ONLY_PROCESS", "preserved")
    result = load_request_config(context(tmp_path))
    assert result.values["PHASE2_ONLY_PROCESS"] == "preserved"
    assert result.diagnostics.env_file_found is base
    assert result.diagnostics.env_local_file_found is local
    assert result.diagnostics.reason is None


def test_absent_context_does_not_read_or_snapshot(monkeypatch):
    monkeypatch.setattr(Path, "open", Mock(side_effect=AssertionError("unexpected read")))
    assert load_request_config(None) is None


def test_dotenv_parsing_and_safe_malformed_lines(tmp_path, capfd, caplog):
    (tmp_path / ".env.local").write_text(
        'BAD LINE synthetic-secret\nEQ=a=b=c\nQUOTED="hello = world"\n'
        "SINGLE='literal # value'\nEMPTY=\nBARE\nREF=${EQ}\n", encoding="utf-8",
    )
    caplog.set_level(logging.DEBUG)
    result = load_request_config(context(tmp_path))
    assert result.values["EQ"] == "a=b=c"
    assert result.values["QUOTED"] == "hello = world"
    assert result.values["SINGLE"] == "literal # value"
    assert result.values["EMPTY"] == ""
    assert result.values["REF"] == "${EQ}"
    assert result.diagnostics.reason == "malformed_environment_lines_ignored"
    output = capfd.readouterr()
    assert output.out == output.err == caplog.text == ""


@pytest.mark.parametrize("local", ["../outside", "sub/../../outside", "sub/../.env.local"])
def test_traversal_rejected_before_any_read(tmp_path, monkeypatch, local):
    read = Mock(side_effect=AssertionError("must validate before reading"))
    monkeypatch.setattr(Path, "open", read)
    result = load_request_config(context(tmp_path, local))
    assert result.diagnostics.reason == "path_traversal_rejected"
    read.assert_not_called()


def test_absolute_outside_path_rejected(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    read = Mock(side_effect=AssertionError("must not read outside project"))
    monkeypatch.setattr(Path, "open", read)
    result = load_request_config(context(root, tmp_path / ".env.local"))
    assert result.diagnostics.reason == "environment_path_outside_project"
    read.assert_not_called()


def test_absolute_inside_path_from_phase1_and_read_allowlist(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("PHASE2_VALUE=base\n")
    (tmp_path / ".env.local").write_text("PHASE2_VALUE=local\n")
    (tmp_path / ".env.other").write_text("PHASE2_VALUE=wrong\n")
    from services import request_config
    original_open = request_config.open_environment
    opened = []

    def track(root, name):
        opened.append(root / name)
        return original_open(root, name)

    monkeypatch.setattr(request_config, "open_environment", track)
    result = load_request_config(context(tmp_path, tmp_path / ".env.local"))
    assert result.values["PHASE2_VALUE"] == "local"
    assert opened == [tmp_path / ".env", tmp_path / ".env.local"]


def test_symlink_or_junction_escape_rejected(tmp_path):
    root, outside = tmp_path / "project", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / ".env.local").write_text("PHASE2_ESCAPE=synthetic-secret\n")
    link = root / "linked"
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    else:
        link.symlink_to(outside, target_is_directory=True)
    result = load_request_config(context(root, "linked/.env.local"))
    assert result.diagnostics.reason == "environment_path_outside_project"
    assert "PHASE2_ESCAPE" not in result.values


@pytest.mark.parametrize("kind", ["missing", "file", "relative"])
def test_unavailable_or_invalid_root(tmp_path, kind):
    root = tmp_path / "missing"
    if kind == "file":
        root.write_text("not a directory")
    elif kind == "relative":
        root = Path("relative-project")
    result = load_request_config(context(root))
    assert not result.diagnostics.project_root_accessible
    assert result.diagnostics.reason in {
        "project_root_unavailable", "project_root_not_directory", "project_root_not_absolute",
    }


def test_permission_error_has_safe_reason(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("PHASE2_VALUE=ignored")
    monkeypatch.setattr("services.request_config.open_environment", Mock(side_effect=PermissionError("sensitive-path-and-value")))
    result = load_request_config(context(tmp_path))
    assert result.diagnostics.reason == "environment_file_unavailable"
    assert "sensitive" not in repr(result)


@pytest.mark.parametrize("root", [r"Z:\Unavailable Client\Project", r"\\unavailable-server\share\Project"])
def test_foreign_windows_paths_are_not_reinterpreted(root, monkeypatch):
    # Simulate the POSIX branch even when tests run on Windows. Any native path
    # resolution is a failure: reject the foreign syntax before calling Path.
    from services import request_config
    monkeypatch.setattr(request_config, "os", SimpleNamespace(environ={}, name="posix"))
    monkeypatch.setattr(request_config, "Path", Mock(side_effect=AssertionError("foreign path resolved")))
    payload = context(Path(root))
    result = load_request_config(payload)
    assert payload.project_root == root
    assert result.diagnostics.reason == "client_path_platform_unavailable"


@pytest.mark.parametrize("filename,reason", [
    (".env", "environment_file_duplicates_base"),
    ("", "invalid_path"),
    ("subdir", "environment_filename_not_allowed"),
])
def test_invalid_local_paths(tmp_path, filename, reason):
    (tmp_path / "subdir").mkdir()
    assert load_request_config(context(tmp_path, filename)).diagnostics.reason == reason


def test_custom_local_file_is_rejected(tmp_path):
    (tmp_path / "settings").mkdir()
    (tmp_path / "settings" / "project.env").write_text("PHASE2_CUSTOM=chosen\n")
    (tmp_path / ".env.local").write_text("PHASE2_CUSTOM=not-selected\n")
    result = load_request_config(context(tmp_path, "settings/project.env"))
    assert result.diagnostics.reason == "environment_filename_not_allowed"
    assert result.diagnostics.fallback_to_process_only
    assert not result.diagnostics.project_environment_loaded


def test_base_file_escape_is_also_rejected(tmp_path, monkeypatch):
    from services import request_config
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == tmp_path / ".env":
            return tmp_path.parent / "outside.env"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    reader = Mock(side_effect=AssertionError("base escape must be validated first"))
    monkeypatch.setattr(request_config, "_read_file", reader)
    assert load_request_config(context(tmp_path)).diagnostics.reason == "environment_path_outside_project"
    reader.assert_not_called()


def test_root_traversal_rejected(tmp_path):
    payload = context(tmp_path / "child" / "..")
    assert load_request_config(payload).diagnostics.reason == "path_traversal_rejected"


@pytest.mark.parametrize("concurrent", [False, True])
def test_project_isolation(tmp_path, monkeypatch, concurrent):
    monkeypatch.delenv("PHASE2_PROJECT", raising=False)
    roots = [tmp_path / "one", tmp_path / "two"]
    for number, root in enumerate(roots):
        root.mkdir()
        (root / ".env.local").write_text(f"PHASE2_PROJECT={number}\n")
    before = fingerprint_environment()
    if concurrent:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(load_request_config, map(context, roots)))
    else:
        results = [load_request_config(context(root)) for root in roots]
    assert [item.values["PHASE2_PROJECT"] for item in results] == ["0", "1"]
    assert results[0].values is not results[1].values
    assert fingerprint_environment() == before


@pytest.mark.parametrize("mode", ["present", "absent", "null", "unavailable"])
def test_api_registry_isolation_and_no_secret_output(tmp_path, monkeypatch, capfd, caplog, mode):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from api import server
    from fastapi.testclient import TestClient
    from services.agents.registry import AgentRegistry
    from services.agents.test_generator import TestGeneratorAgent

    secrets = ["synthetic-anthropic-key", "synthetic-user", "synthetic-password", "synthetic-jira-token"]
    (tmp_path / ".env.local").write_text("\n".join(
        f"{key}={value}" for key, value in zip(
            ["ANTHROPIC_API_KEY", "TEST_USERNAME", "TEST_PASSWORD", "JIRA_API_TOKEN"], secrets,
        )
    ))
    generator = create_autospec(TestGeneratorAgent, instance=True, spec_set=True)
    generator.automate_from_manual_tests.return_value = {"automation_tests": []}
    registry = AgentRegistry.__new__(AgentRegistry)
    registry._agents = {"test_generator": generator}
    registry._llm_client = Mock(spec_set=[])
    registry._mcp_client = Mock(spec_set=[])
    boundary = Mock(wraps=registry.automate_from_manual)
    monkeypatch.setattr(registry, "automate_from_manual", boundary)
    monkeypatch.setattr(server, "_agent_registry", registry)
    # Ensure any accidental request-level load_dotenv is detected.
    monkeypatch.setattr("dotenv.load_dotenv", Mock(side_effect=AssertionError("global env loading")))
    settings_before = [vars(item).copy() for item in (server._llm_settings, server._mcp_settings)]
    clients_before = (server._llm_client, registry._llm_client, registry._mcp_client)
    before = fingerprint_environment()
    capfd.readouterr()
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    payload = {"manual_tests": []}
    if mode != "absent":
        root = tmp_path / "unavailable" if mode == "unavailable" else tmp_path
        payload["project_context"] = None if mode == "null" else context(root).model_dump()
    response = TestClient(server.app).post("/api/v1/tests/automate", json=payload)
    assert response.status_code == 200
    kwargs = boundary.call_args.kwargs
    if mode in ("present", "unavailable"):
        config = kwargs["request_config"]
        assert isinstance(config, RequestConfig)
        if mode == "present":
            assert config.values["TEST_PASSWORD"] == secrets[2]
            assert config.diagnostics.anthropic_key_available
        else:
            assert config.diagnostics.reason == "project_root_unavailable"
    else:
        assert "request_config" not in kwargs
    assert "request_config" not in generator.automate_from_manual_tests.call_args.kwargs
    assert len(generator.mock_calls) == 1
    assert [vars(item) for item in (server._llm_settings, server._mcp_settings)] == settings_before
    assert (server._llm_client, registry._llm_client, registry._mcp_client) == clients_before
    assert fingerprint_environment() == before
    captured = capfd.readouterr()
    output = captured.out + captured.err + caplog.text + response.text
    if mode in ("present", "unavailable"):
        output += repr(kwargs["request_config"])
    for secret in secrets:
        assert secret not in output
    assert "request_config" not in response.json()
    assert "values" not in response.json()



def test_locator_discovery_route_uses_project_scoped_config(tmp_path, monkeypatch, caplog):
    from fastapi.testclient import TestClient
    from api import server

    project_key = "sk-ant-" + "p" * 32
    (tmp_path / ".env.local").write_text(
        f"ANTHROPIC_API_KEY={project_key}\n", encoding="utf-8"
    )
    registry = Mock()
    registry.discover_locators.return_value = {"locators": []}
    monkeypatch.setattr(server, "_agent_registry", registry)
    context_data = context(tmp_path).model_dump()
    caplog.set_level(logging.DEBUG)

    response = TestClient(server.app).post("/api/v1/locators/discover", json={
        "page_url": "https://app.example/login",
        "element_contexts": [{"element_name": "Username input"}],
        "require_llm": True,
        "project_context": context_data,
    })

    assert response.status_code == 200
    request_config = registry.discover_locators.call_args.kwargs["request_config"]
    assert isinstance(request_config, RequestConfig)
    assert request_config.values["ANTHROPIC_API_KEY"] == project_key
    assert project_key not in caplog.text + response.text
    assert "values" not in response.json()
