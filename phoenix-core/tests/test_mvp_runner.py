"""The CLI must execute pytest and cannot report success without passing tests."""
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from click.testing import CliRunner
from phoenix.cli.main import main
from phoenix.execution.runner import TestRunner as Runner
from phoenix.locators.diagnostics import redact_diagnostics


def test_runner_launches_pytest_once_with_current_interpreter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'conftest.py').touch()
    test=tmp_path/'tests/test_generated.py'
    test.parent.mkdir()
    test.write_text('def test_generated(): pass',encoding='utf8')
    calls=[]
    def launch(cmd, **kwargs):
        calls.append((cmd,kwargs))
        return subprocess.CompletedProcess(cmd,0,'1 passed in 0.01s','')
    monkeypatch.setattr('phoenix.execution.runner.subprocess.run',launch)
    monkeypatch.setattr('phoenix.execution.runner._preflight_check',lambda:[])
    runner=Runner(test_output_dir=str(test.parent),reports_dir=str(tmp_path/'reports'),logs_dir=str(tmp_path/'logs'))
    result=runner.run_tests([str(test)])
    cmd,options=calls[0]
    assert cmd[:3]==[sys.executable,'-m','pytest']
    assert cmd.count(sys.executable)==1
    assert str(test.relative_to(tmp_path)) in cmd
    assert options['cwd']==str(tmp_path)
    assert result['passed_tests']==1 and result['return_code']==0


@pytest.mark.parametrize('status,total,passed,failed,skipped,return_code,expected_exit', [
    ('passed',1,1,0,0,0,0), ('failed',1,0,1,0,1,1),
    ('failed',0,0,0,0,1,1), ('error',0,0,0,0,4,1),
    ('skipped',0,0,0,0,5,1), ('passed',1,0,0,1,0,1)])
def test_cli_only_succeeds_when_requested_tests_pass(tmp_path,monkeypatch,status,total,passed,failed,skipped,return_code,expected_exit):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'.phoenixrc').write_text('[project]\nname="fixture"\n',encoding='utf8')
    test=tmp_path/'test_generated.py';test.write_text('def test_generated(): pass',encoding='utf8')
    config=SimpleNamespace(project=SimpleNamespace(name='fixture',test_output_dir=str(tmp_path),report_output_dir=str(tmp_path/'reports')))
    client=SimpleNamespace(config=config,get_project=lambda:'fixture')
    monkeypatch.setattr('phoenix.cli.commands.PhoenixClient',lambda **kwargs:client)
    result={'status':status,'total_tests':total,'passed_tests':passed,'failed_tests':failed,
            'skipped_tests':skipped,'return_code':return_code}
    runner=SimpleNamespace(intelligent_runtime=None,run_tests=lambda *args,**kwargs:result)
    monkeypatch.setattr('phoenix.execution.runner.TestRunner',lambda **kwargs:runner)
    response=CliRunner().invoke(main,['run',str(test)])
    assert response.exit_code==expected_exit,response.output
    if expected_exit:
        assert 'All 0 test(s) passed' not in response.output


def test_diagnostics_preserve_target_and_rejection_but_remove_sensitive_values(monkeypatch):
    monkeypatch.setenv('FIXTURE_API_KEY','synthetic-key')
    case={'steps':[{'test_data':'"supplied-secret"'}]}
    details={'element_name':'Access Email','rejected_candidates':[{'value':'synthetic-key supplied-secret',
             'match_count':1,'identity_matches':False,'rejection_reason':'wrong_element_identity'}]}
    safe=redact_diagnostics(details,[case])
    assert safe['element_name']=='Access Email'
    assert safe['rejected_candidates'][0]['value']=='[REDACTED] [REDACTED]'
    assert safe['rejected_candidates'][0]['rejection_reason']=='wrong_element_identity'
    assert details['rejected_candidates'][0]['value']=='synthetic-key supplied-secret'
