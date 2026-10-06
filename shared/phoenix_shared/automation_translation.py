"""Conservative, website-independent helpers for manual test translation."""

import ast
import re


def environment_reference(value: str) -> str | None:
    """Recognize explicit references only; never infer a variable from a field."""
    text = value.strip().strip("`\"'")
    patterns = (
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
        r"\$([A-Za-z_][A-Za-z0-9_]*)",
        r"(?:the\s+)?value\s+from\s+[`\"']?([A-Za-z_][A-Za-z0-9_]*)[`\"']?",
        r"(?:environment\s+variable|env\s+var)\s+[`\"']?([A-Za-z_][A-Za-z0-9_]*)[`\"']?",
        r"(TEST_[A-Z0-9_]+)",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text)
        if match:
            return match.group(1)
    # Only accept a subscript lookup, never arbitrary Python supplied as data.
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"
            and node.value.attr == "environ" and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)):
        return node.slice.value
    return None


def fill_value_expression(value: str) -> str:
    key = environment_reference(value)
    return f"os.environ[{key!r}]" if key else repr(value)


def resolve_script_environment_values(script: str) -> str:
    """Resolve explicit env tokens only in fill operations, preserving literals."""
    tree = ast.parse(script)
    lines = script.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line.encode("utf-8"))
    raw = script.encode("utf-8")
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        position = 2 if name == "fill_ready" else 0 if name in {"fill", "type"} else None
        if name in {"fill", "type"} and len(node.args) >= 2:
            position = 1
        values = [node.args[position]] if position is not None and len(node.args) > position else []
        if position is not None:
            values.extend(k.value for k in node.keywords if k.arg in {"value", "text"})
        for arg in values:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                key = environment_reference(arg.value)
                if key:
                    start = offsets[arg.lineno - 1] + arg.col_offset
                    end = offsets[arg.end_lineno - 1] + arg.end_col_offset
                    edits.append((start, end, f"os.environ[{key!r}]".encode()))
    needs_os = edits or any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "os" for n in ast.walk(tree))
    if needs_os and not any(isinstance(n, ast.Import) and any(a.name == "os" and a.asname in {None, "os"} for a in n.names) for n in tree.body):
        index = 0
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
            index = 1
        while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == "__future__":
            index += 1
        at = offsets[tree.body[index].lineno - 1] if index < len(tree.body) else len(raw)
        edits.append((at, at, b"import os\n"))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    result = raw.decode("utf-8")
    ast.parse(result)
    return result


def select_page_fixture(code: str, fixture: str) -> str:
    """Keep the local page binding while selecting a different pytest fixture.

    Renaming arbitrary nested references is unsafe. An alias keeps closures,
    strings and helper scopes intact and also works when reversing the selection.
    """
    tree = ast.parse(code)
    lines = code.splitlines(keepends=True)
    offsets = []
    total = 0
    for line in lines:
        offsets.append(total)
        total += len(line.encode("utf-8"))
    raw = code.encode("utf-8")
    edits = []
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not fn.name.startswith("test_"):
            continue
        args = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
        pages = [arg for arg in args if arg.arg in {"page", "authenticated_page", "intelligent_page"}]
        if len(pages) != 1 or pages[0].arg == fixture:
            continue
        arg = pages[0]
        if any(a.arg == fixture for a in args):
            raise ValueError("Conflicting page fixture parameters")
        start = offsets[arg.lineno - 1] + arg.col_offset
        edits.append((start, start + len(arg.arg), fixture.encode()))
        body = fn.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        if not body:
            continue
        first = body[0]
        # Inline suites need a semicolon; multiline suites preserve indentation.
        at = offsets[first.lineno - 1] + first.col_offset
        prefix = lines[first.lineno - 1][:first.col_offset]
        alias = f"{arg.arg} = {fixture}"
        if prefix.strip():
            insertion = alias + "; "
        else:
            insertion = alias + "\n" + prefix
        edits.append((at, at, insertion.encode()))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    result = raw.decode("utf-8")
    ast.parse(result)
    return result


def bind_page_object_body(body: str) -> str:
    """Rebind only Python identifiers; UI text and test data remain unchanged."""
    tree = ast.parse(body)
    lines = body.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line.encode("utf-8"))
    raw = body.encode("utf-8")
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "page" and isinstance(node.ctx, ast.Load):
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            edits.append((start, end))
    for start, end in sorted(edits, reverse=True):
        raw = raw[:start] + b"self._page" + raw[end:]
    return raw.decode("utf-8")


def assertion_lines(expected: str, *, action: str = "", locator: str | None = None,
                    value: str | None = None) -> list[str]:
    """Translate explicit expected evidence; prose alone is not UI evidence."""
    text = expected.strip()
    low = text.lower()
    if not text:
        return []
    if locator and value is not None and re.fullmatch(
            r"The password field contains the supplied value and masks its display\.?", text, re.I):
        return [f"    expect({locator}).to_have_value({value}, timeout=ASSERTION_TIMEOUT_MS)",
                f"    expect({locator}).to_have_attribute('type', 'password', timeout=ASSERTION_TIMEOUT_MS)"]
    # A compound expected result needs separate checks; never verify only half.
    unquoted = re.sub(r"`[^`]*`|\"[^\"]*\"|'[^']*'", "", text)
    if re.search(r"\b(?:and|followed by)\b", unquoted, re.IGNORECASE):
        return []
    negative = bool(re.search(r"\b(?:not|no longer|never)\b", low))
    quoted = re.findall(r"`([^`]*)`|\"([^\"]*)\"|'([^']*)'", text)
    values = [next((v for v in group if v), "") for group in quoted]
    
    # Cart arithmetic: price × quantity, subtotal, total calculations
    cart_keywords = {"cart", "total", "subtotal", "price", "quantity", "amount", "sum", "calculate", "×", "*"}
    if any(kw in low for kw in cart_keywords):
        # Detect numerical comparison requirements
        if any(word in low for word in ("equals", "is", "should be", "matches", "match", "calculated")):
            # Require explicit locator for cart arithmetic - no hardcoded defaults
            if not locator:
                return []  # Cannot generate safe assertion without validated locator
            
            # Generate numerical comparison assertion
            # Extract numeric values from the expected result
            numbers = re.findall(r'[\d,]+\.?\d*', text)
            lines = [
                "    # Cart arithmetic: read displayed value and perform calculation",
                f"    displayed_text = {locator}.inner_text()",
                "    displayed_value = float(displayed_text.replace('$', '').replace(',', '').strip())",
            ]
            # Add calculation if arithmetic is mentioned
            if "multiply" in low or "×" in text or "*" in text:
                lines.append("    calculated_value = quantity * price")
            elif "sum" in low or "add" in low:
                lines.append("    calculated_value = sum(item_prices)")
            elif numbers:
                lines.append(f"    calculated_value = float({numbers[0]})")
            else:
                lines.append("    calculated_value = expected_total  # Replace with actual expected value")
            
            comparison = "!=" if negative else "=="
            if numbers:
                lines.append(f"    assert displayed_value {comparison} calculated_value, f\"Cart arithmetic failed: expected {numbers[0]}, got {{displayed_value}}\"")
            else:
                lines.append(f"    assert displayed_value {comparison} calculated_value, \"Cart arithmetic failed\"")
            return lines
    
    # Address comparison: validate address details match expected values
    address_keywords = {"address", "street", "city", "state", "zip", "postal", "country", "billing", "shipping"}
    if any(kw in low for kw in address_keywords):
        if any(word in low for word in ("matches", "equals", "is", "should be", "displayed")):
            # Require explicit locator for address comparison - no hardcoded defaults
            if not locator:
                return []  # Cannot generate safe assertion without validated locator
            
            # Generate address comparison assertion
            if values:
                lines = [
                    "    # Address comparison: read displayed address and validate",
                    f"    displayed_address = {locator}.inner_text()",
                    "    displayed_address = ' '.join(displayed_address.split())  # Normalize whitespace",
                ]
                if len(values) == 1:
                    lines.append(f"    expected_address = {values[0]!r}")
                else:
                    # Multiple address components
                    lines.append(f"    expected_parts = {values!r}")
                    lines.append("    expected_address = ' '.join(expected_parts)")
                
                comparison = "!=" if negative else "=="
                lines.append(f"    assert displayed_address {comparison} expected_address, f\"Address mismatch: expected {{expected_address}}, got {{displayed_address}}\"")
                return lines
    
    if "url" in low:
        match = re.search(r"https?://[^\s`\"']+|(?<!\w)/[\w/?=&.%#~-]+", text)
        if not match:
            return []
        target = match.group().rstrip(".,;")
        if re.search(r"\b(?:equals|is exactly)\b", low):
            argument = repr(target)
        else:
            argument = f"re.compile({re.escape(target)!r})"
        method = "not_to_have_url" if negative else "to_have_url"
        return [f"    expect(page).{method}({argument}, timeout=ASSERTION_TIMEOUT_MS)"]
    if "title" in low and values:
        method = "not_to_have_title" if negative else "to_have_title"
        return [f"    expect(page).{method}({values[0]!r}, timeout=ASSERTION_TIMEOUT_MS)"]
    if locator and ("contains the value" in low or "field contains" in low or "value is" in low):
        expr = fill_value_expression(values[0]) if values else value
        if expr is None:
            return []
        return [f"    expect({locator}).to_have_value({expr}, timeout=ASSERTION_TIMEOUT_MS)"]
    target = locator
    # Quoted message/heading is supplied UI evidence, unlike an instruction label.
    if values and any(word in low for word in ("message", "text", "heading", "visible", "displayed", "shown")):
        target = f"page.get_by_text({values[0]!r}, exact=True)"
    if target and any(word in low for word in ("visible", "displayed", "shown", "appears", "enabled", "disabled", "checked", "unchecked")):
        if "unchecked" in low:
            method = "not_to_be_checked"
        elif "checked" in low:
            method = "not_to_be_checked" if negative else "to_be_checked"
        elif "disabled" in low:
            method = "to_be_disabled"
        elif "enabled" in low:
            method = "not_to_be_enabled" if negative else "to_be_enabled"
        else:
            method = "not_to_be_visible" if negative else "to_be_visible"
        return [f"    expect({target}).{method}(timeout=ASSERTION_TIMEOUT_MS)"]
    return []


_ACTIONS = {
    "fill": {"fill", "type", "enter", "input", "provide"},
    "click": {"click", "press", "tap", "submit"},
    "goto": {"navigate", "visit", "open", "go"},
    "select_option": {"select", "choose"},
    "check": {"check", "tick"}, "uncheck": {"uncheck", "untick"},
    "hover": {"hover"}, "drag_to": {"drag"},
    "expect": {"verify", "assert", "ensure", "confirm", "validate"},
}
_FILLER = {"the", "and", "with", "from", "into", "that", "then", "field", "input", "button", "value", "page", "user", "should", "visible", "displayed"}


def step_coverage(script: str, steps: list) -> dict:
    """Conservative static coverage; comments and unrelated helpers never count.

    This is translation evidence, not proof that browser behavior passes.
    Each executable operation can satisfy at most one manual operation.
    """
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return {"implemented_steps": 0, "unresolved_steps": list(range(1, len(steps) + 1))}
    operations = []
    tests = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
    for fn in tests:
        for statement in fn.body:
            # Do not count a nested helper's implementation or a docstring.
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == "pytest"
                   and n.func.attr in {"skip", "fail"} for n in ast.walk(statement)):
                break
            for node in ast.walk(statement):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                kind = {"fill_ready": "fill", "click_ready": "click"}.get(name, name)
                if name.startswith(("to_", "not_to_")):
                    kind = "expect"
                if kind not in _ACTIONS:
                    continue
                if kind == "expect" and (name == "expect" or "locator('body')" in ast.unparse(node) or 'locator("body")' in ast.unparse(node)):
                    continue
                tokens = set(re.findall(r"[a-z0-9]+", ast.unparse(node).lower())) - _FILLER
                operations.append((kind, tokens))
    consumed = set()
    unresolved = []
    for index, step in enumerate(steps, 1):
        action = str(step.get("action") or step.get("step") or "") if isinstance(step, dict) else str(step)
        parts = re.split(r"\s+(?:and|then)\s+(?=(?:enter|type|fill|click|press|select|verify|assert)\b)", action, flags=re.I)
        pending = set()
        complete = True
        for part in parts:
            words = set(re.findall(r"[a-z0-9]+", part.lower()))
            kinds = {kind for kind, aliases in _ACTIONS.items() if words & aliases}
            meaningful = words - _FILLER - set().union(*_ACTIONS.values())
            found = next((i for i, (kind, tokens) in enumerate(operations)
                          if i not in consumed | pending and kind in kinds and meaningful & tokens), None)
            if found is None:
                complete = False
                break
            pending.add(found)
        expected = str(step.get("expected_result") or "") if isinstance(step, dict) else ""
        if complete and expected and not any(operations[i][0] == "expect" for i in pending):
            tokens = set(re.findall(r"[a-z0-9]+", expected.lower())) - _FILLER
            assertion = next((i for i, (kind, evidence) in enumerate(operations)
                              if i not in consumed | pending and kind == "expect" and tokens & evidence), None)
            if assertion is None:
                complete = False
            else:
                pending.add(assertion)
        if complete:
            consumed.update(pending)
        else:
            unresolved.append(index)
    return {"implemented_steps": len(steps) - len(unresolved), "unresolved_steps": unresolved}


def explicit_step_data(action: str, test_data) -> str:
    """Bind a single fill action to its supplied scalar data, without guessing.

    Multi-field prose remains unresolved. A quoted empty string is explicit data.
    """
    if not isinstance(test_data, str) or not test_data.strip():
        return action
    if not re.match(r"(?:enter|type|fill|input|provide)\b", action, re.I):
        return action
    if re.search(r"\b(?:and|then)\b", action, re.I):
        return action
    target = re.search(r"\b(?:in|into)\s+(?:the\s+)?(.+?)\s+(?:field|input)\.?$", action, re.I)
    if not target:
        return action
    data = test_data.strip()
    if data.startswith("`") and data.endswith("`"):
        data = data[1:-1]
    elif data.startswith(('"', "'")):
        try:
            literal = ast.literal_eval(data)
        except (SyntaxError, ValueError):
            return action
        if not isinstance(literal, str):
            return action
        data = literal
    # A structured/multiple-value cell cannot safely bind to one field.
    if not environment_reference(data) and re.search(r"[;\n]|\$\{.*\}.*\$\{", data):
        return action
    return f"Enter {data!r} in the {target.group(1)} field"


def fill_operation_evidence(lines: list[str]) -> tuple[str | None, str | None]:
    """Use the actual fill target/value for its corresponding assertion."""
    try:
        tree = ast.parse("\n".join(line.strip() for line in lines))
    except SyntaxError:
        return None, None
    fills = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "fill_ready"
             and len(n.args) >= 3]
    if len(fills) != 1:
        return None, None
    return ast.unparse(fills[0].args[1]), ast.unparse(fills[0].args[2])
