"""Dependency-free regressions: python -m unittest discover -s shared/tests -v."""
import ast
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'shared'))
from phoenix_shared.automation_translation import (
    environment_reference, fill_value_expression, select_page_fixture,
    assertion_lines, step_coverage, resolve_script_environment_values,
)


def load_generator_functions():
    """Run the production translator without optional LLM/MCP dependencies.

    Only service imports/initialization are excluded. All translator functions
    and the actual agent methods are compiled unchanged from the source.
    """
    import enum, json, logging, re, textwrap, time, typing
    p = ROOT / 'phoenix-intelligence/services/agents/test_generator.py'
    tree = ast.parse(p.read_text(encoding="utf-8"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in {'phoenix_shared.automation_translation', 'phoenix_shared.manual_semantics'}:
            nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(n, ast.Name) and n.id == '_prompt_loader' for n in node.targets):
                continue
            nodes.append(node)
    ns = dict(vars(typing))
    ns.update(ast=ast, json=json, logging=logging, re=re, textwrap=textwrap,
              time=time, Path=Path, Enum=enum.Enum, BaseAgent=object,
              logger=logging.getLogger('regression'), assertion_lines=assertion_lines,
              fill_value_expression=fill_value_expression, step_coverage=step_coverage,
              resolve_script_environment_values=resolve_script_environment_values)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(p), 'exec'), ns)
    return ns


class FixtureTests(unittest.TestCase):
    def test_rewritten_test_executes_with_same_page_object(self):
        code = 'def test_cart(other, page: Page):\n    """Cart"""\n    page.goto("/cart")\n'
        final = select_page_fixture(code, 'authenticated_page')
        obj = Mock(); ns = {'Page': object}
        exec(final, ns); ns['test_cart'](None, obj)
        obj.goto.assert_called_once_with('/cart')
        self.assertEqual(final, select_page_fixture(final, 'authenticated_page'))

    def test_reverse_fixture_and_inline_suite(self):
        source = 'def test_login(authenticated_page: Page): authenticated_page.goto("/session")\n'
        final = select_page_fixture(source, 'page')
        ns = {'Page': object}; exec(final, ns); obj = Mock(); ns['test_login'](obj)
        obj.goto.assert_called_once_with('/session')

    def test_annotations_are_optional_and_keyword_fixtures_supported(self):
        for source in ['def test_x(page):\n    page.click("x")\n',
                       'def test_x(extra, *, page):\n    page.click("x")\n']:
            result = select_page_fixture(source, 'authenticated_page')
            self.assertIn('page = authenticated_page', result)
            compile(result, '<test>', 'exec')

    def test_comments_and_other_scopes_preserved(self):
        source = '# café\ndef helper(page):\n    return "page"\ndef test_x(page: Page):\n    page.click("page")\n'
        result = select_page_fixture(source, 'authenticated_page')
        self.assertIn('# café', result)
        self.assertIn('def helper(page)', result)
        self.assertIn('page.click("page")', result)


class DataTests(unittest.TestCase):
    def test_explicit_custom_variables(self):
        for text in ['$ACCOUNT_EMAIL', '${ACCOUNT_EMAIL}', 'the value from `ACCOUNT_EMAIL`',
                     'environment variable ACCOUNT_EMAIL', 'os.environ["ACCOUNT_EMAIL"]']:
            self.assertEqual(environment_reference(text), 'ACCOUNT_EMAIL')

    def test_no_credential_defaults_or_arbitrary_code(self):
        for text in ['', 'wrong_password', 'valid credentials', 'from environment',
                     'os.environ.get("X")', 'os.environ["X"]; dangerous()']:
            self.assertEqual(fill_value_expression(text), repr(text))

    def test_literal_negative_inputs_unchanged(self):
        script = 'from __future__ import annotations\ndef test_x(page):\n    page.get_by_label("Email").fill("${ACCOUNT_EMAIL}")\n    page.get_by_label("Password").fill("")\n    page.get_by_label("Password").fill("wrong_password")\n'
        result = resolve_script_environment_values(script)
        self.assertIn("os.environ['ACCOUNT_EMAIL']", result)
        ns = {}; exec(result, ns)
        page = Mock()
        with unittest.mock.patch.dict(os.environ, {'ACCOUNT_EMAIL': 'configured@example.invalid'}):
            ns['test_x'](page)
        calls = page.get_by_label.return_value.fill.call_args_list
        self.assertEqual([c.args[0] for c in calls], ['configured@example.invalid', '', 'wrong_password'])


class AssertionTests(unittest.TestCase):
    def test_no_invented_route_or_text(self):
        for text in ['User is redirected to Dashboard', 'login was successful', 'invalid-credentials message']:
            self.assertEqual(assertion_lines(text), [])

    def test_explicit_negative_url(self):
        lines = assertion_lines('URL no longer contains `/session`')
        self.assertIn('not_to_have_url', lines[0])
        self.assertIn('/session', lines[0])

    def test_field_value_is_not_visible_text(self):
        lines = assertion_lines('Email field contains the value `${ACCOUNT_EMAIL}`', locator='page.get_by_label("Email")')
        self.assertIn('to_have_value', lines[0])
        self.assertIn("os.environ['ACCOUNT_EMAIL']", lines[0])

    def test_explicit_error_text(self):
        lines = assertion_lines('The message "Access denied" is visible')
        self.assertIn("get_by_text('Access denied', exact=True)", lines[0])

    def test_negative_visibility_and_checkbox(self):
        self.assertIn('not_to_be_visible', assertion_lines('The text "Signed in" is not visible')[0])
        self.assertIn('not_to_be_checked', assertion_lines('Checkbox is unchecked', locator='page.get_by_label("Consent")')[0])

    def test_compound_expected_result_is_not_partially_verified(self):
        self.assertEqual(assertion_lines('URL contains `/session` and "Signed in" is visible'), [])


class CoverageTests(unittest.TestCase):
    def test_comments_and_generic_body_do_not_count(self):
        script = 'def test_x(page):\n    # Click Login button\n    # Verify dashboard heading\n    expect(page.locator("body")).to_be_visible()\n'
        self.assertEqual(step_coverage(script, [{'action': 'Click Login button'}, {'action': 'Verify dashboard heading'}])['implemented_steps'], 0)

    def test_operations_consumed_once(self):
        script = 'def test_x(page):\n    page.get_by_role("button", name="Save").click()\n'
        self.assertEqual(step_coverage(script, [{'action': 'Click Save'}, {'action': 'Click Save'}])['implemented_steps'], 1)

    def test_unrelated_fill_does_not_count(self):
        script = 'def test_x(page):\n    page.get_by_label("Search").fill("query")\n'
        self.assertEqual(step_coverage(script, [{'action': 'Enter password'}])['implemented_steps'], 0)

    def test_helper_definition_does_not_count(self):
        script = 'def helper(page):\n    page.get_by_text("Save").click()\ndef test_x(page):\n    pass\n'
        self.assertEqual(step_coverage(script, [{'action': 'Click Save'}])['implemented_steps'], 0)

    def test_skip_prevents_later_steps_from_counting(self):
        script = 'def test_x(page):\n    pytest.skip("Missing evidence")\n    page.get_by_text("Save").click()\n'
        self.assertEqual(step_coverage(script, [{'action': 'Click Save'}])['implemented_steps'], 0)


class GeneratorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = load_generator_functions()

    def test_empty_input_and_custom_reference_translation(self):
        extract = self.ns['_extract_fill_target_and_value']
        field, value = extract("Enter email ''")
        self.assertEqual(value, '')
        field, value = extract('Enter the value from `${ACCOUNT_EMAIL}` in the email field')
        self.assertEqual(field, 'Email')
        self.assertEqual(environment_reference(value), 'ACCOUNT_EMAIL')

    def test_generic_fallback_and_pom_have_correct_values(self):
        agent = self.ns['TestGeneratorAgent']()
        agent.llm_client = None
        manual = {'name': 'Enter contact email', 'steps': [
            {'step_number': 1, 'action': 'Enter `${ACCOUNT_EMAIL}` in the email field',
             'expected_result': 'Email field contains the value `${ACCOUNT_EMAIL}`'},
            {'step_number': 2, 'action': 'Verify the message', 'expected_result': 'The message "Ready" is visible'},
        ]}
        script = agent._build_fallback_script_from_manual_test(manual, 'https://arbitrary.example.invalid/contact')
        script = self.ns['_normalise_generated_script'](script)
        self.assertNotIn('pytest.skip', script)
        self.assertIn("os.environ['ACCOUNT_EMAIL']", script)
        self.assertIn('to_have_value', script)
        compile(script, '<fallback>', 'exec')
        bundle = self.ns['_synthesize_pom_bundle'](script, 'contact', 'contact', human_name='Enter contact email')
        for section in ('tests', 'page_objects'):
            for node in bundle[section]:
                compile(node['code'], '<pom>', 'exec')
        self.assertIn('def test_contact(page:', bundle['tests'][0]['code'])

    def test_unsupported_authentication_assertion_skips(self):
        agent = self.ns['TestGeneratorAgent'](); agent.llm_client = None
        manual = {'name': 'Verify authentication', 'steps': [{'action': 'Verify login was successful', 'expected_result': 'User is authenticated'}]}
        script = agent._build_fallback_script_from_manual_test(manual, 'https://arbitrary.example.invalid')
        self.assertIn('pytest.skip', script)
        self.assertNotIn('get_by_text("login was successful"', script)

    def test_pom_login_preconditions_do_not_force_auth_fixture(self):
        script = 'def test_invalid_login(page: Page):\n    page.get_by_label("Password").fill("wrong_password")\n'
        bundle = self.ns['_synthesize_pom_bundle'](script, 'session', 'invalid_login',
            preconditions='User is already logged in', human_name='Login with invalid credentials')
        self.assertIn('def test_invalid_login(page:', bundle['tests'][0]['code'])

    def test_login_without_explicit_data_does_not_assume_env_names(self):
        lines = self.ns['_criterion_to_playwright_lines']('Login using valid credentials', 1, 'https://example.invalid')
        self.assertNotIn('TEST_USERNAME', '\n'.join(lines))
        self.assertIn('review required', '\n'.join(lines))

    def test_full_flat_and_pom_generation_reports_quality(self):
        for use_pom in (False, True):
            agent = self.ns['TestGeneratorAgent']()
            agent.llm_client = None
            agent.mcp_client = None
            agent.get_knowledge_context = lambda **kwargs: ''
            manual = {'name': 'Fill contact email', 'steps': [
                {'step_number': 1, 'action': 'Enter `${ACCOUNT_EMAIL}` in the email field',
                 'expected_result': 'Email field contains the value `${ACCOUNT_EMAIL}`'}]}
            result = agent.automate_from_manual_tests([manual], 'https://custom.example.invalid/contact', use_pom=use_pom)
            generated = result['automation_tests'][0]
            self.assertEqual(generated['generation_quality']['implemented_steps'], 1)
            self.assertIn("os.environ['ACCOUNT_EMAIL']", generated['script_code'])
            if use_pom:
                page_code = generated['pom_bundle']['page_objects'][0]['code']
                self.assertIn('https://custom.example.invalid/contact', page_code)
                self.assertNotIn('_po.navigate()', generated['pom_bundle']['tests'][0]['code'])

    def test_pom_unsupported_step_imports_pytest(self):
        agent = self.ns['TestGeneratorAgent'](); agent.llm_client = None
        script = agent._build_fallback_script_from_manual_test(
            {'name': 'Unsupported', 'steps': [{'action': 'Verify authenticated state'}]}, 'https://example.invalid')
        script = self.ns['_normalise_generated_script'](script)
        bundle = self.ns['_synthesize_pom_bundle'](script, 'sample', 'sample')
        self.assertIn('import pytest', bundle['page_objects'][0]['code'])

    def test_pom_does_not_rewrite_literal_page_text(self):
        script = 'def test_x(page: Page):\n    page.get_by_text("Contact page").click()\n'
        bundle = self.ns['_synthesize_pom_bundle'](script, 'contact', 'contact')
        code = bundle['page_objects'][0]['code']
        self.assertIn('self._page.get_by_text("Contact page")', code)

    def test_partial_generation_emits_warning(self):
        agent = self.ns['TestGeneratorAgent'](); agent.llm_client = None; agent.mcp_client = None
        agent.get_knowledge_context = lambda **kwargs: ''
        manual = {'name': 'Verify state', 'steps': [{'action': 'Verify authenticated state'}]}
        result = agent.automate_from_manual_tests([manual], 'https://example.invalid', use_pom=True)
        self.assertEqual(result['metadata']['translation_status'], 'partial')
        self.assertTrue(result['automation_tests'][0]['warnings'])

    def test_production_core_fixture_wrapper(self):
        p = ROOT / 'phoenix-core/phoenix/generators/automation.py'
        t = ast.parse(p.read_text(encoding="utf-8"))
        wanted = {'_NEGATION_AUTH_PATTERNS', '_LOGIN_SCENARIO_PATTERNS', '_AUTH_PRECONDITION_PATTERNS',
                  '_needs_authenticated_page', '_swap_fixtures_by_preconditions'}
        nodes = [n for n in t.body if (isinstance(n, ast.FunctionDef) and n.name in wanted)
                 or (isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id in wanted for x in n.targets))]
        import re
        ns = {'re_module': re, 'select_page_fixture': select_page_fixture}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(p), 'exec'), ns)
        code = 'def test_cart(page: Page):\n    page.goto("/cart")\n'
        result = ns['_swap_fixtures_by_preconditions'](code, 'User is already logged in', 'View cart')
        page = Mock(); runtime = {'Page': object}; exec(result, runtime); runtime['test_cart'](page)
        page.goto.assert_called_once_with('/cart')


if __name__ == '__main__':
    unittest.main()
