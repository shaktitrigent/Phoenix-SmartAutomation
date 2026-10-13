"""Context field capture, identity, persistence, and timeout behavior."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from phoenix.locators.journey import validate_scoped_target, capture_journey
from phoenix.locators.live_session import identity_matches
from phoenix_shared.locator_policy import locator_accepted
from phoenix.sdk.intelligence_client import IntelligenceClient


def descriptor(label='Account code'):
    return {'tag':'input','id':'','name':'','type':'','class':'generic','text':'','role':'',
            'ancestors':[{'tag':'div','id':'','class':'field-group','text':label}]}


def session_for(actual,validation=None,count=1):
    target=Mock();target.count.return_value=count;target.evaluate.return_value=actual
    page=Mock(url='https://fixture/search');page.locator.return_value=target
    session=SimpleNamespace(page=page,validate=Mock(return_value=validation or {
        'match_count':1,'identity_matches':True,'validation_url':page.url,'state_name':'search'}))
    return session


def test_contextual_input_with_no_accessible_name_requires_label_identity():
    actual=descriptor()
    expected={'tag':'input','ancestor_context':{'container_tag':'div','distinguishing_text':'Account code'}}
    assert identity_matches(actual,expected)
    assert not identity_matches(descriptor('Department code'),expected)
    assert not identity_matches(actual,{'tag':'input'})


@pytest.mark.parametrize('label',['Account code','Product code'])
def test_contextual_candidate_gets_live_validation_and_correct_provenance(label):
    session=session_for(descriptor(label))
    definition={'name':'CodeInput','selector':f'div.field-group:has(label:text-is("{label}")) input'}
    b=validate_scoped_target(session,definition,'search')
    assert b is not None and locator_accepted(b.primary,b.metadata)
    assert b.primary.value==definition['selector']
    assert b.primary.metadata['validation_url']=='https://fixture/search'
    assert b.primary.metadata['stability_basis']=='explicit_label_context'
    session.validate.assert_called_once()


@pytest.mark.parametrize('validation',[{'match_count':2,'identity_matches':True},{'match_count':1,'identity_matches':False}])
def test_uniqueness_or_wrong_identity_never_becomes_accepted(validation):
    session=session_for(descriptor(),validation)
    assert validate_scoped_target(session,{'name':'Code','selector':'div:has(label:text-is("Account code")) input'},'search') is None


def test_arbitrary_class_only_candidate_remains_unaccepted():
    session=session_for({'tag':'input','class':'random','ancestors':[]})
    assert validate_scoped_target(session,{'name':'Code','selector':'.random'},'search') is None


def test_capture_preserves_repository_and_skips_expert_when_scoped_candidate_resolves(tmp_path,monkeypatch):
    import phoenix.locators.journey as journey
    states=tmp_path/'states.json';states.write_text(json.dumps({'states':[{'name':'search','fallback_targets':[
        {'name':'CodeInput','selector':'div:has(label:text-is("Account code")) input'}]}]}))
    session=session_for(descriptor());session.scan=Mock(return_value=[]);session.capture=Mock()
    @contextmanager
    def live(*args,**kwargs):
        assert kwargs['storage_state']=='state.json'
        yield session
    monkeypatch.setattr('phoenix.locators.live_session.live_session',live)
    discover=Mock()
    result=capture_journey('https://fixture/start',states,tmp_path/'raw',tmp_path/'locators',storage_state='state.json',discover=discover)
    assert result['states'][0]['llm_calls']==0
    discover.assert_not_called()
    saved=json.loads((tmp_path/'locators/search.json').read_text())
    assert saved[0]['element_name']=='CodeInput'
    assert saved[0]['primary']['metadata']['identity_matches'] is True
    # A second scoped scan must not erase unrelated page bundles.
    old={'element_name':'Existing','primary':{'strategy':'css','value':'#old'}}
    (tmp_path/'locators/search.json').write_text(json.dumps(saved+[old]))
    capture_journey('https://fixture/start',states,tmp_path/'raw',tmp_path/'locators',storage_state='state.json')
    assert any(b['element_name']=='Existing' for b in json.loads((tmp_path/'locators/search.json').read_text()))


def test_http_timeout_is_not_retried(monkeypatch):
    import requests
    post=Mock(side_effect=requests.Timeout('blocked'));monkeypatch.setattr(requests,'post',post)
    config=SimpleNamespace(intelligence=SimpleNamespace(base_url='http://localhost:8001',timeout=1,retry_count=3))
    with pytest.raises(RuntimeError,match='completion is unknown'):
        IntelligenceClient(config)._post('/api/v1/locators/discover',{})
    post.assert_called_once()


def test_parser_keeps_complete_trailing_placeholder_cell():
    spec=importlib.util.spec_from_file_location('parser_for_test',Path(__file__).parents[1]/'phoenix/generators/manual_parser.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    text='Enter `${FIRST}` in First Name and `${LAST}` in Last Name'
    assert mod._strip_md_cell(text)==text
    assert mod._strip_md_cell('`${ONLY}`')=='${ONLY}'


def test_locator_expert_timeout_stops_the_round_budget():
    from phoenix_shared.models.locator import Locator,LocatorBundle,LocatorStrategy
    from phoenix.locators.smartlocator_fallback import resolve_with_locator_expert
    candidate=Locator(element_name='CodeInput',strategy=LocatorStrategy.CSS,value='input',verified_in_snapshot=False,
        metadata={'stability':'Low','match_count':2,'identity_matches':False})
    b=LocatorBundle(element_name='CodeInput',page='search',primary=candidate,metadata={'element_data':{'tag':'input','name':'code'}})
    discover=Mock(side_effect=TimeoutError('slow'))
    result=resolve_with_locator_expert([b],page_url='https://fixture/search',discover=discover,validate=Mock(),max_rounds=3)
    assert result['llm_calls']==1
    assert result['unresolved_elements'][0]['final_failure_reason']=='locator_expert_timeout_completion_unknown'



def test_current_request_correlation_header_is_preserved(monkeypatch):
    import requests
    response=Mock(status_code=200);response.json.return_value={}
    post=Mock(return_value=response);monkeypatch.setattr(requests,'post',post)
    config=SimpleNamespace(intelligence=SimpleNamespace(base_url='http://localhost:8001',timeout=1,retry_count=1))
    IntelligenceClient(config)._post('/fixture',{})
    assert post.call_args.kwargs['headers']['X-Correlation-ID']



def test_current_scoped_seed_path_reports_required_unaccepted_target(tmp_path,monkeypatch):
    import phoenix.locators.journey as journey
    states=tmp_path/'states.json';states.write_text(json.dumps({'states':[{'name':'search','fallback_targets':[
        {'name':'CodeInput','selector':'#code'}]}]}))
    session=session_for({'tag':'input','id':'code','ancestors':[]});session.scan=Mock(return_value=[])
    def revalidate(bundles):
        b=bundles[0]
        return [b.model_copy(update={'primary':b.primary.model_copy(update={'verified_in_snapshot':True,
            'metadata':{'match_count':1,'identity_matches':True}})})]
    session.revalidate=revalidate
    @contextmanager
    def live(*a,**k):yield session
    monkeypatch.setattr('phoenix.locators.live_session.live_session',live)
    monkeypatch.setattr(journey,'validate_scoped_target',lambda *a:None)
    result=capture_journey('https://fixture/start',states,tmp_path/'raw',tmp_path/'locators')
    diagnostic=result['states'][0]['fallback_unresolved'][0]
    assert diagnostic['element_name']=='CodeInput'
    assert diagnostic['reason']=='required_target_needs_accepted_locator_evidence'


def test_explicit_structural_record_scope_gets_validated_and_persisted_without_full_scan(tmp_path,monkeypatch):
    definition={'name':'SearchResults','selector':'[role="table"]','assertion_scope':{'kind':'records','record_role':'row'}}
    states=tmp_path/'states.json';states.write_text(json.dumps({'states':[{'name':'search','scan_mode':'required_targets','fallback_targets':[definition]}]}))
    session=session_for({'tag':'div','role':'table','column_headers':['Identifier','Name'],'class':'dynamic','text':'old contents','ancestors':[]});session.scan=Mock()
    @contextmanager
    def live(*a,**k):yield session
    monkeypatch.setattr('phoenix.locators.live_session.live_session',live)
    result=capture_journey('https://fixture/start',states,tmp_path/'raw',tmp_path/'locators')
    assert result['states'][0]['accepted']==1 and result['states'][0]['fallback_unresolved']==[]
    session.scan.assert_not_called()
    saved=json.loads((tmp_path/'locators/search.json').read_text())[0]
    assert saved['metadata']['assertion_scope']==definition['assertion_scope']
    assert 'text' not in saved['metadata']['element_data'] or not saved['metadata']['element_data']['text']


def test_record_scope_declaration_cannot_turn_arbitrary_div_into_accepted_table():
    session=session_for({'tag':'div','role':'','id':'container','ancestors':[]})
    with pytest.raises(ValueError,match='live table/grid'):
        validate_scoped_target(session,{'selector':'#container','assertion_scope':{'kind':'records','record_role':'row'}},'search')


def test_scope_capture_attaches_only_a_matching_observed_lookup(tmp_path,monkeypatch):
    import phoenix_smartlocatorai.dynamic_states as actions
    from phoenix.locators.record_lookup_observation import observe_record_lookup
    definition={'name':'SearchResults','selector':'[role="table"]','assertion_scope':{
       'kind':'records','record_role':'row','lookup_fields':['givenName','familyName'],
       'entity_name':'account','non_creation_verification':'compare_records'}}
    states=tmp_path/'states.json';states.write_text(json.dumps({'states':[{'name':'search','scan_mode':'required_targets',
        'actions':[{'action':'goto','value':'https://fixture/search'}],'fallback_targets':[definition]}]}))
    session=session_for({'tag':'div','role':'table','column_headers':['Identifier','Name'],'ancestors':[]});callbacks={}
    session.page.on.side_effect=lambda event,callback:callbacks.update({event:callback})
    def action(page,definition):
        response=SimpleNamespace(url='https://fixture/api/accounts?offset=0&limit=50',
          request=SimpleNamespace(method='GET'),json=lambda:{'data':[{'accountId':1,'givenName':'hidden','familyName':'hidden'}],'meta':{'total':1}})
        callbacks['response'](response)
    monkeypatch.setattr(actions,'_execute_state_action',action)
    @contextmanager
    def live(*a,**kw):yield session
    monkeypatch.setattr('phoenix.locators.live_session.live_session',live)
    result=capture_journey('https://fixture/start',states,tmp_path/'raw',tmp_path/'locators')
    saved=json.loads((tmp_path/'locators/search.json').read_text())[0]['metadata']['assertion_scope']
    assert saved['lookup_source']=='observed_live_read_only_response'
    assert saved['record_lookup']['identity_paths']==[['accountId']]
    assert 'hidden' not in str(saved)


def test_native_record_table_requires_matching_stable_header_schema():
    expected={'tag':'table','column_headers':['Identifier','Name']}
    assert identity_matches({'tag':'table','column_headers':['Identifier','Name']},expected)
    assert not identity_matches({'tag':'table','column_headers':['Amount','Currency']},expected)
