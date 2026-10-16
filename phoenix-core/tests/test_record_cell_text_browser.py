import pytest
from phoenix_shared.assertion_runtime import assert_contract


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch()
        try:yield browser.new_page()
        finally:browser.close()


def contract(values=None,kind='record_present'):
    return {'version':1,'kind':kind,'scope':"page.locator('#results')",'record_role':'row',
            'expected_values':values or ['Ada Example']}


@pytest.mark.parametrize('native',[False,True])
def test_adjacent_cells_form_one_record_without_raw_text_whitespace(page,native):
    if native:html='<table id="results"><tr><td>123</td><td>Ada</td><td>Example</td></tr></table>'
    else:html='<div id="results" role="table"><div role="row"><div role="cell">123</div><div role="cell">Ada</div><div role="cell">Example</div></div></div>'
    page.set_content(html)
    assert 'Ada Example' not in page.locator('#results').text_content()
    assert_contract(page,contract(),timeout=500)


@pytest.mark.parametrize('body',[
    '<div role="row"><div role="cell">Ada</div></div><div role="row"><div role="cell">Example</div></div>',
    '<div role="row"><div role="cell">Ada</div><div role="cell">ExampleExtra</div></div>',
    '<div role="row"><div role="cell">Ada</div><div role="cell">Example</div></div>'*2,
    '<div role="row" style="display:none"><div role="cell">Ada</div><div role="cell">Example</div></div>',
])
def test_wrong_partial_split_hidden_or_duplicate_record_fails(page,body):
    page.set_content('<div id="results" role="table" style="min-height:20px">'+body+'</div>')
    with pytest.raises(AssertionError,match='matching visible record'):
        assert_contract(page,contract(),timeout=100)


def test_absence_detects_name_across_cells(page):
    page.set_content('<table id="results"><tr><td>Ada</td><td>Example</td></tr></table>')
    with pytest.raises(AssertionError,match='matching visible record'):
        assert_contract(page,contract(kind='record_absent'),timeout=100)


def test_nested_rows_are_not_combined(page):
    page.set_content('<div id="results" role="table"><div role="row"><div role="cell">Ada</div><div role="row"><div role="cell">Example</div></div></div></div>')
    with pytest.raises(AssertionError,match='matching visible record'):
        assert_contract(page,contract(),timeout=100)


@pytest.mark.parametrize('native',[True,False])
def test_column_headings_do_not_prove_record_data(page,native):
    if native:html='<table id="results"><thead><tr><th>Ada</th><th>Example</th></tr></thead></table>'
    else:html='<div id="results" role="table"><div role="row"><div role="columnheader">Ada</div><div role="columnheader">Example</div></div></div>'
    page.set_content(html)
    with pytest.raises(AssertionError,match='matching visible record'):
        assert_contract(page,contract(),timeout=100)
