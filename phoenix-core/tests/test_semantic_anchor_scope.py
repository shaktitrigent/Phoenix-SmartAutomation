from unittest.mock import Mock
from phoenix.locators.live_session import LiveLocatorSession
from phoenix_shared.models.locator import Locator,LocatorStrategy


def validate_with_tables(monkeypatch,tables):
    import phoenix.locators.live_session as module
    actual={'tag':'div','role':'table','column_headers':['Identifier','Name']}
    target=Mock();target.count.return_value=1;target.evaluate.return_value=actual
    anchors=Mock();anchors.count.return_value=len(tables);anchors.all.return_value=tables
    layout=Mock();layout.count.return_value=800
    page=Mock(url='https://fixture/list')
    page.locator.side_effect=lambda selector:anchors if selector=='div[role="table"]' else layout
    monkeypatch.setattr(module,'locator_on_page',lambda *args:target)
    session=LiveLocatorSession(page)
    candidate=Locator(element_name='Results',strategy=LocatorStrategy.CSS,value='[role="table"]')
    return session.validate(candidate,{'element_data':actual}),page


def table():
    node=Mock();node.evaluate.return_value={'tag':'div','role':'table','column_headers':['Identifier','Name']};return node


def test_unrelated_layout_divs_do_not_reject_a_unique_record_table(monkeypatch):
    result,page=validate_with_tables(monkeypatch,[table()])
    assert result['identity_matches'] is True and result['anchor_count']==1
    page.locator.assert_called_once_with('div[role="table"]')


def test_two_matching_tables_still_fail_identity_uniqueness(monkeypatch):
    result,page=validate_with_tables(monkeypatch,[table(),table()])
    assert result['identity_matches'] is False and result['identity_count']==2
    assert result['validation_reason']=='ambiguous_identity'
