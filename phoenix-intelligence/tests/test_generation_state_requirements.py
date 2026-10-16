from copy import deepcopy
import pytest
from services.agents.state_plan import capture_requirement,matches_context,public_route


def evidence(url='https://accounts.fixture/overview'):
    return {'element_name':'AccountMenu','primary':{'strategy':'css','value':'#account',
        'metadata':{'validation_url':url}},'metadata':{}}


def test_wrong_page_creates_explicit_requirement_without_approving_evidence():
    original=evidence();before=deepcopy(original)
    requirement=capture_requirement(original,step=5,page_context='/records/list',prerequisite_steps=[1,2,3,4])
    assert requirement['required_page_context']=='/records/list'
    assert requirement['prerequisite_steps']==[1,2,3,4]
    assert requirement['requires_live_validation']
    assert requirement['capture_status']=='pending_runtime_resolution'
    assert original==before


@pytest.mark.parametrize('context',['/overview','https://accounts.fixture/overview'])
def test_current_page_observation_needs_no_recapture(context):
    assert capture_requirement(evidence(),step=1,page_context=context,prerequisite_steps=[]) is None


def test_all_state_observations_are_considered():
    bundle=evidence()
    bundle['metadata']['state_evidence']=[evidence(),evidence('https://accounts.fixture/records/list')]
    assert capture_requirement(bundle,step=5,page_context='/records/list',prerequisite_steps=[]) is None


@pytest.mark.parametrize('url,context',[
    ('https://accounts.fixture/records/listing','/records/list'),
    ('https://other.fixture/overview','https://accounts.fixture/overview'),
    ('https://accounts.fixture/profile?next=/records/list','/records/list'),
])
def test_other_host_path_prefix_or_query_does_not_prove_state(url,context):
    assert not matches_context(url,context)


def test_partial_manual_route_can_describe_nested_page():
    assert matches_context('https://accounts.fixture/record/details/42','/record/details/')


def test_requirement_omits_query_fragment_and_credentials():
    value=public_route('https://member:secret@accounts.fixture/overview?token=private#secret')
    assert value=='https://accounts.fixture/overview'


def test_unknown_provenance_requests_capture():
    requirement=capture_requirement(evidence(None),step=1,page_context='/records',prerequisite_steps=[])
    assert requirement['captured_page_urls']==[]


def test_foreign_origin_cannot_satisfy_relative_context():
    requirement=capture_requirement(evidence('https://other.fixture/records'),step=2,
        page_context='/records',prerequisite_steps=[1],application_url='https://accounts.fixture/start')
    assert requirement is not None


def test_untranslated_prerequisites_remain_explicitly_blocked():
    requirement=capture_requirement(evidence(),step=4,page_context='/records',
        prerequisite_steps=[1,2,3],blocked_prerequisite_steps=[2])
    assert requirement['prerequisite_steps']==[1,2,3]
    assert requirement['blocked_prerequisite_steps']==[2]


def test_preceding_actions_in_compound_step_are_referenced_without_data():
    requirement=capture_requirement(evidence(),step=4,page_context='/records',
        prerequisite_steps=[1,2,3],action_index=3)
    assert requirement['action_index']==3
    assert requirement['preceding_action_indexes']==[1,2]


def test_compiler_requests_current_state_for_shared_menu_after_navigation():
    from services.agents.test_generator import _build_script_from_stored_locators
    from test_record_scope_contracts import bundle
    url='https://accounts.fixture/overview'
    menu=bundle('AccountMenu','#account','button',url,text='Account Menu')
    case={'name':'Open account menu after navigation','steps':[
        {'action':'Navigate to https://accounts.fixture/records/list','expected_result':'The URL contains `/records/list`.'},
        {'action':'Click Account Menu','expected_result':'The URL contains `/records/list`.'},
    ]}
    _build_script_from_stored_locators(case,[menu],url)
    compiled=case['_compiled_fallback']
    requirement=next(r for r in compiled['state_requirements'] if r['element_name']=='AccountMenu')
    assert requirement['step']==2
    assert requirement['required_page_context']=='/records/list'
    assert requirement['prerequisite_steps']==[1]
    assert 'validate_target(' in compiled['script_code']


def test_agent_exposes_capture_requirements_to_runtime_consumer():
    from unittest.mock import Mock
    from services.agents.test_generator import TestGeneratorAgent
    from services.knowledge.base import KnowledgeBase
    from services.cache import Cache
    from test_record_scope_contracts import bundle
    url='https://accounts.fixture/overview'
    menu=bundle('AccountMenu','#account','button',url,text='Account Menu')
    case={'name':'Account menu workflow','steps':[
        {'action':'Navigate to https://accounts.fixture/records/list','expected_result':'The URL contains `/records/list`.'},
        {'action':'Click Account Menu','expected_result':'The URL contains `/records/list`.'},
    ]}
    agent=TestGeneratorAgent(KnowledgeBase(),Cache(),llm_client=Mock())
    result=agent.automate_from_manual_tests([case],application_url=url,locator_bundles=[menu],dom_snapshot='',use_pom=False)
    generated=result['automation_tests'][0]
    assert generated['state_requirements'][0]['required_page_context']=='/records/list'
    assert any('Current-page locator capture required' in w for w in generated['warnings'])
    assert 'validate_target(' in generated['script_code']
