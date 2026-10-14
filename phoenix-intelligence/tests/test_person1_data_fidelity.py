import pytest

from phoenix_shared.manual_semantics import data_bindings, expectation_parts
from phoenix_shared.generation_contract import summary_binding


def test_punctuation_inside_ui_label_does_not_split_its_assertion():
    text = 'The "Saved. Next; Continue" heading is visible. The "Close" button is visible.'
    assert expectation_parts(text) == [
        'The "Saved. Next; Continue" heading is visible.',
        'The "Close" button is visible.',
    ]


def test_quoted_data_delimiters_and_apostrophes_are_preserved():
    assert data_bindings('Display Name: "Ada; Lovelace"; Family Name: O\'Brien') == {
        'Display Name': 'Ada; Lovelace', 'Family Name': "O'Brien",
    }


def test_quoted_empty_word_is_literal_and_empty_marker_is_blank():
    assert data_bindings('Status: "empty"; Optional Name: empty') == {
        'Status': 'empty', 'Optional Name': '',
    }


def test_escaped_quote_and_semicolon_remain_in_the_supplied_value():
    assert data_bindings(r'Label: "Say \"Hello; friend\""; Code: x') == {
        'Label': 'Say "Hello; friend"', 'Code': 'x',
    }


def creation_proof(saved_values, found_values):
    records = [{'step': 1, 'status': 'translated', 'url_asserted': True,
                'action_kind': 'click', 'action_text': 'Click Apply'},
               {'step': 2, 'status': 'translated', 'action_kind': 'search'}]
    contracts = [{'step': 1, 'kind': 'data_visible', 'expected_values': saved_values},
                 {'step': 2, 'kind': 'record_present', 'expected_values': found_values,
                  'target_evidence': {'identity': 'validated'},
                  'expected_text': 'Search results contain the matching account record.'}]
    return contracts, records


@pytest.mark.parametrize('saved,found', [
    (['${NAME}'], ['${NAME}_other']),
    (['${GIVEN}', '${FAMILY}'], ['${FAMILY}', '${GIVEN}']),
    (['${NAME}', '${NAME}'], ['${NAME}']),
])
def test_same_environment_names_do_not_prove_same_record(saved, found):
    contracts, records = creation_proof(saved, found)
    assert summary_binding('creates an account', contracts, records) is None


@pytest.mark.parametrize('values', [['Ada', 'Lovelace'], ['${GIVEN}', '${FAMILY}']])
def test_matching_literal_or_symbolic_data_proves_creation(values):
    contracts, records = creation_proof(values, [' '.join(values)])
    assert summary_binding('creates an account', contracts, records)


@pytest.mark.parametrize('values', ['Ada', [' '], [42], {'Name': 'Ada'}])
def test_malformed_record_data_is_blocked_before_emitting_contract(values):
    from services.agents.test_generator import _build_script_from_stored_locators
    from test_record_scope_contracts import bundle
    url = 'https://accounts.fixture/results'
    scope = bundle('Results', '#results', 'div', url, role='table')
    expectation = 'Search results contain a matching record.'
    case = {'name': 'Verify record', 'steps': [{
        'action': 'Verify the record', 'expected_result': expectation,
        'assertion_evidence': [{'expectation': expectation, 'kind': 'record_present',
            'verification_method': 'follow_up_search', 'scope_target': 'Results',
            'record_role': 'row', 'expected_values': values}],
    }]}
    ok, _, _ = _build_script_from_stored_locators(case, [scope], url)
    assert not ok
    compiled = case['_compiled_fallback']
    assert 'invalid_observable_assertion_evidence' in compiled['step_contracts'][0]['reasons']
    assert not any(c['kind'] == 'record_present' for c in compiled['assertion_contracts'])
