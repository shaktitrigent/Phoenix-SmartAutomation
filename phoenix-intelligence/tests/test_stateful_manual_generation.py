"""State observations and explicit manual predicates, independent of any site."""
from copy import deepcopy
from unittest.mock import Mock
import pytest
from phoenix_shared.state_evidence import group_state_evidence
from phoenix_shared.manual_semantics import expectation_parts
from phoenix_shared.generation_contract import Snapshot, artifact_plan_issues
from phoenix.locators.smartlocator_integration import validated_locator_bundles
from services.agents.evidence_fallback import select_subject
from services.agents.test_generator import TestGeneratorAgent, _extract_click_target, _detect_truncated_generation
from services.knowledge.base import KnowledgeBase
from services.cache import Cache


def target(name, selector, data, state='entry'):
    return {'element_name':name,'page':state,'primary':{'element_name':name,'strategy':'css',
        'value':selector,'verified_in_snapshot':True,'metadata':{'stability':'High','stability_score':9,
        'match_count':1,'identity_matches':True,'validation_url':'https://fixture.test/access','state_name':state}},
        'alternates':[], 'metadata':{'element_identity':selector,'element_data':data,'state_name':state}}


def test_same_control_states_keep_observations_but_distinct_controls_remain_ambiguous():
    entry=target('ContactInput','#contact',{'tag':'input','name':'contact','id':'contact'},'entry')
    error=deepcopy(entry);error['page']='rejected';error['primary']['metadata']['state_name']='rejected'
    error['metadata']['element_data']['class']='invalid';error['metadata']['state_name']='rejected'
    grouped=group_state_evidence([entry,error])
    assert len(grouped)==1
    assert {o['page'] for o in grouped[0]['metadata']['state_evidence']}=={'entry','rejected'}
    other=target('ContactInput','#other',{'tag':'input','name':'contact','id':'other'})
    assert len(group_state_evidence([entry,other]))==2
    assert select_subject('Contact','', [entry,other],Snapshot(''),'input') is None


def test_future_state_load_does_not_revalidate_against_entry(tmp_path):
    import json
    entry=target('ContactInput','#contact',{'tag':'input','id':'contact'})
    future=target('ExitMenuItem','#exit',{'tag':'a','role':'menuitem','text':'Exit'},'account_menu')
    for state,bundle in [('entry',entry),('account_menu',future)]:
        (tmp_path/f'{state}.json').write_text(json.dumps([bundle]))
    class Session:
        state_name='entry'
        def __init__(self):self.calls=[]
        def revalidate(self,bundles):self.calls.extend(b.element_name for b in bundles);return bundles
    session=Session()
    result=validated_locator_bundles(tmp_path,'entry',[{'name':'Contact Exit menu item'}],revalidate=session.revalidate)
    assert session.calls==['ContactInput']
    assert any(b.element_name=='ExitMenuItem' and b.metadata['requires_execution_validation'] for b in result)


def test_form_error_text_changes_preserve_same_scope_and_distinct_sections():
    data={'tag':'form','text':'Contact Access','ancestor_context':{'container_tag':'article',
        'container_class':'panel','section_context':{'section_tag':'article','section_heading':'Account access'}}}
    first=target('AccessForm','form.access',data)
    error=deepcopy(first);error['page']='rejected';error['metadata']['element_identity']='error-observation'
    error['metadata']['element_data']['text']='Contact Mandatory Access'
    error['primary']['metadata']['state_name']='rejected'
    grouped=group_state_evidence([first,error])
    assert len(grouped)==1 and len(grouped[0]['metadata']['state_evidence'])==2
    other=deepcopy(error);other['metadata']['element_data']['ancestor_context']['section_context']['section_heading']='Newsletter'
    assert len(group_state_evidence([first,other]))==2


def test_same_message_selector_strategies_keep_widest_validated_state_coverage():
    data={'tag':'span','text':'Mandatory','ancestor_context':{'container_id':'pin-group','container_text':'PIN Mandatory'}}
    narrow=target('PinRequired','.message',data,'pin_empty')
    scoped=target('PinRequired','#pin-group .message',data,'both_empty')
    second=deepcopy(scoped);second['page']='pin_empty';second['primary']['metadata']['state_name']='pin_empty'
    result=group_state_evidence([narrow,scoped,second])
    assert len(result)==1
    assert result[0]['primary']['value']=='#pin-group .message'
    assert len(result[0]['metadata']['state_evidence'])==3


def test_compound_and_empty_predicates_preserve_each_named_subject():
    assert expectation_parts('The Contact field, PIN field, and "Access" button are visible.')==[
        'Contact field is visible.','PIN field is visible.','"Access" button is visible.']
    parts=expectation_parts('Both Contact and PIN remain empty, the URL contains "/access", and the access form remains visible.')
    assert parts[:2]==['The Contact field contains an empty value ("").','The PIN field contains an empty value ("").']
    assert len(parts)==4
    assert _extract_click_target('Click the "Exit account" menu item')==('menuitem','Exit account')
    assert _extract_click_target('Click the "Access" button')==('button','Access')


def test_generated_pom_preserves_future_targets_empty_values_and_menu_action():
    bundles=[target('ContactInput','#contact',{'tag':'input','name':'contact','id':'contact'}),
             target('PinInput','#pin',{'tag':'input','name':'pin','id':'pin'}),
             target('AccountMenu','#menu',{'tag':'button','id':'menu','text':'Account menu'},'account'),
             target('ExitAccountMenuItem','#exit',{'tag':'a','role':'menuitem','text':'Exit account'},'account_menu')]
    rows=[('Enter "${CONTACT_VALUE}" in the Contact field','The Contact field contains "${CONTACT_VALUE}".'),
          ('Leave the PIN field empty','The PIN field contains an empty value ("").'),
          ('Open the account menu','The account menu is open and its "Exit account" menu item is visible.'),
          ('Click the "Exit account" menu item','The Contact field, PIN field are visible.')]
    case={'name':'Independent account flow','steps':[{'step_number':i,'action':a,'expected_result':e} for i,(a,e) in enumerate(rows,1)],
          'expected_result':'The Contact field contains "${CONTACT_VALUE}". The PIN field remains empty.'}
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=Mock()
    result=agent.automate_from_manual_tests([case],application_url='https://fixture.test/access',locator_bundles=bundles,
        dom_snapshot='<html><body><input id="contact"><input id="pin"></body></html>',use_pom=True)['automation_tests'][0]
    assert result['generation_quality']['status']=='translated', repr(result.get('step_contracts'))
    assert result['generation_quality']['implemented_steps']==4
    assert 'page.goto(' not in result['script_code']
    assert 'pytest.skip(' not in result['script_code']
    assert not artifact_plan_issues(result)
    agent.llm_client.generate.assert_not_called()
    assert any(c.get('expected_value')=='' for c in result['assertion_contracts'])
    assert any(c.get('expected_value')=='${CONTACT_VALUE}' for c in result['assertion_contracts'])


def test_ellipsis_identity_text_is_data_but_executable_ellipsis_remains_rejected():
    assert not _detect_truncated_generation('from playwright.sync_api import expect\ndef test_x(page):\n    assert {"container_text": "Long observed text..."}\n',[],coverage={'unresolved_steps':[],'implemented_steps':0})
    assert any('truncation marker' in w for w in _detect_truncated_generation('def test_x(page):\n    ...\n',[],coverage={'unresolved_steps':[],'implemented_steps':0}))


def test_repeated_validation_text_binds_to_two_independent_field_groups():
    bundles=[target('ContactRequired','#contact-help',{'tag':'small','text':'Mandatory',
        'ancestor_context':{'container_tag':'fieldset','container_id':'contact-group','container_text':'Contact Mandatory'}}),
        target('PinRequired','#pin-help',{'tag':'small','text':'Mandatory',
        'ancestor_context':{'container_tag':'section','container_id':'pin-group','container_text':'PIN Mandatory'}})]
    case={'name':'Independent messages', 'steps':[{'step_number':1,'action':'Verify validation',
        'expected_result':'A "Mandatory" validation message is visible within the Contact field group, and a separate "Mandatory" validation message is visible within the PIN field group.'}],
        'expected_result':'A "Mandatory" validation message is visible within the Contact field group.'}
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=None
    result=agent.automate_from_manual_tests([case],application_url='https://fixture.test/access',locator_bundles=bundles,
        dom_snapshot='<html><body></body></html>',use_pom=True)['automation_tests'][0]
    assert result['generation_quality']['status']=='translated',result.get('step_contracts')
    assert {c['subject'] for c in result['assertion_contracts']}=={'page.locator("#contact-help")','page.locator("#pin-help")'}
    assert not artifact_plan_issues(result)


def test_scoped_message_never_uses_global_text_when_evidence_is_missing():
    case={'name':'Missing physical field scope', 'steps':[{'action':'Verify validation',
        'expected_result':'A "Mandatory" validation message is visible within the Contact field group.'}]}
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=None
    result=agent.automate_from_manual_tests([case],application_url='https://fixture.test/access',locator_bundles=[],
        dom_snapshot='<body><span>Mandatory</span><span>Mandatory</span></body>',use_pom=True)['automation_tests'][0]
    assert result['generation_quality']['status']=='partial'
    assert result['step_contracts'][0]['reasons']==['unsupported_expected_outcome']
    assert not result['assertion_contracts']


def test_execution_rejects_unique_wrong_identity_and_future_absence():
    from playwright.sync_api import sync_playwright
    from phoenix_shared.assertion_runtime import validate_target
    evidence=target('ExitMenuItem','#exit',{'tag':'a','id':'exit','role':'menuitem','text':'Exit'})
    evidence['primary']['metadata']['validation_url']='about:blank'
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        try:
            page=browser.new_page();page.set_content('<a id="exit" role="menuitem">Delete</a>')
            with pytest.raises(AssertionError,match='identity'):validate_target(page,evidence,timeout=500)
            page.set_content('<a id="exit" role="menuitem">Exit</a>')
            assert validate_target(page,evidence,timeout=500).inner_text()=='Exit'
            page.set_content('<form><input id="contact"></form>')
            with pytest.raises(AssertionError):validate_target(page,evidence,timeout=200)
        finally:browser.close()
