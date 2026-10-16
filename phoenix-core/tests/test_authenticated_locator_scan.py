"""Authenticated scan readiness, state isolation and truthful fallback evidence."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from phoenix.cli.commands import locators
from phoenix.locators.live_session import LiveLocatorSession, live_session
from phoenix.locators.smartlocator_fallback import fallback_reasons, resolve_with_locator_expert
from phoenix.locators.smartlocator_adaptor import convert_locators


def test_state_path_is_project_relative_from_nested_directory(tmp_path, monkeypatch):
    (tmp_path/'.phoenixrc').write_text('[project]\nname="fixture"\n',encoding='utf8')
    state=tmp_path/'auth.json';state.write_text('{"cookies":[],"origins":[]}',encoding='utf8')
    nested=tmp_path/'nested/deep';nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.setattr('phoenix.cli.commands.PhoenixConfig.load',lambda path:SimpleNamespace(project=SimpleNamespace(resolved_base_url=None)))
    recorded={}
    @contextmanager
    def session(url, **kwargs):
        recorded.update(kwargs)
        yield SimpleNamespace(scan=lambda *a,**k:[],scan_diagnostics={'final_url':url,'captured_element_count':0})
    monkeypatch.setattr('phoenix.locators.live_session.live_session',session)
    result=CliRunner().invoke(locators,['scan','--url','https://fixture.test/dashboard','--page','dashboard','--storage-state','auth.json'],obj={})
    assert result.exit_code==0,result.output
    assert recorded['storage_state']==str(state.resolve())
    assert recorded['state_name']=='dashboard'


def test_missing_state_fails_before_browser_creation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('phoenix.cli.commands.PhoenixConfig.load',lambda path:SimpleNamespace(project=SimpleNamespace(resolved_base_url=None)))
    browser=Mock()
    monkeypatch.setattr('phoenix.locators.live_session.live_session',browser)
    result=CliRunner().invoke(locators,['scan','--url','https://fixture.test/dashboard','--page','dashboard','--storage-state','missing.json'],obj={})
    assert result.exit_code!=0
    assert 'Storage-state file does not exist' in result.output
    browser.assert_not_called()


def test_authenticated_redirect_is_not_saved_under_requested_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'auth.json').write_text('{}',encoding='utf8')
    monkeypatch.setattr('phoenix.cli.commands.PhoenixConfig.load',lambda path:SimpleNamespace(project=SimpleNamespace(resolved_base_url=None)))
    @contextmanager
    def session(*args, **kwargs):
        yield SimpleNamespace(scan=lambda *a,**k:[],scan_diagnostics={'final_url':'https://fixture.test/login','captured_element_count':1})
    monkeypatch.setattr('phoenix.locators.live_session.live_session',session)
    result=CliRunner().invoke(locators,['scan','--url','https://fixture.test/dashboard','--page','dashboard','--storage-state','auth.json'],obj={})
    assert result.exit_code!=0 and 'redirected away' in result.output
    assert not (tmp_path/'locators/dashboard.json').exists()


def test_readiness_timeout_does_not_capture_partial_html(tmp_path):
    from playwright.sync_api import TimeoutError
    page=Mock()
    page.wait_for_load_state.side_effect=TimeoutError('not settled')
    with pytest.raises(TimeoutError):LiveLocatorSession(page).scan(output_dir=tmp_path/'raw')
    page.content.assert_not_called()
    assert not (tmp_path/'raw/locators.json').exists()


def test_insufficient_context_is_not_a_discovery_attempt():
    bundle=convert_locators([{'custom_name':'Control','locator_type':'CSS Selector','locator_value':'#control',
        'stability':'Medium','element_data':{'tag':'button','id':'control'}}],page='dashboard')[0]
    discover=Mock()
    result=resolve_with_locator_expert([bundle],page_url='https://fixture.test/dashboard',discover=discover,
        validate=Mock(),capture=lambda *args:{'capture_status':'insufficient_context','anchor_count':0})
    discover.assert_not_called()
    assert result['llm_calls']==0
    unresolved=result['unresolved_elements'][0]
    assert unresolved['fallback_attempted'] is False and unresolved['discovery_calls']==0
    assert unresolved['capture_attempts']==1
    assert unresolved['final_failure_reason']=='insufficient_live_context'


def test_real_browser_restores_state_and_scans_hydrated_page_once(tmp_path,monkeypatch):
    from playwright.sync_api import Browser
    state=tmp_path/'auth.json'
    state.write_text(json.dumps({'cookies':[{'name':'session','value':'fixture-only-auth','domain':'fixture.test',
        'path':'/','expires':-1,'httpOnly':True,'secure':True,'sameSite':'Lax'}],'origins':[]}),encoding='utf8')
    created=[]
    original=Browser.new_context
    def context(browser, **kwargs):
        created.append(kwargs)
        ctx=original(browser,**kwargs)
        def route(request_route):
            request=request_route.request
            assert 'session=fixture-only-auth' in request.all_headers().get('cookie','')
            if request.url.endswith('/data'):
                request_route.fulfill(content_type='application/json',body=json.dumps({'html':
                    '<main><h1>Overview</h1> <input id="filter" name="filter"> <button id="refresh">Refresh</button> <a id="docs" href="/docs">Docs</a></main>'}))
            else:
                request_route.fulfill(content_type='text/html',body='''<html><body><div id="app" aria-busy="true"><a href="https://public.test">Footer</a></div>
                    <script>fetch('/data').then(r=>r.json()).then(data=>{
                        setTimeout(()=>{const app=document.querySelector('#app');app.innerHTML=data.html;app.removeAttribute('aria-busy');},200);
                    });</script></body></html>''')
        ctx.route('https://fixture.test/**',route)
        return ctx
    monkeypatch.setattr(Browser,'new_context',context)
    with live_session('https://fixture.test/dashboard',storage_state=state,state_name='dashboard') as session:
        page=session.page
        bundles=session.scan(page='dashboard',output_dir=tmp_path/'raw')
        assert page is session.page and page.url=='https://fixture.test/dashboard'
        assert len(created)==1 and created[0]['storage_state']==str(state.resolve())
        assert session.scan_diagnostics['captured_element_count']==3
        assert len(bundles)==3
        assert all(not fallback_reasons(b) for b in bundles), [(b.element_name, fallback_reasons(b), b.primary.value) for b in bundles]
        for bundle in bundles:
            assert bundle.primary.metadata['match_count']==1
            assert bundle.primary.metadata['identity_matches'] is True
            assert bundle.primary.metadata['validation_url']==page.url
            captured=session.capture({'element_data':bundle.metadata['element_data']})
            assert captured['capture_status']=='captured' and captured['anchor_count']==1
        raw=json.loads((tmp_path/'raw/locators.json').read_text(encoding='utf8'))
        assert raw['capture']['final_url']==page.url
        from phoenix.locators.persist import persist_locators
        persist_locators([{'page':'dashboard','locators':bundles}],tmp_path/'locators')
        persisted=json.loads((tmp_path/'locators/dashboard.json').read_text(encoding='utf8'))
        assert all(item['primary']['metadata']['identity_matches'] is True for item in persisted)
        assert all(item['primary']['metadata']['match_count']==1 for item in persisted)


def test_cli_reports_capture_failure_without_claiming_fallback_attempt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "phoenix.cli.commands.PhoenixConfig.load",
        lambda path: SimpleNamespace(project=SimpleNamespace(resolved_base_url=None)),
    )
    bundle = convert_locators([
        {"custom_name": "Control", "locator_type": "CSS Selector",
         "locator_value": "#control", "stability": "Medium",
         "element_data": {"tag": "button", "id": "control"}}
    ], page="dashboard")[0]
    warnings = Mock()
    monkeypatch.setattr("phoenix.cli.commands.print_warning", warnings)
    client = Mock()
    monkeypatch.setattr("phoenix.sdk.client.PhoenixClient",
                        lambda **kwargs: SimpleNamespace(_intelligence_client=client))

    @contextmanager
    def session(url, **kwargs):
        yield SimpleNamespace(
            scan=lambda *args, **options: [bundle],
            scan_diagnostics={"final_url": url, "captured_element_count": 1},
            capture=lambda *args: {"capture_status": "insufficient_context", "anchor_count": 0},
            validate=Mock(),
        )

    monkeypatch.setattr("phoenix.locators.live_session.live_session", session)
    result = CliRunner().invoke(
        locators,
        ["scan", "--url", "https://fixture.test/dashboard", "--page", "dashboard", "--llm-fallback"],
        obj={},
    )
    assert result.exit_code == 0, result.output
    warning_text = "\n".join(call.args[0] for call in warnings.call_args_list)
    assert "fallback attempted: False" in warning_text
    assert "insufficient_live_context" in warning_text
    client.discover_locators.assert_not_called()
