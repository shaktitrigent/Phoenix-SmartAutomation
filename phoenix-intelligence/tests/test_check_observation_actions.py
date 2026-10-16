import pytest
from services.agents.test_generator import _build_script_from_stored_locators
from phoenix_shared.manual_semantics import expectation_parts
from test_record_scope_contracts import bundle


@pytest.mark.parametrize('action',['Check the current URL.','Check the URL and login form.','Check the URL and field values.'])
def test_check_observation_does_not_search_for_checkbox(action):
    case={'name':'Verify URL','steps':[{'action':action,'expected_result':'The URL contains `/login`.'}]}
    ok,code,missing=_build_script_from_stored_locators(case,[], 'https://fixture/login')
    assert ok,missing
    assert '.check()' not in code
    assert case['_compiled_fallback']['step_contracts'][0]['action_kind']=='assert'


def test_check_without_executable_outcome_remains_blocked():
    case={'name':'Review','steps':[{'action':'Check the page.','expected_result':'Everything works correctly.'}]}
    ok,_,_=_build_script_from_stored_locators(case,[], 'https://fixture/login')
    assert not ok


def test_explicit_missing_checkbox_remains_blocked():
    case={'name':'Select','steps':[{'action':'Check the Consent checkbox.','expected_result':''}]}
    ok,_,_=_build_script_from_stored_locators(case,[], 'https://fixture/login')
    assert not ok
    assert 'missing_or_ambiguous_checkbox_target' in case['_compiled_fallback']['step_contracts'][0]['reasons']


def test_real_named_checkbox_keeps_selection_action():
    field=bundle('ConsentCheckbox','#consent','input','https://fixture/login',name='Consent',type='checkbox')
    case={'name':'Select','steps':[{'action':'Check Consent','expected_result':'Consent checkbox is checked.'}]}
    _,code,_=_build_script_from_stored_locators(case,[field], 'https://fixture/login')
    assert '.check()' in code


def test_password_masking_pronoun_binds_only_to_explicit_password_subject():
    assert expectation_parts('The Password field contains the supplied value and masks it.')==[
        'The Password field contains the supplied value.','The password is masked.']
    assert 'The password is masked.' not in expectation_parts('The Email field contains the supplied value and masks it.')
