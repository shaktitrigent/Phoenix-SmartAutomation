"""Runtime checks for explicit expected outcomes, separate from action acceptance."""
from __future__ import annotations
import ast
import re


def resolve_subject(page, expression):
    """Interpret only literal Playwright locator operations; never evaluate code."""
    allowed = {'locator','get_by_role','get_by_text','get_by_label','get_by_placeholder',
               'get_by_test_id','get_by_alt_text','get_by_title','filter'}
    def resolve(node):
        if isinstance(node, ast.Name) and node.id == 'page':
            return page
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr not in allowed:
            raise ValueError('Unsupported assertion subject')
        def argument(value):
            return resolve(value) if isinstance(value, ast.Call) else ast.literal_eval(value)
        if any(k.arg is None for k in node.keywords):
            raise ValueError('Expanded assertion arguments are unsupported')
        kwargs={k.arg:argument(k.value) for k in node.keywords}
        if node.func.attr == 'filter' and set(kwargs) - {'has','has_text','has_not_text','visible'}:
            raise ValueError('Unsupported assertion scope')
        args=[argument(a) for a in node.args]
        if node.func.attr=='locator' and args and isinstance(args[0],str) and re.search(r':(?:nth|first|last)-(?:child|of-type)|\[\s*\d+\s*\]',args[0]):
            raise ValueError('Positional subject does not establish identity')
        return getattr(resolve(node.func.value),node.func.attr)(*args,**kwargs)
    return resolve(ast.parse(expression, mode='eval').body)


def validate_target(page, evidence, *, timeout=30000):
    """Historical acceptance must be checked again in the current live state."""
    from playwright.sync_api import expect
    from phoenix_shared.locator_policy import locator_accepted
    from phoenix_shared.models.locator import Locator
    from phoenix.locators.live_session import LiveLocatorSession
    observations = (evidence.get('metadata') or {}).get('state_evidence') or [evidence]
    candidate = Locator.model_validate({**evidence['primary'], 'element_name': evidence['element_name']})
    target = resolve_subject(page, candidate.to_playwright())
    expect(target).to_have_count(1, timeout=timeout)
    expect(target).to_be_visible(timeout=timeout)
    session = LiveLocatorSession(page)
    for observation in observations:
        if not locator_accepted(observation.get('primary') or {}, observation.get('metadata')):
            continue
        metadata = observation.get('metadata') or {}
        cm = (observation.get('primary') or {}).get('metadata') or {}
        if cm.get('validation_url') and cm['validation_url'] != page.url:
            continue
        expected = metadata.get('element_data') or cm.get('element_data') or {}
        if not expected:
            continue
        result = session.validate(candidate, {'element_data': expected})
        if result.get('match_count') == 1 and result.get('identity_matches') is True:
            return target
    raise AssertionError('Target identity does not match accepted evidence in the current live state')


def assert_contract(page, contract, *, timeout=30000, reference_url=None):
    """Execute a manual-derived expectation in the current execution state.

    Absence requires an explicit scope that exists uniquely and is visible.
    Positive targets must match exactly one element before their state is checked.
    Failures deliberately propagate to pytest; no healing turns them into success.
    """
    from playwright.sync_api import expect
    if contract.get('version') != 1 or contract.get('kind') not in {'visible','hidden','absent','enabled','disabled','checked','unchecked','url','title','url_unchanged','value_missing','invalid','value'}:
        raise ValueError('Unsupported assertion contract')
    scope=contract.get('scope')
    if scope:
        scoped=resolve_subject(page,scope)
        expect(scoped).to_have_count(1,timeout=timeout)
        expect(scoped).to_be_visible(timeout=timeout)
    kind=contract['kind']
    if kind=='url_unchanged':
        if not isinstance(reference_url,str) or not reference_url:
            raise ValueError('URL continuity requires a captured pre-action URL')
        expect(page).to_have_url(reference_url,timeout=timeout)
        return
    if kind in {'url','title'}:
        method='to_have_url' if kind=='url' else 'to_have_title'
        getattr(expect(page),method)(contract['expected'],timeout=timeout)
        return
    if kind in {'absent','hidden'} and not scope:
        raise ValueError('Negative assertions require explicit observed scope')
    target=resolve_subject(page,contract['subject'])
    if contract.get('target_evidence'):
        validate_target(page, contract['target_evidence'], timeout=timeout)
    if contract.get('expected_heading_reference'):
        import os
        expect(target).to_have_text(os.environ[contract['expected_heading_reference']], timeout=timeout)
    if kind=='value':
        from phoenix_shared.automation_translation import environment_reference
        import os
        value=contract['expected_value']
        key=environment_reference(value)
        expect(target).to_have_count(1,timeout=timeout)
        expect(target).to_have_value(os.environ[key] if key else value,timeout=timeout)
        return
    if kind in {'value_missing','invalid'}:
        expect(target).to_have_count(1,timeout=timeout)
        expect(target).to_be_visible(timeout=timeout)
        expression = '(element) => element.validity.valueMissing' if kind == 'value_missing' else '(element) => !element.checkValidity()'
        if target.evaluate(expression) is not True:
            raise AssertionError('Expected required-field validation did not occur')
    elif kind=='absent':
        expect(target).to_have_count(0,timeout=timeout)
    elif kind=='hidden':
        # An ambiguous hidden query is not a proved absence/visibility outcome.
        if target.count()>1:
            raise AssertionError('Negative assertion target is ambiguous')
        expect(target).not_to_be_visible(timeout=timeout)
    else:
        expect(target).to_have_count(1,timeout=timeout)
        method={'visible':'to_be_visible','enabled':'to_be_enabled','disabled':'to_be_disabled',
                'checked':'to_be_checked','unchecked':'not_to_be_checked'}[kind]
        getattr(expect(target),method)(timeout=timeout)
