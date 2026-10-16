from unittest.mock import Mock
import pytest
from phoenix_shared.assertion_runtime import _assert_record_rows


def rows(*texts):
    target=Mock();target.evaluate_all.return_value=[{'text':text,'visible':True} for text in texts]
    return target


def test_all_values_match_one_cell_separated_record():
    _assert_record_rows(Mock(),rows('100 Ada Example Active'),['Ada Example'],expected_count=1,timeout=0)


@pytest.mark.parametrize('texts,values',[
    (['100 Ada ExampleExtra'],['Ada Example']),
    (['100 OtherAda Example'],['Ada Example']),
    (['100 Ada','101 Example'],['Ada','Example']),
    (['100 Ada Example','101 Ada Example'],['Ada Example']),
    ([],['Ada Example']),
])
def test_partial_cross_row_duplicate_and_missing_matches_fail(texts,values):
    with pytest.raises(AssertionError,match='matching visible record'):
        _assert_record_rows(Mock(),rows(*texts),values,expected_count=1,timeout=0)


def test_hidden_record_cannot_prove_presence():
    target=Mock();target.evaluate_all.return_value=[{'text':'Ada Example','visible':False}]
    with pytest.raises(AssertionError):
        _assert_record_rows(Mock(),target,['Ada Example'],expected_count=1,timeout=0)


def test_absent_record_must_not_match_a_visible_row():
    with pytest.raises(AssertionError):
        _assert_record_rows(Mock(),rows('Ada Example'),['Ada Example'],expected_count=0,timeout=0)
    _assert_record_rows(Mock(),rows('Other Record'),['Ada Example'],expected_count=0,timeout=0)


def test_delayed_result_is_rechecked():
    page=Mock();target=rows()
    target.evaluate_all.side_effect=[[],[{'text':'Ada Example','visible':True}]]
    _assert_record_rows(page,target,['Ada Example'],expected_count=1,timeout=1000)
    page.wait_for_timeout.assert_called_once()


def test_timeout_budget_is_bounded(monkeypatch):
    import time
    clock=[0.0];monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    page=Mock();page.wait_for_timeout.side_effect=lambda ms:clock.__setitem__(0,clock[0]+ms/1000)
    with pytest.raises(AssertionError):
        _assert_record_rows(page,rows(),['Ada Example'],expected_count=1,timeout=250)
    assert clock[0]==pytest.approx(.25)
