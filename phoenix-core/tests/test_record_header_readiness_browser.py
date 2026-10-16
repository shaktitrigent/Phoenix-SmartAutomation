"""Real browser coverage for result tables that render after their container."""
import pytest
from phoenix_shared.assertion_runtime import validate_target


@pytest.fixture
def live_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        yield page
        browser.close()


def evidence():
    return {'element_name':'Results','primary':{'strategy':'css','value':'#results','verified_in_snapshot':True,
        'metadata':{'stability':'High','match_count':1,'identity_matches':True}},
        'metadata':{'element_data':{'tag':'div','role':'table','column_headers':['Code','Name']}}}


def test_delayed_headers_require_full_identity_before_acceptance(live_page):
    live_page.set_content('<div id="results" role="table" style="min-height:20px">Loading</div>')
    live_page.evaluate('''() => setTimeout(()=>{
        document.querySelector('#results').innerHTML=
        '<div role="columnheader">Code</div><div role="columnheader">Name</div>';
    },250)''')
    assert validate_target(live_page,evidence(),timeout=2000).count()==1


def test_wrong_full_headers_are_rejected(live_page):
    live_page.set_content('<div id="results" role="table"><div role="columnheader">Code</div><div role="columnheader">Other</div></div>')
    with pytest.raises(AssertionError,match='Target identity'):
        validate_target(live_page,evidence(),timeout=500)


def test_headers_never_appearing_still_fail(live_page):
    live_page.set_content('<div id="results" role="table">Loading</div>')
    with pytest.raises(AssertionError,match='Target identity'):
        validate_target(live_page,evidence(),timeout=200)


def test_duplicate_physical_table_identity_still_fails(live_page):
    headers='<div role="columnheader">Code</div><div role="columnheader">Name</div>'
    live_page.set_content('<div id="results" role="table">'+headers+'</div><div role="table">'+headers+'</div>')
    with pytest.raises(AssertionError,match='Target identity'):
        validate_target(live_page,evidence(),timeout=500)
