"""Cross-application compiler and POM regression evidence; no site shortcuts."""
import ast
from copy import deepcopy
from unittest.mock import Mock
import pytest
from phoenix_shared.manual_semantics import bound_actions, split_actions, expectation_parts, final_artifact_issues
from phoenix_shared.automation_translation import fill_value_expression
from phoenix_shared.generation_contract import Snapshot, artifact_plan_issues, operation_signature
from phoenix_shared.page_objects import synthesize_pages, expanded_pom_script
from services.agents.test_generator import TestGeneratorAgent, _build_script_from_stored_locators, _normalise_generated_script
from services.agents.evidence_fallback import select_subject


def bundle(element_name,selector,tag,page,url,**data):
    return {'element_name':element_name,'page':page,'primary':{'element_name':element_name,'strategy':'css','value':selector,
        'verified_in_snapshot':True,'metadata':{'stability':'High','match_count':1,'identity_matches':True,
        'validation_url':url,'state_name':page}},'alternates':[],
        'metadata':{'element_data':{'tag':tag,'id':selector.removeprefix('#'),**data},'element_identity':selector}}


@pytest.mark.parametrize('domain,entry,form,field,label',[
    ('https://shop.fixture','catalog','cart','Quantity','Add'),
    ('https://office.fixture','overview','settings','Alias','Configure'),
])
def test_two_applications_use_same_compiler_resolver_and_multiple_poms(domain,entry,form,field,label,monkeypatch):
    url=domain+'/'+entry;form_url=domain+'/'+form
    bs=[bundle(label+'Button','#go','button',entry,url,text=label),
        bundle(field+'Input','#value','input',form,form_url,name=field.lower()),
        bundle('ApplyButton','#apply','button',form,form_url,text='Apply'),
        bundle('Acknowledgement','#receipt','span',form,form_url,text='Applied')]
    case={'name':'Independent workflow','steps':[
        {'action':f'Navigate to {url}','expected_result':f'The URL contains "/{entry}".'},
        {'action':f'Click {label}','expected_result':f'The URL contains "/{form}".'},
        {'action':f'Enter "${{EXPLICIT_VALUE}}" in the {field} field','expected_result':f'{field} field contains "${{EXPLICIT_VALUE}}".'},
        {'action':'Click Apply','expected_result':'"Applied" message is visible.'}],
        'expected_result':'"Applied" message is visible.'}
    ok,script,missing=_build_script_from_stored_locators(case,bs,url)
    assert ok,missing
    script=_normalise_generated_script(script)
    pom=synthesize_pages(script,'independent','independent')
    assert len(pom['page_objects'])==2
    assert not final_artifact_issues({'script_code':script,'pom_bundle':pom,'generation_plan':{'operations':operation_signature(script)}})
    assert operation_signature(expanded_pom_script(pom),preserve_selectors=True)==operation_signature(script,preserve_selectors=True)
    assert any('locate_' in p['code'] for p in pom['page_objects'])
    assert '#value' not in pom['tests'][0]['code']
    # Execute generated method calls with recording doubles: verifies cross-
    # method ordering and env binding, without claiming browser validation.
    monkeypatch.setenv('EXPLICIT_VALUE','27')
    page=Mock();events=[]
    class BasePage:
        def __init__(self,page):self._page=page
    instances={}
    for item in pom['page_objects']:
        tree=ast.parse(item['code'])
        tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        ns={'BasePage':BasePage,'Page':object,'Locator':object,'os':__import__('os'),'re':__import__('re'),'pytest':pytest,
            'expect':lambda *a:Mock(),'assert_contract':lambda *a,**kw:events.append('assert'),
            'validate_target':lambda *a,**kw:None}
        exec(compile(tree,'<recording-pom>','exec'),ns)
        ns['fill_ready']=lambda p,t,v,*a:events.append(('fill',v))
        ns['click_ready']=lambda p,t,*a:events.append('click')
        ns['configure_page']=lambda p:None;ns['dismiss_known_overlays']=lambda p:None
        instances[item['class_name']]=ns[item['class_name']](page)
    context={}
    for owner,method in pom['execution_order']:
        cls=''.join(w.capitalize() for w in owner.split('_'))+'Page'
        getattr(instances[cls],method)(context)
    assert ('fill','27') in events
    assert events.count('click')==2


def test_order_checker_detects_dropped_actual_pom_call():
    script='def test_x(page):\n page.goto("https://fixture/a")\n page.goto("https://fixture/b")\n'
    pom=synthesize_pages(script,'flow','flow')
    damaged=deepcopy(pom);damaged['tests'][0]['code']='\n'.join(damaged['tests'][0]['code'].splitlines()[:-1])
    assert artifact_plan_issues({'script_code':script,'pom_bundle':damaged,'generation_plan':{'operations':operation_signature(script)}})


def test_cross_method_url_binding_is_not_lost():
    script='def test_x(page):\n page.goto("https://fixture/a")\n reference = page.url\n page.goto("https://fixture/b")\n assert page.url != reference\n'
    pom=synthesize_pages(script,'flow','flow')
    assert any("context['reference']" in p['code'] for p in pom['page_objects'])
    assert not final_artifact_issues({'script_code':script,'pom_bundle':pom,'generation_plan':{'operations':operation_signature(script)}})


def test_compounds_keep_order_literals_and_empty_values():
    text='Enter "literal and negative" in Token; clear Secret and Alias fields; click Apply, then open Settings'
    assert split_actions(text)==['Enter "literal and negative" in Token field','Clear Secret field','Clear Alias field','click Apply','open Settings']
    assert bound_actions('Enter "${TOKEN}" and "${SECRET}" in the respective fields, then click Apply','Token: `${TOKEN}`; Secret: `${SECRET}`')==[
        "Enter '${TOKEN}' in the Token field","Enter '${SECRET}' in the Secret field",'click Apply']
    assert bound_actions('Enter Token and Secret',{'Token':'x'})==[]


def test_multi_variable_interpolation_keeps_explicit_separator(monkeypatch):
    monkeypatch.setenv('A','North');monkeypatch.setenv('B','Wind')
    expr=fill_value_expression('${A} / ${B}')
    assert eval(expr,{'os':__import__('os')})=='North / Wind'
    assert fill_value_expression('literal')==repr('literal')


def test_visibility_cannot_be_replaced_by_previous_action_target():
    b=bundle('ApplyButton','#apply','button','form','https://fixture/form',text='Apply')
    case={'name':'Missing target','steps':[{'action':'Click Apply','expected_result':'The Customer field is visible.'}]}
    _build_script_from_stored_locators(case,[b],'https://fixture/form')
    c=case['_compiled_fallback']
    assert c['unresolved_steps']==[1]
    assert not any('to_be_visible' in s and '#apply' in s for s in c['script_code'].splitlines())


def test_non_creation_requires_explicit_observable_follow_up():
    b=bundle('SearchButton','#search','button','results','https://fixture/results',text='Search')
    case={'name':'Non creation','steps':[{'action':'Click Search','expected_result':'No order is created.'}]}
    _build_script_from_stored_locators(case,[b],'https://fixture/results')
    assert 'missing_observable_non_creation_evidence' in case['_compiled_fallback']['step_contracts'][0]['reasons']
    scope=bundle('OrdersTable','#orders','table','results','https://fixture/results')
    case['steps'][0]['assertion_evidence']=[{'expectation':'No order is created.','kind':'record_absent',
        'verification_method':'follow_up_search','scope_target':'OrdersTable','record_role':'row','expected_values':['${ORDER_CODE}']}]
    ok,_,missing=_build_script_from_stored_locators(case,[b,scope],'https://fixture/results')
    assert ok,missing
    assert case['_compiled_fallback']['assertion_contracts'][0]['proof_scope']=='observable_filtered_records'


def test_unsupported_overall_summary_is_never_ignored():
    b=bundle('ApplyButton','#apply','button','form','https://fixture/form',text='Apply')
    case={'name':'Summary','steps':[{'action':'Click Apply','expected_result':'"Applied" message is visible.'}],
          'expected_result':'The ledger is persisted atomically in the database.'}
    ok,_,missing=_build_script_from_stored_locators(case,[b],'https://fixture/form')
    assert not ok and 'Overall expected result' in missing
    assert case['_compiled_fallback']['unbound_overall_outcomes']


def test_known_evidence_gap_never_triggers_llm_generation():
    from services.knowledge.base import KnowledgeBase
    from services.cache import Cache
    agent=TestGeneratorAgent(KnowledgeBase(),Cache());agent.llm_client=Mock()
    case={'name':'Missing input','steps':[{'action':'Enter "x" in Customer field','expected_result':'Customer field contains "x".'}],
          '_validated_locator_bundles':[],'_dom_snapshot':''}
    result=agent._generate_script_for_manual_test(case,'https://fixture/form','')
    assert result['generation_mode']=='unresolved_evidence'
    agent.llm_client.generate.assert_not_called()


def test_page_context_does_not_pick_unrelated_duplicate_field():
    bs=[bundle('ContactInput','#a','input','first','https://fixture/first',name='contact'),
        bundle('ContactInput','#b','input','second','https://fixture/second',name='contact')]
    snap=Snapshot('');snap.page_context=['/second']
    assert select_subject('Contact','',bs,snap,'input')=='page.locator("#b")'
    assert select_subject('Contact','',bs,Snapshot(''),'input') is None

@pytest.mark.parametrize('observed_depth',[2,None])
def test_dynamic_validation_requires_an_independent_field_group(monkeypatch,observed_depth):
    import sys
    import types
    from phoenix_shared import assertion_runtime
    expect=Mock(return_value=Mock())
    api=types.ModuleType('playwright.sync_api');api.expect=expect
    monkeypatch.setitem(sys.modules,'playwright',types.ModuleType('playwright'))
    monkeypatch.setitem(sys.modules,'playwright.sync_api',api)
    field=Mock();field.evaluate.return_value=observed_depth
    monkeypatch.setattr(assertion_runtime,'validate_target',lambda *a,**k:field)
    monkeypatch.setattr(assertion_runtime,'resolve_subject',lambda *a:Mock())
    contract={'version':1,'kind':'field_messages','scope':"page.locator('body')",'subject':"page.get_by_text('Mandatory')",
        'field_subjects':['Code'],'field_evidence':[{'primary':{'value':'#code'}}],
        'message':'Mandatory','expected_count':1}
    if observed_depth is None:
        with pytest.raises(AssertionError,match='independent field/message group'):
            assertion_runtime.assert_contract(Mock(),contract)
    else:
        assertion_runtime.assert_contract(Mock(),contract)
        assert expect.return_value.to_have_count.call_count>=2


def test_record_matching_uses_whole_supplied_tokens():
    from phoenix_shared.assertion_runtime import data_pattern
    pattern=data_pattern(['Al','Jones'])
    assert pattern.search('17 Al\nJones Active')
    assert not pattern.search('17 Alan Jones Active')
    assert not pattern.search('17 Al Smith Active')
    assert data_pattern(['North','Wind'],ordered=True).search('North\nWind')


def test_page_objects_extend_across_test_cases_without_losing_selectors():
    from phoenix.output.coordinator import _splice_methods_into_class
    bs=[bundle('ContactInput','#contact','input','form','https://fixture/form',name='contact'),
        bundle('CodeInput','#code','input','form','https://fixture/form',name='code')]
    objects=[]
    for field in ['Contact','Code']:
        case={'name':field,'steps':[{'action':f'Enter "value" in {field} field','expected_result':f'{field} field contains "value".'}]}
        ok,script,_=_build_script_from_stored_locators(case,bs,'https://fixture/form');assert ok
        pom=synthesize_pages(_normalise_generated_script(script),field.lower(),field.lower())
        objects.append(pom['page_objects'][0])
    assert objects[0]['file']==objects[1]['file']
    merged=_splice_methods_into_class(objects[0]['code'],objects[0]['class_name'],objects[1]['code'])
    compile(merged,'<merged-pom>','exec')
    assert '#contact' in merged and '#code' in merged
    tree=ast.parse(merged);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    methods={n.name for n in cls.body if isinstance(n,ast.FunctionDef)}
    assert len([m for m in methods if m.startswith('locate_')])==2
    assert len([m for m in methods if m.startswith('perform_')])==2
    meta=next(n for n in cls.body if isinstance(n,ast.Assign) and n.targets[0].id=='LOCATOR_PROVENANCE')
    assert len(ast.literal_eval(meta.value))==2


def test_numeric_page_route_generates_valid_python_names():
    pom=synthesize_pages('def test_x(page):\n page.goto("https://fixture/123")\n','flow','flow')
    for section in ['page_objects','tests']:
        for artifact in pom[section]:compile(artifact['code'],'<numeric-page>','exec')


def test_single_quoted_data_cannot_inject_a_compound_action():
    assert split_actions("Enter 'literal and click Delete' in Token field; click Apply")==[
        "Enter 'literal and click Delete' in Token field",'click Apply']


@pytest.mark.parametrize('predicate',['are blank','contain empty values','are empty'])
def test_current_empty_predicate_support_is_preserved(predicate):
    assert expectation_parts('Both Code and Secret '+predicate+'.')==[
        'The Code field contains an empty value ("").','The Secret field contains an empty value ("").']


def test_unquoted_placeholders_preserve_ordered_fill_bindings():
    assert split_actions('Enter ${A} in Code and ${B} in Secret')==[
        'Enter ${A} in Code field','Enter ${B} in Secret field']


def test_conflicting_search_data_is_not_silently_substituted():
    case={'name':'Contradictory data','steps':[{'action':'Search for ${A}','test_data':'Code: ${B}','expected_result':'"Found" message is visible.'}]}
    _build_script_from_stored_locators(case,[],'https://fixture/search')
    assert 'contradictory_search_data_binding' in case['_compiled_fallback']['step_contracts'][0]['reasons']


def test_explicit_heading_absence_needs_no_positive_snapshot_bundle():
    b=bundle('ProceedButton','#go','button','entry','https://fixture/entry',text='Proceed')
    case={'name':'Negative heading','steps':[{'action':'Click Proceed','expected_result':'Workspace heading is absent.'}]}
    ok,_,missing=_build_script_from_stored_locators(case,[b],'https://fixture/entry')
    assert ok,missing
    assert case['_compiled_fallback']['assertion_contracts'][0]['scope']=="page.locator('body')"


def test_post_interaction_diagnostics_use_caller_page_and_state():
    from services.agents.evidence_fallback import missing_state_evidence_diagnostic
    text=missing_state_evidence_diagnostic('Currency menu','interaction',page_context='/checkout',state_context='currency_open')
    assert '/checkout' in text and 'currency_open' in text
    assert 'account_menu' not in text



def test_selector_reconciliation_preserves_pure_accessors_without_rescanning():
    from phoenix.locators.reconciliation import reconcile_generated_code
    b=bundle('ProceedButton','#go','button','entry','https://fixture/entry',text='Proceed')
    code='class EntryPage:\n def locate_go(self):\n  return self._page.locator("#go")\n def act(self):\n  click_ready(self._page,self.locate_go(),"Proceed")\n'
    final,used,missing=reconcile_generated_code(code,[b])
    assert not missing
    assert final==code and used
    bad=code.replace('  return self._page.locator','  self.audit()\n  return self._page.locator')
    final,_,missing=reconcile_generated_code(bad,[b])
    assert 'unsupported locator accessor: locate_go' in missing
    assert final==bad
