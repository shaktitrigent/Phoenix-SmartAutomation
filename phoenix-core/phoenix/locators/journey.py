"""Capture caller-specified browser states and persist page-scoped bundles."""
import json
import os
import re
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
        for state in states:
            for action in state.get("actions",[]):
                _execute_state_action(session.page,action)
            if state.get("wait_for_selector"):
                session.page.wait_for_selector(state["wait_for_selector"])
            session.state_name=state["name"]
            bundles=session.scan(page=state["name"],output_dir=Path(output_dir)/state["name"],
                identity_policies=state.get('identity_policies'))
            fallback_result = {}
            if state.get("fallback_targets"):
                from phoenix.locators.live_session import _DESCRIBE, identity_matches
                from phoenix.locators.smartlocator_fallback import resolve_with_locator_expert
                eligible_indices = set()
                missing_targets = []
                for definition in state["fallback_targets"]:
                    selector = definition.get("selector") if isinstance(definition, dict) else definition
                    target = session.page.locator(selector)
                    if target.count() != 1:
                        raise ValueError("Each scoped fallback target must identify one physical node")
                    def matches(bundle):
                        expected = (bundle.metadata or {}).get('element_data') or {}
                        try: descriptor = target.evaluate(_DESCRIBE, expected.get('content_identity'))
                        except Exception: return False
                        return identity_matches(descriptor,expected)
                    matching = [i for i, b in enumerate(bundles) if matches(b)]
                    eligible_indices.update(matching)
                    if not matching:
                        missing_targets.append({"element_name":definition.get("name", selector) if isinstance(definition, dict) else selector,
                            "final_failure_reason":"required_target_not_captured"})
                    elif isinstance(definition, dict) and definition.get("name"):
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
            accepted=[b for b in bundles if locator_accepted(b.primary,b.metadata)]
            persist_locators([{"page":state["name"],"locators":accepted}],locators_dir,replace_pages=True)
            result["states"].append({"name":state["name"],"url":session.page.url,
                                    "accepted":len(accepted),
                                    "unresolved":len(bundles)-len(accepted)+len(fallback_result.get("unresolved_elements", [])),
                                    "llm_calls":fallback_result.get("llm_calls", 0),
                                    "fallback_unresolved":[{"element_name":p["element_name"],
                                        "reason":p.get("final_failure_reason")} for p in fallback_result.get("unresolved_elements", [])]})
    return result
