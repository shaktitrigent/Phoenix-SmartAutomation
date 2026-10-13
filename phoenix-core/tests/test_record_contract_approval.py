import pytest
from phoenix.locators.reconciliation import reconcile_generated_code

LOOKUP={'url':'https://fixture/api/records','records_path':['data'],'total_path':['meta','total'],'identity_paths':[['id']],
        'page_size':50,'offset_parameter':'offset','limit_parameter':'limit'}
SPEC={'version':1,'kind':'no_new_records','lookup':LOOKUP,'baseline_binding':'_baseline'}
B={'element_name':'Submit','primary':{'strategy':'css','value':'#submit','verified_in_snapshot':True,
  'metadata':{'stability':'High','match_count':1,'identity_matches':True}},'metadata':{'element_data':{'tag':'button','id':'submit'}}}


def code(context=False):
    slot="context['_baseline']" if context else '_baseline'
    return 'from phoenix_shared.assertion_runtime import assert_contract\nfrom phoenix_shared.record_verification import read_record_identities\ndef test_invalid(page, context):\n '+slot+' = read_record_identities(page, '+repr(LOOKUP)+')\n page.locator("#submit").click()\n assert_contract(page, '+repr(SPEC)+', record_baseline='+slot+')\n'


@pytest.mark.parametrize('context',[False,True])
def test_approved_comparison_supports_flat_and_pom_baseline_bindings(context):
    _,_,missing=reconcile_generated_code(code(context),[B],assertion_contracts=[SPEC])
    assert missing==[]


@pytest.mark.parametrize('mutation',[
    lambda s:s.replace('from phoenix_shared.record_verification import read_record_identities\n',''),
    lambda s:s.replace('read_record_identities(page, '+repr(LOOKUP)+')','frozenset()'),
    lambda s:s.replace(' assert_contract(', ' _baseline = frozenset()\n assert_contract('),
    lambda s:s.replace(' page.locator("#submit").click()\n',''),
    lambda s:s.replace("'url': 'https://fixture/api/records'", "'url': 'https://fixture/api/other'",1),
])
def test_unproven_or_changed_baseline_is_rejected(mutation):
    _,_,missing=reconcile_generated_code(mutation(code()),[B],assertion_contracts=[SPEC])
    assert 'unapproved assertion contract' in missing


def test_context_mutation_cannot_forge_the_baseline():
    source=code(True).replace(' assert_contract(', " context.update({'_baseline': frozenset()})\n assert_contract(")
    _,_,missing=reconcile_generated_code(source,[B],assertion_contracts=[SPEC])
    assert 'unapproved assertion contract' in missing


def test_unlisted_contract_is_still_rejected():
    _,_,missing=reconcile_generated_code(code(),[B],assertion_contracts=[])
    assert 'unapproved assertion contract' in missing


def test_a_conditional_or_unused_baseline_is_not_proven_to_execute():
    source=code().replace(' _baseline =', ' if False:\n  _baseline =')
    _,_,missing=reconcile_generated_code(source,[B],assertion_contracts=[SPEC])
    assert 'unapproved assertion contract' in missing
