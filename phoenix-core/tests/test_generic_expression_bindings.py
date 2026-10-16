"""A checked operation and its assertion share one physical-target resolution."""
from phoenix.locators.reconciliation import reconcile_generated_code


def bundle():
    return {'page':'profile','element_name':'EmailInput','primary':{'element_name':'EmailInput',
        'strategy':'css','value':'#email','verified_in_snapshot':True,'metadata':{
        'stability':'High','match_count':1,'identity_matches':True}},'alternates':[],'metadata':{}}


EXPRESSION='page.get_by_label("Email").or_(page.get_by_placeholder("Email"))'


def test_action_and_value_assertion_do_not_create_duplicate_prose_targets():
    code='def test_x(page):\n    fill_ready(page, '+EXPRESSION+', "sample", "Email field")\n    # Expected: the email contains the supplied value\n    expect('+EXPRESSION+').to_have_value("sample")\n'
    final,used,missing=reconcile_generated_code(code,[bundle()])
    assert not missing
    assert '.or_(' not in final
    assert final.count("#email")==2


def test_resolution_cache_does_not_authorize_a_different_page_state():
    code='def test_x(page):\n    fill_ready(page, '+EXPRESSION+', "sample", "Email field")\n    page.goto("https://other.test/next")\n    expect('+EXPRESSION+').to_have_value("sample")\n'
    assert reconcile_generated_code(code,[bundle()])[2]


def test_resolution_cache_does_not_leak_between_functions():
    code='def test_x(page):\n    fill_ready(page, '+EXPRESSION+', "sample", "Email field")\ndef test_other(page):\n    expect('+EXPRESSION+').to_have_value("sample")\n'
    assert reconcile_generated_code(code,[bundle()])[2]
