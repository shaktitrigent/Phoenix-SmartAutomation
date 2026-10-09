"""Cross-layer regressions for scoped identity and explicit runtime outcomes."""
from copy import deepcopy
import json
import pytest
from phoenix_shared.generation_contract import clauses, summary_binding, Snapshot
from phoenix.locators.live_session import identity_matches, LiveLocatorSession
from phoenix.locators.reconciliation import reconcile_generated_code
from phoenix.locators.smartlocator_integration import resolve_automation_locator_evidence
from services.agents.test_generator import TestGeneratorAgent
from services.knowledge.base import KnowledgeBase
from services.cache import Cache


HTML = '''<html><body><header><a>Store</a></header><main><section class="access-panel">
<h2>Access account</h2><form><input data-qa="access-email" name="email" placeholder="Email" required>
<input name="password" placeholder="Password" type="password"><button id="access">Access</button></form></section>
<form><input data-qa="newsletter-email" name="email" placeholder="Email"><button>Subscribe</button></form>
</main></body></html>'''


def generate(case, html=HTML, bundles=()):
    return TestGeneratorAgent(KnowledgeBase(), Cache()).automate_from_manual_tests(
        [case], application_url='https://fixture.test/account', locator_bundles=list(bundles),
        dom_snapshot=html, use_pom=True)['automation_tests'][0]


def test_comma_separated_summary_uses_explicit_error_and_ui_absence_evidence():
    contracts=[{'kind':'visible','step':6,'expected_text':'Text "Denied" is visible.', 'action_text':'Verify the account error message'},
               {'kind':'visible','step':7,'expected_text':'Text "Access account" is visible.', 'action_text':'Verify the account form remains available'},
               {'kind':'hidden','scope':"page.get_by_role('banner')",'step':8,'expected_text':'Text "Signed in" is not visible.', 'action_text':'Verify the authenticated header is absent'}]
    records=[{'step':3,'action_kind':'fill','action_text':'Enter the supplied incorrect password in the account password field'},
             {'step':5,'deferred_to_steps':[6]}]
    summary='The incorrect password is rejected, the account error is displayed, and the user remains logged out.'
    parts=clauses(summary)
    assert len(parts)==3
    assert all(summary_binding(part,contracts,records) for part in parts)
    assert summary_binding('The user remains logged out',contracts,records)['proof_scope']=='observable_ui'
    assert summary_binding('The backend session is invalidated',contracts,records) is None
    assert summary_binding('The payment is rejected',contracts,records) is None
    assert summary_binding('The user remains logged out',contracts[:1],records) is None
    invalid=[{'kind':'invalid','step':4,'action_text':'Inspect the Access email field validity','expected_text':'checkValidity() returns false'}]
    assert summary_binding('The empty email field fails required-field validation',invalid,[]) is not None
    assert summary_binding('The empty password field fails required-field validation',invalid,[]) is None


def test_scoped_identity_checks_all_observed_data_attributes_and_same_ancestor():
    expected={'tag':'input','name':'email','data':{'data-qa':'access-email'},
              'ancestor_context':{'container_tag':'form','container_text':'Access',
                  'section_context':{'section_tag':'section','section_class':'access-panel','section_heading':'Access account'}}}
    actual={'tag':'input','name':'email','data-qa':'access-email','ancestors':[
        {'tag':'form','text':'Access'}, {'tag':'section','class':'access-panel','heading':'Access account'}]}
    assert identity_matches(actual,expected)
    wrong=deepcopy(actual);wrong['data-qa']='newsletter-email'
    assert not identity_matches(wrong,expected)
    wrong=deepcopy(actual);wrong['ancestors'][0]={'tag':'body','text':'Access'}
    assert not identity_matches(wrong,expected)


def test_unresolved_action_and_value_assertion_share_one_requested_target():
    expression="page.locator('form').filter(has=page.get_by_role('button', name='Access', exact=True)).get_by_placeholder('Email', exact=True)"
    source='def test_x(page):\n    fill_ready(page, '+expression+', "value", "Access Email")\n    expect('+expression+').to_have_value("value")\n'
    assert reconcile_generated_code(source,[])[2]==['Access Email']


def test_snapshot_proposal_reaches_live_validator_without_granting_acceptance():
    case={'name':'Enter account email','steps':[{'action':'Enter the supplied email in the Access email field',
        'test_data':'fixture@example.test','expected_result':'The email field contains the supplied value.'}]}
    result=generate(case)
    assert result['proposed_locator_targets']
    calls=[]
    def validate(candidate,payload):
        calls.append((candidate,payload))
        return {'match_count':1,'identity_matches':True}
    resolution=resolve_automation_locator_evidence([result],[],application_url='https://fixture.test/account',page='account',
        scan=lambda *a,**k:[],discover=lambda *a:{},validate=validate,capture=lambda *a:{'capture_status':'insufficient_context'})
    assert calls and resolution['proposal_validation'][0]['identity_matches'] is True
    assert resolution['unresolved']  # unique proposal alone does not waive High/Expert policy
    assert calls[0][1]['element_data']['data']['data-qa']=='access-email'


def test_missing_translation_target_is_retained_for_scanning():
    case={'name':'Missing control','steps':[{'action':'Enter "abc" in the Missing field',
        'expected_result':'The field contains the supplied value.'}]}
    result=generate(case,html='')
    assert result['translation_targets']==['Missing']


def test_snapshot_syntax_limit_is_distinct_from_a_missing_element():
    from services.locator_validator import LocatorValidator
    validator=LocatorValidator(HTML)
    assert validator.validate_locator('#missing','Missing').snapshot_status=='not_found'
    unsupported=validator.validate_locator('input:has(label)','Email')
    assert unsupported.snapshot_status=='unsupported_selector_syntax'
    assert unsupported.rejection_reason=='unsupported_selector_syntax'
    assert not unsupported.validation_passed
    missing=LocatorValidator('').validate_locator('#access','Access')
    assert missing.snapshot_status=='missing_snapshot' and not missing.validation_passed


def empty_case():
    pairs=[('Navigate to https://fixture.test/account','The Access form is visible.'),
           ('Clear the Access email field','The email field contains an empty string.'),
           ('Click the Access button inside the Access form','Required-email validation prevents submission.'),
           ("Inspect the Access email field's validity","The field's validity.valueMissing property is true."),
           ("Check the Access email field's validity","The field's checkValidity() method returns false."),
           ('Verify the account form remains available','Text "Access account" is visible.'),
           ('Verify the authenticated header is absent','Text "Signed in as" is not visible in the header.')]
    case={'name':'Empty email','steps':[{'step_number':i,'action':a,'expected_result':e} for i,(a,e) in enumerate(pairs,1)],
          'expected_result':'The empty email field fails required-field validation, submission is prevented, and the user remains logged out.'}
    return case


def test_empty_field_native_validity_and_submission_outcomes_compile():
    result=generate(empty_case())
    assert result['generation_quality']['status']=='translated',result['step_contracts']
    assert not result['overall_outcome_unresolved']
    assert {c['kind'] for c in result['assertion_contracts']} >= {'invalid','value_missing'}
    assert "pytest.skip(" not in result['script_code']
    assert result['step_contracts'][2]['deferred_to_steps']==[4,5]


@pytest.mark.parametrize('required_empty', [False, True])
def test_generated_pom_runs_repeated_controls_and_runtime_states(tmp_path, monkeypatch, required_empty):
    """Write and import the generated POM; execute it with real Chromium."""
    from pathlib import Path
    import runpy
    import sys
    from playwright.sync_api import sync_playwright
    from phoenix.output.coordinator import OutputManager
    from phoenix.locators.smartlocator_integration import reconcile_automation_tests_with_bundles
    from phoenix_shared.models.locator import LocatorBundle
    from phoenix_shared.generation_contract import artifact_plan_issues
    import phoenix_shared.assertion_runtime as runtime

    html = HTML.replace('<button id="access">', '<button id="access" type="button">')
    html += '''<script>document.querySelector('#access').onclick=()=>{
      const p=document.createElement('p');p.textContent='Credentials denied';
      document.querySelector('main').append(p);};</script>'''
    case = empty_case() if required_empty else {
        'name':'Repeated controls rejection', 'steps':[
            {'action':'Navigate to https://fixture.test/account','expected_result':'The Access form is visible.'},
            {'action':'Enter the supplied email in the Access email field','test_data':'fixture@example.test',
             'expected_result':'The email field contains the supplied value.'},
            {'action':'Enter the supplied incorrect password in the Access password field','test_data':'fixture-invalid',
             'expected_result':'The password field is populated (characters masked).'},
            {'action':'Click the Access button inside the Access form','expected_result':'The submission completes.'},
            {'action':'Verify the account error message','expected_result':'Text "Credentials denied" is visible.'},
            {'action':'Verify the account form remains visible','expected_result':'Text "Access account" is visible.'},
            {'action':'Verify the authenticated header is absent','expected_result':'Text "Signed in as" is not visible in the header.'}],
        'expected_result':'The incorrect password is rejected, the account error is displayed, and the user remains logged out.'}
    if required_empty:
        html = HTML.replace('<form><input data-qa="access-email"', '<form onsubmit="throw new Error(\'unexpected submit\')"><input data-qa="access-email"')

    bundles=[]
    for name,selector,identity in [
        ('AccessEmailInput', '[data-qa="access-email"]', {'tag':'input','data':{'data-qa':'access-email'}}),
        ('AccessPasswordInput', '.access-panel input[name="password"]', {'tag':'input','name':'password'}),
        ('AccessButton', '#access', {'tag':'button','id':'access'})]:
        bundles.append(LocatorBundle.model_validate({'element_name':name,'page':'account',
            'primary':{'element_name':name,'strategy':'css','value':selector,
                       'metadata':{'stability':'High','stability_score':9}},
            'metadata':{'element_data':identity}}))
    receipts=[]
    original=runtime.assert_contract
    def observe(page, contract, **kwargs):
        original(page,contract,**kwargs)
        receipts.append((contract['step'],contract['kind']))
    monkeypatch.setattr(runtime,'assert_contract',observe)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        try:
            page=browser.new_page()
            page.route('https://fixture.test/account',lambda route:route.fulfill(body=html,content_type='text/html'))
            page.goto('https://fixture.test/account')
            if not required_empty:
                from phoenix_shared.models.locator import Locator
                session=LiveLocatorSession(page)
                identity={'tag':'input','data':{'data-qa':'access-email'}}
                for selector,count,correct in [('#missing',0,False),('input[name="email"]',2,False),
                                               ('[data-qa="newsletter-email"]',1,False)]:
                    outcome=session.validate(Locator(element_name='Access email',strategy='css',value=selector),{'element_data':identity})
                    assert outcome['match_count']==count and outcome['identity_matches'] is correct
                invalid=session.validate(Locator(element_name='Access email',strategy='css',value='[broken'),{'element_data':identity})
                assert invalid['validation_reason']=='invalid_selector'
            validated=LiveLocatorSession(page).revalidate(bundles)
            evidence=[b.model_dump(mode='json') for b in validated]
            result=generate(case,html=page.content(),bundles=evidence)
            assert result['generation_quality']['status']=='translated',result['step_contracts']
            missing,_=reconcile_automation_tests_with_bundles([result],evidence)
            assert not missing,missing
            assert not artifact_plan_issues(result)
            OutputManager(tmp_path).apply(result['pom_bundle'])
            from jinja2 import Template
            base=Path(__file__).resolve().parents[2]/'phoenix-core/phoenix/templates/project/pages_base_page.py.j2'
            (tmp_path/'pages/base_page.py').write_text(Template(base.read_text(encoding='utf8')).render(project_name='fixture'),encoding='utf8')
            (tmp_path/'pages/__init__.py').touch()
            monkeypatch.syspath_prepend(str(tmp_path))
            for name in list(sys.modules):
                if name=='pages' or name.startswith('pages.'):
                    monkeypatch.delitem(sys.modules,name)
            test_path=tmp_path/result['pom_bundle']['tests'][0]['file']
            namespace=runpy.run_path(str(test_path))
            tests=[value for name,value in namespace.items() if name.startswith('test_')]
            assert len(tests)==1
            tests[0](page)
            assert receipts==[(c['step'],c['kind']) for c in result['assertion_contracts']]
            assert page.locator('[data-qa="newsletter-email"]').input_value()==''
            if required_empty:
                assert page.locator('[data-qa="access-email"]').input_value()==''
                assert (4,'value_missing') in receipts and (5,'invalid') in receipts
            else:
                assert page.locator('[data-qa="access-email"]').input_value()=='fixture@example.test'
                assert page.locator('input[name="password"]').input_value()=='fixture-invalid'
                assert page.get_by_text('Credentials denied',exact=True).count()==1
        finally:
            browser.close()
