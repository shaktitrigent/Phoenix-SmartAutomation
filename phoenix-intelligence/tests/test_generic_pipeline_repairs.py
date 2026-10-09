import json
from unittest.mock import Mock
import pytest
from services.agents.test_generator import TestGeneratorAgent, _derive_expected_result, _missing_fill_data, _normalise_bdd_action, _synthesize_pom_bundle, _criterion_to_playwright_lines_atomic
from phoenix_shared.manual_semantics import bound_actions, final_artifact_issues, unresolved_dependencies
from phoenix_shared.automation_translation import assertion_lines

@pytest.mark.parametrize('prefix', ['Given','When','Then','And','But'])
def test_bdd_grammar(prefix):
    assert _normalise_bdd_action(prefix+' I click Login')=='click Login'
    assert prefix not in _derive_expected_result(prefix+' I click Login')

@pytest.mark.parametrize('action',['When I enter valid username and password','And I enter a password','Enter username and password'])
def test_missing_data(action):
    assert _missing_fill_data(action)
    assert 'NEEDS MANUAL REVIEW' in _derive_expected_result(action)
    assert not any('fill_ready(' in x for x in _criterion_to_playwright_lines_atomic(action,1,'https://example.test'))

def test_explicit_compound_bindings():
    actions=bound_actions('When I enter username and password',json.dumps({'username':'${CUSTOM_USER}','password':'literal and negative'}))
    assert actions==["Enter '${CUSTOM_USER}' in the username field","Enter 'literal and negative' in the password field"]
    assert bound_actions('enter username',{'unrelated':'value'})==[]

def test_explicit_literal():
    assert not _missing_fill_data("When I enter 'bad-password' in the password field")

def test_no_implicit_login():
    agent=TestGeneratorAgent.__new__(TestGeneratorAgent);agent.llm_client=None
    result=agent._generate_manual_tests_fallback('Read news','https://example.test',['Click News'],None)
    assert result[0]['steps'][0]['action']=='Navigate to https://example.test'

def test_pom_dependencies():
    code='from __future__ import annotations\nimport math\nBASE_URL="https://example.test"\ndef helper(x):\n return math.floor(x)\ndef test_x(page):\n    page.goto(BASE_URL)\n    assert helper(2.5)==2\n'
    bundle=_synthesize_pom_bundle(code,'flow','flow')
    page=bundle['page_objects'][0]['code']; test=bundle['tests'][0]['code']
    compile(page,'page','exec');compile(test,'test','exec')
    assert 'BASE_URL=' in page and 'def helper(' in page and 'import math' in page
    assert '_po.navigate()' not in test
    assert not final_artifact_issues({'script_code':code,'pom_bundle':bundle})

def test_undefined_final_names():
    assert unresolved_dependencies('def f(x):\n return len(x)')==[]
    assert final_artifact_issues({'script_code':'def f():\n return MISSING'})

def test_no_invented_arithmetic():
    assert assertion_lines('Total equals price × quantity',locator="page.locator('#total')")==[]
    assert 'to_have_text' in assertion_lines('Quantity should be 2',locator="page.locator('#qty')")[0]

def test_prose_is_not_ui_text():
    assert assertion_lines('Then the product should be added to the cart')==[]
    assert assertion_lines('Then I should be redirected to the Products page')==[]

def test_partial_not_accepted():
    from api.server import _decorate_metadata
    result=_decorate_metadata({'automation_tests':[{'script_code':'pass','generation_quality':{'status':'partial','requires_manual_review':True}}]})
    assert result['metadata']['accepted_count']==0 and result['metadata']['status']=='failed'

@pytest.mark.parametrize('enabled',[True,False])
def test_request_mcp_isolation(monkeypatch,enabled):
    import api.server as server
    from api.models import AutomateRequest
    registry=Mock();registry.automate_from_manual.return_value={'automation_tests':[]}
    monkeypatch.setattr(server,'_agent_registry',registry)
    monkeypatch.setattr('services.mcp.client.MCPClient',Mock(return_value='request-client'))
    original=server._mcp_client;before=vars(server._mcp_settings).copy()
    server.automate_from_manual(AutomateRequest(manual_tests=[],application_url='https://example.test',mcp_config={'enabled':enabled}))
    assert server._mcp_client is original and vars(server._mcp_settings)==before
    assert registry.automate_from_manual.call_args.kwargs['mcp_client']==('request-client' if enabled else None)

def test_compound_password_literal_with_and_stays_literal():
    assert not _missing_fill_data("Enter 'literal and negative' in the password field")

def test_pom_navigation_when_flat_has_none():
    bundle=_synthesize_pom_bundle('def test_x(page):\n    page.get_by_text("Ready").click()','flow','flow')
    assert '_po.navigate()' in bundle['tests'][0]['code']

def test_manual_gate_blocks_wrong_bdd_field():
    from phoenix.generators.manual import ManualTestQualityGate
    gate=ManualTestQualityGate()
    test={'name':'TC-001: Login','description':'A reviewed login flow','steps':[{'action':'Enter a password','expected_result':'"And" field contains a password'}]}
    assert any('scenario keyword' in reason for reason in gate.validate_one(test))

def test_markdown_literal_pipe_is_not_a_column():
    from phoenix.generators.manual_parser import _parse_table_rows
    rows=_parse_table_rows('| # | Action | Expected | Data |\n|---|---|---|---|\n| 1 | Enter text | Field contains value | a\\|b |')
    assert rows[-1][-1]=='a|b' and len(rows[-1])==4

def test_runtime_attempts_have_phase_duration_and_correct_classification():
    from pathlib import Path
    source=(Path(__file__).parents[2]/'phoenix-core/phoenix/execution/runner.py').read_text()
    assert 'navigation_timeout' in source
    assert 'sum(float(test.get(phase' in source

def test_fallback_separates_given_scenarios_and_attaches_outcomes():
    agent=TestGeneratorAgent.__new__(TestGeneratorAgent);agent.llm_client=None
    tests=agent._generate_manual_tests_fallback('Login','https://example.test',[
        'Given I am on the login page','When I click Login','Then I should see "Welcome"',
        'Given I am on the login page','When I enter a password','Then I should see "Error"'],None)
    assert len(tests)==2
    assert tests[0]['preconditions']=='am on the login page'
    assert tests[0]['steps'][-1]['action']=='click Login'
    assert tests[0]['steps'][-1]['expected_result']=='should see "Welcome"'

def test_ast_locator_correction_preserves_env_expression():
    from services.locator_corrector import LocatorCorrector
    corrector=LocatorCorrector('<input name="username"><input name="password">')
    source='fill_ready(page, page.locator("input[name=\'username\']"), os.environ["EXPLICIT"], "Password field")'
    updated,corrections=corrector.apply_corrections_to_fill_operations(source)
    assert 'os.environ["EXPLICIT"]' in updated
    assert "name='password'" in updated
    assert corrections and 'value' not in corrections[0]

def test_no_correction_without_dom_evidence():
    from services.locator_corrector import LocatorCorrector
    original='page.locator("#username")'
    assert LocatorCorrector('')._generate_correction('password',original)==original


def test_incomplete_explicit_mapping_is_rejected():
    assert bound_actions('Enter username and password', {'username':'provided'}) == []

def test_invalid_future_import_is_rejected():
    assert final_artifact_issues({'script_code':'x = 1\nfrom __future__ import annotations'})

def test_failure_screenshot_metadata(tmp_path, monkeypatch):
    from phoenix.execution.reporting_plugin import pytest_json_runtest_metadata
    monkeypatch.chdir(tmp_path)
    page=Mock()
    item=Mock(nodeid='tests/test_flow.py::test_flow',funcargs={'page':page})
    call=Mock(excinfo=ValueError('failure'),when='call')
    result=pytest_json_runtest_metadata(item,call)
    assert result['failure_phase']=='call'
    assert result['screenshot_path'].endswith('failure-call.png')
    page.screenshot.assert_called_once()
    call.excinfo=None
    assert pytest_json_runtest_metadata(item,call)=={}
