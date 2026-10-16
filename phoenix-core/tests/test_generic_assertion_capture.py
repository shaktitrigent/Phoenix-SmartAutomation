from playwright.sync_api import sync_playwright

from phoenix.locators.live_session import LiveLocatorSession
from phoenix_shared.models.locator import Locator, LocatorStrategy
from phoenix_smartlocatorai.dom_scanner import extract_interactable_elements


def candidate(value):
    return Locator(element_name='Target', strategy=LocatorStrategy.CSS, value=value)


def test_real_preceding_heading_identity_rejects_unique_wrong_section():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content('''<h2>Primary</h2><section class="panel"><div class="actions">
                <button value="a">Save</button></div></section>
                <h2>Other</h2><section class="panel"><div class="actions">
                <button value="b">Save</button></div></section>''')
            expected = next(e for e in extract_interactable_elements(page.content())
                            if e['tag'] == 'button')
            session = LiveLocatorSession(page)
            right = session.validate(candidate("button[value='a']"), {'element_data': expected})
            wrong = session.validate(candidate("button[value='b']"), {'element_data': expected})
            assert right['match_count'] == wrong['match_count'] == 1
            assert right['identity_matches'] is True
            assert wrong['identity_matches'] is False
        finally:
            browser.close()


def test_real_repeated_validation_messages_have_distinct_identity():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content('''<h2>Access</h2><form>
              <div class="field"><label>Account</label> <input name="account">
                <span class="validation-message">Required</span></div>
              <div class="field"><label>Passcode</label> <input name="passcode">
                <span class="validation-message">Required</span></div></form>''')
            messages = [e for e in extract_interactable_elements(page.content())
                        if e.get('text') == 'Required']
            assert len(messages) == 2
            session = LiveLocatorSession(page)
            for expected, name in zip(messages, ('account', 'passcode')):
                right = session.validate(candidate(f"div.field:has(input[name='{name}']) span"),
                                         {'element_data': expected})
                other = 'passcode' if name == 'account' else 'account'
                wrong = session.validate(candidate(f"div.field:has(input[name='{other}']) span"),
                                         {'element_data': expected})
                assert right['match_count'] == wrong['match_count'] == 1
                assert right['identity_matches'] is True
                assert wrong['identity_matches'] is False
        finally:
            browser.close()


def test_custom_click_capture_requires_browser_listener_evidence():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content('''<span class="control">Account menu</span>
                <span style="cursor:pointer">Decoration</span>
                <script>document.querySelector('.control').addEventListener('click',()=>{});
                document.body.addEventListener('click',()=>{});</script>''')
            bundles = LiveLocatorSession(page).scan()
            observed = [b for b in bundles if b.metadata.get('element_data', {}).get('interaction_evidence')]
            assert len(observed) == 1
            assert observed[0].metadata['element_data']['text'] == 'Account menu'
            assert not any(b.metadata.get('element_data', {}).get('text') == 'Decoration' for b in bundles)
        finally:
            browser.close()


def test_stored_revalidation_waits_for_delayed_hydration():
    from phoenix_shared.models.locator import LocatorBundle
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content('''<main aria-busy="true"></main><script>
                setTimeout(()=>{const main=document.querySelector('main');
                main.innerHTML='<input id="account">';main.removeAttribute('aria-busy');},650);
                </script>''')
            bundle = LocatorBundle(element_name='Account', page='login',
                primary=candidate('#account').model_copy(update={'metadata': {'stability': 'High'}}),
                metadata={'element_data': {'tag': 'input', 'id': 'account'}})
            validated = LiveLocatorSession(page).revalidate([bundle])[0]
            assert validated.primary.metadata['match_count'] == 1
            assert validated.primary.metadata['identity_matches'] is True
            assert validated.primary.verified_in_snapshot is True
        finally:
            browser.close()


def test_journey_fallback_is_scoped_and_rejects_unique_wrong_message(tmp_path, monkeypatch):
    import json
    from contextlib import contextmanager
    from phoenix.locators.journey import capture_journey
    from phoenix.locators.registry import LocatorRegistry
    states = tmp_path/'states.json'
    states.write_text(json.dumps({'states': [{'name': 'validation', 'fallback_targets': [
        {'name': 'AccountRequired', 'selector': "div.field:has(input[name='account']) span"}
    ]}]}))
    calls = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content('''<h2>Access</h2><form>
              <div class="field"><label>Account</label> <input name="account">
                <span class="validation-message">Required</span></div>
              <div class="field"><label>Passcode</label> <input name="passcode">
                <span class="validation-message">Required</span></div></form>''')
            @contextmanager
            def session(*args, **kwargs):
                yield LiveLocatorSession(page)
            monkeypatch.setattr('phoenix.locators.live_session.live_session', session)
            def discover(payload):
                calls.append(payload)
                return {'locators': [
                    {'strategy': 'css', 'value': "div.field:has(input[name='passcode']) span"},
                    {'strategy': 'css', 'value': "div.field:has(input[name='account']) span"},
                ]}
            result = capture_journey('https://fixture.test', states, tmp_path/'raw',
                                     tmp_path/'locators', values={}, discover=discover)
            assert len(calls) == 1
            assert calls[0]['original_element_name'] == 'AccountRequired'
            assert calls[0]['state_name'] == 'validation'
            saved = list(LocatorRegistry.load_page(tmp_path/'locators/validation.json'))
            required = next(b for b in saved if b.element_name == 'AccountRequired')
            assert 'account' in required.primary.value
            assert required.primary.metadata['match_count'] == 1
            assert required.primary.metadata['identity_matches'] is True
            assert result['states'][0]['llm_calls'] == 1
            assert not any(b.primary.metadata.get('source') == 'locator_expert'
                           for b in saved if b.element_name != 'AccountRequired')
        finally:
            browser.close()
