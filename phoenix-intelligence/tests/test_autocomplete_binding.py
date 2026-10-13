import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from phoenix_shared.assertion_runtime import select_autocomplete_option


def test_selection_uses_one_owned_option_matching_complete_explicit_data(monkeypatch):
    import types
    expected=[]
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(expect=lambda target:Mock()))
    field=Mock();field.evaluate.return_value=1;group=field.locator.return_value;option=group.get_by_role.return_value.filter.return_value
    select_autocomplete_option(Mock(),field,'Given Family',{'kind':'autocomplete','option_role':'option'})
    field.locator.assert_called_once_with('xpath=..')
    option.click.assert_called_once()
    pattern=group.get_by_role.return_value.filter.call_args.kwargs['has_text']
    assert pattern.search('Given Family') and not pattern.search('Given Familyson')


def test_no_owned_options_cannot_be_replaced_by_global_page_match(monkeypatch):
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(expect=lambda target:Mock()))
    page=Mock()
    with pytest.raises(AssertionError,match='owns this field'):
        select_autocomplete_option(page,Mock(),'Given Family',{'kind':'autocomplete','option_role':'option'},timeout=0)
    page.get_by_role.assert_not_called()
