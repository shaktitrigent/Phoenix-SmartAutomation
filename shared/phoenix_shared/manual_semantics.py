"""Explicit, site-independent step bindings and generation validation."""
import ast
import json
import re
import symtable


def negative_expectation(text):
    """Recognize predicate negation without treating quoted UI labels as grammar."""
    predicate = re.sub(r"`[^`]*`|\"[^\"]*\"|'[^']*'", "", str(text).lower())
    return bool(re.search(r"\b(?:not|no|never|absent)\b", predicate))


def normalize_action(text):
    text = re.sub(r"^(?:Given|When|Then|And|But)\s+", "", str(text).strip(), flags=re.I)
    return re.sub(r"^I\s+", "", text, flags=re.I)


def expectation_parts(text, fields=()):
    """Expand explicit shared predicates without splitting subject lists away."""
    from phoenix_shared.generation_contract import clauses
    visible = re.compile(r'(?:The\s+)?(.+?)\s+(?:are|is)\s+visible\.?$', re.I)
    sentences = re.split(r'(?<=[.!;])\s+', ' '.join(str(text or '').split()))
    result = []
    for sentence in sentences:
        display=re.search(r'\bdisplays?\s+((?:the\s+)?[^.]+(?:field|button|control|input))\.?$',sentence,re.I)
        if display and ',' in display[1] and not re.search(r'\b(?:heading|URL)\b',display[1],re.I):
            prefix=sentence[:display.start()].strip().removesuffix('and').strip()
            if prefix:result.extend(expectation_parts(prefix,fields))
            result.extend(expectation_parts(display[1]+' are visible.',fields));continue
        # Keep trailing lists with a shared predicate intact while separating
        # preceding URL/other outcomes.
        sentence=re.sub(r'^After [\w -]+,\s*', '',sentence,flags=re.I)
        trailing=re.search(r'(?:,\s*(?:and\s+)?|\s+and\s+)((?:the\s+)?[^,]+ field, .+ (?:are|is) visible\.?)$',sentence,re.I)
        if trailing and re.search(r'\b(?:URL|visible|empty)\b',sentence[:trailing.start()],re.I):
            result.extend(expectation_parts(sentence[:trailing.start()],fields))
            result.extend(expectation_parts(trailing[1],fields));continue
        empty_prefix=re.match(r'(Both .+? (?:remain empty|contain empty values))(?=,|\.|$)',sentence,re.I)
        if empty_prefix and empty_prefix.end()<len(sentence.rstrip('.')):
            result.extend(expectation_parts(empty_prefix[1],fields))
            result.extend(expectation_parts(sentence[empty_prefix.end():].lstrip(', ').removeprefix('and '),fields));continue
        match = visible.fullmatch(sentence)
        if match and (',' in match[1] or ' and ' in match[1]):
            subjects = re.split(r',\s*(?:and\s+)?|\s+and\s+', match[1])
            if all(re.search(r'\b(?:field|button|control|input|heading|menu item)\b', s, re.I) for s in subjects):
                result.extend(f'{s.strip()} is visible.' for s in subjects)
                continue
        empty = re.fullmatch(r'Both (.+?) (?:remain empty|contain empty values)\.?', sentence, re.I)
        if empty:
            names = list(fields) if empty[1].lower() in {'credential fields', 'fields'} else re.split(r'\s+and\s+', empty[1], flags=re.I)
            if len(names) >= 2:
                result.extend(f'The {name} field contains an empty value ("").' for name in names)
                continue
        result.extend(clauses(sentence))
    return result


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
    from phoenix_shared.generation_contract import artifact_plan_issues
    issues = artifact_plan_issues(result)
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
