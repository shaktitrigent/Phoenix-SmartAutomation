"""Capture caller-specified browser states and persist page-scoped bundles."""
import json
import os
import re
import hashlib
import time
import logging
logger=logging.getLogger(__name__)
from pathlib import Path
from phoenix.locators.smartlocator_adaptor import convert_file
from phoenix.locators.persist import persist_locators


def prepare_states(definitions, values):
    if not isinstance(definitions, list) or not definitions:
        raise ValueError("Journey requires a nonempty states array")
    states = []
    names = set()
    for definition in definitions:
        state = dict(definition)
        name = state.get("name", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
            raise ValueError("State name must be a unique filename-safe page identifier")
        if name.lower() in names:
            raise ValueError("Duplicate state name")
        names.add(name.lower())
        state["actions"] = []
        for source in definition.get("actions", []):
            action = dict(source)
            kind = str(action.get("action") or action.get("type") or "").strip().lower()
            # Normalize actions for SmartLocator runtime compatibility:
            # If selector is not provided and value looks like a selector, move it to selector field
            if "selector" not in action and kind in {"fill", "click", "press", "check", "uncheck", "select_option", "wait_for_selector"}:
                selector = action.get("value")
                if selector is not None:
                    action["selector"] = selector
                    if kind == "fill" and "text" in action and action.get("text") is not None:
                        action["value"] = action["text"]
                    elif kind != "fill":
                        action["value"] = None
            value = action.get("value")
            if isinstance(value, str):
                match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value)
                if match:
                    if match.group(1) not in values: raise ValueError("Missing explicitly referenced journey variable")
                    action["value"] = values[match.group(1)]
            state["actions"].append(action)
        states.append(state)
    return states


def load_journey(states_file, project_root="."):
    from dotenv import dotenv_values
    root=Path(project_root)
    definitions=json.loads(Path(states_file).read_text(encoding="utf-8"))
    values={**dotenv_values(root/".env"),**os.environ,**dotenv_values(root/".env.local")}
    return prepare_states(definitions.get("states") if isinstance(definitions,dict) else definitions,values)


def wait_for_scoped_target(session, definition, state_name, timeout_ms=15000):
    """Wait for a caller-declared target; never choose one ambiguous match."""
    from urllib.parse import urlsplit, urlunsplit
    selector = definition.get("selector") if isinstance(definition, dict) else str(definition)
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError(f"State {state_name}: required target needs a nonempty selector")
    target = session.page.locator(selector)
    try:
        target.wait_for(state="visible", timeout=timeout_ms)
    except Exception as exc:
        # Playwright errors can contain DOM and input values. Report only
        # the target count and sanitized route, retaining the original cause.
        count = target.count()
        parts = urlsplit(str(session.page.url))
        route = urlunsplit((parts.scheme, parts.hostname or "", parts.path, "", ""))
        reason = "target_not_visible" if count == 1 else "target_missing" if count == 0 else "target_ambiguous"
        raise ValueError(f"State {state_name}: {reason}; matches={count}; current_page={route}; "
                         "check journey authentication, navigation and target selector") from exc
    count = target.count()
    if count != 1:
        raise ValueError(f"State {state_name}: target_ambiguous; matches={count}; "
                         "required target must identify one physical node")
    return target


def validate_scoped_target(session, definition, state_name):
    """A caller's contextual candidate still needs live uniqueness and identity."""
    from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy
    from phoenix.locators.live_session import _DESCRIBE
    selector=definition.get('selector') if isinstance(definition,dict) else str(definition)
    name=definition.get('name',selector) if isinstance(definition,dict) else selector
    target=wait_for_scoped_target(session, definition, state_name)
    actual=target.evaluate(_DESCRIBE)
    label_context=None
    # Context selectors must identify their intended field by a supplied label.
    # Arbitrary unique CSS/classes alone cannot become high-stability evidence.
    match=re.search(r'label:(?:text-is|has-text)\(("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\)',selector)
    if match:
        import ast
        label=ast.literal_eval(match[1])
        label_context=next((a for a in actual.get('ancestors',[]) if label.casefold() in str(a.get('text','')).casefold()),None)
        if label_context is None:return None
    stable={k:actual[k] for k in ('id','name','aria-label','data-testid','data-test') if actual.get(k)}
    scope = definition.get('assertion_scope') if isinstance(definition,dict) else None
    if scope is not None and not isinstance(scope,dict):
        raise ValueError('assertion_scope must be an object')
    if scope and 'lookup_fields' in scope and (not isinstance(scope['lookup_fields'],list) or not scope['lookup_fields']
            or not all(isinstance(v,str) and v for v in scope['lookup_fields'])):
        raise ValueError('Record lookup needs an explicit nonempty field-name array')
    if scope and scope.get('non_creation_verification') not in {None,'compare_records'}:
        raise ValueError('Unknown non-creation verification policy')
    if scope and scope.get('non_creation_verification')=='compare_records' and not scope.get('entity_name'):
        raise ValueError('Record comparison needs an explicit entity_name')
    structural = bool(scope and scope.get('kind')=='records' and scope.get('record_role')=='row'
                      and (actual.get('role') in {'table','grid'} or actual.get('tag')=='table')
                      and bool(stable or actual.get('column_headers')))
    if scope and not structural:
        raise ValueError('Record scope requires a live table/grid and explicit row role')
    if not stable and not label_context and not structural:return None
    if re.search(r':nth-|\.nth\(|\.(?:first|last)\b',selector):return None
    data={k:v for k,v in actual.items() if k not in {'ancestors','siblings','table_context','text','class'}}
    if actual.get('text') and not structural:data['text']=actual['text']
    if label_context:
        data['ancestor_context']={'container_tag':label_context['tag'],
            'container_id':label_context.get('id',''),'distinguishing_text':label,
            'container_class':label_context.get('class','')}
    interaction=definition.get('interaction_contract') if isinstance(definition,dict) else None
    if interaction and (interaction!={'kind':'autocomplete','option_role':'option'} or actual.get('tag')!='input'):
        raise ValueError('Autocomplete contract must identify an input and declare the option role')
    candidate=Locator(element_name=name,strategy=LocatorStrategy.CSS,value=selector)
    outcome=session.validate(candidate,{'element_data':data})
    if outcome.get('match_count')!=1 or outcome.get('identity_matches') is not True:return None
    metadata={**outcome,'source':'contextual_capture','stability':'High','stability_score':9,
              'stability_basis':'explicit_label_context' if label_context else 'unique_structural_record_scope' if structural else 'stable_identity_attributes'}
    candidate=candidate.model_copy(update={'verified_in_snapshot':True,'metadata':metadata})
    import hashlib
    identity=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    return LocatorBundle(element_name=name,page=state_name,primary=candidate,alternates=[],
        metadata={'element_data':data,'element_identity':identity,'state_name':state_name,'validation_url':session.page.url,
                  **({'assertion_scope':scope} if scope else {}),
                  **({'interaction_contract':interaction} if interaction else {})})


def capture_journey(application_url, states_file, output_dir, locators_dir, *, values=None, storage_state=None,
                    discover=None, max_rounds=2):
    from phoenix.locators.live_session import live_session
    from phoenix_smartlocatorai.dynamic_states import _execute_state_action
    from phoenix_shared.locator_policy import locator_accepted
    definitions=json.loads(Path(states_file).read_text(encoding="utf-8"))
    states=prepare_states(definitions.get("states") if isinstance(definitions,dict) else definitions,
                          values if values is not None else dict(os.environ))
    result={"states":[]}
    with live_session(application_url,storage_state=storage_state) as session:
        lookup_observations=[]
        observe=any((d.get('assertion_scope') or {}).get('lookup_fields') for st in states
                    for d in st.get('fallback_targets',[]) if isinstance(d,dict))
        if observe:
            from phoenix.locators.record_lookup_observation import observe_record_lookup
            def on_response(response):
                try:lookup_observations.extend(observe_record_lookup(response,application_url))
                except Exception:logger.debug('Response did not provide a usable read-only record lookup')
            session.page.on('response',on_response)
        for state in states:
            stages={};stage_start=time.perf_counter()
            logger.info('Journey state=%s stage=navigation',state['name'])
            for action in state.get("actions",[]):
                _execute_state_action(session.page,action)
            if state.get("wait_for_selector"):
                session.page.wait_for_selector(state["wait_for_selector"])
            # SPA navigation may finish before its controls are rendered.
            # Establish required target readiness before snapshot scanning.
            for definition in state.get('fallback_targets', []):
                wait_for_scoped_target(session, definition, state['name'])
            stages['navigation_seconds']=time.perf_counter()-stage_start
            stage_start=time.perf_counter()
            logger.info('Journey state=%s stage=scan_validation',state['name'])
            session.state_name=state["name"]
            mode=state.get('scan_mode','full')
            if mode not in {'full','required_targets'}:
                raise ValueError('Unknown journey scan_mode; use full or required_targets')
            if mode=='required_targets' and not state.get('fallback_targets'):
                raise ValueError('required_targets scanning needs explicit fallback_targets')
            bundles=[] if mode=='required_targets' else session.scan(
                page=state["name"],output_dir=Path(output_dir)/state["name"],
                identity_policies=state.get('identity_policies'))
            stages['scan_validation_seconds']=time.perf_counter()-stage_start
            stage_start=time.perf_counter()
            logger.info('Journey state=%s stage=contextual_resolution',state['name'])
            fallback_result = {}
            if state.get("fallback_targets"):
                from phoenix.locators.live_session import _DESCRIBE, identity_matches
                from phoenix.locators.smartlocator_fallback import resolve_with_locator_expert
                eligible_indices = set()
                missing_targets = []
                for definition in state["fallback_targets"]:
                    selector = definition.get("selector") if isinstance(definition, dict) else definition
                    target = wait_for_scoped_target(session, definition, state['name'])
                    def matches(bundle):
                        expected = (bundle.metadata or {}).get('element_data') or {}
                        try: descriptor = target.evaluate(_DESCRIBE, expected.get('content_identity'))
                        except Exception: return False
                        return identity_matches(descriptor,expected)
                    scoped=validate_scoped_target(session,definition,state['name'])
                    declared=definition.get('assertion_scope') if isinstance(definition,dict) else None
                    if scoped is not None and declared and declared.get('lookup_fields'):
                        required=set(declared['lookup_fields']);deadline=time.monotonic()+10
                        candidates=[]
                        while time.monotonic()<deadline:
                            candidates=[v for v in lookup_observations if required<=set(v['record_fields'])]
                            unique={json.dumps(v['lookup'],sort_keys=True):v for v in candidates}
                            if unique:break
                            session.page.wait_for_timeout(100)
                        if len(unique)!=1:
                            raise ValueError('Record scope needs one observed read-only lookup matching declared fields; no endpoint is guessed')
                        observed=next(iter(unique.values()))
                        scoped=scoped.model_copy(update={'metadata':{**scoped.metadata,
                            'assertion_scope':{**declared,'record_lookup':observed['lookup'],'lookup_source':observed['source']}}})
                    matching = [i for i, b in enumerate(bundles) if matches(b)]
                    if scoped is not None:
                        # Preserve existing bundles and add only the physically
                        # validated candidate. Resolved primaries never need LLM.
                        bundles.append(scoped)
                        matching = [len(bundles)-1]
                    eligible_indices.update(matching)
                    if not matching:
                        # A caller-supplied scoped selector is itself an
                        # observed physical target. Seed an unresolved bundle
                        # from its current DOM descriptor so LocatorExpert can
                        # propose a better selector and validate it in this
                        # state; never mark the supplied selector accepted.
                        from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy
                        descriptor = target.evaluate(_DESCRIBE)
                        name = definition.get("name", selector) if isinstance(definition, dict) else selector
                        # The caller supplies semantic intent separately from
                        # observed DOM identity; carry it for discovery without
                        # treating it as selector verification.
                        descriptor = {**descriptor,"label":name}
                        identity = hashlib.sha256(json.dumps(descriptor,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                        seed = LocatorBundle(element_name=name, page=state["name"],
                            primary=Locator(element_name=name,strategy=LocatorStrategy.CSS,value=selector,
                                confidence=0.5,fallback=False,verified_in_snapshot=False),
                            alternates=[],metadata={"element_data":descriptor,
                                "element_identity":"scoped_target:"+identity,"state_name":state["name"]})
                        seed = session.revalidate([seed])[0]
                        if (seed.primary.metadata or {}).get("match_count") != 1 or (seed.primary.metadata or {}).get("identity_matches") is not True:
                            failure=seed.primary.metadata or {}
                            raise ValueError(f"State {state['name']}, target {name}: scoped target identity rejected; "
                                f"matches={failure.get('match_count')}, anchors={failure.get('anchor_count')}, "
                                f"identity_matches={failure.get('identity_matches')}, reason={failure.get('validation_reason')}")
                        bundles.append(seed)
                        matching = [len(bundles)-1]
                    eligible_indices.update(matching)
                    if discover is None and not any(locator_accepted(bundles[i].primary,bundles[i].metadata) for i in matching):
                        missing_targets.append({'element_name':definition.get('name',selector) if isinstance(definition,dict) else selector,
                            'final_failure_reason':'required_target_needs_accepted_locator_evidence'})
                    if isinstance(definition, dict) and definition.get("name"):
                        name = definition["name"]
                        for index in matching:
                            bundle = bundles[index]
                            bundles[index] = bundle.model_copy(update={"element_name":name,
                                "primary":bundle.primary.model_copy(update={"element_name":name}),
                                "alternates":[c.model_copy(update={"element_name":name}) for c in bundle.alternates],
                                "metadata":{**bundle.metadata,"aliases":[bundle.element_name]}})
                eligible = [b for i,b in enumerate(bundles) if i in eligible_indices]
                if discover is not None:
                    fallback_result = resolve_with_locator_expert(eligible, page_url=session.page.url,
                        discover=discover, validate=session.validate, capture=session.capture,
                        max_rounds=max_rounds)
                    fallback_result["unresolved_elements"].extend(missing_targets)
                    resolved = fallback_result["resolved_bundles"]
                    keys = {(b.metadata or {}).get("element_identity") or b.element_name for b in eligible}
                    bundles = [b for b in bundles if ((b.metadata or {}).get("element_identity") or b.element_name) not in keys] + resolved
                else:
                    fallback_result = {"unresolved_elements":missing_targets}
            stages['contextual_resolution_seconds']=time.perf_counter()-stage_start
            stage_start=time.perf_counter()
            logger.info('Journey state=%s stage=persistence',state['name'])
            accepted=[b for b in bundles if locator_accepted(b.primary,b.metadata)]
            persist_locators([{"page":state["name"],"locators":accepted}],locators_dir,replace_pages=False)
            stages['persistence_seconds']=time.perf_counter()-stage_start
            result["states"].append({"name":state["name"],"stage_timings":stages,"url":session.page.url,
                                    "accepted":len(accepted),
                                    "unresolved":len(bundles)-len(accepted)+len(fallback_result.get("unresolved_elements", [])),
                                    "llm_calls":fallback_result.get("llm_calls", 0),
                                    "fallback_unresolved":[{"element_name":p.get("original_element_name") or p["element_name"],
                                        "reason":p.get("final_failure_reason"),
                                        "rejected_candidates":p.get("rejected_candidates",[])} for p in fallback_result.get("unresolved_elements", [])]})
    return result
