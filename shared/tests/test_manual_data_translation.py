"""Regression coverage for explicit manual Test Data and matching assertions."""
import unittest
from test_automation_translation import load_generator_functions
from phoenix_shared.automation_translation import explicit_step_data


class ManualDataTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_generator_functions()
        self.agent = self.ns['TestGeneratorAgent']()
        self.agent.llm_client = None

    def test_scalar_env_data_is_executable_and_assertion_matches_fill(self):
        script = self.agent._build_fallback_script_from_manual_test({'name': 'Contact', 'steps': [{
            'action': 'Enter the registered email address in the login email field.',
            'test_data': '${CUSTOM_ACCOUNT_EMAIL}',
            'expected_result': 'The email field contains the supplied registered email address.'
        }]}, 'https://custom.example.invalid/')
        self.assertIn("os.environ['CUSTOM_ACCOUNT_EMAIL']", script)
        self.assertNotIn("'registered email address'", script)
        self.assertNotIn('pytest.skip', script)
        compile(script, '<script>', 'exec')

    def test_masking_checks_both_value_and_type(self):
        script = self.agent._build_fallback_script_from_manual_test({'name': 'Secret', 'steps': [{
            'action': 'Enter the registered password in the login password field.',
            'test_data': '${CUSTOM_SECRET}',
            'expected_result': 'The password field contains the supplied value and masks its display.'
        }]}, 'https://custom.example.invalid/')
        self.assertIn("os.environ['CUSTOM_SECRET']", script)
        self.assertIn("to_have_attribute('type', 'password'", script)
        self.assertNotIn('pytest.skip', script)

    def test_literal_empty_and_negative_values_preserved(self):
        action = 'Enter a value in the email field.'
        self.assertEqual(explicit_step_data(action, '""'), "Enter '' in the email field")
        self.assertEqual(explicit_step_data(action, 'wrong-password'), "Enter 'wrong-password' in the email field")
        self.assertEqual(explicit_step_data(action, ''), action)
        self.assertEqual(explicit_step_data(action, '${A}; ${B}'), action)

    def test_navigation_once_and_no_fabricated_click_ids(self):
        script = self.agent._build_fallback_script_from_manual_test({'name': 'Navigate', 'steps': [{
            'action': 'Navigate to the application URL.'
        }]}, 'https://custom.example.invalid/')
        self.assertEqual(script.count('page.goto('), 1)
        target = self.ns['_semantic_locator_expr']('Signup / Login', kind='button')
        self.assertEqual(target, "page.get_by_text('Signup / Login', exact=True)")

    def test_unsupported_expectation_still_reports_review(self):
        script = self.agent._build_fallback_script_from_manual_test({'name': 'State', 'steps': [{
            'action': 'Click Login.', 'expected_result': 'User is successfully logged in'
        }]}, 'https://custom.example.invalid/')
        self.assertIn('pytest.skip', script)
