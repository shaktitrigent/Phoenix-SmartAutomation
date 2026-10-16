from copy import deepcopy
from unittest.mock import Mock
import pytest
from services.agents.evidence_fallback import select_subject
from services.agents.test_generator import TestGeneratorAgent, _extract_click_target
from services.knowledge.base import KnowledgeBase
from services.cache import Cache
from phoenix_shared.generation_contract import Snapshot, artifact_plan_issues
from phoenix_shared.automation_translation import assertion_lines
from phoenix.locators.reconciliation import match_locator_bundle
from phoenix.locators.live_session import LiveLocatorSession
from phoenix_shared.models.locator import Locator, LocatorStrategy
from phoenix.locators.persist import persist_locators


def bundle(name, selector, data, state='entry'):
    return {'element_name':name,'page':state,'primary':{'strategy':'css','value':selector,'verified_in_snapshot':True,
        'metadata':{'stability':'High','stability_score':10,'match_count':1,'identity_matches':True,'state_name':state,
                    'validation_url':'https://fixture.test/entry' if state=='entry' else 'https://fixture.test/activity'}},
        'metadata':{'element_identity':selector,'element_data':data}}


def test_fill_reconciliation_selects_editable_control_over_its_label():
    items=[bundle('ContactText','#caption',{'tag':'label','id':'caption','text':'Contact'}),
           bundle('ContactEntry','#contact',{'tag':'input','id':'contact','type':'email','name':'contact'})]
    assert match_locator_bundle('Contact',items,context='Enter the Contact field')['primary']['value']=='#contact'
    assert select_subject('Contact','Enter the Contact field',items,Snapshot('<body></body>'),'input')=='page.locator("#contact")'


def test_competing_editable_controls_remain_ambiguous():
    items=[bundle('ContactEntry','#primary',{'tag':'input','id':'primary','name':'contact'}),
           bundle('ContactEntry','#secondary',{'tag':'textarea','id':'secondary','name':'contact'})]
    assert select_subject('Contact','Enter the Contact field',items,Snapshot('<body></body>'),'input') is None
    assert match_locator_bundle('Contact',items,context='Enter the Contact field') is None


def test_native_input_button_is_not_an_editable_field():
    item=bundle('ProceedControl','#go',{'tag':'input','id':'go','type':'submit','text':'Proceed'})
    assert select_subject('Proceed','Click the Proceed button',[item],Snapshot('<body></body>'),'button')=='page.locator("#go")'
    assert select_subject('Proceed','Enter the Proceed field',[item],Snapshot('<body></body>'),'input') is None


def test_native_input_semantics_win_over_unrelated_container_role_words():
    item=bundle('ContactInput','#contact',{'tag':'input','id':'contact','name':'contact',
       'ancestor_context':{'container_id':'tools','container_text':'Contact Button tools'}})
    assert select_subject('Contact','Enter the Contact field',[item],Snapshot('<body></body>'),'input')=='page.locator("#contact")'


def test_named_noninteractive_text_cannot_authorize_click():
    item=bundle('ProceedButton','#caption',{'tag':'span','id':'caption','text':'Proceed Button'})
    assert select_subject('Proceed','Click the Proceed button',[item],Snapshot('<body></body>'),'button') is None
    assert match_locator_bundle('Proceed', [item],context='Click the Proceed button') is None


@pytest.mark.parametrize('action,label', [('Click the "Access" button','Access'),('Click the "Exit session" option within the opened menu','Exit session')])
def test_quotes_never_leak_into_click_label(action,label):
    assert _extract_click_target(action)[1]==label


def test_menu_anchor_and_environment_heading_compile_without_model_calls():
    items=[bundle('ProceedControl','#go',{'tag':'input','id':'go','type':'button','text':'Proceed'}),
           bundle('ActivityHeading','#activity',{'tag':'h2','id':'activity','text':'Activity'},'activity'),
           bundle('UserMenu','#tray',{'tag':'a','id':'tray','href':'#','text':'Account'},'activity'),
           bundle('ExitSessionMenuItem','#exit',{'tag':'a','id':'exit','href':'/exit','text':'Exit session'},'menu')]
    steps=[('Click the "Proceed" button','URL equals "${CONFIRMED_DESTINATION}"; the heading "${CONFIRMED_HEADING}" is visible.'),
           ('Open the user menu','The "Exit session" option is visible within the opened user menu.'),
           ('Click the "Exit session" option within the opened user menu','URL equals "https://fixture.test/entry".')]
    manual={'name':'Independent account entry','steps':[{'step_number':n,'action':a,'expected_result':e} for n,(a,e) in enumerate(steps,1)]}
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=Mock()
    agent.environment_values={'CONFIRMED_DESTINATION':'https://fixture.test/activity','CONFIRMED_HEADING':'Activity'}
    result=agent.automate_from_manual_tests([manual],application_url='https://fixture.test/entry',locator_bundles=items,
       dom_snapshot='<body></body>',use_pom=True)['automation_tests'][0]
    assert result['generation_quality']['status']=='translated',result['step_contracts']
    assert result['generation_quality']['implemented_steps']==3
    assert any(c.get('expected_heading_reference')=='CONFIRMED_HEADING' for c in result['assertion_contracts'])
    assert "os.environ['CONFIRMED_DESTINATION']" in result['script_code']
    assert not artifact_plan_issues(result)
    agent.llm_client.generate.assert_not_called()


def test_missing_environment_heading_remains_unresolved():
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=None
    result=agent.automate_from_manual_tests([{'name':'Missing binding','steps':[{'action':'Verify heading','expected_result':'The heading "${UNSUPPLIED_HEADING}" is visible.'}]}],
       application_url='https://fixture.test',locator_bundles=[],dom_snapshot='<body></body>',use_pom=True)['automation_tests'][0]
    assert result['generation_quality']['status']=='partial'
    assert 'unbound_environment_heading' in result['step_contracts'][0]['reasons']


@pytest.mark.parametrize('selector',['','   '])
def test_empty_candidates_never_reach_browser_evaluation(selector):
    page=Mock(url='https://fixture.test');session=LiveLocatorSession(page)
    outcome=session.validate(Locator(element_name='Control',strategy=LocatorStrategy.CSS,value=selector),{'element_data':{'tag':'input','id':'control'}})
    assert outcome['identity_matches'] is False
    page.locator.assert_not_called()
    page.get_by_role.assert_not_called()


def test_complete_capture_replaces_obsolete_targets_but_generation_still_merges(tmp_path):
    old=bundle('Entry','#entry',{'tag':'input','id':'entry'})
    fresh=bundle('Activity','#activity',{'tag':'h2','id':'activity','text':'Activity'},'activity')
    persist_locators([{'page':'state','locators':[old]}],tmp_path)
    persist_locators([{'page':'state','locators':[fresh]}],tmp_path,replace_pages=True)
    import json
    assert [b['element_name'] for b in json.loads((tmp_path/'state.json').read_text())]==['Activity']
    persist_locators([{'page':'state','locators':[old]}],tmp_path)
    assert len(json.loads((tmp_path/'state.json').read_text()))==2
    persist_locators([{'page':'state','locators':[]}],tmp_path,replace_pages=True)
    assert json.loads((tmp_path/'state.json').read_text())==[]


def test_runtime_heading_reference_checks_the_configured_business_text(monkeypatch):
    from playwright.sync_api import sync_playwright
    from phoenix_shared.assertion_runtime import assert_contract
    contract={'version':1,'kind':'visible','subject':'page.locator("#activity")',
              'expected_heading_reference':'CONFIRMED_HEADING'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);page=browser.new_page()
        page.set_content('<main><h2 id="activity">Activity</h2></main>')
        monkeypatch.setenv('CONFIRMED_HEADING','Activity')
        assert_contract(page,contract,timeout=200)
        monkeypatch.setenv('CONFIRMED_HEADING','Billing')
        with pytest.raises(AssertionError):assert_contract(page,contract,timeout=200)
        browser.close()


def test_semicolon_visibility_checks_and_narrative_summary_keep_each_assertion():
    from phoenix_shared.manual_semantics import expectation_parts
    parts=expectation_parts('Displays the Contact field, PIN field, and "Proceed" button.')
    assert parts==['Contact field is visible.','PIN field is visible.','"Proceed" button is visible.']
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=None
    items=[bundle('ContactInput','#contact',{'tag':'input','id':'contact','name':'contact'}),
           bundle('PinInput','#pin',{'tag':'input','id':'pin','type':'password','name':'pin'}),
           bundle('ProceedButton','#proceed',{'tag':'input','id':'proceed','type':'button','text':'PROCEED'})]
    manual={'name':'Independent visibility','steps':[{'action':'Verify controls','expected_result':'The Contact field is visible; the PIN field is visible; the "Proceed" button is visible.'}],
            'expected_result':'The Contact field, PIN field, and Proceed button are visible.'}
    result=agent.automate_from_manual_tests([manual],application_url='https://fixture.test',locator_bundles=items,dom_snapshot='<body></body>',use_pom=True)['automation_tests'][0]
    assert result['generation_quality']['status']=='translated'
    assert len(result['assertion_contracts'])==3
    assert {c['subject'] for c in result['assertion_contracts']}=={'page.locator("#contact")','page.locator("#pin")','page.locator("#proceed")'}
    assert not result['unbound_overall_outcomes']


def test_transition_summary_requires_the_named_action_and_executable_url_assertion():
    from phoenix_shared.generation_contract import summary_binding
    record={'step':4,'status':'translated','action_kind':'click','action_text':'Click the "Proceed" button',
            'url_asserted':True,'expected_result':'URL equals "${CONFIRMED_ACTIVITY_URL}".'}
    assert summary_binding('Proceed reaches the configured Activity URL',[],[record])['steps']==[4]
    for key,value in [('url_asserted',False),('status','partial'),('action_text','Click the "Other" button')]:
        wrong={**record,key:value}
        assert summary_binding('Proceed reaches the configured Activity URL',[],[wrong]) is None


def test_floating_labels_use_snapshot_text_without_dropping_identity_checks():
    from playwright.sync_api import sync_playwright
    from phoenix.locators.live_session import _DESCRIBE, identity_matches
    from phoenix_smartlocatorai.dom_scanner import extract_interactable_elements
    html='<form id="entry"><div id="contact-group"><span>Contact</span><input id="contact" name="contact"></div><script>ignored code</script></form>'
    expected=next(e for e in extract_interactable_elements(html) if e.get('id')=='contact')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);page=browser.new_page();page.set_content(html)
        target=page.locator('#contact')
        assert identity_matches(target.evaluate(_DESCRIBE),expected)
        target.fill('sample value')
        page.locator('#contact-group span').evaluate("n => n.style.display='none'")
        assert page.locator('#contact-group').inner_text()==''
        assert identity_matches(target.evaluate(_DESCRIBE),expected)
        page.locator('#contact-group span').evaluate("n => n.textContent='Other field'")
        assert not identity_matches(target.evaluate(_DESCRIBE),expected)
        browser.close()
