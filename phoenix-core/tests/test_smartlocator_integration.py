"""Tests for the SmartLocatorAI runtime orchestration seam."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from phoenix.locators.smartlocator_integration import (
    SmartLocatorUnavailableError,
    enrich_automation_tests_with_smartlocator,
    generate_smartlocator_bundles,
    smartlocator_prompt_context,
)


def test_generate_bundles_runs_validated_js_prepass(monkeypatch):
    captured = {}

    def fake_generate(url, **kwargs):
        captured.update({"url": url, **kwargs})
        output = Path(kwargs["output_dir"]) / "locators.json"
        output.write_text(json.dumps({
            "locators": [{
                "custom_name": "LoginButton",
                "locator_type": "CSS Selector",
                "locator_value": "#login",
                "validated": True,
                "match_count": 1,
                "recommended": True,
                "element_data": {"tag": "button", "id": "login"},
            }]
        }), encoding="utf-8")
        return {"locators_json": str(output)}

    monkeypatch.setitem(
        sys.modules,
        "phoenix_smartlocatorai",
        types.SimpleNamespace(generate_locators_from_dom=fake_generate),
    )

    bundles = generate_smartlocator_bundles("https://app.example", page="login")

    assert len(bundles) == 1
    assert bundles[0].page == "login"
    assert bundles[0].primary.value == "#login"
    assert bundles[0].primary.verified_in_snapshot is True
    assert captured["use_js"] is True
    assert captured["validate"] is True


def test_missing_package_has_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "phoenix_smartlocatorai", None)
    with pytest.raises(SmartLocatorUnavailableError, match="pip install -e"):
        generate_smartlocator_bundles("https://app.example")


def test_enrichment_feeds_same_bundles_to_flat_and_pom_locator_inputs():
    from phoenix.locators.smartlocator_adaptor import convert_locators

    bundles = convert_locators([{
        "custom_name": "SubmitButton",
        "locator_type": "CSS Selector",
        "locator_value": "#submit",
        "validated": True,
        "recommended": True,
        "element_data": {"tag": "button", "id": "submit"},
    }], page="form")
    tests = [
        {"name": "flat", "locators": []},
        {"name": "pom", "pom_bundle": {}, "locators": []},
    ]

    enriched = enrich_automation_tests_with_smartlocator(tests, bundles)

    for test in enriched:
        assert test["locators"][0]["primary"]["value"] == "#submit"
        assert test["locators"][0]["page"] == "form"

    context = smartlocator_prompt_context(bundles)
    assert "SmartLocatorAI validated locator evidence" in context
    assert '"value":"#submit"' in context
    assert "verified_in_snapshot" in context
