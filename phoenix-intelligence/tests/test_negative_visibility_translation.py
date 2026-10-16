import pytest
from phoenix_shared.automation_translation import assertion_lines
from phoenix_shared.generation_contract import Snapshot, outcome_contract


@pytest.mark.parametrize('expectation', [
    'No heading named "Orders" is visible anywhere on the current page.',
    'The heading "Orders" is not visible.',
    'The "Orders" heading is never displayed.',
])
def test_negative_visibility_retains_absence(expectation):
    lines = assertion_lines(expectation, locator='page.get_by_role("heading", name="Orders", exact=True)')
    assert len(lines) == 1
    assert '.not_to_be_visible(' in lines[0]


def test_negative_word_in_quoted_label_does_not_negate_visibility():
    lines = assertion_lines('The message "No records" is visible.', locator='page.get_by_text("No records", exact=True)')
    assert len(lines) == 1
    assert '.to_be_visible(' in lines[0]
    assert '.not_to_be_visible(' not in lines[0]


@pytest.mark.parametrize('expectation, kind', [
    ('No heading named "Orders" is visible anywhere on the current page.', 'hidden'),
    ('The heading "Orders" is absent anywhere on the current page.', 'absent'),
    ('The heading "No records" is visible anywhere on the current page.', 'visible'),
])
def test_scoped_generation_contract_preserves_predicate_polarity(expectation, kind):
    contract = outcome_contract(expectation, 'Verify the orders region', Snapshot('<body><main></main></body>'), 1)
    assert contract['kind'] == kind
    assert contract['scope'] == "page.locator('body')"
    assert '.get_by_role("heading"' in contract['subject']


def test_absence_cannot_be_generated_without_an_existing_scope():
    assert outcome_contract('No message "Orders" is visible.', 'Verify messages', Snapshot('<section></section>'), 1) is None
