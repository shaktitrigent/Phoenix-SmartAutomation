"""Tests for the LLM-free ``phoenix locators scan`` workflow."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import types

from click.testing import CliRunner

import phoenix

# commands.py imports the SDK client for unrelated commands.
from phoenix.cli.commands import locators
from phoenix.locators.smartlocator_adaptor import convert_locators


def test_scan_persists_only_uniquely_validated_bundles(monkeypatch, tmp_path):
    bundles = convert_locators(
        [
            {
                "custom_name": "UsernameInput",
                "locator_type": "CSS Selector",
                "locator_value": "#username",
                "validated": True,
                "match_count": 1,
                "recommended": True,
                "element_data": {"tag": "input", "id": "username"},
            },
            {
                "custom_name": "AmbiguousButton",
                "locator_type": "CSS Selector",
                "locator_value": ".button",
                "validated": False,
                "match_count": 2,
                "element_data": {"tag": "button", "class": "button"},
            },
        ],
        page="login",
    )
    captured = {}

    def fake_generate(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return bundles

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        fake_generate,
    )
    monkeypatch.setattr(
        "phoenix.cli.commands.PhoenixConfig.load",
        lambda _path=None: SimpleNamespace(
            project=SimpleNamespace(resolved_base_url=None)
        ),
    )

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        locators,
        ["scan", "--url", "https://app.example", "--page", "login"],
        obj={},
    )
    persisted = json.loads(Path("locators/login.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0, result.output
    assert captured["url"] == "https://app.example"
    assert captured["validate"] is True
    assert captured["output_dir"] is None
    assert len(persisted) == 1
    assert persisted[0]["element_name"] == "UsernameInput"


def test_scan_can_keep_raw_artifacts_in_page_directory(monkeypatch, tmp_path):
    captured = {}

    def fake_generate(url, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        fake_generate,
    )
    monkeypatch.setattr(
        "phoenix.cli.commands.PhoenixConfig.load",
        lambda _path=None: SimpleNamespace(
            project=SimpleNamespace(resolved_base_url="https://configured.example")
        ),
    )

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        locators,
        ["scan", "--page", "checkout", "--keep-raw"],
        obj={},
    )

    assert result.exit_code == 0, result.output
    assert captured["output_dir"].name == "checkout"
    assert captured["output_dir"].parent.name == "smartlocator_raw"


def test_scan_default_no_llm_fallback(monkeypatch, tmp_path):
    """Default scan (--no-llm-fallback) must not trigger paid LLM fallback."""
    bundles = convert_locators([
        {
            "custom_name": "UnresolvedField",
            "locator_type": "CSS Selector",
            "locator_value": ".unknown",
            "validated": False,
            "match_count": 0,
        }
    ], page="login")

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        lambda url, **kwargs: bundles,
    )
    monkeypatch.setattr(
        "phoenix.cli.commands.PhoenixConfig.load",
        lambda _path=None: SimpleNamespace(
            project=SimpleNamespace(resolved_base_url="https://app.example")
        ),
    )

    fallback_called = []
    def fake_resolve(*args, **kwargs):
        fallback_called.append(True)
        return {"resolved_bundles": [], "unresolved_elements": [], "llm_calls": 0, "duration_ms": 0}

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_fallback.resolve_with_locator_expert",
        fake_resolve,
    )

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        locators,
        ["scan", "--page", "login"],
        obj={},
    )

    assert result.exit_code == 0, result.output
    assert not fallback_called, "LocatorExpert should NOT be invoked by default"
    assert "Sent to LocatorExpert:   0" in result.output


def test_scan_with_llm_fallback_enabled(monkeypatch, tmp_path):
    """--llm-fallback sends unresolved elements to LocatorExpert fallback service."""
    bundles = convert_locators([
        {
            "custom_name": "UnresolvedField",
            "locator_type": "CSS Selector",
            "locator_value": ".unknown",
            "validated": False,
            "match_count": 0,
            "element_data": {"dom_id": "unresolved"},
        }
    ], page="login")

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        lambda url, **kwargs: bundles,
    )
    monkeypatch.setattr(
        "phoenix.cli.commands.PhoenixConfig.load",
        lambda _path=None: SimpleNamespace(
            project=SimpleNamespace(resolved_base_url="https://app.example")
        ),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

    fallback_called = []
    def fake_resolve(bundles_in, page_url, discover, validate):
        fallback_called.append((bundles_in, page_url))
        # Simulate LLM returning a valid candidate (match_count == 1)
        response = {
            "locators": [{"strategy": "role", "value": "input[name='User']"}],
            "metadata": {"provider": "anthropic", "tokens_used": 150},
        }
        cand_locs = discover({"element_name": "UnresolvedField", "page_url": page_url})
        return {
            "resolved_bundles": [
                bundles_in[0].model_copy(update={"primary": bundles_in[0].primary.model_copy(update={"verified_in_snapshot": True})})
            ],
            "unresolved_elements": [],
            "llm_calls": 1,
            "tokens_used": 150,
            "duration_ms": 250.0,
        }

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_fallback.resolve_with_locator_expert",
        fake_resolve,
    )

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        locators,
        ["scan", "--page", "login", "--llm-fallback"],
        obj={},
    )

    assert result.exit_code == 0, result.output
    assert len(fallback_called) == 1
    assert "Sent to LocatorExpert:   1" in result.output
    assert "LLM calls:               1" in result.output


def test_scan_llm_fallback_rejects_ambiguous_and_invalid(monkeypatch, tmp_path):
    """Candidate with count==0 or count>1 must be rejected."""
    bundles = convert_locators([
        {
            "custom_name": "AmbiguousField",
            "locator_type": "CSS Selector",
            "locator_value": ".dup",
            "validated": False,
            "match_count": 2,
        }
    ], page="form")

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_integration.generate_smartlocator_bundles",
        lambda url, **kwargs: bundles,
    )
    monkeypatch.setattr(
        "phoenix.cli.commands.PhoenixConfig.load",
        lambda _path=None: SimpleNamespace(
            project=SimpleNamespace(resolved_base_url="https://app.example")
        ),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

    def fake_resolve(bundles_in, page_url, discover, validate):
        return {
            "resolved_bundles": [],
            "unresolved_elements": [{
                "element_name": "AmbiguousField",
                "fallback_reasons": ["ambiguous"],
                "rejected_candidates": [{"strategy": "css", "value": ".dup", "match_count": 2}],
            }],
            "llm_calls": 1,
            "tokens_used": 100,
            "duration_ms": 180.0,
        }

    monkeypatch.setattr(
        "phoenix.locators.smartlocator_fallback.resolve_with_locator_expert",
        fake_resolve,
    )

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        locators,
        ["scan", "--page", "form", "--llm-fallback"],
        obj={},
    )

    assert result.exit_code == 0, result.output
    assert "Still unresolved:        1" in result.output


def test_repeated_scans_do_not_duplicate_locators(tmp_path):
    """Repeated scans and persistence must logically deduplicate locator entries."""
    from phoenix.locators.persist import persist_locators
    from phoenix.locators.registry import LocatorRegistry

    loc_dir = tmp_path / "locators"
    loc_dir.mkdir()

    bundles = convert_locators([
        {
            "custom_name": "SubmitButton",
            "locator_type": "CSS Selector",
            "locator_value": "#submit",
            "validated": True,
            "match_count": 1,
        }
    ], page="checkout")

    script = [{"page": "checkout", "locators": bundles}]

    # Run persistence 3 times
    persist_locators(script, loc_dir)
    persist_locators(script, loc_dir)
    persist_locators(script, loc_dir)

    registry = LocatorRegistry.load_all(loc_dir)
    assert len(registry) == 1
    bundle = registry.require("SubmitButton")
    assert bundle.primary.value == "#submit"
    assert len(bundle.alternates) == 0


def test_registry_reload_preserves_bundle_integrity(tmp_path):
    """Registry loading must preserve primary, alternates, and SmartLocator metadata."""
    from phoenix.locators.persist import persist_locators
    from phoenix.locators.registry import LocatorRegistry

    loc_dir = tmp_path / "locators"

    bundles = convert_locators([
        {
            "custom_name": "UsernameInput",
            "element_data": {"dom_id": "user"},
            "recommended": {
                "locator_type": "CSS Selector",
                "locator_value": "#user",
                "validated": True,
            },
            "context_strategy": "role-first",
            "stability_category": "stable",
        }
    ], page="login")

    persist_locators([{"page": "login", "locators": bundles}], loc_dir)

    registry = LocatorRegistry.load_all(loc_dir)
    reloaded = registry.require("UsernameInput")

    assert reloaded.element_name == "UsernameInput"
    assert reloaded.page == "login"
    assert reloaded.primary.value == "#user"
    assert reloaded.primary.verified_in_snapshot is True
    assert reloaded.metadata["context_strategy"] == "role-first"

