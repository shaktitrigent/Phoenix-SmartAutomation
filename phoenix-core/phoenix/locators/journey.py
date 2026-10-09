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


def capture_journey(application_url, states_file, output_dir, locators_dir, *, values=None, storage_state=None):
    from phoenix_smartlocatorai.dynamic_states import scan_dynamic_states
    definitions = json.loads(Path(states_file).read_text(encoding="utf-8"))
    states = prepare_states(definitions.get("states") if isinstance(definitions, dict) else definitions, values if values is not None else dict(os.environ))
    manifest = scan_dynamic_states(application_url, states, output_dir, storage_state=storage_state)
    for state in manifest["states"]:
        bundles = convert_file(state["locators_json"], page=state["name"])
        persist_locators([{"page": state["name"], "locators": bundles}], locators_dir)
    return manifest
