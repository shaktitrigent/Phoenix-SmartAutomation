from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from phoenix_shared.record_verification import read_record_identities,assert_no_new_records
from services.agents.test_generator import _build_script_from_stored_locators

LOOKUP={'url':'https://fixture/api/records','records_path':['data'],'total_path':['meta','total'],
 'identity_paths':[['id']],'page_size':2,'offset_parameter':'offset','limit_parameter':'limit'}

def page_with(responses):
    page=SimpleNamespace(url='https://fixture/form',context=SimpleNamespace(request=Mock()))
    page.context.request.get.side_effect=[SimpleNamespace(ok=True,json=lambda r=r:r) for r in responses]
    return page

def payload(ids,total=None):return {'data':[{'id':i} for i in ids],'meta':{'total':len(ids) if total is None else total}}


def test_complete_pagination_compares_stable_ids_not_only_counts():
    page=page_with([payload([1,2],3),payload([3],3),payload([1,2],3),payload([4],3)])
    baseline=read_record_identities(page,LOOKUP)
    assert baseline==frozenset({(1,),(2,),(3,)})
    with pytest.raises(AssertionError,match='New record identities'):assert_no_new_records(page,LOOKUP,baseline)
    assert page.context.request.get.call_args_list[1].kwargs['params']['offset']==2


@pytest.mark.parametrize('responses',[[payload([1,1],2)],[payload([1],2),payload([],2)],[payload([1],2),payload([2],3)]])
def test_duplicate_incomplete_or_changing_lookup_cannot_pass(responses):
    with pytest.raises(AssertionError):read_record_identities(page_with(responses),LOOKUP)


def test_cross_origin_lookup_is_rejected_without_request():
    page=page_with([])
    with pytest.raises(ValueError,match='current application origin'):read_record_identities(page,{**LOOKUP,'url':'https://other/api'})
    page.context.request.get.assert_not_called()


def test_empty_collection_and_unchanged_ids_can_pass():
    page=page_with([payload([]),payload([])])
    baseline=read_record_identities(page,LOOKUP);assert_no_new_records(page,LOOKUP,baseline)


def test_non_creation_contract_captures_before_action_and_compares_after():
    b={'element_name':'ApplyButton','page':'form','primary':{'element_name':'ApplyButton','strategy':'css','value':'#apply','verified_in_snapshot':True,
       'metadata':{'stability':'High','match_count':1,'identity_matches':True}},'metadata':{'element_data':{'tag':'button','id':'apply','text':'Apply'}}}
    case={'name':'Invalid submission','steps':[{'action':'Click Apply','expected_result':'no account is created.',
       'assertion_evidence':[{'expectation':'no account is created.','kind':'no_new_records','verification_method':'api_record_comparison','lookup':LOOKUP}]}]}
    ok,code,missing=_build_script_from_stored_locators(case,[b],'https://fixture/form')
    assert ok,missing
    assert code.index('= read_record_identities(')<code.index('click_ready(')<code.index('record_baseline=_record_baseline_1')


@pytest.mark.parametrize('entity',['account','product'])
def test_live_observed_scope_can_bind_non_creation_without_site_specific_code(entity):
    url='https://fixture/form'
    button={'element_name':'ApplyButton','page':'form','primary':{'element_name':'ApplyButton','strategy':'css','value':'#apply','verified_in_snapshot':True,
       'metadata':{'stability':'High','match_count':1,'identity_matches':True}},'metadata':{'element_data':{'tag':'button','id':'apply','text':'Apply'}}}
    scope={'element_name':'SearchResults','page':'results','primary':{'element_name':'SearchResults','strategy':'css','value':'#results','verified_in_snapshot':True,
       'metadata':{'stability':'High','match_count':1,'identity_matches':True}},'metadata':{'element_data':{'tag':'div','role':'table'},
        'assertion_scope':{'kind':'records','record_role':'row','entity_name':entity,'non_creation_verification':'compare_records',
          'lookup_source':'observed_live_read_only_response','record_lookup':LOOKUP}}}
    case={'name':'Invalid submission','steps':[{'action':'Click Apply','expected_result':f'no {entity} is created.'}]}
    ok,code,missing=_build_script_from_stored_locators(case,[button,scope],url)
    assert ok,missing
    assert case['_compiled_fallback']['assertion_contracts'][0]['kind']=='no_new_records'
