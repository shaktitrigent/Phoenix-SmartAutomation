"""Browser checks for exact text, native tag and container preservation."""
import pytest
from playwright.sync_api import sync_playwright
from phoenix_shared.generation_contract import outcome_contract,Snapshot
from phoenix_shared.assertion_runtime import assert_contract


@pytest.fixture
def page():
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        try:yield browser.new_page()
        finally:browser.close()


def contract():
    text='The central `h3` element with text `Account Overview` is visible within the `main` content area.'
    return outcome_contract(text,'Check content',Snapshot('<body>Initial page</body>'),1)


def test_exact_heading_is_scoped_to_main(page):
    page.set_content('<aside><h3>Account Overview</h3></aside><main><h3>Account Overview</h3></main>')
    assert_contract(page,contract(),timeout=500)


@pytest.mark.parametrize('html',[
    '<aside><h3>Account Overview</h3></aside><main><p>h3</p></main>',
    '<main><h2>Account Overview</h2></main>',
    '<main><h3>Account Overview Settings</h3></main>',
    '<main><h3>Account Overview<span> Settings</span></h3></main>',
    '<main><h3>Account Overview</h3><h3>Account Overview</h3></main>',
])
def test_wrong_scope_tag_text_or_duplicate_cannot_pass(page,html):
    page.set_content(html)
    with pytest.raises(AssertionError):assert_contract(page,contract(),timeout=500)
