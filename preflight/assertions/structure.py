"""T2 structure checks — deterministic static analysis of generated project."""
from __future__ import annotations

import ast
import fnmatch
import json
import py_compile
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List

from preflight.assertions.result import AssertionResult


# ---------------------------------------------------------------------------
# T2 assertions
# ---------------------------------------------------------------------------

def check_required_folders(sandbox: Path, spec: dict) -> AssertionResult:
    """Assert every folder listed in spec['required_folders'] exists under sandbox."""
    name = "T2:required_folders"
    required: List[str] = spec.get("required_folders", [])
    missing = [f for f in required if not (sandbox / f).is_dir()]
    if missing:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=f"Missing folders: {missing}",
            data={"missing": missing},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail=f"All {len(required)} required folders present.",
    )


def check_required_files(sandbox: Path, spec: dict) -> AssertionResult:
    """Assert every file listed in spec['required_files'] exists under sandbox."""
    name = "T2:required_files"
    required: List[str] = spec.get("required_files", [])
    missing = [f for f in required if not (sandbox / f).is_file()]
    if missing:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=f"Missing files: {missing}",
            data={"missing": missing},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail=f"All {len(required)} required files present.",
    )


def check_test_grouping(sandbox: Path, spec: dict) -> AssertionResult:
    """FAIL if tests/test_tc_*.py exists (one-file-per-test antipattern)."""
    name = "T2:test_grouping"
    rule = spec.get("test_grouping_rule", {})
    violation_pattern = rule.get("violation_pattern", "tests/test_tc_*.py")

    # Convert glob pattern to parts
    tests_dir = sandbox / "tests"
    if not tests_dir.exists():
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail="tests/ directory does not exist yet — skip.",
        )

    # Glob directly from sandbox
    violations = list(sandbox.glob(violation_pattern))
    if violations:
        rel = [str(v.relative_to(sandbox)) for v in violations]
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=(
                f"Antipattern: one-file-per-test detected. "
                f"Violations ({len(rel)}): {rel[:10]}"
            ),
            data={"violations": rel},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail="No one-file-per-test antipattern detected.",
    )


def check_spec_grouping(sandbox: Path, spec: dict) -> AssertionResult:
    """FAIL if manual_tests/manual_test_00*.md exists (antipattern)."""
    name = "T2:spec_grouping"
    rule = spec.get("spec_grouping_rule", {})
    violation_pattern = rule.get("violation_pattern", "manual_tests/manual_test_00*.md")

    mt_dir = sandbox / "manual_tests"
    if not mt_dir.exists():
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail="manual_tests/ directory does not exist yet — skip.",
        )

    violations = list(sandbox.glob(violation_pattern))
    if violations:
        rel = [str(v.relative_to(sandbox)) for v in violations]
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=(
                f"Antipattern: one-file-per-spec detected. "
                f"Violations ({len(rel)}): {rel[:10]}"
            ),
            data={"violations": rel},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail="No one-file-per-spec antipattern detected.",
    )


def check_no_raw_selectors_in_pages(sandbox: Path, spec: dict) -> AssertionResult:
    """Parse pages/*.py; fail if any line matches forbidden_patterns."""
    name = "T2:no_raw_selectors_in_pages"
    rule = spec.get("page_object_rule", {})
    forbidden_patterns: List[str] = rule.get("forbidden_patterns", [])

    pages_dir = sandbox / "pages"
    if not pages_dir.exists():
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail="pages/ directory does not exist yet — skip.",
        )

    compiled = [re.compile(p) for p in forbidden_patterns]
    violations = []

    for py_file in sorted(pages_dir.glob("*.py")):
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            violations.append(f"{py_file}: read error — {exc}")
            continue
        for lineno, line in enumerate(lines, 1):
            for pattern in compiled:
                if pattern.search(line):
                    rel = py_file.relative_to(sandbox)
                    violations.append(f"{rel}:{lineno}: {line.strip()}")

    if violations:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=f"Raw selectors found in page objects ({len(violations)} hit(s)):\n" + "\n".join(violations[:20]),
            data={"violations": violations},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail=f"No raw selectors in {len(list(pages_dir.glob('*.py')))} page file(s).",
    )


def check_locator_registry(sandbox: Path, spec: dict) -> AssertionResult:
    """Load every locators/*.json; fail if primary is forbidden or required_keys missing."""
    name = "T2:locator_registry"
    rule = spec.get("locator_registry_rule", {})
    required_keys: List[str] = rule.get("required_keys", ["element_name", "primary"])
    forbidden_primaries: List[str] = rule.get("forbidden_primaries", ["css=body", "body"])

    locators_dir = sandbox / "locators"
    if not locators_dir.exists():
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail="locators/ directory does not exist yet — skip.",
        )

    json_files = sorted(locators_dir.glob("*.json"))
    if not json_files:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail="No locator JSON files found yet — skip.",
        )

    violations = []
    for jf in json_files:
        try:
            raw = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"{jf.name}: parse error — {exc}")
            continue

        # raw may be a list of bundles or a single bundle dict
        bundles = raw if isinstance(raw, list) else [raw]
        for bundle in bundles:
            if not isinstance(bundle, dict):
                continue
            # Check required keys
            for key in required_keys:
                if key not in bundle:
                    rel = jf.relative_to(sandbox)
                    violations.append(
                        f"{rel}: bundle missing required key '{key}' — bundle keys: {list(bundle.keys())}"
                    )
            # Check forbidden primaries
            primary = bundle.get("primary", "")
            if primary in forbidden_primaries:
                rel = jf.relative_to(sandbox)
                violations.append(
                    f"{rel}: forbidden primary value '{primary}' for element '{bundle.get('element_name', '?')}'"
                )

    if violations:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=f"Locator registry violations ({len(violations)}):\n" + "\n".join(violations[:20]),
            data={"violations": violations},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail=f"All {len(json_files)} locator file(s) valid.",
    )


def check_imports(sandbox: Path, spec: dict) -> AssertionResult:
    """ast.parse every generated .py; fail on duplicate imports or import inside a string node."""
    name = "T2:import_hygiene"
    rules = spec.get("import_rules", {})
    check_duplicates: bool = rules.get("no_duplicate_imports", True)
    check_in_strings: bool = rules.get("no_imports_in_docstrings", True)

    py_files = sorted(sandbox.rglob("*.py"))
    violations = []

    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            # syntax errors caught by check_syntax
            continue
        except OSError as exc:
            violations.append(f"{py_file.relative_to(sandbox)}: read error — {exc}")
            continue

        rel = py_file.relative_to(sandbox)

        if check_duplicates:
            seen_imports: set = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        key = f"import {alias.name}"
                        if key in seen_imports:
                            violations.append(
                                f"{rel}:{node.lineno}: duplicate import '{alias.name}'"
                            )
                        seen_imports.add(key)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        key = f"from {module} import {alias.name}"
                        if key in seen_imports:
                            violations.append(
                                f"{rel}:{node.lineno}: duplicate 'from {module} import {alias.name}'"
                            )
                        seen_imports.add(key)

        if check_in_strings:
            # Detect import statements that appear inside string literals
            import_re = re.compile(r"^\s*(import\s+\w|from\s+\w.*import\s+)", re.MULTILINE)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if import_re.search(node.value):
                        violations.append(
                            f"{rel}:{node.lineno}: import-like statement inside a string literal"
                        )

    if violations:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=f"Import hygiene violations ({len(violations)}):\n" + "\n".join(violations[:20]),
            data={"violations": violations},
        )
    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail=f"Import hygiene OK across {len(py_files)} file(s).",
    )


def check_syntax(sandbox: Path) -> AssertionResult:
    """py_compile every .py in sandbox; detail = first failing file + error."""
    name = "T2:syntax_check"
    py_files = sorted(sandbox.rglob("*.py"))

    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as exc:
            rel = py_file.relative_to(sandbox)
            return AssertionResult(
                tier="T2",
                name=name,
                passed=False,
                detail=f"Syntax error in {rel}: {exc}",
                data={"file": str(rel), "error": str(exc)},
            )

    return AssertionResult(
        tier="T2",
        name=name,
        passed=True,
        detail=f"Syntax OK in all {len(py_files)} .py file(s).",
    )


def check_collect(sandbox: Path, python_exe: str) -> AssertionResult:
    """Run pytest --collect-only; pass if exit code 0 or 5 (no tests collected)."""
    name = "T2:pytest_collect"
    tests_dir = sandbox / "tests"
    if not tests_dir.exists():
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail="tests/ directory does not exist yet — skip.",
        )

    try:
        result = subprocess.run(
            [python_exe, "-m", "pytest", "--collect-only", "-q", str(tests_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail="pytest --collect-only timed out after 60s",
        )
    except Exception as exc:
        return AssertionResult(
            tier="T2",
            name=name,
            passed=False,
            detail=f"Failed to run pytest: {exc}",
        )

    # 0 = tests found, 5 = no tests collected — both acceptable
    if result.returncode in (0, 5):
        return AssertionResult(
            tier="T2",
            name=name,
            passed=True,
            detail=f"pytest collect exit={result.returncode}. stdout: {result.stdout.strip()[:200]}",
        )

    return AssertionResult(
        tier="T2",
        name=name,
        passed=False,
        detail=(
            f"pytest collect exit={result.returncode}\n"
            f"stdout: {result.stdout[-400:]}\n"
            f"stderr: {result.stderr[-400:]}"
        ),
    )
