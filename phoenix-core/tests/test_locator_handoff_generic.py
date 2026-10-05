"""Generic locator handoff regression tests."""
import ast
import json
from pathlib import Path
import pytest
from jinja2 import Template
from phoenix.locators.reconciliation import match_locator_bundle, reconcile_generated_code


def bundle(page="alpha", value="#validated", name="EmailInput", tag="input"):
    return {"page": page, "element_name": name,
            "primary": {"strategy": "css", "value": value, "verified_in_snapshot": True},
            "alternates": [], "metadata": {"element_identity": "shared-dom-id", "element_data": {"tag": tag}}}


@pytest.mark.parametrize("expression", [
    "page.get_by_label('Email')", "page.get_by_placeholder('Email')",
    "page.get_by_test_id('EmailInput')", "page.get_by_role('textbox', name='Email')",
])
def test_direct_semantic_calls_use_validated_bundle(expression):
    code = f"def test_contact(page):\n    {expression}.fill('literal@example.invalid')\n"
    final, used, missing = reconcile_generated_code(code, [bundle()])
    assert "#validated" in final
    assert "literal@example.invalid" in final
    assert len(used) == 1 and not missing
    ast.parse(final)


def test_same_dom_hash_on_different_pages_requires_explicit_page():
    candidates = [bundle("alpha", "#first"), bundle("beta", "#second")]
    assert match_locator_bundle("EmailInput", candidates) is None
    selected = match_locator_bundle("EmailInput", candidates, page="beta")
    assert selected["primary"]["value"] == "#second"
    final, used, missing = reconcile_generated_code(
        "page.get_by_label('Email').fill('x')", candidates, page="beta")
    assert "#second" in final and used[0]["page"] == "beta" and not missing


def test_unvalidated_semantic_target_is_reported_not_replaced():
    item = bundle(); item["primary"]["verified_in_snapshot"] = False
    source = "page.get_by_label('Email').fill('x')"
    final, used, missing = reconcile_generated_code(source, [item])
    assert final == source and not used and missing == ["Email"]


def test_link_role_uses_validated_link_evidence():
    final, used, missing = reconcile_generated_code(
        "page.get_by_role('link', name='Open Account').click()",
        [bundle(name="OpenAccountLink", tag="a")])
    assert "#validated" in final and len(used) == 1 and not missing


def test_generic_scaffolds_compile_without_application_credentials():
    templates = Path(__file__).resolve().parents[1] / "phoenix/templates/project"
    for name in ("test_example.py.j2", "fixtures_auth.py.j2", "pages_base_page.py.j2", "conftest.py.j2"):
        source = (templates / name).read_text(encoding="utf-8")
        rendered = Template(source).render(project_name="Example", base_url="https://explicit.example.invalid", browser="chromium", bdd=False)
        ast.parse(rendered)
        if name in ("test_example.py.j2", "fixtures_auth.py.j2"):
            assert "TEST_USERNAME" not in source and "TEST_PASSWORD" not in source
            assert "password123" not in source and "get_by_label" not in source


def _load_template_without_browser_imports(name):
    templates = Path(__file__).resolve().parents[1] / "phoenix/templates/project"
    source = Template((templates / name).read_text(encoding="utf-8")).render(project_name="Example")
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not (isinstance(node, ast.ImportFrom) and node.module == "playwright.sync_api")]
    ns = {"Browser": object, "BrowserContext": object, "Page": object, "Locator": object, "__file__": str(templates / name)}
    exec(compile(tree, name, "exec"), ns)
    return ns


def test_base_navigation_requires_explicit_url(monkeypatch):
    from unittest.mock import Mock
    monkeypatch.delenv("APP_URL", raising=False)
    ns = _load_template_without_browser_imports("pages_base_page.py.j2")
    browser_page = Mock()
    base = ns["BasePage"](browser_page)
    with pytest.raises(ValueError, match="APP_URL"):
        base.navigate()
    browser_page.goto.assert_not_called()
    monkeypatch.setenv("APP_URL", "https://provided.example.invalid")
    base.navigate()
    browser_page.goto.assert_called_once_with("https://provided.example.invalid", timeout=60_000)


def test_auth_scaffold_requires_explicit_state_and_preserves_supplied_data(tmp_path, monkeypatch):
    monkeypatch.delenv("PHOENIX_AUTH_STORAGE_STATE", raising=False)
    ns = _load_template_without_browser_imports("fixtures_auth.py.j2")
    load = ns["auth_storage_state"].__wrapped__
    with pytest.raises(pytest.UsageError, match="PHOENIX_AUTH_STORAGE_STATE"):
        load()
    path = tmp_path / "state.json"
    state = {"cookies": [], "origins": []}
    path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setenv("PHOENIX_AUTH_STORAGE_STATE", str(path))
    assert load() == state
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(pytest.UsageError, match="cookies and origins"):
        load()


def test_shared_identical_validated_evidence_records_all_pages():
    result = match_locator_bundle("EmailInput", [bundle("alpha"), bundle("beta")])
    assert result["metadata"]["matched_pages"] == ["alpha", "beta"]
    assert result["primary"]["value"] == "#validated"


def test_different_physical_elements_do_not_merge_even_when_selectors_match():
    first, second = bundle("alpha"), bundle("beta")
    second["metadata"]["element_identity"] = "different-dom-id"
    assert match_locator_bundle("EmailInput", [first, second]) is None
