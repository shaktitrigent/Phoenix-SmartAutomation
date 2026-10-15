"""Explicit, site-independent step bindings and generation validation."""
import ast
import json
import re
import symtable


_QUOTED = re.compile(r"`[^`]*`|\"(?:[^\"\\]|\\.)*\"|(?<!\w)'(?:[^'\\]|\\.)*'")


def split_unquoted(pattern, text, *, flags=0):
    """Split grammar delimiters while preserving quoted data and UI labels."""
    text = str(text or '')
    spans = [match.span() for match in _QUOTED.finditer(text)]
    parts = []
    start = 0
    for match in re.finditer(pattern, text, flags):
        if any(left <= match.start() < right for left, right in spans):
            continue
        parts.append(text[start:match.start()])
        start = match.end()
    parts.append(text[start:])
    return parts


def negative_expectation(text):
    """Recognize predicate negation without treating quoted UI labels as grammar."""
    predicate = re.sub(r"`[^`]*`|\"[^\"]*\"|'[^']*'", "", str(text).lower())
    return bool(re.search(r"\b(?:not|no|never|absent)\b", predicate))


def normalize_action(text):
    text = re.sub(r"^(?:Given|When|Then|And|But)\s+", "", str(text).strip(), flags=re.I)
    return re.sub(r"^I\s+", "", text, flags=re.I)


def expectation_parts(text, fields=()):
    """Separate predicates while keeping shared field/control lists together."""
    from phoenix_shared.generation_contract import clauses
    result=[]
    for sentence in split_unquoted(r'(?<=[.!;])\s+', ' '.join(str(text or '').split())):
        sentence=sentence.rstrip(';').strip()
        if not sentence:continue
        masked=re.fullmatch(r'((?:The )?Password field contains the supplied value) and masks it\.?',sentence,re.I)
        if masked:
            result.extend([masked[1]+'.','The password is masked.']);continue
        if re.fullmatch(r'(?:A|The) record is successfully created and searchable when .+? are supplied and .+? is omitted\.?',sentence,re.I):
            result.append(sentence);continue
        display=re.search(r'\bdisplays?\s+((?:the\s+)?[^.]+(?:field|button|control|input))\.?$',sentence,re.I)
        if display and ',' in display[1] and not re.search(r'\b(?:heading|URL)\b',display[1],re.I):
            prefix=sentence[:display.start()].strip().removesuffix('and').strip()
            if prefix:result.extend(expectation_parts(prefix,fields))
            result.extend(expectation_parts(display[1]+' are visible.',fields));continue
        empty_prefix=re.match(r'(Both .+? (?:remain empty|contain empty values|are empty|are blank))(?=,|\.|$)',sentence,re.I)
        if empty_prefix and empty_prefix.end()<len(sentence.rstrip('.')):
            result.extend(expectation_parts(empty_prefix[1],fields))
            result.extend(expectation_parts(sentence[empty_prefix.end():].lstrip(', ').removeprefix('and '),fields));continue
        required=re.fullmatch(r'(?:A\s+)?[`\"]([^`\"]+)[`\"] (?:validation(?: message)?|message) is (?:visible|shown) for (?:both )?(.+?)\.?',sentence,re.I)
        if required:
            names=re.split(r',\s*(?:and\s+)?|\s+and\s+',required[2])
            result.append(f'{len(names)} "{required[1]}" validation messages are visible for '+', '.join(names)+'.');continue
        required=re.fullmatch(r'[`\"]([^`\"]+)[`\"] validation is shown for (.+?)\.?',sentence,re.I)
        if required:
            names=re.split(r',\s*(?:and\s+)?|\s+and\s+',required[2])
            result.append(f'{len(names)} "{required[1]}" validation messages are visible for '+', '.join(names)+'.');continue
        # Shared visibility or empty predicates apply independently to every name.
        match=re.fullmatch(r'(?:The\s+)?(.+?)\s+(?:are|is)\s+(visible|empty|absent)\.?',sentence,re.I)
        if match and (',' in match[1] or ' and ' in match[1]):
            names=re.split(r',\s*(?:and\s+)?|\s+and\s+',match[1]);predicate=match[2]
            shared=re.search(r'\b(controls?|fields?|buttons?)$',names[-1],re.I)
            if shared:
                suffix={'controls':'control','fields':'field','buttons':'button'}.get(shared[1].lower(),shared[1].lower())
                names=[n if re.search(r'\b(fields?|buttons?|controls?|input|heading|menu item)\b',n,re.I) else n+' '+suffix for n in names]
            if all(re.search(r'\b(fields?|buttons?|controls?|input|heading|menu item)\b',n,re.I) for n in names):
                names=[re.sub(r'\b(controls|fields|buttons)$',lambda m:m[1][:-1],n.strip()) for n in names]
                result.extend(f'{n} is {predicate}.' for n in names);continue
        empty=re.fullmatch(r'Both (.+?) (?:are empty|remain empty|contain empty values|are blank)\.?',sentence,re.I)
        if empty:
            names=list(fields) if empty[1].lower() in {'fields','credential fields'} else re.split(r'\s+and\s+',empty[1],flags=re.I)
            if len(names)>=2:
                result.extend(f'The {n} field contains an empty value ("").' for n in names);continue
        # Preserve explicitly named subjects with a shared value predicate.
        shared=re.fullmatch(r'(.+?)\s+(?:show|contain) (?:the )?(?:supplied|entered) values\.?',sentence,re.I)
        if shared:
            names=re.split(r',\s*(?:and\s+)?|\s+and\s+',shared[1])
            if len(names)>1:
                result.extend(f'{n} field contains the supplied value.' for n in names);continue
        result.extend(p.rstrip(';') for p in clauses(sentence))
    return result


def data_bindings(data):
    """Read explicit JSON or semicolon-separated field/value cells."""
    if isinstance(data, dict):
        return data if all(isinstance(k,str) and isinstance(v,str) for k,v in data.items()) else {}
    if not isinstance(data,str):return {}
    try:
        parsed=json.loads(data)
        if isinstance(parsed,dict):return data_bindings(parsed)
    except ValueError:pass
    result={}
    for part in split_unquoted(';', data):
        match=re.fullmatch(r'\s*([^:]+):\s*(.*?)\s*',part)
        if not match:return {}
        key,value=match.groups()
        value=value.strip()
        quoted=bool(_QUOTED.fullmatch(value))
        if quoted:
            # Delimiting quotes are syntax; preserve the value inside them.
            if value.startswith('"'):
                try:value=json.loads(value)
                except ValueError:return {}
            else:value=value[1:-1]
        if not quoted and value.casefold()=='empty':value=''
        result[key.strip()]=value
    return result


def split_actions(text):
    """Split ordered verbs outside quotes; carry only explicit fill grammar."""
    saved=[]
    def hide(m):saved.append(m[0]);return f'QUOTEDTOKEN{len(saved)-1}X'
    hidden=re.sub(r"`[^`]*`|\"(?:[^\"\\]|\\.)*\"|(?<!\w)'(?:[^'\\]|\\.)*'",hide,normalize_action(text))
    verbs=r'enter|type|fill|input|provide|click|press|tap|submit|select|choose|check|uncheck|verify|assert|validate|open|navigate|leave|clear|wait|search'
    if re.search(r'\brespective fields\b',hidden,re.I):
        hidden=re.sub(r'(QUOTEDTOKEN\d+X|\$\{[^}]+\})\s+and\s+(?=QUOTEDTOKEN|\$\{)',r'\1 RESPECTIVEJOIN ',hidden)
    parts=re.split(r';\s*|,?\s+(?:and|then)\s+(?=(?:'+verbs+r')\b)|\s+and\s+(?=(?:QUOTEDTOKEN\d+X|\$\{[A-Za-z_][A-Za-z0-9_]*\})\s+(?:in|into)\b)',hidden,flags=re.I)
    result=[]
    for part in parts:
        part=re.sub(r'QUOTEDTOKEN(\d+)X',lambda m:saved[int(m[1])],part).replace('RESPECTIVEJOIN','and').strip()
        if result and re.match(r"[`\"']|\$\{",part) and re.match(r'(?:enter|fill|type|input|provide)\b',result[-1],re.I):part='Enter '+part
        path=re.fullmatch(r'(?:navigate|go) to (.+?)\s*>\s*(.+)',part,re.I)
        if path:
            result.extend('Click '+p.strip() for p in re.split(r'\s*>\s*',path[1]+' > '+path[2]));continue
        # Navigation qualifiers describe the control, not its accessible name.
        part=re.sub(r'^(Click .+?) in (?:the )?(?:application )?navigation$',r'\1',part,flags=re.I)
        clear=re.fullmatch(r'(clear|leave) (?:the )?(.+?)(?: fields?| empty)\.?',part,re.I)
        if clear and (',' in clear[2] or ' and ' in clear[2]):
            result.extend('Clear '+f.strip()+' field' for f in re.split(r',\s*(?:and\s+)?|\s+and\s+',clear[2]) if f.strip());continue
        part=re.sub(r'^(Leave .+?) empty$',r'\1 field empty',part,flags=re.I) if not re.search(r'field empty$',part,re.I) else part
        if re.match(r'(?:enter|fill|type|input|provide)\b',part,re.I) and re.search(r'\b(?:in|into) (?:the )?[\w -]+$',part,re.I) and not re.search(r'\b(?:field|input|textbox)$',part,re.I):part+=' field'
        result.append(part)
    return result


def bound_actions(action, data):
    """Bind named fields to explicit values; never infer data from business prose."""
    result=[];mapping=data_bindings(data)
    for part in split_actions(action):
        # 'respective fields' needs a complete explicit named mapping.
        respective=re.search(r'\brespective fields\b',part,re.I)
        compound=re.match(r'(?:enter|fill|type|input|provide)\b',part,re.I) and not re.search(r'\b(?:in|into)\b',part,re.I)
        if mapping and (respective or compound):
            if compound and not respective:
                targets=re.sub(r'^(?:enter|fill|type|input|provide)\s+','',part,flags=re.I)
                names=[re.sub(r'\b(?:the|valid|invalid|field|fields)\b','',n,flags=re.I).strip() for n in re.split(r'\s+and\s+|,',targets,flags=re.I)]
                if not re.search(r'[`\"\']',targets) and {n.casefold() for n in names}!={k.casefold() for k in mapping}:return []
            values=re.findall(r'\$\{[^}]+\}',part)
            if values and all(v in ' '.join(mapping.values()) for v in values):
                result.extend(f"Enter {v!r} in the {k} field" for k,v in mapping.items());continue
            if not values and all(re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',part,re.I) for k in mapping):
                result.extend(f"Enter {v!r} in the {k} field" for k,v in mapping.items());continue
        result.append(part)
    return result


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
