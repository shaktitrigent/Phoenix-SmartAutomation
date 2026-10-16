import pytest
from services.agents.test_generator import _build_script_from_stored_locators
from test_record_scope_contracts import bundle


@pytest.mark.parametrize('suffix',['',' anywhere on the page',' from the current page'])
def test_named_control_page_absence_emits_scoped_zero_count_contract(suffix):
    target=bundle('SubmitButton','#submit','button','https://fixture/login',text='Submit')
    case={'name':'Verify absence','steps':[{'action':'Verify Submit button absence',
        'expected_result':f'The Submit button is absent{suffix}.'}]}
    ok,code,missing=_build_script_from_stored_locators(case,[target],'https://fixture/home')
    assert ok,missing
    contracts=case['_compiled_fallback']['assertion_contracts']
    assert len(contracts)==1
    assert contracts[0]['kind']=='absent'
    assert contracts[0]['scope']=="page.locator('body')"
    assert '#submit' in contracts[0]['subject']
    assert 'target_evidence' not in contracts[0]
    assert 'assert_contract(page,' in code


def test_unknown_container_scope_cannot_be_replaced_with_whole_page():
    target=bundle('SubmitButton','#submit','button','https://fixture/login',text='Submit')
    case={'name':'Verify panel','steps':[{'action':'Verify Submit button absence',
        'expected_result':'The Submit button is absent within the billing panel.'}]}
    ok,_,_=_build_script_from_stored_locators(case,[target],'https://fixture/home')
    assert not ok
