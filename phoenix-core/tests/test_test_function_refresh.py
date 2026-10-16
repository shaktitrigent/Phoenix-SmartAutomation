import ast
from phoenix.output.coordinator import _append_test_functions


def test_existing_generated_test_calls_the_new_page_and_retains_other_tests():
    old='from pages.old import OldPage\ndef test_example(page):\n OldPage(page).run()\ndef test_other(page):\n assert True\n'
    new='from __future__ import annotations\nfrom pages.new import NewPage\ndef test_example(page):\n NewPage(page).perform({})\n'
    result=_append_test_functions(old,new)
    tree=ast.parse(result);functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    assert [n.name for n in functions]==['test_example','test_other']
    assert 'NewPage(page).perform({})' in result and 'OldPage(page).run()' not in result
    assert 'from pages.new import NewPage' in result
    compile(result,'test','exec')
    assert _append_test_functions(result,new)==result


def test_refresh_keeps_incoming_decorators_and_does_not_append_nested_tests():
    result=_append_test_functions('def test_x():\n pass\n', 'import pytest\n@pytest.mark.smoke\ndef test_x():\n assert 1\ndef helper():\n def test_nested():\n  pass\n')
    assert '@pytest.mark.smoke' in result and 'test_nested' not in result


def test_import_alias_collision_is_rejected_instead_of_running_old_page():
    import pytest
    with pytest.raises(ValueError,match='import conflicts'):
        _append_test_functions('from pages.old import Old as Page\ndef test_x(page):\n Page(page).run()\n',
                               'from pages.new import New as Page\ndef test_x(page):\n Page(page).run()\n')
