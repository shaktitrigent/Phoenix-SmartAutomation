"""Delta-aware OutputManager — Phase C.3.

Applies the <automation_bundle> delta to disk:

  action=create  → write new file (back up existing with .bak)
  action=extend  → splice new methods into an existing page-object class
                   (AST-aware insert; keeps imports, no duplicate method names)
                   OR append new test functions to an existing test file
  action=merge   → deep-merge JSON by element_id (locators) or top-level key
                   (test_data); never drops existing entries

The entire apply() call is wrapped in a transaction: on any failure, every
.bak file is restored.  After a successful apply, the manifest is refreshed.
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _backup(path: Path) -> Optional[Path]:
    """Copy *path* → *path*.bak and return the bak path, or None if not present."""
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(str(path), str(bak))
    return bak


def _restore(bak: Path) -> None:
    """Restore the original from a .bak file and delete the .bak."""
    original = Path(str(bak)[: -len(".bak")])
    shutil.copy2(str(bak), str(original))
    bak.unlink(missing_ok=True)


def _discard_bak(bak: Path) -> None:
    bak.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AST splice — extend a page object class with new methods
# ---------------------------------------------------------------------------

def _get_existing_method_names(source: str, class_name: str) -> List[str]:
    """Return the names of all methods defined in *class_name* within *source*."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return []


def _extract_new_methods(new_class_source: str, existing_names: List[str]) -> str:
    """Extract method source lines from *new_class_source* that are not in *existing_names*."""
    try:
        tree = ast.parse(new_class_source)
    except SyntaxError:
        return ""

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        lines = new_class_source.splitlines(keepends=True)
        new_parts: List[str] = []
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if method.name in existing_names:
                continue
            # Include any decorators
            start = method.decorator_list[0].lineno - 1 if method.decorator_list else method.lineno - 1
            end = method.end_lineno  # type: ignore[attr-defined]
            method_lines = lines[start:end]
            new_parts.append("".join(method_lines).rstrip())
        return "\n\n    ".join(new_parts)

    return ""


def _splice_methods_into_class(existing_source: str, class_name: str, new_methods_source: str) -> str:
    """Insert *new_methods_source* methods just before the closing of *class_name* in *existing_source*.

    Falls back to appending at end-of-file if the class cannot be located.
    """
    existing_names = _get_existing_method_names(existing_source, class_name)
    new_code = _extract_new_methods(new_methods_source, existing_names)
    if not new_code:
        return existing_source  # nothing new to add

    # Find the last line of the class body and insert before the next class/EOF
    try:
        tree = ast.parse(existing_source)
    except SyntaxError:
        return existing_source + "\n\n" + new_code

    target_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            target_class = node
            break

    if target_class is None:
        return existing_source + "\n\n" + new_code

    lines = existing_source.splitlines(keepends=True)
    insert_at = target_class.end_lineno  # type: ignore[attr-defined]

    # Indent the new methods with 4 spaces to sit inside the class
    indented = "\n".join(
        ("    " + ln if ln.strip() else ln)
        for ln in new_code.splitlines()
    )
    lines.insert(insert_at, "\n" + indented + "\n")
    return "".join(lines)


def _append_test_functions(existing_source: str, new_source: str) -> str:
    """Append test functions from *new_source* to *existing_source*, skipping duplicates."""
    try:
        existing_tree = ast.parse(existing_source)
        new_tree = ast.parse(new_source)
    except SyntaxError:
        return existing_source + "\n\n" + new_source

    existing_funcs = {
        n.name for n in ast.walk(existing_tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    new_lines = new_source.splitlines(keepends=True)
    parts_to_add: List[str] = []

    for node in ast.walk(new_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        if node.name in existing_funcs:
            continue
        start = node.decorator_list[0].lineno - 1 if node.decorator_list else node.lineno - 1
        end = node.end_lineno  # type: ignore[attr-defined]
        parts_to_add.append("".join(new_lines[start:end]))

    if not parts_to_add:
        return existing_source

    return existing_source.rstrip() + "\n\n\n" + "\n\n\n".join(parts_to_add) + "\n"


# ---------------------------------------------------------------------------
# JSON merge
# ---------------------------------------------------------------------------

def _merge_locators(existing: List[Dict], incoming: List[Dict]) -> List[Dict]:
    """Deep-merge locator lists by element_id; incoming wins on conflict."""
    merged: Dict[str, Dict] = {
        e.get("element_id", e.get("element_name", f"__idx_{i}")): e
        for i, e in enumerate(existing)
    }
    for entry in incoming:
        key = entry.get("element_id", entry.get("element_name", ""))
        if key:
            merged[key] = entry
        else:
            merged[f"__new_{len(merged)}"] = entry
    return list(merged.values())


def _merge_test_data(existing: Dict, incoming: Dict) -> Dict:
    """Merge two test_data dicts. Top-level list keys (scenarios, edge_cases) are appended."""
    result = dict(existing)
    for key, value in incoming.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], list) and isinstance(value, list):
            # Avoid duplicate scenario_ids
            existing_ids = {
                s.get("scenario_id") for s in result[key] if isinstance(s, dict)
            }
            result[key] = result[key] + [
                s for s in value
                if not (isinstance(s, dict) and s.get("scenario_id") in existing_ids)
            ]
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# OutputManager
# ---------------------------------------------------------------------------

class OutputManager:
    """Applies a pom_bundle delta to the project on disk.

    Usage::

        manager = OutputManager(project_root=Path("my-project"))
        manager.apply(pom_bundle)
    """

    def __init__(self, project_root: Path) -> None:
        self.root = project_root

    def apply(self, bundle: Dict[str, Any]) -> List[str]:
        """Apply a parsed pom_bundle to disk.

        Returns a list of files written/modified.
        Raises RuntimeError and rolls back on failure.
        """
        backups: List[tuple[Path, Optional[Path]]] = []
        written: List[str] = []

        try:
            for node in bundle.get("page_objects", []):
                path, bak = self._apply_page_object(node)
                backups.append((path, bak))
                written.append(str(path))

            for node in bundle.get("locators", []):
                path, bak = self._apply_locators(node)
                backups.append((path, bak))
                written.append(str(path))

            for node in bundle.get("tests", []):
                path, bak = self._apply_test(node)
                backups.append((path, bak))
                written.append(str(path))

            for node in bundle.get("test_data", []):
                path, bak = self._apply_test_data(node)
                backups.append((path, bak))
                written.append(str(path))

        except Exception as exc:
            # Roll back all changes
            for path, bak in backups:
                if bak and bak.exists():
                    _restore(bak)
                elif path.exists():
                    path.unlink(missing_ok=True)
            raise RuntimeError(f"Delta apply failed (rolled back): {exc}") from exc

        # Commit — discard all backups
        for _, bak in backups:
            if bak:
                _discard_bak(bak)

        # Refresh manifest
        try:
            from phoenix.intelligence.manifest import ProjectIndexer
            indexer = ProjectIndexer(self.root)
            indexer.save(indexer.build())
        except Exception:
            pass

        return list(dict.fromkeys(written))  # deduplicate, preserve order

    # ------------------------------------------------------------------
    # Per-node handlers
    # ------------------------------------------------------------------

    def _apply_page_object(self, node: Dict[str, Any]) -> tuple[Path, Optional[Path]]:
        action = node.get("action", "create")
        path = self.root / node["file"]
        code = node.get("code", "")
        class_name = node.get("class_name", "")

        bak = _backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if action == "create" or not path.exists():
            path.write_text(code, encoding="utf-8")
        elif action == "extend" and class_name:
            existing = path.read_text(encoding="utf-8")
            path.write_text(_splice_methods_into_class(existing, class_name, code), encoding="utf-8")

        return path, bak

    def _apply_locators(self, node: Dict[str, Any]) -> tuple[Path, Optional[Path]]:
        action = node.get("action", "create")
        path = self.root / node["file"]
        incoming = node.get("entries", [])

        bak = _backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if action == "create" or not path.exists():
            path.write_text(json.dumps(incoming, indent=2), encoding="utf-8")
        elif action == "merge" and path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                existing = existing if isinstance(existing, list) else [existing]
            except (json.JSONDecodeError, OSError):
                existing = []
            merged = _merge_locators(existing, incoming)
            path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

        return path, bak

    def _apply_test(self, node: Dict[str, Any]) -> tuple[Path, Optional[Path]]:
        action = node.get("action", "create")
        path = self.root / node["file"]
        code = node.get("code", "")

        bak = _backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if action == "create" or not path.exists():
            path.write_text(code, encoding="utf-8")
        elif action == "extend" and path.exists():
            existing = path.read_text(encoding="utf-8")
            path.write_text(_append_test_functions(existing, code), encoding="utf-8")

        return path, bak

    def _apply_test_data(self, node: Dict[str, Any]) -> tuple[Path, Optional[Path]]:
        action = node.get("action", "create")
        path = self.root / node["file"]
        incoming = node.get("data", {})

        bak = _backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if action == "create" or not path.exists():
            path.write_text(json.dumps(incoming, indent=2), encoding="utf-8")
        elif action == "merge" and path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}
            merged = _merge_test_data(existing, incoming)
            path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

        return path, bak
