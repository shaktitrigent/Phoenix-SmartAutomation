import copy
import pytest
from phoenix_shared.manual_semantics import expectation_parts
from phoenix_shared.generation_contract import summary_binding

VALIDATION='The form displays required-field validation when Given Name and Family Name are empty.'
CREATION='A record is successfully created and searchable when Given Name and Family Name are supplied, Other Name is omitted, and an Account Code is entered.'


def proof():
    records=[
        {'step':1,'status':'translated','input_values':{'Given Name':'','Family Name':''}},
        {'step':2,'status':'translated','input_values':{'Given Name':'${GIVEN}','Family Name':'${FAMILY}','Other Name':''}},
        {'step':3,'status':'translated','input_values':{'Account Code':'${CODE}'}},
        {'step':4,'status':'translated','url_asserted':True,'action_kind':'click','action_text':'Click Apply'},
        {'step':5,'status':'translated','action_kind':'search'},
    ]
    contracts=[
        {'step':1,'kind':'field_messages','expected_text':'2 "Required" validation messages are visible for Given Name, Family Name.',
         'field_subjects':['given','family'],'expected_count':2,'require_visible':True,'proof_scope':'independent_field_groups'},
        {'step':4,'kind':'data_visible','expected_values':['${GIVEN}','${FAMILY}']},
        {'step':5,'kind':'record_present','expected_values':['${GIVEN} ${FAMILY}'],'target_evidence':{'identity':'validated'},
         'expected_text':'Search results contain a matching account record.'},
    ]
    return contracts,records


def test_field_lists_and_all_creation_conditions_stay_intact():
    assert expectation_parts(VALIDATION+' '+CREATION)==[VALIDATION,CREATION]


def test_validation_binds_only_its_empty_inputs_and_independent_field_messages():
    contracts,records=proof()
    binding=summary_binding(VALIDATION,contracts,records)
    assert binding['steps']==[1]
    assert binding['proof_scope']=='observable_field_validation'


@pytest.mark.parametrize('change',['nonempty','wrong_field','duplicate_subject','partial','wrong_count','global_message'])
def test_missing_validation_proof_stays_blocked(change):
    contracts,records=proof()
    if change=='nonempty':records[0]['input_values']['Given Name']='present'
    if change=='wrong_field':contracts[0]['expected_text']='2 "Required" validation messages are visible for Given Name, Access Code.'
    if change=='duplicate_subject':contracts[0]['field_subjects']=['given','given']
    if change=='partial':records[0]['status']='partial'
    if change=='wrong_count':contracts[0]['expected_count']=1
    if change=='global_message':contracts[0]['proof_scope']='global'
    assert summary_binding(VALIDATION,contracts,records) is None


def test_conditional_creation_includes_inputs_and_both_record_proofs():
    contracts,records=proof()
    assert summary_binding(CREATION,contracts,records)['steps']==[2,3,4,5]


@pytest.mark.parametrize('change',['missing_code','nonempty_optional','wrong_record','late_input','partial','unused_claim'])
def test_creation_cannot_drop_any_condition(change):
    contracts,records=proof();text=CREATION
    if change=='missing_code':records[2]['input_values']={}
    if change=='nonempty_optional':records[1]['input_values']['Other Name']='unexpected'
    if change=='wrong_record':contracts[2]['expected_values']=['${OTHER}']
    if change=='late_input':records[2]['step']=6
    if change=='partial':records[2]['status']='partial'
    if change=='unused_claim':text=text.replace('an Account Code','an unused Account Code')
    assert summary_binding(text,contracts,records) is None


def test_non_creation_is_not_proved_by_validation_messages():
    contracts,records=proof()
    assert summary_binding('The form blocks submission when required fields are empty.',contracts,records) is None


def test_old_conditional_creation_wording_still_binds():
    contracts,records=proof()
    text='A record is successfully created and searchable when Given Name and Family Name are supplied and Other Name is omitted.'
    assert summary_binding(text,contracts,records)


def test_complete_generic_compiler_binds_summary_without_skipping_checks():
    from services.agents.test_generator import _build_script_from_stored_locators
    from test_record_scope_contracts import bundle
    url='https://accounts.fixture/form'
    fields=[bundle(label+'Input','#'+key,'input',url,name=label)
            for label,key in [('Given Name','given'),('Family Name','family'),('Other Name','other'),('Account Code','code')]]
    scope=bundle('SearchResults','#results','div',url,role='table')
    scope['metadata']['assertion_scope']={'kind':'records','record_role':'row'}
    bundles=fields+[bundle('ApplyButton','#apply','button',url,text='Apply'),
                    bundle('SearchButton','#search','button',url,text='Search'),scope]
    case={'name':'Account creation','steps':[
        {'action':'Clear Given Name and Family Name fields; click Apply',
         'test_data':{'Given Name':'','Family Name':''},
         'expected_result':'"Required" validation is shown for Given Name and Family Name.'},
        {'action':'Enter "${GIVEN}" in Given Name and "${FAMILY}" in Family Name; clear Other Name field',
         'test_data':{'Given Name':'${GIVEN}','Family Name':'${FAMILY}','Other Name':''},
         'expected_result':'Given Name and Family Name show the supplied values. The Other Name field is empty.'},
        {'action':'Enter "${CODE}" in Account Code','test_data':{'Account Code':'${CODE}'},
         'expected_result':'Account Code contains the supplied value.'},
        {'action':'Click Apply','expected_result':'The URL contains `/form`; the saved account name is visible.'},
        {'action':'Search for "${GIVEN} ${FAMILY}"','test_data':{'Given Name':'${GIVEN} ${FAMILY}'},
         'expected_result':'Search results contain a matching account record.'},
    ],'expected_result':VALIDATION+' '+CREATION}
    ok,code,missing=_build_script_from_stored_locators(case,bundles,url)
    assert ok, (missing,case.get('_compiled_fallback'))
    compiled=case['_compiled_fallback']
    assert not compiled['overall_outcome_unresolved']
    assert len(compiled['overall_bindings'])==2
    assert {c['kind'] for c in compiled['assertion_contracts']} >= {'field_messages','data_visible','record_present'}
    assert 'pytest.skip' not in code
