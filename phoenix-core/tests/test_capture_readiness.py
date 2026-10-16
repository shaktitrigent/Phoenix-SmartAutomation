from contextlib import contextmanager
import json
from unittest.mock import Mock
import pytest
from phoenix.locators.journey import wait_for_scoped_target, capture_journey


def test_readiness_precedes_count_for_delayed_spa():
    page=Mock(url='https://fixture/list');target=page.locator.return_value
    ready={'value':False}
    target.wait_for.side_effect=lambda **kwargs:ready.update(value=True)
    target.count.side_effect=lambda:1 if ready['value'] else 0
    assert wait_for_scoped_target(Mock(page=page), {'selector':'#code'}, 'list') is target
    assert ready['value']


@pytest.mark.parametrize('count,reason',[(0,'target_missing'),(2,'target_ambiguous'),(1,'target_not_visible')])
def test_failure_diagnostic_identifies_count_and_route_without_secrets(count,reason):
    page=Mock(url='https://user:secret@fixture/login?token=private#password');target=page.locator.return_value
    target.wait_for.side_effect=TimeoutError('DOM contains sensitive content')
    target.count.return_value=count
    with pytest.raises(ValueError) as caught:
        wait_for_scoped_target(Mock(page=page),'#code','list')
    msg=str(caught.value)
    assert reason in msg and f'matches={count}' in msg and 'https://fixture/login' in msg
    assert 'secret' not in msg and 'private' not in msg and 'password' not in msg and 'sensitive' not in msg


def test_ready_but_ambiguous_target_is_never_accepted():
    page=Mock();page.locator.return_value.count.return_value=2
    with pytest.raises(ValueError,match='target_ambiguous'):
        wait_for_scoped_target(Mock(page=page),'#code','list')


def test_capture_scans_only_after_required_control_is_ready(tmp_path,monkeypatch):
    import phoenix.locators.journey as journey
    page=Mock(url='https://fixture/list');target=page.locator.return_value
    ready={'value':False}
    target.wait_for.side_effect=lambda **kw:ready.update(value=True)
    target.count.side_effect=lambda:1 if ready['value'] else 0
    session=Mock(page=page)
    def scan(**kwargs):
        assert ready['value']
        return []
    session.scan.side_effect=scan
    @contextmanager
    def live(*a,**kw):yield session
    monkeypatch.setattr('phoenix.locators.live_session.live_session',live)
    # Stop after scan, which is the point of this sequencing regression.
    def validation(*a):raise RuntimeError('scan_completed')
    monkeypatch.setattr(journey,'validate_scoped_target',validation)
    states=tmp_path/'states.json';states.write_text(json.dumps({'states':[{'name':'list','fallback_targets':['#code']}]}))
    with pytest.raises(RuntimeError,match='scan_completed'):
        capture_journey('https://fixture/start',states,tmp_path/'raw',tmp_path/'locators')
    session.scan.assert_called_once()
