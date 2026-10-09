import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest
from phoenix.locators.journey import prepare_states, capture_journey

@pytest.mark.parametrize('name',['../escape','a/b','login\\cart','', 'A B'])
def test_unsafe_state_names_rejected(name):
    with pytest.raises(ValueError):prepare_states([{'name':name}],{})

def test_state_bindings_and_duplicate_names():
    original=[{'name':'login','actions':[{'action':'fill','selector':'#field','value':'${EXPLICIT}'}]}]
    states=prepare_states(original,{'EXPLICIT':'synthetic'})
    assert states[0]['actions'][0]['value']=='synthetic'
    assert original[0]['actions'][0]['value']=='${EXPLICIT}'
    with pytest.raises(ValueError):prepare_states(original,{})
    with pytest.raises(ValueError):prepare_states([{'name':'Login'},{'name':'login'}],{})

def test_journey_persistence_keeps_state_identity(tmp_path,monkeypatch):
    import phoenix.locators.journey as journey
    import phoenix_smartlocatorai.dynamic_states as scanner
    f=tmp_path/'states.json';f.write_text('{"states":[{"name":"login"},{"name":"cart"}]}')
    manifest={'states':[{'name':'login','locators_json':'login.json'},{'name':'cart','locators_json':'cart.json'}]}
    monkeypatch.setattr(scanner,'scan_dynamic_states',Mock(return_value=manifest))
    monkeypatch.setattr(journey,'convert_file',Mock(side_effect=lambda path,page:[page]))
    save=Mock();monkeypatch.setattr(journey,'persist_locators',save)
    capture_journey('https://example.test',f,tmp_path,tmp_path/'locators',values={})
    assert [c.args[0][0]['page'] for c in save.call_args_list]==['login','cart']

def test_scaffold_migration_dry_run_and_backup(tmp_path):
    script=Path(__file__).parents[2]/'tools/migrate_generic_scaffold.py'
    spec=importlib.util.spec_from_file_location('migration',script);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    p=tmp_path/'pages/base_page.py';p.parent.mkdir();p.write_text('import os\nx=os.environ.get("APP_URL", "https://old.example")\n')
    assert mod.migrate(tmp_path)==['pages/base_page.py'] and 'old.example' in p.read_text()
    mod.migrate(tmp_path,True)
    assert 'old.example' not in p.read_text() and p.with_suffix('.py.pre_generic_backup').exists()
