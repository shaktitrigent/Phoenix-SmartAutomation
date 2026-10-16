import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from phoenix_shared import assertion_runtime as runtime


def setup(monkeypatch, depths):
    field=Mock()
    field.evaluate.side_effect=depths
    page=Mock()
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(expect=lambda target:Mock()))
    monkeypatch.setattr(runtime,'resolve_subject',lambda page, subject:Mock())
    monkeypatch.setattr(runtime,'validate_target',lambda page, identity, timeout:field)
    contract={'version':1,'kind':'field_messages','subject':'messages','message':'Required',
              'field_subjects':['field'],'field_evidence':[{'id':'accepted'}],'expected_count':1}
    return page,field,contract


def test_delayed_message_group_is_retried(monkeypatch):
    page,field,contract=setup(monkeypatch,[None,None,1])
    runtime.assert_contract(page,contract,timeout=1000)
    assert field.evaluate.call_count==3
    assert page.wait_for_timeout.call_count==2


def test_missing_independent_group_still_fails(monkeypatch):
    page,field,contract=setup(monkeypatch,[None])
    with pytest.raises(AssertionError,match='independent field/message group'):
        runtime.assert_contract(page,contract,timeout=0)
    page.wait_for_timeout.assert_not_called()


@pytest.mark.parametrize('depth',[True,0,9])
def test_invalid_group_depth_cannot_pass(monkeypatch,depth):
    page,field,contract=setup(monkeypatch,[depth])
    with pytest.raises(AssertionError,match='independent field/message group'):
        runtime.assert_contract(page,contract,timeout=0)
