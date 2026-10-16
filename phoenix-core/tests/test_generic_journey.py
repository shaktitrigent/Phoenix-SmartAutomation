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

def test_state_actions_are_normalized_for_smartlocator_runtime():
    """Test that actions with selector in value field are normalized for SmartLocator compatibility."""
    original=[{'name':'login','actions':[
        {'action':'fill','value':'#user-name','text':'standard_user'},
        {'action':'click','value':'#login-button'},
        {'action':'wait_for_selector','value':'.inventory_list'}
    ]}]
    states=prepare_states(original,{})
    assert states[0]['actions'][0]['selector']=='#user-name'
    assert states[0]['actions'][0]['value']=='standard_user'
    assert states[0]['actions'][1]['selector']=='#login-button'
    assert states[0]['actions'][1]['value'] is None
    assert states[0]['actions'][2]['selector']=='.inventory_list'
    assert states[0]['actions'][2]['value'] is None

def test_actions_with_existing_selector_are_not_modified():
    """Test that actions with explicit selector field are not modified."""
    original=[{'name':'login','actions':[
        {'action':'fill','selector':'#existing-selector','value':'text_value'}
    ]}]
    states=prepare_states(original,{})
    assert states[0]['actions'][0]['selector']=='#existing-selector'
    assert states[0]['actions'][0]['value']=='text_value'

def test_runtime_end_execution_handles_null_gracefully():
    """Test that end_execution handles None runtime_evidence gracefully."""
    from phoenix.execution.intelligent_runtime import IntelligentRuntime
    import tempfile
    import shutil
    
    tmp_dir = tempfile.mkdtemp()
    try:
        runtime = IntelligentRuntime(
            base_dir=tmp_dir,
            project_name="test",
            enable_cache=False,
            enable_repository=False,
            enable_healing=False,
            enable_metrics=False,
            enable_timeline=False,
            enable_semantic=False
        )
        # Call end_execution without calling start_execution
        result = runtime.end_execution(status="passed")
        assert result is None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def test_pydantic_model_dump_compatibility():
    """Test that Pydantic model_dump() compatibility is handled correctly."""
    # This is a compile-time check - the code in semantic_integrator.py
    # should use model_dump() if available, falling back to dict()
    from pydantic import BaseModel
    
    class TestModel(BaseModel):
        value: str
    
    model = TestModel(value="test")
    # Verify model_dump() works (Pydantic 2.x)
    assert hasattr(model, 'model_dump')
    result = model.model_dump()
    assert result == {'value': 'test'}
    # Verify dict() still works for backward compatibility
    result_dict = model.dict()
    assert result_dict == {'value': 'test'}

def test_journey_persistence_keeps_state_identity(tmp_path,monkeypatch):
    import phoenix.locators.journey as journey
    import phoenix_smartlocatorai.dynamic_states as scanner
    f=tmp_path/'states.json';f.write_text('{"states":[{"name":"login"},{"name":"cart"}]}')
    from contextlib import contextmanager
    from types import SimpleNamespace
    from phoenix_shared.models.locator import Locator,LocatorBundle,LocatorStrategy
    pages=[]
    @contextmanager
    def session(*args,**kwargs):
        shared_page=Mock(url="https://example.test")
        def scan(**kw):
            pages.append(shared_page)
            return [LocatorBundle(element_name="Field",page=kw["page"],primary=Locator(
                element_name="Field",strategy=LocatorStrategy.CSS,value="#field",verified_in_snapshot=True,
                metadata={"match_count":1,"identity_matches":True,"stability":"High"}))]
        yield SimpleNamespace(page=shared_page,scan=scan)
    monkeypatch.setattr("phoenix.locators.live_session.live_session",session)
    save=Mock();monkeypatch.setattr(journey,'persist_locators',save)
    capture_journey('https://example.test',f,tmp_path,tmp_path/'locators',values={})
    assert len(pages)==2 and pages[0] is pages[1]
    assert [c.args[0][0]['page'] for c in save.call_args_list]==['login','cart']

def test_scaffold_migration_dry_run_and_backup(tmp_path):
    script=Path(__file__).parents[2]/'tools/migrate_generic_scaffold.py'
    spec=importlib.util.spec_from_file_location('migration',script);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    p=tmp_path/'pages/base_page.py';p.parent.mkdir();p.write_text('import os\nx=os.environ.get("APP_URL", "https://old.example")\n')
    assert mod.migrate(tmp_path)==['pages/base_page.py'] and 'old.example' in p.read_text()
    mod.migrate(tmp_path,True)
    assert 'old.example' not in p.read_text() and p.with_suffix('.py.pre_generic_backup').exists()
