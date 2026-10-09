"""Deterministic enforcement of validated locator evidence in generated code."""

from __future__ import annotations

import ast
import re
from typing import Any, Iterable


_ROLE_WORDS = {
    "button": {"button"},
    "input": {"input", "field", "textbox"},
    "link": {"link", "anchor"},
    "checkbox": {"checkbox"},
    "combobox": {"combobox", "dropdown", "select"},
}
_NON_NAME_SUFFIXES = {"input", "field", "element", "control"}
_ACTION_WORDS = {
    "given", "when", "then", "and", "but", "enter", "type", "fill", "click",
    "press", "tap", "select", "choose", "pick", "verify", "check", "assert",
    "ensure", "confirm", "navigate", "open", "visit", "locate", "find", "the",
    "a", "an", "i", "we", "you", "my", "your", "in", "into", "on", "to",
    "for", "of", "from", "with", "please", "value", "using", "use", "should",
    "be", "is", "are", "was", "were", "displayed", "visible", "shown", "field",
    "input", "button", "element", "control", "textbox", "page", "locator", "get",
    "by", "role", "name", "hastext", "filter", "form", "div",
}
_ROLE_TOKENS = {token for aliases in _ROLE_WORDS.values() for token in aliases}
_TOKEN_FILLER = {"test", "data", "user", "name"}


def normalize_element_name(value: object) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _semantic_tokens(value: object) -> frozenset[str]:
    """Remove action phrasing and test-data placeholders, retaining identity words."""
    text = str(value or "")
    text = re.sub(r"\bTEST_[A-Z0-9_]+\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return frozenset(
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if token not in _ACTION_WORDS and token not in _TOKEN_FILLER
    )


def _name_forms(value: object) -> set[str]:
    normalized = normalize_element_name(value)
    if not normalized:
        return set()
    words = normalized.split()
    forms = {normalized}
    if words[-1] in _NON_NAME_SUFFIXES:
        forms.add(" ".join(words[:-1]))
    return {form for form in forms if form}


def _bundle_aliases(bundle: dict[str, Any]) -> set[str]:
    metadata = bundle.get("metadata") or {}
    values: list[object] = [
        bundle.get("element_name"), bundle.get("element_id"),
        metadata.get("bundle_element_name"), metadata.get("custom_name"),
    ]
    source_names = metadata.get("source_names", [])
    values.extend(source_names if isinstance(source_names, list) else [source_names])
    for locator in [bundle.get("primary"), *(bundle.get("alternates") or [])]:
        if not isinstance(locator, dict):
            continue
        values.extend([locator.get("element_name"), locator.get("element_id")])
        locator_metadata = locator.get("metadata") or {}
        values.extend([locator_metadata.get("custom_name"), locator_metadata.get("element_name")])
    return {form for value in values for form in _name_forms(value)}


def _bundle_identity_profiles(bundle: dict[str, Any]) -> list[frozenset[str]]:
    """Return element-name profiles, plus profiles qualified by their own context."""
    metadata = bundle.get("metadata") or {}
    names: list[object] = [
        bundle.get("element_name"),
        bundle.get("element_id"),
        metadata.get("bundle_element_name"),
        metadata.get("custom_name"),
    ]
    source_names = metadata.get("source_names", [])
    names.extend(source_names if isinstance(source_names, list) else [source_names])
    contexts: list[object] = []

    def add_element_data(element_data: object) -> None:
        if not isinstance(element_data, dict):
            return
        names.extend(
            element_data.get(key)
            for key in ("aria-label", "aria_label", "accessible_name", "placeholder", "name", "id", "text", "label")
        )
        contexts.extend(
            element_data.get(key)
            for key in ("container_text", "section_context", "form_context", "form_name", "container_id", "container_testid")
        )
        ancestor = element_data.get("ancestor_context")
        if isinstance(ancestor, dict):
            contexts.extend(ancestor.values())

    add_element_data(metadata.get("element_data"))
    raw_records = metadata.get("smartlocator_raw_records", [])
    if isinstance(raw_records, list):
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            names.extend(record.get(key) for key in ("custom_name", "element_name", "label"))
            add_element_data(record.get("element_data"))
            ancestor = record.get("ancestor_context")
            if isinstance(ancestor, dict):
                contexts.extend(ancestor.values())

    context_profiles = [tokens for value in contexts if (tokens := _semantic_tokens(value))]
    profiles: list[frozenset[str]] = []
    for value in names:
        tokens = _semantic_tokens(value)
        if tokens:
            profiles.append(tokens)
            profiles.extend(tokens | context for context in context_profiles)

    for locator in [bundle.get("primary"), *(bundle.get("alternates") or [])]:
        if not isinstance(locator, dict):
            continue
        locator_metadata = locator.get("metadata") or {}
        names.extend(locator.get(key) for key in ("element_name", "element_id"))
        names.extend(locator_metadata.get(key) for key in ("custom_name", "element_name"))
        add_element_data(locator_metadata.get("element_data"))
        if str(locator.get("strategy", "")).casefold() == "context":
            tokens = _semantic_tokens(locator.get("value"))
            if tokens:
                profiles.append(tokens)
                profiles.extend(tokens | context for context in context_profiles)

    return list(dict.fromkeys(profiles))


def _bundle_role(bundle: dict[str, Any]) -> str | None:
    metadata = bundle.get("metadata") or {}
    element_data = metadata.get("element_data") or {}
    if not isinstance(element_data, dict):
        element_data = {}
    locator_metadata = (bundle.get("primary") or {}).get("metadata") or {}
    locator_data = locator_metadata.get("element_data") or {}
    if not isinstance(locator_data, dict):
        locator_data = {}
    tag = str(element_data.get("tag") or locator_data.get("tag") or "").casefold()
    role = str(element_data.get("role") or locator_data.get("role") or "").casefold()
    input_type = str(element_data.get("type") or locator_data.get("type") or "").casefold()
    if role in _ROLE_WORDS:
        return role
    if tag == "input" and input_type in {"submit", "button", "reset", "image"}:
        return "button"
    if tag in {"input", "textarea"}:
        return "input"
    if tag == "button":
        return "button"
    if tag == "a":
        return "link"
    if input_type == "checkbox":
        return "checkbox"
    return None


def _role_compatible(label: str, bundle: dict[str, Any]) -> bool:
    words = set(normalize_element_name(label).split())
    requested = {role for role, aliases in _ROLE_WORDS.items() if words & aliases}
    actual = _bundle_role(bundle)
    return not requested or actual is None or actual in requested


def bundle_matches_element(label: str, bundle: dict[str, Any]) -> bool:
    """Return whether semantic identity and element-role evidence match."""
    query = _semantic_tokens(label) - _ROLE_TOKENS
    return bool(query) and any(
        query.issubset(profile)
        for profile in _bundle_identity_profiles(bundle)
    ) and _role_compatible(label, bundle)


def _bundle_match_score(
    label: str,
    bundle: dict[str, Any],
    *,
    context: str = "",
) -> tuple[int, int, int] | None:
    query = _semantic_tokens(label) - _ROLE_TOKENS
    if not query or not _role_compatible(label, bundle):
        return None
    context_tokens = (_semantic_tokens(context) - _ROLE_TOKENS) - query
    matching = [
        profile for profile in _bundle_identity_profiles(bundle)
        if query.issubset(profile)
    ]
    if not matching:
        return None
    return max(
        (
            len(query),
            len(profile & context_tokens),
            -len(profile - query - context_tokens),
        )
        for profile in matching
    )


def match_locator_bundle(
    label: str,
    bundles: Iterable[dict[str, Any]],
    *,
    context: str = "",
    page: str | None = None,
) -> dict[str, Any] | None:
    """Match a generated element label to one unambiguous validated bundle."""
    query_tokens = _semantic_tokens(label) - _ROLE_TOKENS
    if not query_tokens:
        return None
    matches = []
    for order, bundle in enumerate(bundles):
        if page is not None and str(bundle.get("page", "")) != page:
            continue
        metadata = bundle.get("metadata") or {}
        score = _bundle_match_score(label, bundle, context=context)
        if score is None:
            continue
        usable = []
        for candidate in [bundle.get("primary"), *(bundle.get("alternates") or [])]:
            if not isinstance(candidate, dict):
                continue
            value = candidate.get("value") or candidate.get("selector")
            candidate_metadata = candidate.get("metadata") or {}
            status = str(candidate_metadata.get("status", metadata.get("status", ""))).casefold()
            from phoenix.locators.smartlocator_fallback import has_positional_selector

            if (
                isinstance(value, str) and value.strip()
                and candidate.get("verified_in_snapshot") is True
                and not candidate.get("broken") and not candidate.get("unresolved")
                and not metadata.get("broken") and not metadata.get("unresolved")
                and not candidate_metadata.get("broken") and not candidate_metadata.get("unresolved")
                and status not in {"broken", "unresolved", "invalid"}
                and not has_positional_selector(str(value))
            ):
                usable.append(candidate)
        if usable:
            identity = (str(bundle.get("page", "")), metadata["element_identity"]) if metadata.get("element_identity") else None
            matches.append((score, order, identity, bundle, usable))

    if not matches:
        return None
    best_score = max(score for score, *_ in matches)
    matches = [match for match in matches if match[0] == best_score]
    identities = {identity for _, _, identity, _, _ in matches if identity}
    if len(matches) > 1 and (
        len(identities) != 1 or any(identity is None for _, _, identity, _, _ in matches)
    ):
        # Identical physical evidence and selector may be reusable on several
        # pages (e.g. a shared navigation link). Record every page instead of
        # treating that safe reuse as a new LocatorExpert target.
        physical_ids = {identity[1] for _, _, identity, _, _ in matches if identity}
        selections = {
            (str(usable[0].get("strategy", "css")),
             str(usable[0].get("value") or usable[0].get("selector") or ""))
            for _, _, _, _, usable in matches
        }
        if len(physical_ids) != 1 or any(identity is None for _, _, identity, _, _ in matches) or len(selections) != 1:
            return None
    _, _, _, bundle, usable = matches[0]
    primary = bundle.get("primary")
    selected = next((item for item in usable if item is primary), None)
    selected = selected or usable[0]
    metadata = bundle.get("metadata") or {}
    source = (
        (selected.get("metadata") or {}).get("locator_source")
        or metadata.get("locator_source")
        or ("stored_primary" if primary is selected else "stored_alternate")
    )
    strategy = str(selected.get("strategy", "css")).casefold()
    value = str(selected.get("value") or selected.get("selector") or "").strip()
    try:
        from phoenix_shared.models.locator import Locator, LocatorStrategy

        strategy_value = LocatorStrategy(strategy)
        rendered = Locator(
            element_name=str(bundle.get("element_name") or label),
            strategy=strategy_value,
            value=value,
            verified_in_snapshot=True,
        ).to_playwright()
        ast.parse(rendered, mode="eval")
    except (ValueError, TypeError, SyntaxError):
        return None

    result = dict(bundle)
    result_metadata = dict(metadata)
    result_metadata["locator_source"] = source
    result_metadata["matched_pages"] = sorted({str(item[3].get("page", "")) for item in matches})
    result["metadata"] = result_metadata
    result_primary = dict(selected)
    result_primary["metadata"] = {
        **(selected.get("metadata") or {}),
        "locator_source": source,
    }
    result["primary"] = result_primary
    result["alternates"] = [
        {
            **item,
            "metadata": {
                **(item.get("metadata") or {}),
                "locator_source": "stored_alternate",
            },
        }
        for item in usable
        if item is not selected
    ]
    return result


def _root_expression(node: ast.expr) -> ast.expr:
    current = node
    while isinstance(current, ast.Call):
        current = current.func.value if isinstance(current.func, ast.Attribute) else current.func
    while isinstance(current, ast.Attribute):
        if current.attr == "_page":
            return current
        current = current.value
    if isinstance(current, ast.Name) and current.id == "page":
        return current
    return ast.Name(id="page", ctx=ast.Load())


class _PageRoot(ast.NodeTransformer):
    def __init__(self, root: ast.expr) -> None:
        self.root = root

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if node.id == "page":
            return ast.copy_location(self.root, node)
        return node


def _render_for_root(bundle: dict[str, Any], root: ast.expr) -> str:
    from phoenix_shared.models.locator import Locator, LocatorStrategy

    primary = bundle["primary"]
    strategy = LocatorStrategy(str(primary.get("strategy", "css")).casefold())
    locator = Locator(
        element_name=str(bundle.get("element_name", "element")),
        strategy=strategy,
        value=str(primary.get("value") or primary.get("selector") or "").strip(),
        verified_in_snapshot=True,
    )
    expression = ast.parse(locator.to_playwright(), mode="eval").body
    return ast.unparse(_PageRoot(root).visit(expression))


def reconcile_generated_code(
    source: str,
    bundles: Iterable[dict[str, Any]],
    *,
    page: str | None = None,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Replace generated locator expressions with validated bundle selectors.

    Only locator expression spans are changed. Other generated source, including
    interaction values and comments, is preserved byte-for-byte.
    """
    tree = ast.parse(source)
    bundle_list = list(bundles)
    lines = source.splitlines(keepends=True)
    byte_offsets = []
    total = 0
    for line in lines:
        byte_offsets.append(total)
        total += len(line.encode("utf-8"))
    source_bytes = source.encode("utf-8")
    edits: list[tuple[int, int, bytes]] = []
    used: list[dict[str, Any]] = []
    unresolved: list[str] = []
    seen_used: set[tuple[str, str, str]] = set()

    def span(node: ast.AST) -> tuple[int, int]:
        start = byte_offsets[node.lineno - 1] + node.col_offset
        end = byte_offsets[node.end_lineno - 1] + node.end_col_offset
        return start, end

    def process_target(target: ast.expr, label: str) -> None:
        context = _preceding_step_context(target, lines)
        selected = match_locator_bundle(label, bundle_list, context=context, page=page)
        if selected is None:
            unresolved.append(label)
            return
        root = _root_expression(target)
        rendered = _render_for_root(selected, root).encode("utf-8")
        start, end = span(target)
        edits.append((start, end, rendered))
        primary = selected["primary"]
        identity = (str(selected.get("page", "")), str(selected.get("element_name", "")), str(primary.get("value", "")))
        if identity not in seen_used:
            seen_used.add(identity)
            used.append(selected)

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            function_name = node.func.id if isinstance(node.func, ast.Name) else ""
            if function_name.endswith("_ready") and len(node.args) >= 2:
                string_labels = [arg.value for arg in node.args[2:] if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
                if string_labels:
                    process_target(node.args[1], string_labels[-1])
                    for arg in node.args[2:]:
                        self.visit(arg)
                    return
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "get_by_role", "get_by_label", "get_by_placeholder", "get_by_test_id",
                "get_by_text", "get_by_alt_text", "get_by_title",
            }:
                method = node.func.attr
                label_node = next((kw.value for kw in node.keywords if kw.arg == "name"), None) if method == "get_by_role" else (node.args[0] if node.args else None)
                if isinstance(label_node, ast.Constant) and isinstance(label_node.value, str):
                    label = label_node.value.strip()
                    if method == "get_by_role" and node.args and isinstance(node.args[0], ast.Constant):
                        label += " " + str(node.args[0].value)
                    process_target(node, label)
                    return
            if isinstance(node.func, ast.Attribute) and node.func.attr == "locator" and node.args:
                selector = node.args[0]
                if isinstance(selector, ast.Constant) and isinstance(selector.value, str):
                    raw = selector.value.strip()
                    label = raw.lstrip("#.").replace("-", " ").replace("_", " ")
                    selected = match_locator_bundle(label, bundle_list, context=_preceding_step_context(node, lines), page=page)
                    if selected is not None:
                        process_target(node, label)
                        return
            self.generic_visit(node)

    Visitor().visit(tree)
    for start, end, replacement in sorted(edits, reverse=True):
        source_bytes = source_bytes[:start] + replacement + source_bytes[end:]
    final = source_bytes.decode("utf-8")
    ast.parse(final)
    return final, used, list(dict.fromkeys(unresolved))


def _preceding_step_context(node: ast.AST, lines: list[str]) -> str:
    """Get the nearest generated step comment immediately associated with a call."""
    index = node.lineno - 2
    while index >= 0 and not lines[index].strip():
        index -= 1
    if index < 0:
        return ""
    comment = lines[index].strip()
    if not comment.startswith("#"):
        return ""
    comment = comment.lstrip("#").strip().strip("- ").strip()
    return re.sub(r"^step\s+\d+\s*:\s*", "", comment, flags=re.IGNORECASE)