import pytest
from phoenix_shared.automation_translation import explicit_step_data,fill_value_expression

@pytest.mark.parametrize('field,value',[('Contact','${CONTACT}'),('Secret','${SECRET}'),('Display Name','Ada; Lovelace'),('Optional','')])
def test_named_binding_does_not_enter_field_label(field,value):
    import json
    supplied=field+': '+json.dumps(value)
    assert explicit_step_data(f'Enter the supplied value in the {field} field.',supplied)==f'Enter {value!r} in the {field} field'


def test_multi_field_cell_binds_only_the_named_target():
    assert explicit_step_data('Enter the value in the Family Name field.','Given Name: Ada; Family Name: Lovelace')=="Enter 'Lovelace' in the Family Name field"


def test_quoted_colon_prefix_is_preserved_as_literal_data():
    assert explicit_step_data('Enter the value in the Contact field.','"Contact: literal"')=="Enter 'Contact: literal' in the Contact field"


def test_runtime_reference_from_named_binding_is_only_environment_value():
    action=explicit_step_data('Enter ${CONTACT} in the Contact field.','Contact: ${CONTACT}')
    assert action=="Enter '${CONTACT}' in the Contact field"
    assert fill_value_expression('${CONTACT}')=="os.environ['CONTACT']"


def test_compiler_uses_named_data_without_label_in_fill_or_value_assertion():
    import ast
    from services.agents.test_generator import _build_script_from_stored_locators
    from test_record_scope_contracts import bundle
    url='https://fixture/results'
    field=bundle('ContactInput','#contact','input',url,name='contact',type='text')
    case={'name':'Fill contact','steps':[{'action':'Enter ${CONTACT} in the Contact field.',
           'test_data':'Contact: ${CONTACT}', 'expected_result':'The Contact field contains the supplied value.'}]}
    ok,code,missing=_build_script_from_stored_locators(case,[field],url)
    assert ok,missing
    ast.parse(code)
    assert "'Contact: '" not in code
    assert "os.environ['CONTACT']" in code
    assert "to_have_value(os.environ['CONTACT']" in code
