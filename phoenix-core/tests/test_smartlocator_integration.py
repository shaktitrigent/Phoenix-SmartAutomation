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


def test_generate_bundles_can_keep_raw_artifacts(monkeypatch, tmp_path):
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
                "element_data": {"tag": "button", "id": "login"},
            }]
        }), encoding="utf-8")
        return {"locators_json": str(output)}

    monkeypatch.setitem(
        sys.modules,
        "phoenix_smartlocatorai",
        types.SimpleNamespace(generate_locators_from_dom=fake_generate),
    )
    raw_dir = tmp_path / "smartlocator_raw" / "login"

    bundles = generate_smartlocator_bundles(
        "https://app.example",
        page="login",
        output_dir=raw_dir,
    )

    assert len(bundles) == 1
    assert captured["output_dir"] == str(raw_dir)
    assert (raw_dir / "locators.json").is_file()


def test_targeted_generation_filters_elements_before_locator_validation(monkeypatch, tmp_path):
    import pytest

    captured = {}
    package = types.ModuleType("phoenix_smartlocatorai")
    package.__path__ = []
    package.generate_locators_from_dom = lambda *_args, **_kwargs: pytest.fail(
        "targeted scans must use the element-filtered path"
    )
    scanner = types.ModuleType("phoenix_smartlocatorai.dom_scanner")
    elements = [
        {"tag": "input", "aria-label": "Username", "id": "user-name"},
        {"tag": "button", "text": "Purchase", "id": "purchase"},
    ]
    scanner.scan_dom = lambda *_args, **_kwargs: elements
    scanner._guess_custom_name = lambda element: (
        "UsernameInput" if element["tag"] == "input" else "PurchaseButton"
    )

    def generate(selected):
        captured["selected"] = selected
        return [{
            "custom_name": scanner._guess_custom_name(element),
            "locator_type": "CSS Selector",
            "locator_value": "#user-name",
            "validated": False,
            "match_count": 0,
            "element_data": element,
        } for element in selected]

    scanner.generate_locators_from_elements = generate
    core = types.ModuleType("phoenix_smartlocatorai.core")

    def validate(_url, locators, _auth):
        for locator in locators:
            locator.update(validated=True, match_count=1, recommended=True)
        return locators

    core._validate_locators_with_playwright = validate
    monkeypatch.setitem(sys.modules, "phoenix_smartlocatorai", package)
    monkeypatch.setitem(sys.modules, "phoenix_smartlocatorai.dom_scanner", scanner)
    monkeypatch.setitem(sys.modules, "phoenix_smartlocatorai.core", core)

    bundles = generate_smartlocator_bundles(
        "https://app.example",
        page="login",
        validate=True,
        output_dir=tmp_path / "raw",
        element_names=["Username input"],
    )

    assert len(captured["selected"]) == 1
    assert captured["selected"][0]["id"] == "user-name"
    assert len(bundles) == 1
    assert bundles[0].primary.verified_in_snapshot is True


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
