from phoenix_shared.generation_contract import summary_binding
from phoenix_shared.manual_semantics import expectation_parts


def test_business_creation_summary_cannot_bind_to_url_or_message_alone():
    records=[{'step':1,'status':'translated','url_asserted':True}]
    contracts=[{'step':1,'kind':'visible','expected_text':'Saved','action_text':'Click Apply'}]
    assert summary_binding('creates an account',contracts,records) is None


def test_non_creation_summary_requires_record_comparison_and_field_validation():
    text='The form blocks submission when required fields are empty.'
    records=[{'step':1,'status':'translated'}]
    messages={'step':1,'kind':'field_messages','expected_text':'Required','action_text':'Click Apply'}
    assert summary_binding(text,[messages],records) is None
    assert summary_binding(text,[messages,{'step':1,'kind':'no_new_records'}],records)
    records[0]['status']='partial'
    assert summary_binding(text,[messages,{'step':1,'kind':'no_new_records'}],records) is None


def test_shared_named_input_conditions_are_not_dropped_or_split():
    text='A record is successfully created and searchable when Given Name and Family Name are supplied and Other Name is omitted.'
    assert expectation_parts(text)==[text]
