import json
import pytest
from phoenix.locators.smartlocator_integration import validated_locator_bundles


def saved_bundle(name,selector,tag='h1',accepted=True):
    return {'element_name':name,'page':'destination',
            'primary':{'element_name':name,'strategy':'css','value':selector,
                       'verified_in_snapshot':accepted,'metadata':{'match_count':1,'identity_matches':True,'stability':'High'}},
            'alternates':[],'metadata':{'element_data':{'tag':tag,'text':name.removesuffix('Heading')}}}


@pytest.mark.parametrize('label',['Workspace','Inventory'])
def test_assertion_only_heading_is_not_excluded(tmp_path,label):
    (tmp_path/'destination.json').write_text(json.dumps([saved_bundle(label+'Heading','#heading'),saved_bundle('UnrelatedHeading','#other')]))
    case={'name':'Authenticate','steps':[{'action':'Click Submit','expected_result':f'The {label} heading is visible.'}]}
    result=validated_locator_bundles(tmp_path,'manual_tests',[case])
    assert [b.primary.value for b in result]==['#heading']


def test_overall_expected_result_is_part_of_discovery(tmp_path):
    (tmp_path/'destination.json').write_text(json.dumps([saved_bundle('ConfirmationHeading','#confirm')]))
    result=validated_locator_bundles(tmp_path,'manual_tests',[{'name':'Submit','expected_result':'The Confirmation heading is visible.','steps':[]}])
    assert len(result)==1


def test_matching_expected_result_never_accepts_unvalidated_evidence(tmp_path):
    (tmp_path/'destination.json').write_text(json.dumps([saved_bundle('WorkspaceHeading','#bad',accepted=False)]))
    result=validated_locator_bundles(tmp_path,'manual_tests',[{'steps':[{'expected_result':'Workspace heading is visible.'}]}])
    assert result==[]
