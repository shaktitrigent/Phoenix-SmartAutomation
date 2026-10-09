from copy import deepcopy

from phoenix_shared.state_evidence import group_state_evidence
from phoenix_shared.locator_utils import normalize_locator_bundles, _are_locator_bundles_sufficient
from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy
from phoenix_shared.automation_translation import step_coverage


def test_normalization_retains_candidate_metadata_alternates_and_state():
    candidate = Locator(element_name='Contact', strategy=LocatorStrategy.CSS, value='#contact',
        verified_in_snapshot=True, metadata={'stability':'High','match_count':1,'identity_matches':True,
            'state_name':'rejected','validation_url':'https://fixture.test/access'})
    bundle = LocatorBundle(element_name='Contact',page='rejected',primary=candidate,alternates=[candidate],
        metadata={'element_data':{'tag':'input','id':'contact'},'state_evidence':[{'page':'entry'}]})
    assert normalize_locator_bundles([bundle]) == [bundle.model_dump(mode='json')]


def test_snapshot_flag_alone_cannot_disable_mcp():
    bundle={'element_name':'ContactInput','primary':{'strategy':'css','value':'#contact','verified_in_snapshot':True}}
    assert not _are_locator_bundles_sufficient({'steps':[{'action':'Fill Contact with sample'}]},[bundle])[0]


def test_same_native_name_in_textually_distinct_forms_is_not_collapsed():
    base={'element_name':'ContactInput','primary':{'strategy':'css','value':'#first','verified_in_snapshot':True,
        'metadata':{'stability':'High','match_count':1,'identity_matches':True}},
        'metadata':{'element_data':{'tag':'input','name':'contact','ancestor_context':{'container_text':'Shipping'}}}}
    other=deepcopy(base);other['primary']['value']='#second'
    other['metadata']['element_data']['ancestor_context']['container_text']='Billing'
    assert len(group_state_evidence([base,other])) == 2


def test_pom_step_coverage_preserves_unreachable_operation_rejection():
    code='''class AccessPage:
    def tc_001_access(self):
        pytest.skip("unresolved")
        self._page.locator("#contact").fill("sample")
'''
    coverage=step_coverage(code,[{'action':'Fill Contact with sample'}])
    assert coverage['implemented_steps']==0
    assert coverage['first_blocking_line'] == 3
    assert coverage['unreachable_operations'] == 1
