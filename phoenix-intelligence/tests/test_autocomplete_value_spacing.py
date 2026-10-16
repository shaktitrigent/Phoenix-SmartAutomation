import sys
from types import SimpleNamespace
from unittest.mock import Mock

from phoenix_shared.assertion_runtime import select_autocomplete_option


def test_selected_full_label_tolerates_only_whitespace_variation(monkeypatch):
    checks=Mock()
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(expect=lambda target:checks))
    field=Mock();field.evaluate.return_value=1
    select_autocomplete_option(Mock(),field,'Ada Lovelace',{'kind':'autocomplete','option_role':'option'})
    pattern=checks.to_have_value.call_args.args[0]
    assert pattern.fullmatch('Ada  Lovelace ')
    assert pattern.fullmatch(' Ada Lovelace')
    assert not pattern.fullmatch('Ada Lovelace Other')
    assert not pattern.fullmatch('Ada Other Lovelace')
    assert not pattern.fullmatch('Ada Lovelaceson')
    field.locator.return_value.get_by_role.return_value.filter.return_value.click.assert_called_once()
