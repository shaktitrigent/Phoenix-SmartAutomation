import pytest
from services.agents.test_generator import _build_script_from_stored_locators


def bundle(element_name,selector,tag,url,**data):
    return {'element_name':element_name,'page':'results','primary':{'element_name':element_name,'strategy':'css','value':selector,
        'verified_in_snapshot':True,'metadata':{'stability':'High','match_count':1,'identity_matches':True,
        'validation_url':url,'state_name':'results'}},'alternates':[],
        'metadata':{'element_data':{'tag':tag,**data},'element_identity':selector}}


@pytest.mark.parametrize('host,label',[('https://inventory.fixture','Product Code'),('https://accounts.fixture','Account Name')])
def test_matching_record_binds_search_data_to_declared_scope(host,label):
    url=host+'/results'
    bs=[bundle(label+'Input','#query','input',url,name=label),bundle('SearchButton','#search','button',url,text='Search')]
    scope=bundle('SearchResults','#results','div',url,role='table');scope['metadata']['assertion_scope']={'kind':'records','record_role':'row'};bs.append(scope)
    case={'name':'Find record','steps':[{'action':'Search for "${EXPLICIT_VALUE}"','test_data':{label:'${EXPLICIT_VALUE}'},'expected_result':'Search results contain a matching record.'}]}
    ok,code,missing=_build_script_from_stored_locators(case,bs,url)
    assert ok,missing
    c=case['_compiled_fallback']['assertion_contracts'][0]
    assert c['kind']=='record_present' and c['expected_values']==['${EXPLICIT_VALUE}'] and '#results' in c['scope']
    assert c['target_evidence'] and c['record_role']=='row'


@pytest.mark.parametrize('mode',['undeclared','wrong_page','ambiguous'])
def test_result_scope_never_guessed(mode):
    url='https://fixture/results'
    bs=[bundle('CodeInput','#query','input',url,name='Code'),bundle('SearchButton','#search','button',url,text='Search')]
    scope=bundle('SearchResults','#results','div','https://fixture/other' if mode=='wrong_page' else url,role='table')
    if mode!='undeclared':scope['metadata']['assertion_scope']={'kind':'records','record_role':'row'}
    bs.append(scope)
    if mode=='ambiguous':
        other=bundle('OtherResults','#other','div',url,role='table');other['metadata']['assertion_scope']={'kind':'records','record_role':'row'};bs.append(other)
    case={'name':'Find','steps':[{'action':'Search for "x"','test_data':{'Code':'x'},'expected_result':'Search results contain a matching record.'}]}
    ok,_,missing=_build_script_from_stored_locators(case,bs,url)
    assert not ok and 'missing_observable_record_scope' in case['_compiled_fallback']['step_contracts'][0]['reasons']


def test_declared_autocomplete_is_selected_before_search_submission():
    url='https://fixture/results'
    field=bundle('CodeInput','#query','input',url,name='Code')
    field['metadata']['interaction_contract']={'kind':'autocomplete','option_role':'option'}
    scope=bundle('SearchResults','#results','div',url,role='table');scope['metadata']['assertion_scope']={'kind':'records','record_role':'row'}
    case={'name':'Find','steps':[{'action':'Search for "${CODE}"','test_data':{'Code':'${CODE}'},'expected_result':'Search results contain a matching record.'}]}
    ok,code,missing=_build_script_from_stored_locators(case,[field,scope,bundle('SearchButton','#search','button',url,text='Search')],url)
    assert ok,missing
    assert code.index('select_autocomplete_option(page,')<code.index('click_ready(page,')
