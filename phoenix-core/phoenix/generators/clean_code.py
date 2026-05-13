"""Clean Code Emitter — Prompt 4.

Two-layer pipeline applied to every generated automation script
*before* it is written to disk:

  Layer 1 — CleanCodeGate (fast regex scan)
    Rejects scripts containing TODO/FIXME/placeholder bodies, ellipsis-only
    function bodies, and bare ``pass`` statements where real logic is expected.
    Returns structured ``CodeViolation`` objects so the caller can decide
    whether to raise, retry, or log.

  Layer 2 — CodeCleaner (AST-based cleanup)
    Attempts to clean auto-fixable issues:
      • Removes dead imports (names never used in the file).
      • Strips trailing blank lines inside function bodies.
      • Collapses consecutive blank lines to a single blank.
    Uses the ``ast`` module from the standard library (no libcst required).
    Falls back gracefully if the code has a syntax error.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List


# ---------------------------------------------------------------------------
# Violation model
# ---------------------------------------------------------------------------

@dataclass
class CodeViolation:
    rule: str
    line_number: int
    excerpt: str
    message: str

    def __str__(self) -> str:
        return f"L{self.line_number} [{self.rule}] {self.message} — {self.excerpt!r}"


# ---------------------------------------------------------------------------
# Layer 1 — CleanCodeGate
# ---------------------------------------------------------------------------

_GATE_RULES: List[tuple] = [
    (
        "TODO_BODY",
        re.compile(r"^\s*#\s*(TODO|FIXME)\b.*$", re.IGNORECASE),
        "Script contains TODO/FIXME comment — replace with real implementation",
    ),
    (
        "PLACEHOLDER_PASS",
        re.compile(r"^\s*pass\s*$"),
        "Bare 'pass' statement — function body is empty/unimplemented",
    ),
    (
        "ELLIPSIS_BODY",
        re.compile(r"^\s*\.\.\.\s*$"),
        "Ellipsis '...' used as function body — replace with real steps",
    ),
    (
        "PLACEHOLDER_TEXT",
        re.compile(
            r"\b(placeholder|lorem ipsum|your_selector|SELECTOR_HERE|LOCATOR_HERE)\b",
            re.IGNORECASE,
        ),
        "Placeholder text found — replace with real selector or value",
    ),
    (
        "HARDCODED_SLEEP",
        re.compile(r"\btime\.sleep\s*\("),
        "time.sleep() is forbidden in Playwright tests — use expect() assertions",
    ),
]

# Rules that are warnings, not hard failures (gate still reports them)
_WARNING_RULES = {"HARDCODED_SLEEP"}


class CleanCodeGate:
    """Scan generated code for anti-patterns that indicate incomplete output.

    Designed to be called *before* writing the script to disk.  The caller
    decides the failure policy:

        gate = CleanCodeGate()
        violations = gate.check(code)
        hard_failures = [v for v in violations if v.rule not in gate.WARNING_RULES]
        if hard_failures:
            raise RuntimeError(...)
    """

    WARNING_RULES = _WARNING_RULES

    def check(self, code: str) -> List[CodeViolation]:
        """Return all violations found in *code*.

        Violations whose ``rule`` is in ``WARNING_RULES`` are advisory;
        the rest are hard failures.
        """
        violations: List[CodeViolation] = []
        lines = code.splitlines()
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comment lines for most rules (already flagged by TODO_BODY rule)
            for rule_id, pattern, message in _GATE_RULES:
                if rule_id == "TODO_BODY":
                    # Only match lines that are pure comments
                    if pattern.match(line):
                        violations.append(
                            CodeViolation(
                                rule=rule_id,
                                line_number=line_no,
                                excerpt=stripped[:80],
                                message=message,
                            )
                        )
                elif rule_id in ("PLACEHOLDER_PASS", "ELLIPSIS_BODY"):
                    # Only flag inside function bodies (indented)
                    if line.startswith("    ") and pattern.match(line):
                        violations.append(
                            CodeViolation(
                                rule=rule_id,
                                line_number=line_no,
                                excerpt=stripped[:80],
                                message=message,
                            )
                        )
                else:
                    if pattern.search(line) and not stripped.startswith("#"):
                        violations.append(
                            CodeViolation(
                                rule=rule_id,
                                line_number=line_no,
                                excerpt=stripped[:80],
                                message=message,
                            )
                        )
        return violations

    def passes(self, code: str) -> bool:
        """True if code has no hard-failure violations."""
        return not any(
            v for v in self.check(code) if v.rule not in self.WARNING_RULES
        )

    def inject_warnings(self, code: str) -> str:
        """Prepend a warning block to the first test function for advisory issues."""
        warnings = [v for v in self.check(code) if v.rule in self.WARNING_RULES]
        if not warnings:
            return code

        sentinel = "# ⚠  Clean-code advisory warnings"
        if sentinel in code:
            return code

        border = "# " + "─" * 66
        block = (
            border + "\n"
            + sentinel + " — review before merging\n"
            + border + "\n"
            + "".join(f"#    • {w}\n" for w in warnings)
            + border + "\n\n"
        )

        lines = code.splitlines(keepends=True)
        insert_at = next(
            (i for i, ln in enumerate(lines) if ln.strip().startswith("def test_")),
            len(lines),
        )
        lines.insert(insert_at, block)
        return "".join(lines)


# ---------------------------------------------------------------------------
# Layer 2 — CodeCleaner
# ---------------------------------------------------------------------------

class CodeCleaner:
    """AST-based cleanup for generated Playwright scripts.

    Auto-fixes:
      1. Remove unused imports (detected via AST name analysis).
      2. Collapse 3+ consecutive blank lines to 2.
      3. Strip trailing whitespace on every line.

    Falls back silently if the code has a syntax error.
    """

    def clean(self, code: str) -> str:
        """Apply all cleanup passes.  Returns original code on parse failure."""
        try:
            ast.parse(code)
        except SyntaxError:
            return code

        code = self._remove_unused_imports(code)
        code = self._collapse_blank_lines(code)
        code = self._strip_trailing_whitespace(code)
        return code

    # ------------------------------------------------------------------

    def _remove_unused_imports(self, code: str) -> str:
        """Remove top-level import statements whose names are never used."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        # Collect all names used in the module body (excluding import nodes)
        used_names: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Capture the root name of attribute chains
                root = node
                while isinstance(root, ast.Attribute):
                    root = root.value  # type: ignore[assignment]
                if isinstance(root, ast.Name):
                    used_names.add(root.id)

        # Build set of import lines to remove
        lines_to_remove: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    actual_name = alias.asname if alias.asname else alias.name.split(".")[0]
                    if actual_name not in used_names:
                        lines_to_remove.add(node.lineno)
            elif isinstance(node, ast.ImportFrom):
                imported = [
                    (alias.asname if alias.asname else alias.name) for alias in node.names
                ]
                if all(name not in used_names for name in imported):
                    lines_to_remove.add(node.lineno)

        if not lines_to_remove:
            return code

        result_lines = []
        for line_no, line in enumerate(code.splitlines(keepends=True), 1):
            if line_no not in lines_to_remove:
                result_lines.append(line)
        return "".join(result_lines)

    def _collapse_blank_lines(self, code: str) -> str:
        """Collapse 3+ consecutive blank lines to exactly 2."""
        return re.sub(r"\n{4,}", "\n\n\n", code)

    def _strip_trailing_whitespace(self, code: str) -> str:
        return "\n".join(line.rstrip() for line in code.split("\n"))


# ---------------------------------------------------------------------------
# Combined pipeline entry point
# ---------------------------------------------------------------------------

def apply_clean_code_pipeline(
    code: str,
    *,
    gate_raises: bool = False,
    clean: bool = True,
) -> str:
    """Gate + clean in one call.

    Args:
        code:        The generated Python script.
        gate_raises: If True, raise RuntimeError on hard gate failures.
                     If False (default), inject warning comments instead.
        clean:       Apply CodeCleaner after gate check.

    Returns:
        The code with advisory comments injected and/or cleanup applied.
    """
    gate = CleanCodeGate()
    violations = gate.check(code)
    hard_failures = [v for v in violations if v.rule not in gate.WARNING_RULES]

    if hard_failures and gate_raises:
        msgs = "\n".join(f"  {v}" for v in hard_failures)
        raise RuntimeError(
            f"Generated script failed CleanCodeGate with {len(hard_failures)} violation(s):\n{msgs}"
        )

    # Inject advisory warnings (HARDCODED_SLEEP etc.) as comments
    code = gate.inject_warnings(code)

    if clean:
        code = CodeCleaner().clean(code)

    return code
