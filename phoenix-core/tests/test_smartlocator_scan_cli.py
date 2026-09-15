"""Tests for the LLM-free ``phoenix locators scan`` workflow."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import types

from click.testing import CliRunner

import phoenix

# commands.py imports the SDK client for unrelated commands. Keep this focused
# CLI test independent of optional database dependencies.
phoenix.PhoenixClient = object
sdk_client = types.ModuleType("phoenix.sdk.client")
sdk_client.PhoenixClient = object
sys.modules.setdefault("phoenix.sdk.client", sdk_client)

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
