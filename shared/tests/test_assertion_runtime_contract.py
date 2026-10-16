"""Negative scopes and future subjects must fail on missing/ambiguous evidence."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from phoenix_shared import assertion_runtime as runtime


class Expected:
    def __init__(self,target):self.target=target
    def to_have_count(self,count,**kwargs):
        if self.target.count()!=count:raise AssertionError('count mismatch')
    def to_be_visible(self,**kwargs):
        if not self.target.visible:raise AssertionError('not visible')
    def not_to_be_visible(self,**kwargs):
        if self.target.visible and self.target.count():raise AssertionError('still visible')


def setup(monkeypatch,scope_count,target_count,visible=True):
    import playwright.sync_api
    monkeypatch.setattr(playwright.sync_api,'expect',Expected)
    scope=SimpleNamespace(count=lambda:scope_count,visible=True)
    target=SimpleNamespace(count=lambda:target_count,visible=visible)
    monkeypatch.setattr(runtime,'resolve_subject',lambda page,expr: scope if expr=='scope' else target)
    return {'version':1,'kind':'absent','scope':'scope','subject':'target'}


@pytest.mark.parametrize('scope_count',[0,2])
def test_absence_cannot_pass_with_missing_or_ambiguous_scope(monkeypatch,scope_count):
    spec=setup(monkeypatch,scope_count,0)
    with pytest.raises(AssertionError):runtime.assert_contract(object(),spec)


def test_absence_rejects_present_subject(monkeypatch):
    spec=setup(monkeypatch,1,1)
    with pytest.raises(AssertionError):runtime.assert_contract(object(),spec)


def test_explicit_absence_passes_only_after_scope_check(monkeypatch):
    runtime.assert_contract(object(),setup(monkeypatch,1,0))


@pytest.mark.parametrize('target_count',[0,2])
def test_future_positive_subject_must_be_unique_at_execution(monkeypatch,target_count):
    spec=setup(monkeypatch,1,target_count);spec['kind']='visible'
    with pytest.raises(AssertionError):runtime.assert_contract(object(),spec)


def test_positive_subject_checks_visibility(monkeypatch):
    spec=setup(monkeypatch,1,1,False);spec['kind']='visible'
    with pytest.raises(AssertionError):runtime.assert_contract(object(),spec)


@pytest.mark.parametrize('expression',["__import__('os').system('anything')","page.get_by_text('x').first",'page.locator(selector)','page.goto("anywhere")'])
def test_resolver_rejects_non_literal_or_executable_subjects(expression):
    with pytest.raises((ValueError,TypeError)):runtime.resolve_subject(Mock(),expression)


def test_resolver_supports_nested_observed_form_scope():
    page=Mock()
    runtime.resolve_subject(page,"page.locator('form').filter(has=page.get_by_role('button', name='Access', exact=True))")
    page.locator.assert_called_once_with('form')
    page.get_by_role.assert_called_once_with('button',name='Access',exact=True)
    page.locator.return_value.filter.assert_called_once_with(has=page.get_by_role.return_value)
