from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from phoenix_shared.assertion_runtime import _wait_for_record_headers

EXPECTED={'tag':'div','role':'table','column_headers':['Code','Name','Status']}


def target_with(*snapshots,count=1):
    target=Mock();target.count.return_value=count
    target.evaluate.side_effect=list(snapshots)
    return target


def test_missing_then_partial_headers_become_ready():
    page=Mock();target=target_with([],['Code'],['Code','Name','Status'])
    assert _wait_for_record_headers(page,target,EXPECTED,timeout=1000)
    assert page.wait_for_timeout.call_count==2


@pytest.mark.parametrize('headers',[['Wrong'],['Code','Wrong'],['Code','Name','Other'],['Code','Name','Status','Extra']])
def test_wrong_headers_fail_without_wait_or_relaxing_text(headers):
    page=Mock();target=target_with(headers)
    assert not _wait_for_record_headers(page,target,EXPECTED,timeout=1000)
    page.wait_for_timeout.assert_not_called()


@pytest.mark.parametrize('count',[0,2])
def test_uniqueness_is_required(count):
    page=Mock();target=target_with(count=count)
    assert not _wait_for_record_headers(page,target,EXPECTED,timeout=1000)
    target.evaluate.assert_not_called()


def test_loading_timeout_is_bounded(monkeypatch):
    import time
    clock=[0.0]
    monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    page=Mock();page.wait_for_timeout.side_effect=lambda milliseconds:clock.__setitem__(0,clock[0]+milliseconds/1000)
    target=Mock();target.count.return_value=1;target.evaluate.return_value=[]
    assert not _wait_for_record_headers(page,target,EXPECTED,timeout=250)
    assert clock[0]==pytest.approx(.25)


@pytest.mark.parametrize('data',[{}, {'tag':'input','column_headers':['Code']}, {'role':'table','column_headers':[]}])
def test_non_record_targets_do_not_get_a_header_wait(data):
    target=Mock()
    assert not _wait_for_record_headers(Mock(),target,data,timeout=1000)
    target.count.assert_not_called()


@pytest.mark.parametrize('final_identity',[True,False])
def test_runtime_rechecks_full_identity_after_header_wait(monkeypatch,final_identity):
    import sys
    import phoenix_shared.assertion_runtime as runtime
    import phoenix.locators.live_session as live
    # Importing Playwright is optional for this orchestration unit test.
    expect=Mock()
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(expect=expect))
    evidence={'element_name':'Results','primary':{'strategy':'css','value':'#results','verified_in_snapshot':True,
        'metadata':{'stability':'High','match_count':1,'identity_matches':True}},'metadata':{'element_data':EXPECTED}}
    page=Mock();target=Mock()
    monkeypatch.setattr(runtime,'resolve_subject',lambda *args:target)
    session=Mock();session.validate.side_effect=[{'match_count':1,'identity_matches':False},
                                               {'match_count':1,'identity_matches':final_identity}]
    monkeypatch.setattr(live,'LiveLocatorSession',lambda page:session)
    ready=Mock(return_value=True);monkeypatch.setattr(runtime,'_wait_for_record_headers',ready)
    if final_identity:assert runtime.validate_target(page,evidence) is target
    else:
        with pytest.raises(AssertionError,match='Target identity'):runtime.validate_target(page,evidence)
    assert session.validate.call_count==2
