"""Generic contracts exercised through real flat and POM generation and gates."""
from copy import deepcopy
import ast
import pytest
from services.agents.test_generator import TestGeneratorAgent
from services.knowledge.base import KnowledgeBase
from services.cache import Cache
from phoenix.locators.smartlocator_integration import reconcile_automation_tests_with_bundles
from phoenix.locators.reconciliation import reconcile_generated_code
from phoenix_shared.generation_contract import artifact_plan_issues, Snapshot


def evidence(name,selector):
    return {'element_name':name,'page':'account','primary':{'element_name':name,'strategy':'css',
        'value':selector,'verified_in_snapshot':True,'metadata':{'stability':'High','stability_score':9,
        'match_count':1,'identity_matches':True}},'alternates':[],'metadata':{}}


HTML='''<html><body><header><a>Store</a></header><main>
<div><h2>Access account</h2><form><input id="account-email" placeholder="Email" name="email">
<input id="secret" placeholder="Password" name="password" type="password"><button>Access</button></form></div>
<form><input placeholder="Email" name="email"><button>Subscribe</button></form>
</main></body></html>'''
BUNDLES=[evidence('AccessEmailInput','#account-email'),evidence('AccessPasswordInput','#secret'),evidence('AccessButton','#access')]


def manual():
    steps=[
        ('Navigate to https://example.test/account', 'The Access form is visible.', ''),
        ('Verify the account heading', 'The heading "Access account" is visible.', ''),
        ('Enter the supplied email in the Access email field', 'The email field contains the supplied value.', '${ACCOUNT_EMAIL}'),
        ('Enter the supplied password in the Access password field', 'The password field is populated (characters masked).', 'incorrect-value'),
        ('Click the Access button inside the Access form', 'The message "Credentials rejected" is displayed.', ''),
        ('Verify that the account header is absent', 'The text "Signed in as" is NOT present anywhere on the page.', ''),
    ]
    return {'name':'Account negative scenario','preconditions':'Fresh logged-out browser',
        'steps':[{'step_number':i,'action':a,'expected_result':e,'test_data':d} for i,(a,e,d) in enumerate(steps,1)],
        'expected_result':'The message "Credentials rejected" is displayed.'}


def generate(case,bundles=BUNDLES,html=HTML,pom=False):
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=None
    return agent.automate_from_manual_tests([case],application_url='https://example.test/account',
        locator_bundles=bundles,dom_snapshot=html,use_pom=pom)['automation_tests'][0]


@pytest.mark.parametrize('pom',[False,True])
def test_complete_negative_flow_uses_evidence_and_future_state_contracts(pom):
    source=manual();original=deepcopy(source);result=generate(source,pom=pom)
    assert source==original
    assert result['generation_mode']=='deterministic'
    assert 'pytest.skip(' not in result['script_code']
    assert '.or_(' not in result['script_code']
    assert "os.environ['ACCOUNT_EMAIL']" in result['script_code']
    assert "'#secret'" in result['script_code'] or '"#secret"' in result['script_code']
    assert result['assertion_contracts']
    assert any(c['kind']=='absent' for c in result['assertion_contracts'])
    assert not artifact_plan_issues(result)
    missing,used=reconcile_automation_tests_with_bundles([result],BUNDLES)
    assert not missing,missing
    assert used
    assert result['generation_quality']['status']=='translated',result['generation_quality']


def test_missing_absence_scope_does_not_become_success():
    case=manual();case['steps'][-1]['action']='Verify no authentication indicator';case['steps'][-1]['expected_result']='The text "Signed in as" is NOT present.'
    result=generate(case)
    assert 'pytest.skip(' in result['script_code']
    assert result['generation_quality']['status']=='partial'


def test_missing_data_does_not_invent_credentials():
    case=manual();case['steps'][2]['test_data']=''
    result=generate(case)
    assert 'missing_explicit_fill_data' in result['script_code']
    assert result['generation_quality']['status']=='partial'


def test_ambiguous_controls_not_selected_arbitrarily():
    case=manual();case['steps'][2]['action']='Enter "value" in the email field'
    result=generate(case,bundles=[],html=HTML)
    assert 'missing_or_ambiguous_fill_target' in result['script_code']
    assert '.first' not in result['script_code']


def test_final_pom_cannot_drop_a_business_assertion():
    result=generate(manual(),pom=True)
    node=result['pom_bundle']['page_objects'][0]
    node['code']='\n'.join(line for line in node['code'].splitlines() if 'Credentials rejected' not in line)
    assert artifact_plan_issues(result)
    assert reconcile_automation_tests_with_bundles([result],BUNDLES)[0]


def test_assertion_contract_cannot_be_borrowed_or_spoofed():
    result=generate(manual());spec=result['assertion_contracts'][0]
    code='from phoenix_shared.assertion_runtime import assert_contract\ndef test_x(page):\n    assert_contract(page, '+repr(spec)+')\n'
    assert reconcile_generated_code(code,[],assertion_contracts=[spec])[2]==[]
    assert reconcile_generated_code(code,[])[2]
    assert reconcile_generated_code(code.replace('def test_x', 'assert_contract = lambda *args: None\ndef test_x'),[],assertion_contracts=[spec])[2]
    altered=dict(spec,subject='page.locator("#invented")')
    assert reconcile_generated_code(code.replace(repr(spec),repr(altered)),[],assertion_contracts=[spec])[2]


def test_generic_form_scope_is_observed_not_guessed():
    snapshot=Snapshot(HTML)
    assert snapshot.scope('Verify the Access form')
    assert snapshot.scope('Verify the Unknown form') is None
    assert snapshot.scope('Verify the header')


@pytest.mark.parametrize('pom',[False,True])
def test_positive_navigation_and_outcome_use_only_supplied_url_and_message(pom):
    case={'name':'Open a different page','steps':[{'action':'Navigate to https://other.test/workspace',
        'expected_result':'The heading "Workspace ready" is visible.'}],
        'expected_result':'The heading "Workspace ready" is visible.'}
    result=generate(case,pom=pom)
    assert result['generation_quality']['status']=='translated'
    assert 'https://other.test/workspace' in result['script_code']
    assert reconcile_automation_tests_with_bundles([result],[])[0]==[]


@pytest.mark.parametrize('pom',[False,True])
def test_explicit_empty_input_is_preserved_and_asserted(pom):
    case={'name':'Empty field validation','steps':[{'action':'Enter the supplied email in the Access email field',
        'test_data':'""','expected_result':'The email field contains the supplied value.'}]}
    result=generate(case,pom=pom)
    assert result['generation_quality']['status']=='translated'
    assert "'', 'Access Email'" in result['script_code']
    assert '.to_have_value(\'\'' in result['script_code']
    assert not reconcile_automation_tests_with_bundles([result],BUNDLES)[0]


def test_multi_page_explicit_navigation_order_is_preserved():
    case={'name':'Explicit journey','steps':[
        {'action':'Navigate to https://other.test/catalog','expected_result':'The heading "Catalog" is visible.'},
        {'action':'Navigate to https://other.test/cart','expected_result':'The heading "Cart review" is visible.'}]}
    result=generate(case,pom=True)
    assert result['generation_quality']['status']=='translated'
    assert not artifact_plan_issues(result)
    assert result['script_code'].index('/catalog')<result['script_code'].index('/cart')


def test_unrelated_high_controls_cannot_satisfy_missing_target():
    result=generate(manual(),bundles=[evidence('NewsletterInput','#newsletter')],html='')
    assert result['generation_quality']['status']=='partial'
    assert '#newsletter' not in result['script_code']


def test_unknown_compound_outcome_is_not_silently_dropped():
    case={'name':'Business calculation','steps':[{'action':'Navigate to https://other.test/cart',
        'expected_result':'The heading "Cart" is visible and the total equals the calculated price.'}]}
    result=generate(case)
    assert result['generation_quality']['status']=='partial'
    assert 'unsupported_expected_outcome' in result['script_code']


def test_serialized_plan_survives_json_and_detects_action_data_changes():
    import json
    result=json.loads(json.dumps(generate(manual(),pom=True)))
    assert not artifact_plan_issues(result)
    result['script_code']=result['script_code'].replace("'incorrect-value'", "'different-value'")
    assert artifact_plan_issues(result)


def test_checkbox_action_and_state_are_kept_in_both_artifacts():
    case={'name':'Preferences','steps':[{'action':'Check the Notifications checkbox',
        'expected_result':'The checkbox is checked.'}]}
    checkbox=evidence('NotificationsCheckbox','#notifications')
    result=generate(case,bundles=[checkbox],pom=True)
    assert result['generation_quality']['status']=='translated'
    assert not reconcile_automation_tests_with_bundles([result],[checkbox])[0]


def test_local_browser_generated_negative_flow(monkeypatch):
    """No public site/provider: intercept a local fixture page in a real browser."""
    from playwright.sync_api import sync_playwright, Error
    from phoenix.locators.live_session import LiveLocatorSession
    from phoenix_shared.models.locator import LocatorBundle
    monkeypatch.setenv('ACCOUNT_EMAIL','fixture@example.test')
    html=HTML.replace('<button>Access</button>','<button id="access" type="button">Access</button>')
    html=html.replace('</body>', '''<script>
      document.querySelector('#access').onclick = () => {
        const p = document.createElement('p'); p.textContent = 'Credentials rejected';
        document.querySelector('main').appendChild(p);
      };
    </script></body>''')
    with sync_playwright() as playwright:
        try:browser=playwright.chromium.launch()
        except Error as exc:
            if "Executable doesn't exist" in str(exc):pytest.skip('Chromium is not installed; run python -m playwright install chromium')
            raise
        try:
            page=browser.new_page()
            page.route('https://example.test/account',lambda route:route.fulfill(body=html,content_type='text/html'))
            page.goto('https://example.test/account')
            actual=deepcopy(BUNDLES)
            for bundle,tag,element_id in zip(actual,['input','input','button'],['account-email','secret','access']):
                bundle['metadata']['element_data']={'tag':tag,'id':element_id}
            validated=LiveLocatorSession(page).revalidate([LocatorBundle.model_validate(b) for b in actual])
            validated=[b.model_dump(mode='json') for b in validated]
            result=generate(manual(),bundles=validated,html=page.content())
            missing,_=reconcile_automation_tests_with_bundles([result],validated)
            assert not missing,missing
            namespace={};exec(result['script_code'],namespace)
            functions=[value for name,value in namespace.items() if name.startswith('test_')]
            assert len(functions)==1
            functions[0](page)
            assert page.locator('#account-email').input_value()=='fixture@example.test'
            assert page.get_by_text('Credentials rejected',exact=True).count()==1
        finally:browser.close()


def test_flat_repair_cannot_remove_prescribed_assertions():
    from phoenix.generators.automation import AutomationTestGenerator
    result=generate(manual())
    code='\n'.join(line for line in result['script_code'].splitlines() if 'Credentials rejected' not in line)
    with pytest.raises(RuntimeError):AutomationTestGenerator._enforce_locator_evidence(code,result)


def test_api_serialization_preserves_assertion_and_operation_contracts():
    from api.models import AutomateResponse
    result=generate(manual(),pom=True)
    mapped=AutomateResponse.model_validate({'automation_tests':[result]}).model_dump()['automation_tests'][0]
    assert mapped['assertion_contracts']==result['assertion_contracts']
    assert not artifact_plan_issues(mapped)


def test_contract_helper_import_cannot_be_replaced():
    result=generate(manual());spec=result['assertion_contracts'][0]
    code='from phoenix_shared.assertion_runtime import assert_contract\nfrom untrusted import assert_contract\ndef test_x(page):\n    assert_contract(page, '+repr(spec)+')\n'
    assert reconcile_generated_code(code,[],assertion_contracts=[spec])[2]


def test_explicit_submission_completion_binds_to_later_message_outcome():
    case=manual();case['steps'][4]['expected_result']='The account submission completes.'
    case['steps'].insert(5,{'step_number':6,'action':'Verify the rejection message',
        'expected_result':'The message "Credentials rejected" is visible.'})
    case['steps'][-1]['step_number']=7
    result=generate(case,pom=True)
    assert result['generation_quality']['status']=='translated'
    assert result['step_contracts'][4]['deferred_to_steps']==[6]
    assert not reconcile_automation_tests_with_bundles([result],BUNDLES)[0]


def test_submission_without_an_explicit_later_outcome_stays_partial():
    case=manual();case['steps']=case['steps'][:5];case['steps'][-1]['expected_result']='The account submission completes.'
    case['expected_result']=''
    result=generate(case)
    assert result['generation_quality']['status']=='partial'
    assert 'submission_outcome_not_supplied' in result['script_code']


def test_url_continuity_uses_captured_url_before_submission():
    case=manual();case['steps'][4]['expected_result']='The page does not redirect. The message "Credentials rejected" is visible.'
    result=generate(case,pom=True)
    assert result['generation_quality']['status']=='translated'
    assert 'reference_url=_phoenix_navigation_url_1' in result['script_code']
    assert not reconcile_automation_tests_with_bundles([result],BUNDLES)[0]
    corrupted=result['script_code'].replace('reference_url=_phoenix_navigation_url_1','reference_url=page.url')
    assert reconcile_generated_code(corrupted,BUNDLES,assertion_contracts=result['assertion_contracts'])[2]


def test_complete_contract_translation_does_not_call_provider():
    from unittest.mock import Mock
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=Mock()
    result=agent.automate_from_manual_tests([manual()],application_url='https://example.test/account',
        locator_bundles=BUNDLES,dom_snapshot=HTML,use_pom=True)['automation_tests'][0]
    assert result['generation_mode']=='deterministic'
    agent.llm_client.generate.assert_not_called()


def test_empty_input_cannot_satisfy_populated_expectation():
    case=manual();case['steps'][3]['test_data']='""'
    result=generate(case)
    assert result['generation_quality']['status']=='partial'
    assert 'contradictory_expected_input_state' in result['script_code']


@pytest.mark.parametrize('pom', [False, True])
def test_persisted_bundle_sdk_api_generation_round_trip(pom):
    from phoenix_shared.models.locator import LocatorBundle
    from phoenix.locators.smartlocator_integration import locator_bundle_evidence
    from api.models import AutomateRequest, AutomateResponse
    import json

    serialized = locator_bundle_evidence([LocatorBundle.model_validate(b) for b in BUNDLES])
    assert all('element_name' not in b['primary'] for b in serialized)
    original = deepcopy(serialized)
    request = AutomateRequest.model_validate(json.loads(json.dumps({
        'manual_tests': [manual()], 'application_url': 'https://example.test/account',
        'locator_bundles': serialized, 'dom_snapshot': HTML, 'use_pom': pom,
    })))
    agent = TestGeneratorAgent(KnowledgeBase(), Cache())
    agent.llm_client = None
    response = agent.automate_from_manual_tests(request.manual_tests,
        application_url=request.application_url, locator_bundles=request.locator_bundles,
        dom_snapshot=request.dom_snapshot, use_pom=request.use_pom)
    result = AutomateResponse.model_validate(response).model_dump()['automation_tests'][0]
    assert result['generation_quality']['status'] == 'translated'
    assert result['generation_mode'] == 'deterministic'
    assert not artifact_plan_issues(result)
    assert not reconcile_automation_tests_with_bundles([result], serialized)[0]
    assert serialized == original


def test_malformed_primary_uses_only_valid_accepted_alternate():
    from services.agents.evidence_fallback import select_subject
    bundle = evidence('AccessButton', '#access')
    alternate = deepcopy(bundle['primary'])
    alternate.pop('element_name')
    bundle['alternates'] = [alternate]
    bundle['primary']['strategy'] = 'invalid-strategy'
    original = deepcopy(bundle)
    assert select_subject('Access button', 'Click Access button', [bundle], Snapshot(''), 'button') == 'page.locator("#access")'
    assert bundle == original
    bundle['alternates'][0]['metadata']['match_count'] = 2
    assert select_subject('Access button', 'Click Access button', [bundle], Snapshot(''), 'button') is None


def test_malformed_evidence_remains_unresolved_without_snapshot():
    from services.agents.evidence_fallback import select_subject
    bundle = evidence('AccessButton', '#access')
    bundle['primary'].pop('value')
    assert select_subject('Access button', 'Click Access button', [bundle], Snapshot(''), 'button') is None


def scoped_capture(name, selector, scope, tag='input', role=None):
    bundle = evidence(name, selector)
    bundle['metadata']['element_data'] = {
        'tag': tag, 'role': role,
        'href': '/observed-link' if tag=='a' else None,
        'ancestor_context': {'container_tag': 'form', 'container_text': scope,
            'section_context': {'section_class': scope.lower()+'-form', 'section_heading': scope+' account'}},
    }
    return bundle


def test_control_binding_uses_captured_scope_and_keeps_other_form_distinct():
    from services.agents.evidence_fallback import select_subject
    inputs = [scoped_capture('PasswordInput', '#secret', 'Access'),
              scoped_capture('PasswordInput', '#registration-secret', 'Register')]
    assert select_subject('Access password', 'Enter supplied password in Access password field', inputs, Snapshot(''), 'input') == 'page.locator("#secret")'
    assert select_subject('password', 'Enter supplied password in password field', inputs, Snapshot(''), 'input') is None
    inputs[0]['primary']['metadata']['match_count'] = 2
    assert select_subject('Access password', 'Enter supplied password', inputs, Snapshot(''), 'input') is None


def test_button_binding_excludes_same_named_navigation_link():
    from services.agents.evidence_fallback import select_subject
    bundles = [scoped_capture('AccessButton', '#access', 'Access', 'button'),
               scoped_capture('AccessLink', '#access-link', 'Access', 'a')]
    assert select_subject('Access', 'Click Access button inside Access form', bundles, Snapshot(''), 'button') == 'page.locator("#access")'
    assert select_subject('Access', 'Click Access link', bundles, Snapshot(''), 'link') == 'page.locator("#access-link")'
    assert select_subject('Access', 'Click Access button', bundles[1:], Snapshot('<a>Access</a>'), 'button') is None


@pytest.mark.parametrize('pom', [False, True])
def test_submission_deferred_to_explicit_message_action_and_scoped_controls(pom):
    case = manual()
    case['steps'][4]['expected_result'] = 'The account submission completes.'
    case['steps'].insert(5, {'step_number': 6, 'action': 'Verify the account error message',
        'expected_result': 'Text "Credentials rejected" is visible.', 'test_data': ''})
    case['steps'][-1]['step_number'] = 7
    bundles = [scoped_capture('EmailInput', '#account-email', 'Access'),
               scoped_capture('PasswordInput', '#secret', 'Access'),
               scoped_capture('AccessButton', '#access', 'Access', 'button'),
               scoped_capture('AccessLink', '#link', 'Access', 'a')]
    result = generate(case, bundles=bundles, pom=pom)
    assert result['generation_quality']['status'] == 'translated'
    assert result['step_contracts'][4]['deferred_to_steps'] == [6]
    assert not artifact_plan_issues(result)
    assert not reconcile_automation_tests_with_bundles([result], bundles)[0]


def test_unbound_overall_summary_preserves_steps_and_blocks_acceptance():
    from unittest.mock import Mock
    from api.models import AutomateResponse
    case = manual()
    case['expected_result'] = 'The account remains secure.'
    agent = TestGeneratorAgent(KnowledgeBase(), Cache())
    agent.llm_client = Mock()
    result = agent.automate_from_manual_tests([case], application_url='https://example.test/account',
        locator_bundles=BUNDLES, dom_snapshot=HTML, use_pom=True)
    test = AutomateResponse.model_validate(result).model_dump()['automation_tests'][0]
    assert test['overall_outcome_unresolved'] is True
    assert test['generation_quality']['implemented_steps'] == 6
    assert test['generation_quality']['unresolved_steps'] == []
    assert test['generation_quality']['status'] == 'partial'
    assert test['generation_quality']['requires_manual_review'] is True
    assert 'pytest.skip(' in test['script_code']
    agent.llm_client.generate_script.assert_not_called()
    assert not artifact_plan_issues(test)


def test_snapshot_field_label_binds_observed_form_without_promoting_stability():
    from services.agents.evidence_fallback import select_subject
    html = '<body><form><input placeholder="Password"><button>Access</button></form><form><input placeholder="Password"><button>Register</button></form></body>'
    low = scoped_capture('PasswordInput', '#old-secret', 'Access')
    low['primary']['metadata']['stability'] = 'Low'
    original = deepcopy(low)
    expression = select_subject('Access password', 'Enter supplied password in Access password field', [low], Snapshot(html), 'input')
    assert expression == "page.locator('form').filter(has=page.get_by_role('button', name='Access', exact=True)).get_by_placeholder('Password', exact=True)"
    assert low == original
    assert select_subject('password', 'Enter supplied password', [], Snapshot(html), 'input') is None


def test_snapshot_controls_enter_existing_live_resolution_path():
    from phoenix.locators.smartlocator_integration import resolve_automation_locator_evidence
    from phoenix_shared.models.locator import LocatorBundle
    case = manual()
    result = generate(case, bundles=[], pom=True)
    assert result['generation_quality']['status'] == 'translated'
    calls = []
    def scan(*args, **kwargs):
        calls.append(kwargs['element_names'])
        return []
    resolution = resolve_automation_locator_evidence([result], [], application_url='https://example.test/account',
        page='account', scan=scan, discover=lambda payload: {'locators': []},
        validate=lambda *args: {'match_count': 0, 'identity_matches': False},
        capture=lambda *args: {'capture_status': 'insufficient_context'}, max_rounds=1)
    assert calls and calls[0]
    assert resolution['unresolved']
    assert any('email' in label.lower() for label in calls[0])
    assert any('password' in label.lower() for label in calls[0])
