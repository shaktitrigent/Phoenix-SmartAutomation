import copy

import pytest
from playwright.sync_api import sync_playwright

from phoenix.locators.live_session import LiveLocatorSession, observed_click_paths
from phoenix_shared.models.locator import Locator, LocatorStrategy
from phoenix_smartlocatorai.dom_scanner import extract_interactable_elements


def candidate(selector):
    return Locator(element_name='Trigger', strategy=LocatorStrategy.CSS, value=selector)


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser.new_page()
        finally:
            browser.close()


def capture(page, html, selector='section#account button', slots=None):
    page.set_content(html)
    elements = extract_interactable_elements(page.content(), interaction_paths=observed_click_paths(page))
    session = LiveLocatorSession(page)
    session.apply_content_identity(elements, {'selector':selector,
        'mutable_text_selectors':slots or ['.display']})
    return session, next(e for e in elements if e.get('content_identity'))


def test_explicit_display_change_preserves_identity_and_other_text(page):
    session, expected = capture(page, '''<section id="account"><div class="tools">
        <button class="menu"><span class="display">User A</span><b>Account actions</b></button>
        </div></section>''')
    page.locator('.display').evaluate("n => n.textContent = 'User B'")
    assert session.validate(candidate('button'), {'element_data':expected})['identity_matches']
    page.locator('b').evaluate("n => n.textContent = 'Billing actions'")
    assert not session.validate(candidate('button'), {'element_data':expected})['identity_matches']
    # Undeclared historical descriptors still require exact display text.
    ordinary = copy.deepcopy(expected)
    ordinary.pop('content_identity')
    assert not session.validate(candidate('button'), {'element_data':ordinary})['identity_matches']


def test_different_unique_same_looking_trigger_rejected(page):
    session, expected = capture(page, '''<section id="account"><div class="tools">
        <button class="menu"><span class="display">User A</span></button></div></section>
        <section id="billing"><div class="tools"><button class="menu">
        <span class="display">User A</span></button></div></section>''')
    outcome = session.validate(candidate('#billing button'), {'element_data':expected})
    assert outcome['match_count'] == 1
    assert not outcome['identity_matches']
    page.locator('#account button').evaluate("n => n.setAttribute('data-testid','other-trigger')")
    assert not session.validate(candidate('#account button'), {'element_data':expected})['identity_matches']


def test_repeated_controls_require_remaining_distinguishing_text(page):
    session, expected = capture(page, '''<section id="account"><div class="tools">
        <button class="menu"><span class="display">User A</span><b>Personal</b></button>
        <button class="menu"><span class="display">User A</span><b>Team</b></button>
        </div></section>''', selector='button:has-text("Personal")')
    page.locator('button:has-text("Personal") .display').evaluate("n=>n.textContent='User B'")
    assert session.validate(candidate('button:has-text("Personal")'), {'element_data':expected})['identity_matches']
    wrong = session.validate(candidate('button:has-text("Team")'), {'element_data':expected})
    assert wrong['match_count'] == 1
    assert not wrong['identity_matches']


def test_ambiguous_mutable_display_contract_rejected_at_capture(page):
    with pytest.raises(ValueError, match='uniquely establish'):
        capture(page, '''<section id="account"><div class="tools">
          <button class="menu"><span class="display">User A</span></button>
          <button class="menu"><span class="display">User B</span></button>
          </div></section>''',selector='button:has-text("User A")')


def test_new_lookalike_breaks_live_identity_uniqueness(page):
    session, expected = capture(page, '''<section id="account"><div class="tools">
        <button class="menu"><span class="display">User A</span></button></div></section>''')
    page.locator('button').evaluate("n => {const copy=n.cloneNode(true);copy.querySelector('.display').textContent='User B';n.after(copy)}")
    outcome = session.validate(candidate('button:has-text("User A")'), {'element_data':expected})
    assert outcome['match_count'] == 1
    assert not outcome['identity_matches']


def test_custom_trigger_policy_survives_capture_adapter_and_runtime(page):
    from phoenix_shared.assertion_runtime import validate_target
    page.set_content('''<header><nav id="site-header"><ul><li id="account-trigger" class="profile">
        <em class="display">Member A</em><i class="caret"></i></li></ul></nav></header>
        <script>document.querySelector('li').addEventListener('click',()=>{});</script>''')
    bundles = LiveLocatorSession(page).scan(identity_policies=[
        {'selector':'#account-trigger','mutable_text_selectors':['em.display']}])
    bundle = next(b for b in bundles if b.metadata.get('element_data',{}).get('content_identity'))
    assert bundle.metadata['element_data']['interaction_evidence']['source'] == 'browser_event_listener'
    evidence = bundle.model_dump(mode='json')
    page.locator('em').evaluate("n=>n.textContent='Member B'")
    assert validate_target(page,evidence).count() == 1
    page.locator('nav').evaluate("n=>n.id='different-header'")
    with pytest.raises(AssertionError, match='identity'):
        validate_target(page,evidence)


@pytest.mark.parametrize('markup', ['<a class="display" href="/exit">Exit</a>',
    '<span class="display"><b>Display</b></span>', '<span class="other">Display</span>'])
def test_mutable_slots_cannot_hide_interactive_or_structural_identity(page, markup):
    with pytest.raises(Exception, match='distinct noninteractive text leaves'):
        capture(page, f'<section id="account"><div class="tools"><button class="menu">{markup}</button></div></section>')
