"""Architecture regressions independent of provider credentials/public sites."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from phoenix_shared.locator_policy import locator_accepted
from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy
from phoenix.locators.live_session import LiveLocatorSession, identity_matches, live_session, locator_on_page
from phoenix.locators.reconciliation import reconcile_generated_code
from phoenix.locators.smartlocator_fallback import fallback_reasons, resolve_with_locator_expert
from phoenix.locators.smartlocator_integration import locator_expert_targets, live_locator_validator


def bundle(stability="High", **metadata):
    primary=Locator(element_name="SubmitButton",strategy=LocatorStrategy.CSS,value="#submit",
        verified_in_snapshot=True,metadata={"match_count":1,"identity_matches":True,
            "stability":stability,**metadata})
    return LocatorBundle(element_name="SubmitButton",page="checkout",primary=primary,
        metadata={"element_identity":"submit","element_data":{"tag":"button","id":"submit"}})


@pytest.mark.parametrize("stability,accepted",[("High",True),("Medium",False),("Low",False),(None,False)])
def test_deterministic_stability_gate(stability,accepted):
    b=bundle(stability)
    assert locator_accepted(b.primary,b.metadata) is accepted
    assert bool(fallback_reasons(b)) is not accepted


@pytest.mark.parametrize("metadata",[{"match_count":0},{"match_count":2},{"match_count":True},
    {"match_count":None},{"identity_matches":None},{"identity_matches":False},{"dynamic":True}])
def test_validation_evidence_cannot_be_faked_by_verified_flag(metadata):
    assert not locator_accepted(bundle(**metadata).primary)


def test_expert_acceptance_requires_identity_but_not_deterministic_stability():
    assert locator_accepted(bundle("Low",source="locator_expert").primary)
    assert not locator_accepted(bundle("High",source="locator_expert",identity_matches=None).primary)


def test_threshold_can_tighten_but_cannot_promote_medium():
    assert not locator_accepted(bundle(stability_score=8).primary,stability_threshold=0.9)
    assert not locator_accepted(bundle("Medium",stability_score=10).primary)


@pytest.mark.parametrize("code",[
    'page.locator("#unknown").click()', 'page.click("#unknown")',
    'page.fill(selector, "value")','page.locator(selector).click()',
    'page.get_by_text("Submit").first.click()', 'control.click()',
])
def test_unknown_operations_fail_closed(code):
    final,used,missing=reconcile_generated_code('def test_x(page):\n    '+code+'\n',[])
    assert missing
    assert not used


@pytest.mark.parametrize("code",['page.locator("#submit").click()', 'page.click("#submit")',
    'page.get_by_role("button", name="Submit").click()'])
def test_validated_operations_are_reconciled(code):
    final,used,missing=reconcile_generated_code('def test_x(page):\n    '+code+'\n',[bundle().model_dump()])
    assert not missing
    assert used
    assert '#submit' in final
    assert '.first' not in final


def test_quoted_selectors_render_without_syntax_corruption():
    candidate=Locator(element_name="quote",strategy=LocatorStrategy.CSS,value='[title="A \\"quoted\\" name"]')
    compile(candidate.to_playwright(),"selector","eval")


def test_identity_checks_distinguishing_container():
    expected={"tag":"button","text":"Add to Cart","ancestor_context":{"container_id":"blue-card"}}
    wrong={"tag":"button","text":"Add to Cart","ancestors":[{"id":"red-card"}]}
    right={**wrong,"ancestors":[{"id":"blue-card"}]}
    assert not identity_matches(wrong,expected)
    assert identity_matches(right,expected)
    assert not identity_matches(right,{"tag":"button"})


def test_context_expression_uses_allowlist_no_eval():
    page=Mock()
    c=Locator(element_name="cart",strategy=LocatorStrategy.CONTEXT,
              value='page.locator("#blue-card").getByText(\'Add to Cart\')')
    locator_on_page(page,c)
    page.locator.assert_called_once_with("#blue-card")
    page.locator.return_value.get_by_text.assert_called_once_with("Add to Cart")
    c.value='__import__("os").system("anything")'
    with pytest.raises(ValueError): locator_on_page(page,c)


def test_live_session_validation_does_not_navigate_or_launch():
    page=Mock(url="https://example.test/checkout")
    page.locator.return_value.count.return_value=1
    page.locator.return_value.evaluate.return_value={"tag":"button","id":"submit","ancestors":[]}
    page.locator.return_value.all.return_value=[page.locator.return_value]
    with live_session("https://example.test",page=page) as session:
        outcome=session.validate(bundle().primary,{"element_data":{"tag":"button","id":"submit"}})
    assert outcome["identity_matches"] is True
    assert outcome["validation_url"].endswith("checkout")
    page.goto.assert_not_called()
    page.close.assert_not_called()


def test_missing_page_never_falls_back_to_anonymous_browser():
    result=live_locator_validator("https://example.test")(bundle().primary,{})
    assert result["match_count"] is None
    assert result["error"]=="current_browser_session_required"


def test_old_bundle_is_revalidated_before_acceptance():
    b=bundle()
    page=Mock(url="https://example.test")
    page.locator.return_value.count.return_value=0
    updated=LiveLocatorSession(page).revalidate([b])[0]
    assert not locator_accepted(updated.primary)
    assert updated.primary.metadata["match_count"]==0


def test_repeated_elements_produce_disambiguation_target():
    a=bundle("Low").model_copy(update={"element_name":"SubmitButton"})
    b=a.model_copy(update={"metadata":{**a.metadata,"element_identity":"other"}})
    targets=locator_expert_targets(["Submit button"],[a,b],page="checkout")
    assert len(targets)==1
    assert len(targets[0].metadata["candidate_elements"])==2


def test_expert_count_only_response_is_rejected():
    result=resolve_with_locator_expert([bundle("Low")],page_url="https://example.test",
        discover=lambda _: {"locators":[{"strategy":"css","value":"#submit"}]},
        validate=lambda *args:{"match_count":1})
    assert not result["resolved_bundles"]
    assert result["unresolved_elements"][0]["rejected_candidates"][0]["rejection_reason"]=="missing_identity_evidence"


def test_successful_expert_replaces_unique_but_low_stability_primary():
    result=resolve_with_locator_expert([bundle("Low")],page_url="https://example.test",
        discover=lambda _: {"locators":[{"strategy":"css","value":"#stable-submit"}]},
        validate=lambda *args:{"match_count":1,"identity_matches":True})
    assert result["resolved_bundles"][0].primary.value=="#stable-submit"
    assert locator_accepted(result["resolved_bundles"][0].primary)


def test_unchanged_context_stops_paid_retries():
    discover=Mock(return_value={"locators":[{"strategy":"css","value":".submit"}]})
    result=resolve_with_locator_expert([bundle("Low")],page_url="https://example.test",
        discover=discover,validate=lambda *args:{"match_count":2},max_rounds=3,
        capture=lambda *args:{"capture_status":"captured","context_fingerprint":"same"})
    assert discover.call_count==1
    assert result["unresolved_elements"][0]["final_failure_reason"]=="context_unchanged_after_rejection"


def test_missing_live_context_does_not_call_expert():
    discover=Mock()
    result=resolve_with_locator_expert([bundle("Low")],page_url="https://example.test",
        discover=discover,validate=Mock(),capture=lambda *args:{"capture_status":"insufficient_context"})
    discover.assert_not_called()
    assert result["unresolved_elements"][0]["final_failure_reason"]=="insufficient_live_context"
