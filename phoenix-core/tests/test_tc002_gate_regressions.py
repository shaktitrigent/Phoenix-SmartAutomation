"""Regressions for generated helper provenance and document readiness."""
from types import SimpleNamespace

import pytest

from phoenix.locators.reconciliation import reconcile_generated_code
from phoenix.locators.smartlocator_adaptor import convert_locators
from phoenix.locators.live_session import LiveLocatorSession
from phoenix_shared.automation_translation import step_coverage


GUARD = '''def unique_visible(locator, description):
    expect(locator).to_have_count(1)
    expect(locator).to_be_visible()
    return locator
'''


@pytest.mark.parametrize("operation", ["target.click()", "target.fill(value)"])
def test_generated_guard_preserves_checked_helper_binding(operation):
    source = GUARD + 'def fill_ready(page, locator, value, description):\n    target = unique_visible(locator, description)\n    ' + operation + '\n'
    assert reconcile_generated_code(source, [])[2] == []


def test_helper_cannot_authorize_unvalidated_call_site():
    source = GUARD + 'def click_ready(page, locator, description):\n    target = unique_visible(locator, description)\n    target.click()\ndef test_x(page):\n    click_ready(page, page.locator("#unknown"), "Unknown")\n'
    assert reconcile_generated_code(source, [])[2]


def test_unknown_or_mutating_guard_cannot_establish_alias():
    for guard in ['', GUARD.replace('return locator', 'return page.locator("#other")'),
                  GUARD.replace('return locator', 'locator = page.locator("#other")\n    return locator')]:
        source = guard + 'def click_ready(page, locator, description):\n    target = unique_visible(locator, description)\n    target.click()\n'
        assert reconcile_generated_code(source, [])[2]


@pytest.mark.parametrize("root", ["page", "authenticated_page", "self.page", "self._page"])
def test_only_positive_body_readiness_is_infrastructure(root):
    assert reconcile_generated_code('def test_x(page):\n    expect(' + root + '.locator("body")).to_be_visible()\n', [])[2] == []


@pytest.mark.parametrize("expression", [
    'page.locator("body").click()',
    'expect(page.locator("body")).not_to_be_visible()',
    'expect(page.locator("#form")).to_be_visible()',
    'expect(page.get_by_text("Logged in as")).not_to_be_visible()',
    'expect(page.get_by_text("Login error")).to_be_visible()',
])
def test_business_actions_and_state_assertions_still_require_evidence(expression):
    assert reconcile_generated_code('def test_x(page):\n    ' + expression + '\n', [])[2]


def records():
    common = dict(custom_name='LoginButton', element_data={'dom_id':'login-btn','tag':'button'},
        element_has_working_locator=True, working_locator_type='Role', working_locator_value='button[name="Login"]', validated=True)
    return [
        dict(common, locator_type='CSS Selector', locator_value='.login', stability='Low', stability_score=2, duplicate=True),
        dict(common, locator_type='Role', locator_value='button[name="Login"]', stability='High', stability_score=9, duplicate=False),
    ]


def test_rollup_does_not_copy_other_selectors_stability_or_duplicate_flag():
    bundles = convert_locators(records(), page='login')
    role = next(c for c in [bundles[0].primary, *bundles[0].alternates] if c.value == 'button[name="Login"]')
    assert role.metadata['stability'] == 'High'
    assert role.metadata['stability_score'] == 9
    assert role.metadata['duplicate'] is False
    css = next(c for c in [bundles[0].primary, *bundles[0].alternates] if c.value == '.login')
    assert css.metadata['stability'] == 'Low'
    assert css.metadata['duplicate'] is True


def test_old_bundle_metadata_recovered_then_revalidated_on_current_page():
    stored = convert_locators(records(), page='login')[0]
    stored.primary.metadata.update(stability=['Low','High'], duplicate=True)
    session = LiveLocatorSession(SimpleNamespace(url='https://example.test/login'))
    session.wait_for_ready=lambda: None  # This unit fixture supplies validation, not a browser.
    outcomes=[]
    def validate(candidate, payload):
        outcomes.append(candidate.value)
        return {'match_count':1, 'identity_matches':True}
    session.validate=validate
    restored = session.revalidate([stored])[0]
    assert restored.primary.metadata['stability'] == 'High'
    assert restored.primary.metadata['duplicate'] is False
    assert restored.primary.value in outcomes
    session.validate=lambda *args: {'match_count':0,'identity_matches':False}
    rejected=session.revalidate([stored])[0]
    assert not rejected.primary.verified_in_snapshot


def test_coverage_keeps_unreachable_steps_unresolved_but_reports_first_blocker():
    source='def test_x(page):\n    page.goto("/login")\n    pytest.skip("untranslated expected result")\n    page.get_by_text("Login").click()\n'
    result=step_coverage(source,[{'action':'Click Login'}])
    assert result['implemented_steps']==0
    assert result['unresolved_steps']==[1]
    assert result['first_blocking_line']==3
    assert result['unreachable_operations']==1
