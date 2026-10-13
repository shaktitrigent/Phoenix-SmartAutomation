import json
from phoenix.generators.manual_parser import parse_manual_test_file


def test_markdown_can_declare_explicit_record_verification_without_changing_actions(tmp_path):
    evidence={'1':[{'expectation':'no record is created.','kind':'no_new_records','verification_method':'api_record_comparison','lookup':{'url':'https://fixture/api'}}]}
    p=tmp_path/'case.md';p.write_text('# Verification\n\n## Test Steps\n| # | Action | Expected Result | Test Data |\n|---|---|---|---|\n|1|Click Apply|no record is created.||\n\n## Assertion Evidence\n```json\n'+json.dumps(evidence)+'\n```\n')
    case=parse_manual_test_file(p)
    assert case['steps'][0]['action']=='Click Apply'
    assert case['steps'][0]['assertion_evidence']==evidence['1']
