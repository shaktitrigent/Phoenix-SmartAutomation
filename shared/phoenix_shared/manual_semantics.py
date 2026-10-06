"""Explicit, site-independent step bindings and generation validation."""
import ast
import json
import re
import symtable


def normalize_action(text):
    text = re.sub(r"^(?:Given|When|Then|And|But)\s+", "", str(text).strip(), flags=re.I)
    return re.sub(r"^I\s+", "", text, flags=re.I)


def bound_actions(action, data):
    """JSON field/value maps expand fills; unspecified prose never supplies values."""
    action = normalize_action(action)
    if isinstance(data, str):
        try:
            mapping = json.loads(data)
        except (ValueError, TypeError):
            mapping = None
    else:
        mapping = data
    if isinstance(mapping, dict) and re.match(r"(?:enter|fill|type|input|provide)\b", action, re.I):
        fields = list(mapping)
        if not fields or any(not isinstance(k, str) or not isinstance(v, str) for k,v in mapping.items()):
            return []
        # Binding keys must occur as field names in the supplied action.
        if any(not re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", action, re.I) for k in fields):
            return []
        targets = re.sub(r"^(?:enter|fill|type|input|provide)\s+", "", action, flags=re.I)
        if " and " in targets.lower() and not any(c in targets for c in "'\""):
            for target in re.split(r"\s+and\s+|,", targets, flags=re.I):
                target = re.sub(r"\b(?:valid|invalid|the|field|fields)\b", "", target, flags=re.I).strip()
                if target and target.casefold() not in {k.casefold() for k in fields}:
                    return []
        return [f"Enter {v!r} in the {k} field" for k,v in mapping.items()]
    return [action]


def unresolved_dependencies(code):
    """Find global names absent from the module and Python builtins."""
    import builtins
    table = symtable.symtable(code, "<generated>", "exec")
    available = set(vars(builtins)) | {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported()} | {"__name__"}
    missing = set()
    def walk(t):
        for symbol in t.get_symbols():
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in available:
                missing.add(symbol.get_name())
        for child in t.get_children(): walk(child)
    walk(table)
    return sorted(missing)


def final_artifact_issues(result):
    issues = []
    artifacts = [("flat", result.get("script_code", ""))]
    for key in ("pom_bundle", "bdd_bundle"):
        for section in ("page_objects", "steps", "tests"):
            artifacts.extend((section, node.get("code", "")) for node in (result.get(key) or {}).get(section, []))
    for label, code in artifacts:
        if not code: continue
        try:
            compile(code, "<generated>", "exec")
            ast.parse(code)
            missing = unresolved_dependencies(code)
            if missing: issues.append(f"{label}: undefined names: {', '.join(missing)}")
        except (SyntaxError, ValueError):
            issues.append(f"{label}: invalid Python")
    return issues
