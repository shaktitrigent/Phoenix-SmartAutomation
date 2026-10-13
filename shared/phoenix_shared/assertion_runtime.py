"""Runtime checks for explicit expected outcomes, separate from action acceptance."""
from __future__ import annotations
import ast
import re


def data_pattern(values, *, ordered=False):
    """Bind complete data tokens; substrings must not match another record."""
    tokens=[r'(?<!\w)'+r'\s+'.join(re.escape(part) for part in value.split())+r'(?!\w)' for value in values]
    return re.compile(r'\s+'.join(tokens) if ordered else ''.join(r'(?=[\s\S]*'+token+')' for token in tokens))


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
        if cm.get('validation_url') and cm['validation_url'] != page.url and not (evidence.get('metadata') or {}).get('shared_component'):
            continue
        expected = metadata.get('element_data') or cm.get('element_data') or {}
        if not expected:
            continue
        result = session.validate(candidate, {'element_data': expected})
        if result.get('match_count') == 1 and result.get('identity_matches') is True:
            return target
    raise AssertionError('Target identity does not match accepted evidence in the current live state')


def assert_contract(page, contract, *, timeout=30000, reference_url=None, record_baseline=None):
    """Execute a manual-derived expectation in the current execution state.

    Absence requires an explicit scope that exists uniquely and is visible.
    Positive targets must match exactly one element before their state is checked.
    Failures deliberately propagate to pytest; no healing turns them into success.
    """
    from playwright.sync_api import expect
    if contract.get('version') != 1 or contract.get('kind') not in {'visible','hidden','absent','enabled','disabled','checked','unchecked','url','title','url_unchanged','value_missing','invalid','value','count','data_visible','record_present','record_absent','field_messages','no_new_records'}:
        raise ValueError('Unsupported assertion contract')
    if contract['kind']=='no_new_records':
        from phoenix_shared.record_verification import assert_no_new_records
        assert_no_new_records(page,contract['lookup'],record_baseline)
        return
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
    if kind in {'data_visible','record_present','record_absent'}:
        import os
        def interpolate(value):
            return re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}',lambda m:os.environ[m[1]],value)
        values=[interpolate(v) for v in contract['expected_values']]
        if not values or any(not v for v in values):raise ValueError('Visible data needs nonempty explicit values')
        if kind!='data_visible':
            if contract.get('target_evidence'):validate_target(page,contract['target_evidence'],timeout=timeout)
            if not scope or not contract.get('record_role'):raise ValueError('Records need explicit results scope and role')
            # All supplied tokens must occur in one record, never across rows.
            pattern=data_pattern(values)
            rows=resolve_subject(page,scope).get_by_role(contract['record_role']).filter(has_text=pattern)
            expect(rows).to_have_count(0 if kind=='record_absent' else 1,timeout=timeout)
            if kind=='record_present':expect(rows).to_be_visible(timeout=timeout)
            return
        pattern=data_pattern(values,ordered=True)
        target=(resolve_subject(page,scope) if scope else page).get_by_text(pattern)
        expect(target).to_have_count(1,timeout=timeout)
        expect(target).to_be_visible(timeout=timeout)
        return
    target=resolve_subject(page,contract['subject'])
    if contract.get('target_evidence'):
        validate_target(page, contract['target_evidence'], timeout=timeout)
    if contract.get('expected_heading_reference'):
        import os
        expect(target).to_have_text(os.environ[contract['expected_heading_reference']], timeout=timeout)
    if kind=='field_messages':
        subjects=contract.get('field_subjects') or []
        evidence=contract.get('field_evidence') or []
        if not subjects or len(subjects)!=len(evidence):raise ValueError('Validation needs independent field identities')
        message=contract['message']
        for subject,identity in zip(subjects,evidence):
            if not identity:raise ValueError('Validation field lacks accepted identity evidence')
            field=validate_target(page,identity,timeout=timeout)
            # Find an observed group that owns exactly this one input and an
            # exact message. A whole form containing several inputs is not proof
            # that an error belongs to the requested field.
            depth=field.evaluate('''(field, message) => {
                for (let node=field.parentElement, depth=1; node && depth<=8; node=node.parentElement, depth++) {
                    const controls=[...node.querySelectorAll('input,textarea,select')];
                    if (controls.length!==1 || controls[0]!==field) continue;
                    const messages=[...node.querySelectorAll('*')].filter(n=>!n.children.length && (n.textContent||'').trim()===message);
                    if (messages.length===1) return depth;
                }
                return null;
            }''',message)
            if type(depth) is not int or not 1<=depth<=8:raise AssertionError('No observed independent field/message group')
            group=field
            for _ in range(depth):group=group.locator('xpath=..')
            text=group.get_by_text(message,exact=True)
            expect(text).to_have_count(1,timeout=timeout)
            expect(text).to_be_visible(timeout=timeout)
        expect(target).to_have_count(contract['expected_count'],timeout=timeout)
        return
    if kind=='count':
        count=contract['expected_count']
        if type(count) is not int or count<0:raise ValueError('Count must be a nonnegative integer')
        expect(target).to_have_count(count,timeout=timeout)
        if contract.get('require_visible'):
            for item in target.all():expect(item).to_be_visible(timeout=timeout)
        return
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


def select_autocomplete_option(page, field, value, contract, *, timeout=15000):
    """Choose explicit data from a live option group owning exactly this input."""
    import time
    from playwright.sync_api import expect
    if contract!={'kind':'autocomplete','option_role':'option'} or not isinstance(value,str) or not value:
        raise ValueError('Autocomplete selection needs explicit nonempty data and an option contract')
    expect(field).to_have_count(1,timeout=timeout)
    expect(field).to_be_visible(timeout=timeout)
    depth=None;deadline=time.monotonic()+timeout/1000
    while time.monotonic()<deadline:
        depth=field.evaluate('''field => {
            for(let p=field.parentElement,d=1;p && d<=8;p=p.parentElement,d++) {
                if(p.matches('body,html')) break;
                const controls=[...p.querySelectorAll('input,textarea,select')];
                if(controls.length!==1 || controls[0]!==field) continue;
                if([...p.querySelectorAll('[role="option"]')].some(n=>n.getClientRects().length)) return d;
            }
            return null;
        }''')
        if type(depth) is int and 1<=depth<=8:break
        page.wait_for_timeout(50)
    if type(depth) is not int or not 1<=depth<=8:
        raise AssertionError('No observed autocomplete option group owns this field')
    group=field
    for _ in range(depth):group=group.locator('xpath=..')
    option=group.get_by_role('option').filter(has_text=data_pattern([value],ordered=True))
    expect(option).to_have_count(1,timeout=timeout)
    expect(option).to_be_visible(timeout=timeout)
    option.click(timeout=timeout)
    expect(field).to_have_value(value,timeout=timeout)
