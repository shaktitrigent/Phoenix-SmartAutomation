"""Tests for the SmartLocatorAI adapter conversion layer."""

from __future__ import annotations

import json
import sys
from pathlib import Path


phoenix_core_path = Path(__file__).resolve().parents[1]
repo_root = phoenix_core_path.parent
sys.path.insert(0, str(phoenix_core_path))
sys.path.insert(0, str(repo_root))

from phoenix.locators.smartlocator_adaptor import convert_file, convert_locators
from shared.phoenix_shared.models.locator import LocatorStrategy


def _identity_payload(identity: str) -> dict:
    return {"element_data": {"dom_id": identity, "tag": "button", "role": "button"}}


def test_validated_recommended_locator_wins():
    bundles = convert_locators(
        [
            {
                "custom_name": "LoginButton",
                **_identity_payload("login-button"),
                "recommended": {
                    "locator_type": "CSS Selector",
                    "locator_value": "#login",
                    "validated": True,
                    "stability_score": 9,
                },
                "locators": [
                    {
                        "locator_type": "XPath",
                        "locator_value": "//button[@id='login']",
                        "stability_score": 2,
                    }
                ],
                "warnings": ["keep"],
            }
        ]
    )

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.primary.strategy == LocatorStrategy.CSS
    assert bundle.primary.value == "#login"
    assert bundle.primary.verified_in_snapshot is True
    assert bundle.primary.metadata["smartlocator_recommended"] is True
    assert bundle.primary.metadata.get("smartlocator_working_rollup") is None
    assert bundle.metadata["warnings"] == ["keep"]


def test_working_rollup_replaces_invalid_recommended_locator():
    bundles = convert_locators(
        [
            {
                "custom_name": "LoginButton",
                **_identity_payload("login-button"),
                "recommended": {
                    "locator_type": "CSS Selector",
                    "locator_value": "#broken",
                    "validated": False,
                    "stability_score": 9,
                },
                "element_has_working_locator": True,
                "working_locator_type": "XPath",
                "working_locator_value": "//button[@data-testid='login']",
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#broken",
                        "stability_score": 9,
                    }
                ],
            }
        ]
    )

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.primary.strategy == LocatorStrategy.XPATH
    assert bundle.primary.value == "//button[@data-testid='login']"
    assert any(loc.strategy == LocatorStrategy.CSS and loc.value == "#broken" for loc in bundle.alternates)


def test_no_working_fallback_preserves_existing_behavior():
    bundles = convert_locators(
        [
            {
                "custom_name": "LoginButton",
                **_identity_payload("login-button"),
                "recommended": {
                    "locator_type": "CSS Selector",
                    "locator_value": "#broken",
                    "validated": False,
                    "stability_score": 1,
                },
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#broken",
                        "stability_score": 1,
                    },
                    {
                        "locator_type": "XPath",
                        "locator_value": "//button[@id='login']",
                        "stability_score": 8,
                    },
                ],
            }
        ]
    )

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.primary.strategy == LocatorStrategy.XPATH
    assert bundle.primary.value == "//button[@id='login']"


def test_incomplete_working_fallback_is_ignored():
    bundles = convert_locators(
        [
            {
                "custom_name": "LoginButton",
                **_identity_payload("login-button"),
                "recommended": {
                    "locator_type": "CSS Selector",
                    "locator_value": "#broken",
                    "validated": False,
                    "stability_score": 1,
                },
                "element_has_working_locator": True,
                "working_locator_type": None,
                "working_locator_value": None,
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#fallback",
                        "stability_score": 6,
                    }
                ],
            }
        ]
    )

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.primary.value == "#fallback"
    assert bundle.primary.strategy == LocatorStrategy.CSS


def test_metadata_is_preserved_on_bundle_and_primary():
    bundles = convert_locators(
        [
            {
                "custom_name": "ProfileLink",
                **_identity_payload("profile-link"),
                "recommended": {
                    "locator_type": "Text Selector",
                    "locator_value": "Profile",
                    "validated": True,
                    "stability_score": 7,
                },
                "context_strategy": "near_text",
                "stability": {"category": "stable", "details": "aria label"},
                "stability_score": 7,
                "stability_category": "stable",
                "stability_details": "aria label",
                "estimated_unique": True,
                "warnings": ["a", "b"],
                "element_has_working_locator": True,
                "working_locator_type": "CSS Selector",
                "working_locator_value": "a[data-testid='profile']",
            }
        ]
    )

    bundle = bundles[0]
    assert bundle.metadata["context_strategy"] == "near_text"
    assert bundle.metadata["stability_category"] == "stable"
    assert bundle.metadata["stability_details"] == "aria label"
    assert bundle.metadata["estimated_unique"] is True
    assert bundle.metadata["warnings"] == ["a", "b"]
    assert bundle.metadata["element_has_working_locator"] is True
    assert bundle.metadata["working_locator_type"] == "CSS Selector"
    assert bundle.metadata["working_locator_value"] == "a[data-testid='profile']"
    assert bundle.primary.metadata["smartlocator_recommended"] is True
    assert bundle.primary.metadata.get("smartlocator_working_rollup") is None
    assert bundle.primary.verified_in_snapshot is True


def test_same_physical_element_with_different_names_merges_to_one_bundle():
    identity = _identity_payload("shared-element")
    bundles = convert_locators(
        [
            {
                "custom_name": "login_button",
                **identity,
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#login",
                        "stability_score": 4,
                    }
                ],
                "warnings": ["from extractor"],
            },
            {
                "custom_name": "sign_in_button",
                **identity,
                "recommended": {
                    "locator_type": "XPath",
                    "locator_value": "//button[@id='login']",
                    "validated": True,
                    "stability_score": 9,
                },
                "warnings": ["from smartlocator"],
            },
        ]
    )

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.element_name == "login_button"
    assert bundle.primary.strategy == LocatorStrategy.XPATH
    assert bundle.primary.value == "//button[@id='login']"
    assert bundle.metadata["source_names"] == ["login_button", "sign_in_button"]
    assert bundle.metadata["warnings"] == ["from extractor", "from smartlocator"]


def test_different_physical_elements_with_same_name_do_not_merge():
    bundles = convert_locators(
        [
            {
                "custom_name": "submit_button",
                **_identity_payload("submit-a"),
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#submit-a",
                        "stability_score": 5,
                    }
                ],
            },
            {
                "custom_name": "submit_button",
                **_identity_payload("submit-b"),
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#submit-b",
                        "stability_score": 5,
                    }
                ],
            },
        ]
    )

    assert len(bundles) == 2
    identities = {bundle.metadata["element_identity"] for bundle in bundles}
    assert len(identities) == 2
    assert all(identity.startswith("element_data:") for identity in identities)


def test_merged_entry_keeps_stronger_locator():
    identity = _identity_payload("merge-target")
    bundles = convert_locators(
        [
            {
                "custom_name": "merge_target",
                **identity,
                "recommended": {
                    "locator_type": "CSS Selector",
                    "locator_value": "#broken",
                    "validated": False,
                    "stability_score": 2,
                },
                "warnings": ["broken"],
            },
            {
                "custom_name": "merge_target_alt",
                **identity,
                "recommended": {
                    "locator_type": "XPath",
                    "locator_value": "//button[@id='good']",
                    "validated": True,
                    "stability_score": 9,
                },
                "warnings": ["good"],
            },
        ]
    )

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.primary.strategy == LocatorStrategy.XPATH
    assert bundle.primary.value == "//button[@id='good']"
    assert bundle.primary.verified_in_snapshot is True


def test_merge_preserves_metadata_from_both_representations():
    identity = _identity_payload("merge-meta")
    bundles = convert_locators(
        [
            {
                "custom_name": "merge_meta",
                **identity,
                "context_strategy": "role-first",
                "stability": {"category": "stable"},
                "warnings": ["one"],
                "locators": [
                    {
                        "locator_type": "CSS Selector",
                        "locator_value": "#first",
                        "stability_score": 5,
                    }
                ],
            },
            {
                "custom_name": "merge_meta_alt",
                **identity,
                "estimated_unique": False,
                "working_locator_type": "XPath",
                "working_locator_value": "//button[@id='second']",
                "element_has_working_locator": True,
                "warnings": ["two"],
            },
        ]
    )

    bundle = bundles[0]
    assert bundle.metadata["context_strategy"] == "role-first"
    assert bundle.metadata["warnings"] == ["one", "two"]
    assert bundle.metadata["working_locator_type"] == "XPath"
    assert bundle.metadata["working_locator_value"] == "//button[@id='second']"
    assert bundle.metadata["element_has_working_locator"] is True


def test_convert_file_supports_top_level_recommended_locator(tmp_path):
    payload = {
        "recommended_locator": {
            "custom_name": "TopLevelRecommended",
            **_identity_payload("top-level"),
            "locator_type": "CSS Selector",
            "locator_value": "#top-level",
            "validated": True,
            "stability_score": 9,
        },
        "locators": [],
    }
    path = tmp_path / "smartlocator.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    bundles = convert_file(path)
    assert len(bundles) == 1
    assert bundles[0].primary.value == "#top-level"
