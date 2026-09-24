"""Unit tests for conditional LocatorExpert fallback core logic."""

from __future__ import annotations

from phoenix.locators.smartlocator_fallback import (
    build_unresolved_payload,
    fallback_reasons,
    intelligence_discoverer,
    parse_locator_expert_candidates,
    resolve_with_locator_expert,
)
from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy


def _bundle(*, verified=False, match_count=0, stability="Low", warnings=None):
    record = {
        "custom_name": "SubmitButton",
        "locator_type": "CSS Selector",
        "locator_value": ".submit",
        "validated": verified,
        "match_count": match_count,
        "stability": stability,
        "warnings": warnings or [],
        "element_has_working_locator": verified,
        "working_locator_type": "CSS Selector" if verified else None,
        "working_locator_value": "#submit" if verified else None,
        "element_data": {
            "tag": "button",
            "text": "Submit",
            "ancestor_context": {"container_id": "checkout"},
        },
    }
    return LocatorBundle(
        element_name="SubmitButton",
        page="checkout",
        primary=Locator(
            element_name="SubmitButton",
            strategy=LocatorStrategy.CSS,
            value="#submit" if verified else ".submit",
            verified_in_snapshot=verified,
        ),
        metadata={
            "element_identity": "element_data:submit",
            "smartlocator_raw_records": [record],
        },
    )


def test_verified_unique_bundle_is_never_eligible():
    assert fallback_reasons(_bundle(verified=True, match_count=1)) == []


def test_not_found_low_stability_bundle_is_eligible():
    reasons = fallback_reasons(_bundle(match_count=0, stability="Low"))
    assert "not_found" in reasons
    assert "no_validated_working_locator" in reasons
    assert "low_stability" in reasons


def test_ambiguous_medium_warning_bundle_is_eligible():
    reasons = fallback_reasons(
        _bundle(match_count=2, stability="Medium", warnings=["ambiguous selector"])
    )
    assert "ambiguous" in reasons
    assert "unstable_medium_locator" in reasons


def test_payload_contains_identity_context_attempts_and_reasons():
    payload = build_unresolved_payload(
        _bundle(match_count=0),
        page_url="https://app.example/checkout",
    )
    assert payload is not None
    assert payload["element_identity"] == "element_data:submit"
    assert payload["ancestor_context"]["container_id"] == "checkout"
    assert payload["tag"] == "button"
    assert payload["visible_text"] == "Submit"
    assert payload["container_context"] == {"container_id": "checkout"}
    assert payload["custom_name"] == "SubmitButton"
    assert payload["attempted_locators"][0]["match_count"] == 0
    assert "not_found" in payload["fallback_reasons"]


def test_response_parser_rejects_positional_and_unsupported_candidates():
    payload = build_unresolved_payload(_bundle(), page_url="https://app.example")
    candidates = parse_locator_expert_candidates({
        "locators": [
            {"strategy": "css", "value": ".submit", "confidence": 0.8},
            {"strategy": "css", "value": ".button.nth(2)"},
            {"strategy": "css", "value": "li:nth-child(3) button"},
            {"strategy": "made-up", "value": "anything"},
        ],
        "metadata": {"provider": "anthropic", "model": "claude"},
    }, payload)
    assert [(candidate.strategy.value, candidate.value) for candidate in candidates] == [
        ("css", ".submit")
    ]
    assert candidates[0].metadata["source"] == "locator_expert"
    assert candidates[0].metadata["provider"] == "anthropic"


def test_resolved_bundle_causes_zero_locator_expert_calls():
    calls = []

    result = resolve_with_locator_expert(
        [_bundle(verified=True, match_count=1)],
        page_url="https://app.example",
        discover=lambda payload: calls.append(payload) or {},
        validate=lambda candidate, payload: {"match_count": 1},
    )

    assert calls == []
    assert result["llm_calls"] == 0
    assert len(result["resolved_bundles"]) == 1


def test_only_live_unique_llm_candidate_is_merged_as_primary():
    validations = iter([{"match_count": 2}, {"match_count": 1}])

    result = resolve_with_locator_expert(
        [_bundle(match_count=2, stability="Medium")],
        page_url="https://app.example",
        discover=lambda payload: {
            "locators": [
                {"strategy": "role", "value": "button[name=Submit]", "confidence": 0.9},
                {"strategy": "test-id", "value": "submit-button", "confidence": 0.8},
            ],
            "metadata": {"provider": "anthropic", "model": "claude"},
        },
        validate=lambda candidate, payload: next(validations),
    )

    assert result["llm_calls"] == 1
    assert result["unresolved_elements"] == []
    bundle = result["resolved_bundles"][0]
    assert bundle.primary.strategy == LocatorStrategy.TEST_ID
    assert bundle.primary.value == "submit-button"
    assert bundle.primary.verified_in_snapshot is True
    assert bundle.primary.metadata["source"] == "locator_expert"
    assert bundle.primary.metadata["match_count"] == 1
    assert bundle.primary.metadata["attempt_number"] == 2
    assert bundle.primary.metadata["resolution_timestamp"]
    assert any(locator.value == ".submit" for locator in bundle.alternates)


def test_non_unique_llm_candidates_remain_unresolved():
    result = resolve_with_locator_expert(
        [_bundle(match_count=0)],
        page_url="https://app.example",
        discover=lambda payload: {
            "locators": [{"strategy": "css", "value": ".submit"}],
        },
        validate=lambda candidate, payload: {"match_count": 0, "error": "not found"},
    )

    assert result["resolved_bundles"] == []
    assert len(result["unresolved_elements"]) == 1
    assert result["unresolved_elements"][0]["rejected_candidates"][0]["match_count"] == 0
    assert result["unresolved_elements"][0]["rejected_candidates"][0]["rejection_reason"] == "not_found"


def test_locator_expert_failure_remains_unresolved():
    result = resolve_with_locator_expert(
        [_bundle(match_count=0)],
        page_url="https://app.example",
        discover=lambda _payload: (_ for _ in ()).throw(RuntimeError("service down")),
        validate=lambda _candidate, _payload: {"match_count": 1},
    )
    assert result["resolved_bundles"] == []
    assert "locator_expert_failed" in result["unresolved_elements"][0]["error"]
    assert result["llm_calls"] == 1


def test_validation_failure_remains_unresolved():
    result = resolve_with_locator_expert(
        [_bundle(match_count=0)],
        page_url="https://app.example",
        discover=lambda _payload: {
            "locators": [{"strategy": "css", "value": "#submit"}]
        },
        validate=lambda _candidate, _payload: (_ for _ in ()).throw(
            RuntimeError("browser stopped")
        ),
    )
    rejection = result["unresolved_elements"][0]["rejected_candidates"][0]
    assert rejection["match_count"] is None
    assert "validation_failed" in rejection["error"]
    assert result["duration_ms"] >= 0


def test_unique_candidate_for_wrong_element_identity_is_rejected():
    result = resolve_with_locator_expert(
        [_bundle(match_count=2, stability="Medium")],
        page_url="https://app.example",
        discover=lambda _payload: {
            "locators": [{"strategy": "css", "value": "#other-submit"}]
        },
        validate=lambda _candidate, _payload: {
            "match_count": 1,
            "element_identity": "element_data:different-button",
        },
    )

    assert result["resolved_bundles"] == []
    rejection = result["unresolved_elements"][0]["rejected_candidates"][0]
    assert rejection["rejection_reason"] == "wrong_element_identity"


def test_empty_locator_expert_response_has_final_failure_reason():
    result = resolve_with_locator_expert(
        [_bundle(match_count=0)],
        page_url="https://app.example",
        discover=lambda _payload: {"locators": []},
        validate=lambda _candidate, _payload: {"match_count": 1},
    )

    assert result["unresolved_elements"][0]["final_failure_reason"] == (
        "no_valid_locator_expert_candidates"
    )


def test_intelligence_discoverer_sends_one_scoped_strict_request():
    class Client:
        def __init__(self):
            self.kwargs = None

        def discover_locators(self, **kwargs):
            self.kwargs = kwargs
            return {"locators": []}

    client = Client()
    payload = build_unresolved_payload(_bundle(), page_url="https://app.example")
    response = intelligence_discoverer(client)(payload)

    assert response == {"locators": []}
    assert client.kwargs["elements"] == []
    assert client.kwargs["element_contexts"] == [payload]
    assert client.kwargs["require_llm"] is True
