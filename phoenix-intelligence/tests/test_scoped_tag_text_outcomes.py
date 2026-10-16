import ast
import pytest
from phoenix_shared.generation_contract import Snapshot,outcome_contract
from phoenix_shared.automation_translation import assertion_lines
from services.agents.test_generator import _build_script_from_stored_locators
from phoenix.locators.reconciliation import reconcile_generated_code


def expectation(tag='h3',label='Account Overview',scope='main',quote='`'):
    return f'The central {quote}{tag}{quote} element with text {quote}{label}{quote} is visible within the {quote}{scope}{quote} content area.'


@pytest.mark.parametrize('tag,scope,quote',[('h3','main','`'),('h2','article','"'),('p','section',"'")])
def test_explicit_structure_preserves_tag_text_and_scope_without_current_page_dom(tag,scope,quote):
    spec=outcome_contract(expectation(tag,scope=scope,quote=quote),'Check the content',Snapshot('<body><form>Initial page</form></body>'),1)
    assert spec['scope']==f'page.locator({scope!r})'
    tree=ast.parse(spec['subject'],mode='eval').body
    selector=ast.literal_eval(tree.args[0])
    assert selector==tag+':text-is("Account Overview")'
    assert 'get_by_text' not in spec['subject']
    assert spec['expected_exact_text']=='Account Overview'


@pytest.mark.parametrize('text',[
    expectation(tag='script'),expectation(scope='unknown-container'),
    'The `h3` element with text `Account Overview` is visible within the selected panel.',
])
def test_unknown_structure_does_not_fall_back_to_literal_tag_or_global_text(text):
    assert outcome_contract(text,'Check content',Snapshot('<body>h3</body>'),1) is None
    assert assertion_lines(text)==[]
    case={'name':'Check content','steps':[{'action':'Check the content','expected_result':text}]}
    ok,code,_=_build_script_from_stored_locators(case,[],'https://fixture/start')
    assert not ok
    assert 'get_by_text' not in code
    assert 'unsupported_structured_expected_outcome' in case['_compiled_fallback']['step_contracts'][0]['reasons']


def test_compiler_emits_approved_scoped_contract_instead_of_tag_text():
    case={'name':'Check content','steps':[{'action':'Check the central content','expected_result':expectation()}]}
    ok,code,missing=_build_script_from_stored_locators(case,[],'https://fixture/start')
    assert ok,missing
    assert 'get_by_text' not in code
    contracts=case['_compiled_fallback']['assertion_contracts']
    assert len(contracts)==1 and contracts[0]['scope']=="page.locator('main')"
    # Reconciliation must accept the exact manual-derived contract.
    result=reconcile_generated_code(code,[],assertion_contracts=contracts)
    assert not result[2]


def test_quotes_in_text_are_escaped_as_a_selector_string():
    spec=outcome_contract(expectation(label='Member "A"'),'Check content',Snapshot(''),1)
    selector=ast.literal_eval(ast.parse(spec['subject'],mode='eval').body.args[0])
    assert selector=='h3:text-is("Member \\"A\\"")'
