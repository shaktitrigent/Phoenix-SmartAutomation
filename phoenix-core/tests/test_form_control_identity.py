import copy
from unittest.mock import Mock
import pytest
from phoenix.locators.live_session import identity_matches,valid_form_control_identity,LiveLocatorSession
from phoenix_shared.models.locator import Locator,LocatorBundle,LocatorStrategy


def profile():
    keys=('tag','id','name','type','role','placeholder','aria-label','href','data-testid','data-test','data-cy','label','text')
    def control(**values):return {**dict.fromkeys(keys,''),**values}
    return {'version':1,'source':'validated_live_form_controls',
      'form':dict.fromkeys(('id','name','action','method','role','data-testid','data-test','data-cy'),''),
      'controls':[control(tag='input',name='account',type='text',label='Account'),
                  control(tag='button',text='Continue')],
      'scope_anchor':{'tag':'section','id':'account-section','data-testid':'','data-test':''}}


def evidence():
    return {'tag':'button','text':'Continue','ancestor_context':{'container_tag':'form',
       'container_text':'Account Continue','distinguishing_text':'Account'},'form_control_identity':profile()}


def observed():
    return {'tag':'button','text':'Continue','ancestors':[{'tag':'form','text':'Account Required Continue'}],
            'form_identity':profile()}


def test_validation_text_changes_with_same_complete_form_signature():
    assert identity_matches(observed(),evidence())


@pytest.mark.parametrize('mutation',['label','target','controls','scope','form'])
def test_changed_control_or_form_identity_remains_rejected(mutation):
    actual=observed()
    if mutation=='label':actual['form_identity']['controls'][0]['label']='Other account'
    if mutation=='target':actual['text']='Remove'
    if mutation=='controls':actual['form_identity']['controls'].pop()
    if mutation=='scope':actual['form_identity']['scope_anchor']['id']='other-section'
    if mutation=='form':actual['form_identity']['form']['action']='/different'
    assert not identity_matches(actual,evidence())


def test_historical_text_only_evidence_is_not_silently_upgraded():
    expected=evidence();expected.pop('form_control_identity')
    assert not identity_matches(observed(),expected)


def test_form_profile_cannot_weaken_a_non_form_scope():
    expected=evidence();expected['ancestor_context']['container_tag']='section'
    assert not identity_matches(observed(),expected)


@pytest.mark.parametrize('mutation',['value','empty','anonymous','wrong_version'])
def test_malformed_or_value_bearing_profile_rejected(mutation):
    p=profile()
    if mutation=='value':p['controls'][0]['text']='entered private data'
    if mutation=='empty':p['controls']=[]
    if mutation=='anonymous':p['controls'][0]={**dict.fromkeys(p['controls'][0],''),'tag':'input'}
    if mutation=='wrong_version':p['version']=2
    assert not valid_form_control_identity(p)


def test_two_matching_buttons_still_fail_global_identity_uniqueness(monkeypatch):
    import phoenix.locators.live_session as module
    actual=observed();target=Mock();target.count.return_value=1;target.evaluate.return_value=actual
    nodes=[Mock(),Mock()]
    for node in nodes:node.evaluate.return_value=actual
    anchors=Mock();anchors.count.return_value=2;anchors.all.return_value=nodes
    page=Mock();page.locator.return_value=anchors
    monkeypatch.setattr(module,'locator_on_page',lambda *args:target)
    candidate=Locator(element_name='Continue',strategy=LocatorStrategy.CSS,value='#continue')
    outcome=LiveLocatorSession(page).validate(candidate,{'element_data':evidence()})
    assert outcome['identity_matches'] is False and outcome['identity_count']==2


def test_capture_requires_prior_acceptance_and_revalidates_strengthened_profile(monkeypatch):
    import phoenix.locators.live_session as module
    candidate=Locator(element_name='Continue',strategy=LocatorStrategy.CSS,value='#continue',verified_in_snapshot=True,
       metadata={'stability':'High','match_count':1,'identity_matches':True,'validation_url':'https://fixture/form'})
    expected=evidence();expected.pop('form_control_identity')
    bundle=LocatorBundle(element_name='Continue',page='form',primary=candidate,metadata={'element_data':expected})
    target=Mock();target.evaluate.return_value=observed()
    monkeypatch.setattr(module,'locator_on_page',lambda *args:target)
    session=LiveLocatorSession(Mock());session.validate=Mock(return_value={'match_count':1,'identity_matches':True})
    result=session.capture_form_control_identities([bundle])
    assert result[0].metadata['element_data']['form_control_identity']==profile()
    session.validate.assert_called_once()
    rejected=bundle.model_copy(update={'primary':candidate.model_copy(update={'verified_in_snapshot':False,
       'metadata':{'match_count':1,'identity_matches':False}})})
    assert 'form_control_identity' not in session.capture_form_control_identities([rejected])[0].metadata['element_data']
