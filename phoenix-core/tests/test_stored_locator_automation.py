"""Stored LocatorBundle discovery and automation request evidence."""

import json
import ast

import pytest

from phoenix.locators.smartlocator_integration import (
    locator_bundle_evidence,
    validated_locator_bundles,
)
from phoenix.locators.reconciliation import match_locator_bundle, reconcile_generated_code
from phoenix.locators.smartlocator_adaptor import convert_locators
from phoenix.locators.smartlocator_integration import resolve_automation_locator_evidence
from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy


def _bundle(verified=True):
    return {
        "element_name": "LoginButton",
        "page": "login",
        "primary": {
            "element_name": "LoginButton", "strategy": "css", "value": "#login",
            "confidence": 0.9, "verified_in_snapshot": verified,
        },
        "alternates": [{
            "element_name": "LoginButton", "strategy": "role",
            "value": "button[name=Login]", "confidence": 0.8,
            "verified_in_snapshot": True,
        }],
        "metadata": {"context_strategy": "form"},
    }


def test_loads_only_validated_candidates_and_marks_provenance(tmp_path):
    locators = tmp_path / "locators"
    locators.mkdir()
    (locators / "login.json").write_text(json.dumps([_bundle(False)]), encoding="utf-8")
    bundles = validated_locator_bundles(locators, "login")
    assert len(bundles) == 1
    assert bundles[0].primary.value == "button[name=Login]"
    assert bundles[0].alternates == []
    evidence = locator_bundle_evidence(bundles)
    assert evidence[0]["primary"]["metadata"]["locator_source"] == "stored_alternate"
    assert evidence[0]["primary"]["verified_in_snapshot"] is True


def test_ignores_bundle_with_no_validated_locator(tmp_path):
    item = _bundle(False)
    item["alternates"][0]["verified_in_snapshot"] = False
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([item]), encoding="utf-8")
    assert validated_locator_bundles(path, "login") == []


def test_single_page_file_is_used_when_manual_directory_name_differs(tmp_path):
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([_bundle()]), encoding="utf-8")
    assert len(validated_locator_bundles(path, "manual_tests")) == 1


def test_discovers_page_file_by_scenario_context_among_multiple_files(tmp_path):
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([_bundle()]), encoding="utf-8")
    cart = _bundle()
    cart["element_name"] = "CartButton"
    cart["primary"]["element_name"] = "CartButton"
    (path / "cart.json").write_text(json.dumps([cart]), encoding="utf-8")

    bundles = validated_locator_bundles(path, "manual_tests", [{
        "name": "Login scenario",
        "steps": [{"action": "Enter username and password"}],
    }])

    assert [bundle.element_name for bundle in bundles] == ["LoginButton"]


def test_exact_page_file_is_first_when_other_files_are_relevant(tmp_path):
    path = tmp_path / "locators"
    path.mkdir()
    exact = _bundle()
    exact["element_name"] = "ExactLoginButton"
    exact["primary"]["element_name"] = "ExactLoginButton"
    (path / "login.json").write_text(json.dumps([exact]), encoding="utf-8")
    other = _bundle()
    other["element_name"] = "UsernameInput"
    other["primary"]["element_name"] = "UsernameInput"
    (path / "form.json").write_text(json.dumps([other]), encoding="utf-8")

    bundles = validated_locator_bundles(path, "login", [{
        "name": "Login and username form",
        "steps": [],
    }])

    assert bundles[0].element_name == "ExactLoginButton"


def test_uses_validated_alternate_when_primary_is_empty(tmp_path):
    item = _bundle()
    item["primary"]["value"] = ""
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([item]), encoding="utf-8")

    bundles = validated_locator_bundles(path, "login")

    assert len(bundles) == 1
    assert bundles[0].primary.value == "button[name=Login]"
    assert bundles[0].metadata["locator_source"] == "stored_alternate"


def test_uses_validated_alternate_when_primary_value_is_null(tmp_path):
    item = _bundle()
    item["primary"]["value"] = None
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([item]), encoding="utf-8")

    bundles = validated_locator_bundles(path, "login")

    assert len(bundles) == 1
    assert bundles[0].primary.value == "button[name=Login]"
    assert bundles[0].metadata["locator_source"] == "stored_alternate"


def test_uses_validated_alternate_when_primary_object_is_null(tmp_path):
    item = _bundle()
    item["primary"] = None
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([item]), encoding="utf-8")

    bundles = validated_locator_bundles(path, "login")

    assert len(bundles) == 1
    assert bundles[0].primary.value == "button[name=Login]"
    assert bundles[0].metadata["locator_source"] == "stored_alternate"
    assert bundles[0].metadata["unresolved_reason"] == "primary_missing"


def test_null_primary_without_alternate_is_persisted_as_unresolved_not_usable(tmp_path):
    from phoenix.locators.persist import _merge_locators

    merged = _merge_locators([{
        "element_id": "EmailAddressInput_Login",
        "element_name": "EmailAddressInput_Login",
        "primary": None,
        "alternates": [],
    }])

    assert merged[0]["primary"]["value"] == ""
    assert merged[0]["primary"]["verified_in_snapshot"] is False
    assert merged[0]["metadata"]["locator_source"] == "unresolved"
    assert merged[0]["metadata"]["unresolved_reason"] == "primary_missing"
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps(merged), encoding="utf-8")
    assert validated_locator_bundles(path, "login") == []


@pytest.mark.parametrize("status", ["broken", "unresolved"])
def test_ignores_broken_or_unresolved_bundle(tmp_path, status):
    item = _bundle()
    item["metadata"][status] = True
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([item]), encoding="utf-8")

    assert validated_locator_bundles(path, "login") == []


def test_camel_and_snake_case_aliases_match_exactly():
    item = _bundle()
    item["element_name"] = "UsernameInput"
    item["primary"]["element_name"] = "UsernameInput"
    item["primary"]["value"] = "#user-name"
    item["metadata"]["source_names"] = ["username_input"]

    assert match_locator_bundle("Username input", [item])["primary"]["value"] == "#user-name"
    assert match_locator_bundle("username_input", [item])["primary"]["value"] == "#user-name"


def test_submit_input_bundle_matches_button_requirement():
    item = _bundle()
    item["element_name"] = "LoginButtonInput"
    item["primary"]["element_name"] = "LoginButtonInput"
    item["primary"]["value"] = "#login-button"
    item["metadata"]["element_data"] = {"tag": "input", "type": "submit"}

    assert match_locator_bundle("Login button", [item])["primary"]["value"] == "#login-button"


def test_action_sentence_matches_context_qualified_login_email_and_not_signup_email():
    login_email = {
        "element_name": "EmailAddressInput_Login",
        "primary": {
            "strategy": "context",
            "value": '''page.locator("div").filter({ hasText: "Login to your account" }).locator("form").filter({ hasText: "Login" }).locator("input[name='email']")''',
            "verified_in_snapshot": True,
        },
        "metadata": {
            "element_identity": "login-email-identity",
            "element_data": {
                "tag": "input", "type": "text", "name": "email",
                "placeholder": "Email Address",
                "ancestor_context": {"container_text": "Login to your account"},
            },
        },
    }
    signup_email = {
        "element_name": "EmailAddressInput_Signup",
        "primary": {
            "strategy": "css", "value": "#signup-email", "verified_in_snapshot": True,
        },
        "metadata": {
            "element_identity": "signup-email-identity",
            "element_data": {
                "tag": "input", "type": "text", "name": "email",
                "placeholder": "Email Address",
                "ancestor_context": {"container_text": "Signup form"},
            },
        },
    }

    selected = match_locator_bundle(
        "When I enter TEST_USERNAME in the login email field",
        [signup_email, login_email],
    )

    assert selected["element_name"] == "EmailAddressInput_Login"


def test_login_button_action_sentence_matches_login_button_bundle():
    login_button = {
        "element_name": "LoginButton",
        "primary": {"strategy": "css", "value": "#login-button", "verified_in_snapshot": True},
        "metadata": {
            "element_identity": "login-button-identity",
            "element_data": {"tag": "button", "text": "Login"},
        },
    }

    selected = match_locator_bundle("And I click the Login button", [login_button])

    assert selected["primary"]["value"] == "#login-button"


def test_context_chain_converts_to_python_and_is_inserted_into_generated_code():
    context_value = '''page.locator("div").filter({ hasText: "Login to your account" }).locator("form").filter({ hasText: "Login" }).locator("input[name='email']")'''
    bundle = {
        "element_name": "EmailAddressInput_Login",
        "primary": {
            "strategy": "context", "value": context_value,
            "verified_in_snapshot": True,
        },
        "metadata": {
            "element_identity": "login-email-identity",
            "element_data": {
                "tag": "input", "type": "text", "name": "email",
                "placeholder": "Email Address",
                "ancestor_context": {"container_text": "Login to your account"},
            },
        },
    }
    source = (
        "def login(page):\n"
        '    fill_ready(page, page.get_by_label("Email Address"), "user", '
        '"When I enter TEST_USERNAME in the login email field")\n'
    )

    final, selected, unresolved = reconcile_generated_code(source, [bundle])

    ast.parse(final)
    assert ".filter(has_text='Login to your account')" in final
    assert ".filter(has_text='Login')" in final
    assert 'locator("input[name=\'email\']")' in final
    assert selected[0]["metadata"]["locator_source"] == "stored_primary"
    assert unresolved == []


def test_null_primary_without_validated_alternate_is_not_usable():
    item = {
        "element_name": "EmailAddressInput_Login",
        "primary": {"strategy": "css", "value": None, "verified_in_snapshot": True},
        "alternates": [],
        "metadata": {"element_identity": "login-email-identity"},
    }

    assert match_locator_bundle("login email field", [item]) is None


def test_password_input_stored_primary_regression():
    password = {
        "element_name": "PasswordInput",
        "primary": {"strategy": "css", "value": "[name='password']", "verified_in_snapshot": True},
        "metadata": {
            "element_identity": "password-identity",
            "element_data": {"tag": "input", "type": "password", "name": "password"},
        },
    }

    assert match_locator_bundle("When I enter TEST_PASSWORD in the Password field", [password])["primary"]["value"] == "[name='password']"


def test_semantic_matching_is_domain_agnostic_for_unbranded_elements():
    address = {
        "element_name": "ShippingAddressInput",
        "primary": {"strategy": "css", "value": "#shipping-address", "verified_in_snapshot": True},
        "metadata": {
            "element_identity": "shipping-address-identity",
            "element_data": {
                "tag": "input", "name": "address", "placeholder": "Address",
                "ancestor_context": {"container_text": "Shipping details"},
            },
        },
    }

    selected = match_locator_bundle("When I enter the shipping address field", [address])

    assert selected["primary"]["value"] == "#shipping-address"


def test_all_login_elements_resolve_without_scan_or_locator_expert():
    email = {
        "element_name": "EmailAddressInput_Login",
        "primary": {
            "strategy": "context",
            "value": '''page.locator("div").filter({ hasText: "Login to your account" }).locator("form").filter({ hasText: "Login" }).locator("input[name='email']")''',
            "verified_in_snapshot": True,
            "metadata": {"locator_source": "stored_primary"},
        },
        "metadata": {
            "element_identity": "login-email-identity",
            "locator_source": "stored_primary",
            "element_data": {
                "tag": "input", "type": "text", "name": "email",
                "placeholder": "Email Address",
                "ancestor_context": {"container_text": "Login to your account"},
            },
        },
    }
    password = {
        "element_name": "PasswordInput",
        "primary": {
            "strategy": "css", "value": "[name='password']", "verified_in_snapshot": True,
            "metadata": {"locator_source": "stored_primary"},
        },
        "metadata": {
            "element_identity": "password-identity", "locator_source": "stored_primary",
            "element_data": {"tag": "input", "type": "password", "name": "password"},
        },
    }
    button = {
        "element_name": "LoginButton",
        "primary": {
            "strategy": "css", "value": "#login-button", "verified_in_snapshot": True,
            "metadata": {"locator_source": "stored_primary"},
        },
        "metadata": {
            "element_identity": "login-button-identity", "locator_source": "stored_primary",
            "element_data": {"tag": "button", "text": "Login"},
        },
    }
    evidence = [email, password, button]
    stored = [
        LocatorBundle(
            element_name=bundle["element_name"],
            page="login",
            primary=Locator(
                element_name=bundle["element_name"],
                strategy=LocatorStrategy(bundle["primary"]["strategy"]),
                value=bundle["primary"]["value"],
                verified_in_snapshot=True,
                metadata={
                    **(bundle["primary"].get("metadata") or {}),
                    "element_data": (bundle.get("metadata") or {}).get("element_data"),
                    "locator_source": "stored_primary",
                },
            ),
            metadata={**bundle["metadata"], "locator_source": "stored_primary"},
        )
        for bundle in evidence
    ]
    tests = [{
        "script_code": (
            "def login(page):\n"
            '    fill_ready(page, page.get_by_label("Email Address"), "user", '
            '"When I enter TEST_USERNAME in the login email field")\n'
            '    fill_ready(page, page.get_by_label("Password"), "password", '
            '"When I enter TEST_PASSWORD in the Password field")\n'
            '    click_ready(page, page.get_by_role("button", name="Login"), '
            '"And I click the Login button")\n'
        ),
    }]
    calls = []

    result = resolve_automation_locator_evidence(
        tests,
        stored,
        application_url="https://example.invalid/login",
        page="login",
        scan=lambda *args, **kwargs: calls.append("scan") or [],
        discover=lambda payload: calls.append(payload) or {},
        validate=lambda *_: {},
    )

    assert calls == []
    assert result["locator_expert_calls"] == 0
    assert result["unresolved"] == []
    assert all(selector in tests[0]["script_code"] for selector in (
        "input[name='email']", "[name='password']", "#login-button"
    ))
    assert {item["source"] for item in tests[0]["locator_provenance"]} == {"stored_primary"}


def test_output_manager_reconciles_actual_email_or_chain_and_login_button(tmp_path):
    from phoenix.locators.smartlocator_integration import reconcile_automation_tests_with_bundles
    from phoenix.output.coordinator import OutputManager

    email_context = '''page.locator("div").filter({ hasText: "Login to your account" }).locator("form").filter({ hasText: "Login" }).locator("input[name='email']")'''
    stored = [
        {
            "element_name": "EmailAddressInput_Login",
            "primary": {"strategy": "context", "value": email_context, "verified_in_snapshot": True},
            "alternates": [],
            "metadata": {
                "element_identity": "login-email-identity",
                "locator_source": "stored_primary",
                "element_data": {
                    "tag": "input", "type": "text", "name": "email",
                    "placeholder": "Email Address",
                    "ancestor_context": {"container_text": "Login to your account"},
                },
            },
        },
        {
            "element_name": "EmailAddressInput_Signup",
            "primary": {"strategy": "css", "value": "#signup-email", "verified_in_snapshot": True},
            "alternates": [],
            "metadata": {
                "element_identity": "signup-email-identity",
                "locator_source": "stored_primary",
                "element_data": {
                    "tag": "input", "type": "text", "name": "email",
                    "placeholder": "Email Address",
                    "ancestor_context": {"container_text": "Signup form"},
                },
            },
        },
        {
            "element_name": "PasswordInput",
            "primary": {"strategy": "css", "value": "[name='password']", "verified_in_snapshot": True},
            "alternates": [],
            "metadata": {
                "element_identity": "password-identity",
                "locator_source": "stored_primary",
                "element_data": {"tag": "input", "type": "password", "name": "password"},
            },
        },
        {
            "element_name": "LoginButton",
            "primary": {"strategy": "role", "value": "button[name=Login]", "verified_in_snapshot": True},
            "alternates": [],
            "metadata": {
                "element_identity": "login-button-identity",
                "locator_source": "stored_primary",
                "element_data": {"tag": "button", "text": "Login"},
            },
        },
    ]
    generic_email_or_chain = """self._page.get_by_test_id("username").or_(self._page.get_by_test_id("email")).or_(self._page.get_by_placeholder("Login Email", exact=True)).or_(self._page.get_by_placeholder("Username", exact=True)).or_(self._page.get_by_placeholder("Email", exact=True)).or_(self._page.get_by_label("Login Email", exact=True)).or_(self._page.get_by_label("Username", exact=True)).or_(self._page.get_by_label("Email", exact=True)).or_(self._page.locator("[data-test='username'], [data-testid='username'], [data-test='email'], [data-testid='email']")).or_(self._page.locator("input[name='username'], input[name='email'], input[type='email']"))"""
    old_page_code = (
        "class RegisteredUserLoginPage:\n"
        "    def registered_user_login(self):\n"
        f"        fill_ready(self._page, {generic_email_or_chain}, "
        '"TEST_USERNAME", "Email field")\n'
    )
    generated_page_code = (
        "class RegisteredUserLoginPage:\n"
        "    def registered_user_login(self):\n"
        "        # --- Step 5: Enter the value from `TEST_USERNAME` in the login email field ---\n"
        f"        fill_ready(self._page, {generic_email_or_chain}, "
        '"TEST_USERNAME", "Email field")\n'
        "        # --- Step 6: Enter the value from `TEST_PASSWORD` in the login password field ---\n"
        '        fill_ready(self._page, self._page.locator("[name=\'password\']"), "TEST_PASSWORD", "Password field")\n'
        "        # --- Step 7: Click the Login button ---\n"
        '        click_ready(self._page, self._page.get_by_role("button", name="Login"), "Login button")\n'
    )
    tests = [{
        "locators": [],
        "pom_bundle": {
            "page_objects": [{
                "action": "extend",
                "file": "pages/registered_user_login_page.py",
                "class_name": "RegisteredUserLoginPage",
                "code": generated_page_code,
            }],
            "tests": [], "locators": [], "test_data": [],
        },
    }]
    page_path = tmp_path / "pages" / "registered_user_login_page.py"
    page_path.parent.mkdir()
    page_path.write_text(old_page_code, encoding="utf-8")

    unresolved, _used = reconcile_automation_tests_with_bundles(tests, stored)
    OutputManager(tmp_path).apply(tests[0]["pom_bundle"])
    final_page = page_path.read_text(encoding="utf-8")

    assert unresolved == []
    assert "filter(has_text='Login to your account')" in final_page
    assert "filter(has_text='Login')" in final_page
    assert "input[name='email']" in final_page
    assert "[name='password']" in final_page
    assert "get_by_role('button', name='Login')" in final_page
    assert ".or_(" not in final_page
    assert "#signup-email" not in final_page
    assert {item["source"] for item in tests[0]["locator_provenance"]} == {"stored_primary"}


def test_name_matching_rejects_similar_but_distinct_elements():
    username = _bundle()
    username["element_name"] = "UsernameInput"
    username["metadata"]["element_identity"] = "username-identity"
    profile = _bundle()
    profile["element_name"] = "UserProfileInput"
    profile["metadata"]["element_identity"] = "profile-identity"

    assert match_locator_bundle("user", [username, profile]) is None
    assert match_locator_bundle("Username input", [username, profile])["element_name"] == "UsernameInput"


def test_duplicate_aliases_for_different_physical_elements_are_rejected():
    first = _bundle()
    first["metadata"]["element_identity"] = "first"
    second = _bundle()
    second["metadata"]["element_identity"] = "second"

    assert match_locator_bundle("Login button", [first, second]) is None


def test_reconciler_replaces_invented_selector_and_preserves_provenance():
    item = _bundle()
    item["element_name"] = "UsernameInput"
    item["primary"]["element_name"] = "UsernameInput"
    item["primary"]["value"] = "#user-name"
    item["metadata"]["source_names"] = ["username_input"]
    source = 'def login(page):\n    fill_ready(page, page.locator("#Username"), "user", "Username input")\n'

    final, selected, unresolved = reconcile_generated_code(source, [item])

    assert "#user-name" in final
    assert "#Username" not in final
    assert selected[0]["metadata"]["locator_source"] == "stored_primary"
    assert unresolved == []


def test_persist_merge_preserves_validated_bundle_when_legacy_selector_collides():
    from phoenix.locators.persist import _merge_locators

    stored = {
        "element_id": "LoginButtonInput",
        "element_name": "LoginButtonInput",
        "primary": {
            "strategy": "css",
            "value": "#login-button",
            "confidence": 1.0,
            "verified_in_snapshot": True,
            "metadata": {"locator_source": "stored_primary"},
        },
        "alternates": [],
        "metadata": {"locator_source": "stored_primary"},
    }
    generated = {
        "element_id": "LoginButtonInput",
        "element_name": "LoginButtonInput",
        "selector": "#Login",
    }

    merged = _merge_locators([stored, generated])

    assert len(merged) == 1
    assert merged[0]["primary"]["value"] == "#login-button"
    assert merged[0]["primary"]["verified_in_snapshot"] is True
    assert merged[0]["metadata"]["locator_source"] == "stored_primary"
    assert merged[0]["alternates"][0]["value"] == "#Login"
    assert merged[0]["alternates"][0].get("verified_in_snapshot") is None


def test_persist_merge_keeps_provenance_on_equal_validated_primary():
    from phoenix.locators.persist import _merge_locators

    existing = {
        "element_id": "UsernameInput",
        "element_name": "UsernameInput",
        "primary": {
            "strategy": "css",
            "value": "#user-name",
            "verified_in_snapshot": True,
            "metadata": {"validated": True},
        },
        "alternates": [],
        "metadata": {"element_identity": "username-identity"},
    }
    incoming = {
        **existing,
        "primary": {
            **existing["primary"],
            "metadata": {"validated": True, "locator_source": "stored_primary"},
        },
        "metadata": {
            "element_identity": "username-identity",
            "locator_source": "stored_primary",
        },
    }

    merged = _merge_locators([existing, incoming])[0]

    assert merged["primary"]["value"] == "#user-name"
    assert merged["primary"]["metadata"]["locator_source"] == "stored_primary"
    assert merged["metadata"]["locator_source"] == "stored_primary"


def test_output_manager_replaces_stale_same_named_page_object_method():
    from phoenix.output.coordinator import _splice_methods_into_class

    existing = (
        "class LoginPage:\n"
        "    def login(self):\n"
        "        self.page.locator('#Login').click()\n"
        "\n"
        "    def logout(self):\n"
        "        self.page.get_by_role('button', name='Logout').click()\n"
    )
    incoming = (
        "class LoginPage:\n"
        "    def login(self):\n"
        "        self.page.locator('#login-button').click()\n"
        "\n"
        "    def checkout(self):\n"
        "        self.page.get_by_role('button', name='Checkout').click()\n"
    )

    merged = _splice_methods_into_class(existing, "LoginPage", incoming)

    assert "#login-button" in merged
    assert "#Login'" not in merged
    assert "def logout(self)" in merged
    assert "def checkout(self)" in merged


def test_reconciler_keeps_partial_coverage_and_reports_only_unresolved_labels():
    item = _bundle()
    item["element_name"] = "UsernameInput"
    item["primary"]["element_name"] = "UsernameInput"
    item["primary"]["value"] = "#user-name"
    source = (
        'def login(page):\n'
        '    fill_ready(page, page.locator("#Username"), "user", "Username input")\n'
        '    click_ready(page, page.locator("#Purchase"), "Purchase button")\n'
    )

    final, selected, unresolved = reconcile_generated_code(source, [item])

    assert "#user-name" in final
    assert "#Purchase" in final
    assert len(selected) == 1
    assert unresolved == ["Purchase button"]


def test_stored_coverage_skips_scan_and_locator_expert(tmp_path):
    item = _bundle()
    item["element_name"] = "UsernameInput"
    item["primary"]["element_name"] = "UsernameInput"
    item["primary"]["value"] = "#user-name"
    path = tmp_path / "locators"
    path.mkdir()
    (path / "login.json").write_text(json.dumps([item]), encoding="utf-8")
    stored = validated_locator_bundles(path, "login")
    tests = [{
        "script_code": 'def login(page):\n    fill_ready(page, page.locator("#Username"), "u", "Username input")\n',
        "pom_bundle": {"page_objects": [{"code": 'fill_ready(self._page, self._page.locator("#Username"), "u", "Username input")'}]},
    }]
    calls = []

    result = resolve_automation_locator_evidence(
        tests,
        stored,
        application_url="https://app.example",
        page="login",
        scan=lambda *args, **kwargs: calls.append("scan") or [],
        discover=lambda payload: calls.append(payload) or {},
        validate=lambda *_: {},
    )

    assert calls == []
    assert result["unresolved"] == []
    assert "#user-name" in tests[0]["script_code"]
    assert "#Username" not in tests[0]["pom_bundle"]["page_objects"][0]["code"]
    assert tests[0]["locator_provenance"][0]["source"] == "stored_primary"


def test_partial_coverage_scans_and_selects_only_unresolved_element():
    stored = convert_locators([{
        "custom_name": "UsernameInput",
        "locator_type": "CSS Selector",
        "locator_value": "#user-name",
        "validated": True,
        "match_count": 1,
        "recommended": True,
        "element_data": {"tag": "input", "id": "user-name", "aria-label": "Username"},
    }], page="login")
    scan_results = convert_locators([
        {
            "custom_name": "UsernameInput",
            "locator_type": "CSS Selector",
            "locator_value": "#scanned-user",
            "validated": True,
            "match_count": 1,
            "recommended": True,
            "element_data": {"tag": "input", "id": "scanned-user"},
        },
        {
            "custom_name": "PurchaseButton",
            "locator_type": "CSS Selector",
            "locator_value": "#purchase",
            "validated": True,
            "match_count": 1,
            "recommended": True,
            "element_data": {"tag": "button", "id": "purchase", "text": "Purchase"},
        },
    ], page="login")
    tests = [{
        "script_code": (
            'def checkout(page):\n'
            '    fill_ready(page, page.locator("#Username"), "u", "Username input")\n'
            '    click_ready(page, page.locator("#Purchase"), "Purchase button")\n'
        ),
    }]
    scan_calls = []
    expert_calls = []

    result = resolve_automation_locator_evidence(
        tests,
        stored,
        application_url="https://app.example",
        page="login",
        scan=lambda *args, **kwargs: scan_calls.append(kwargs) or scan_results,
        discover=lambda payload: expert_calls.append(payload) or {},
        validate=lambda *_: {},
    )

    assert scan_calls == [{
        "page": "login",
        "validate": True,
        "element_names": ["Purchase button"],
    }]
    assert expert_calls == []
    assert result["fresh_count"] == 1
    assert "#user-name" in tests[0]["script_code"]
    assert "#purchase" in tests[0]["script_code"]
    assert {item["source"] for item in tests[0]["locator_provenance"]} == {
        "stored_primary", "fresh_smartlocator_scan"
    }


def test_locator_expert_receives_only_unresolved_and_provenance_persists(tmp_path):
    stored = convert_locators([{
        "custom_name": "UsernameInput",
        "locator_type": "CSS Selector",
        "locator_value": "#user-name",
        "validated": True,
        "match_count": 1,
        "recommended": True,
        "element_data": {"tag": "input", "id": "user-name", "aria-label": "Username"},
    }], page="login")
    tests = [{
        "script_code": (
            'def checkout(page):\n'
            '    fill_ready(page, page.locator("#Username"), "u", "Username input")\n'
            '    click_ready(page, page.locator("#Purchase"), "Purchase button")\n'
        ),
    }]
    expert_targets = []

    result = resolve_automation_locator_evidence(
        tests,
        stored,
        application_url="https://app.example",
        page="login",
        scan=lambda *_args, **_kwargs: [],
        discover=lambda payload: expert_targets.append(payload) or {
            "locators": [{"strategy": "css", "value": "#purchase"}],
        },
        validate=lambda *_args: {"match_count": 1, "identity_matches": True},
    )

    assert [payload["element_name"] for payload in expert_targets] == ["Purchase button"]
    assert result["locator_expert_calls"] == 1
    assert result["unresolved"] == []
    assert "#purchase" in tests[0]["script_code"]
    expert_provenance = [
        source for source in tests[0]["locator_provenance"]
        if source["source"] == "locator_expert"
    ]
    assert expert_provenance

    from phoenix.locators.persist import persist_locators

    assert persist_locators([{"page": "login", "locators": tests[0]["locators"]}], tmp_path) == 1
    saved = json.loads((tmp_path / "login.json").read_text(encoding="utf-8"))
    assert any(
        bundle.get("metadata", {}).get("locator_source") == "locator_expert"
        for bundle in saved
    )


def test_multiple_pages_are_not_guessed(tmp_path):
    path = tmp_path / "locators"
    path.mkdir()
    for name in ("login", "cart"):
        (path / f"{name}.json").write_text(json.dumps([_bundle()]), encoding="utf-8")
    assert validated_locator_bundles(path, "manual_tests") == []


def test_discovery_is_confined_to_the_configured_project_directory(tmp_path):
    first = tmp_path / "project-one" / "locators"
    second = tmp_path / "project-two" / "locators"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    one = _bundle()
    one["element_name"] = "ProjectOneLogin"
    two = _bundle()
    two["element_name"] = "ProjectTwoLogin"
    (first / "login.json").write_text(json.dumps([one]), encoding="utf-8")
    (second / "login.json").write_text(json.dumps([two]), encoding="utf-8")

    bundles = validated_locator_bundles(first, "login")

    assert [bundle.element_name for bundle in bundles] == ["ProjectOneLogin"]


def test_discovery_rejects_locator_symlink_outside_project(tmp_path):
    project = tmp_path / "project" / "locators"
    external = tmp_path / "other-project" / "login.json"
    project.mkdir(parents=True)
    external.parent.mkdir()
    external.write_text(json.dumps([_bundle()]), encoding="utf-8")
    try:
        (project / "login.json").symlink_to(external)
    except OSError:
        pytest.skip("file symlink support is unavailable")

    assert validated_locator_bundles(project, "login") == []
