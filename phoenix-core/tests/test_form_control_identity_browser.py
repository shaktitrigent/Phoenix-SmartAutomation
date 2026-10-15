"""Live browser checks for captured form identity; uses a generic local fixture."""
import json
import pytest
from playwright.sync_api import sync_playwright
from phoenix.locators.live_session import LiveLocatorSession
from phoenix_shared.assertion_runtime import validate_target
from phoenix_shared.models.locator import LocatorBundle


@pytest.fixture
def captured_form():
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        try:
            page=browser.new_page()
            page.set_content('''<section id="account-section"><form>
              <label>Account<input name="account" type="text"></label>
              <label>Secret<input name="secret" type="password"></label>
              <button id="continue">Continue</button>
              </form></section><section id="other-section"></section>''')
            bundles=LiveLocatorSession(page).scan(page='form')
            target=next(b for b in bundles if (b.metadata.get('element_data') or {}).get('tag')=='button'
                        and (b.metadata.get('element_data') or {}).get('text')=='Continue')
            assert target.metadata['element_data']['form_control_identity']['version']==1
            yield page,target
        finally:
            browser.close()


def add_message(page):
    page.locator('form').evaluate('''form => {
      const message=document.createElement('p');message.textContent='Required';
      form.insertBefore(message,form.children[1]);
    }''')


def test_capture_persistence_and_runtime_accept_validation_text_change(captured_form):
    page,bundle=captured_form
    bundle=LocatorBundle.model_validate_json(bundle.model_dump_json())
    page.locator('[name=account]').fill('fixture-user')
    page.locator('[name=secret]').fill('fixture-secret')
    add_message(page)
    target=validate_target(page,bundle.model_dump())
    assert target.count()==1
    assert 'fixture-secret' not in json.dumps(bundle.metadata['element_data']['form_control_identity'])
    assert 'fixture-user' not in json.dumps(bundle.metadata['element_data']['form_control_identity'])


def test_changed_control_rejected_after_validation_text_change(captured_form):
    page,bundle=captured_form;add_message(page)
    page.locator('[name=account]').evaluate("n=>n.name='other-account'")
    with pytest.raises(AssertionError,match='identity'):
        validate_target(page,bundle.model_dump())


def test_same_looking_form_moved_to_wrong_scope_rejected(captured_form):
    page,bundle=captured_form
    page.locator('form').evaluate("n=>document.querySelector('#other-section').append(n)")
    with pytest.raises(AssertionError,match='identity'):
        validate_target(page,bundle.model_dump())
