"""Project Manifest & Indexer — Phase B.

Walks a pom-v1 project and builds a compact index of:
  - pages/       → class names, public methods, url_path
  - tests/       → function names, pytest markers, page classes imported
  - locators/    → element_ids per page
  - test_data/   → top-level keys per file

The manifest is saved to .phoenix/manifest.json and also converted to a
compact text summary (to_prompt_context()) that is injected into the LLM
prompt so the generator knows what already exists and can reuse it.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class PageIndex:
    def __init__(self, class_name: str, file_path: str, url_path: str, methods: List[str]) -> None:
        self.class_name = class_name
        self.file_path = file_path
        self.url_path = url_path
        self.methods = methods

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "file_path": self.file_path,
            "url_path": self.url_path,
            "methods": self.methods,
        }


class TestIndex:
    def __init__(self, function_name: str, file_path: str, markers: List[str], pages_used: List[str]) -> None:
        self.function_name = function_name
        self.file_path = file_path
        self.markers = markers
        self.pages_used = pages_used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_name": self.function_name,
            "file_path": self.file_path,
            "markers": self.markers,
            "pages_used": self.pages_used,
        }


class FeatureIndex:
    def __init__(self, feature_name: str, file_path: str, scenarios: List[str], steps: List[str]) -> None:
        self.feature_name = feature_name
        self.file_path = file_path
        self.scenarios = scenarios    # scenario titles
        self.steps = steps            # all unique step texts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "file_path": self.file_path,
            "scenarios": self.scenarios,
            "steps": self.steps,
        }


class StepIndex:
    def __init__(self, function_name: str, file_path: str, step_text: str, step_type: str) -> None:
        self.function_name = function_name
        self.file_path = file_path
        self.step_text = step_text    # text from @given/@when/@then decorator
        self.step_type = step_type    # given | when | then

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_name": self.function_name,
            "file_path": self.file_path,
            "step_text": self.step_text,
            "step_type": self.step_type,
        }


class ProjectManifest:
    def __init__(self) -> None:
        self.pages: List[PageIndex] = []
        self.tests: List[TestIndex] = []
        self.features: List[FeatureIndex] = []
        self.step_defs: List[StepIndex] = []
        self.locators: Dict[str, List[str]] = {}   # page_name → [element_ids]
        self.test_data: Dict[str, List[str]] = {}  # module → [top-level keys]
        self.built_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "built_at": self.built_at,
            "pages": [p.to_dict() for p in self.pages],
            "tests": [t.to_dict() for t in self.tests],
            "features": [f.to_dict() for f in self.features],
            "step_defs": [s.to_dict() for s in self.step_defs],
            "locators": self.locators,
            "test_data": self.test_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectManifest":
        m = cls()
        m.built_at = data.get("built_at", "")
        m.pages = [
            PageIndex(
                p["class_name"], p["file_path"], p.get("url_path", "/"), p.get("methods", [])
            )
            for p in data.get("pages", [])
        ]
        m.tests = [
            TestIndex(
                t["function_name"], t["file_path"], t.get("markers", []), t.get("pages_used", [])
            )
            for t in data.get("tests", [])
        ]
        m.features = [
            FeatureIndex(
                f["feature_name"], f["file_path"], f.get("scenarios", []), f.get("steps", [])
            )
            for f in data.get("features", [])
        ]
        m.step_defs = [
            StepIndex(s["function_name"], s["file_path"], s.get("step_text", ""), s.get("step_type", "when"))
            for s in data.get("step_defs", [])
        ]
        m.locators = data.get("locators", {})
        m.test_data = data.get("test_data", {})
        return m

    def to_prompt_context(self) -> str:
        """Return a compact text summary for injection into the LLM prompt."""
        lines: List[str] = ["## Project Manifest — what already exists\n"]

        if self.pages:
            lines.append("### Page Object Classes")
            for page in self.pages:
                method_list = ", ".join(page.methods[:10])
                if len(page.methods) > 10:
                    method_list += f" (+{len(page.methods) - 10} more)"
                lines.append(
                    f"- `{page.class_name}` ({page.file_path}) "
                    f"url_path={page.url_path!r}  methods=[{method_list}]"
                )
            lines.append("")

        if self.tests:
            lines.append("### Existing Tests")
            for test in self.tests:
                markers = ", ".join(test.markers) if test.markers else "none"
                pages = ", ".join(test.pages_used) if test.pages_used else "none"
                lines.append(
                    f"- `{test.function_name}` ({test.file_path}) "
                    f"markers=[{markers}] pages=[{pages}]"
                )
            lines.append("")

        if self.locators:
            lines.append("### Known Locators")
            for page_name, elements in self.locators.items():
                lines.append(f"- {page_name}: {', '.join(elements[:12])}")
            lines.append("")

        if self.test_data:
            lines.append("### Test Data Keys")
            for module, keys in self.test_data.items():
                lines.append(f"- {module}.json: {', '.join(keys)}")
            lines.append("")

        if self.features:
            lines.append("### Gherkin Features")
            for feat in self.features:
                scen_list = ", ".join(f'"{s}"' for s in feat.scenarios[:5])
                lines.append(f"- `{feat.file_path}`: scenarios=[{scen_list}]")
            lines.append("")

        if self.step_defs:
            lines.append("### Existing Step Definitions (reuse these)")
            for step in self.step_defs:
                lines.append(f"  - [{step.step_type}] {step.step_text!r}  -> {step.function_name} ({step.file_path})")
            lines.append("")

        if not (self.pages or self.tests or self.features or self.locators or self.test_data):
            return "## Project Manifest\nNo existing pages, tests, or locators found — this is a fresh project.\n"

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _extract_classes_from_ast(tree: ast.Module) -> List[Dict[str, Any]]:
    """Return list of {name, url_path, methods} for each class in the AST."""
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        url_path = "/"
        # Look for URL_PATH class attribute
        for body_node in node.body:
            if isinstance(body_node, ast.Assign):
                for target in body_node.targets:
                    if isinstance(target, ast.Name) and target.id == "URL_PATH":
                        if isinstance(body_node.value, ast.Constant):
                            url_path = body_node.value.value
        # Collect public method names
        methods = [
            n.name for n in ast.walk(node)
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
        ]
        results.append({"name": node.name, "url_path": url_path, "methods": methods})
    return results


def _extract_tests_from_ast(tree: ast.Module, file_path: str) -> List[Dict[str, Any]]:
    """Return list of {name, markers, pages_used} for each test_ function."""
    results = []

    # Collect imports to map imported names to page classes
    imported_names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name[0].isupper():
                    imported_names.append(name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[-1]
                if name[0].isupper():
                    imported_names.append(name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue

        # Collect pytest markers from decorators
        markers = []
        for dec in node.decorator_list:
            dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            m = re.search(r"pytest\.mark\.(\w+)", dec_str)
            if m:
                markers.append(m.group(1))

        # Detect page class usage in function body
        pages_used = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id in imported_names:
                if child.id not in pages_used:
                    pages_used.append(child.id)

        results.append({"name": node.name, "markers": markers, "pages_used": pages_used})
    return results


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------

class ProjectIndexer:
    """Walks a pom-v1 project root and builds a ProjectManifest."""

    def __init__(self, project_root: str | Path) -> None:
        self.root = Path(project_root)

    def build(self) -> ProjectManifest:
        manifest = ProjectManifest()
        manifest.built_at = datetime.now(timezone.utc).isoformat()

        self._index_pages(manifest)
        self._index_tests(manifest)
        self._index_locators(manifest)
        self._index_test_data(manifest)
        self._index_features(manifest)
        self._index_steps(manifest)

        return manifest

    def _index_pages(self, manifest: ProjectManifest) -> None:
        pages_dir = self.root / "pages"
        if not pages_dir.exists():
            return
        for py_file in sorted(pages_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for cls in _extract_classes_from_ast(tree):
                    if cls["name"] in ("BasePage",):
                        continue
                    rel = str(py_file.relative_to(self.root))
                    manifest.pages.append(
                        PageIndex(cls["name"], rel, cls["url_path"], cls["methods"])
                    )
            except (SyntaxError, OSError):
                pass

    def _index_tests(self, manifest: ProjectManifest) -> None:
        tests_dir = self.root / "tests"
        if not tests_dir.exists():
            return
        for py_file in sorted(tests_dir.rglob("test_*.py")):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                rel = str(py_file.relative_to(self.root))
                for test in _extract_tests_from_ast(tree, rel):
                    manifest.tests.append(
                        TestIndex(test["name"], rel, test["markers"], test["pages_used"])
                    )
            except (SyntaxError, OSError):
                pass

    def _index_locators(self, manifest: ProjectManifest) -> None:
        locators_dir = self.root / "locators"
        if not locators_dir.exists():
            return
        for json_file in sorted(locators_dir.glob("*.json")):
            if json_file.name.startswith("_"):
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                bundles = data if isinstance(data, list) else [data]
                element_ids = [
                    b.get("element_id", b.get("element_name", ""))
                    for b in bundles
                    if isinstance(b, dict)
                ]
                element_ids = [e for e in element_ids if e]
                if element_ids:
                    manifest.locators[json_file.stem] = element_ids
            except (json.JSONDecodeError, OSError):
                pass

    def _index_test_data(self, manifest: ProjectManifest) -> None:
        data_dir = self.root / "test_data"
        if not data_dir.exists():
            return
        for json_file in sorted(data_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    manifest.test_data[json_file.stem] = list(data.keys())
            except (json.JSONDecodeError, OSError):
                pass

    def _index_features(self, manifest: ProjectManifest) -> None:
        features_dir = self.root / "features"
        if not features_dir.exists():
            return
        for feat_file in sorted(features_dir.rglob("*.feature")):
            try:
                text = feat_file.read_text(encoding="utf-8")
                rel = str(feat_file.relative_to(self.root))
                feature_name = ""
                scenarios: List[str] = []
                all_steps: List[str] = []
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.lower().startswith("feature:"):
                        feature_name = stripped[8:].strip()
                    elif stripped.lower().startswith("scenario"):
                        title = re.sub(r"^scenario\s*(?:outline)?:", "", stripped, flags=re.IGNORECASE).strip()
                        if title:
                            scenarios.append(title)
                    elif re.match(r"^(given|when|then|and|but)\s", stripped, re.IGNORECASE):
                        step = re.sub(r"^(given|when|then|and|but)\s+", "", stripped, flags=re.IGNORECASE)
                        if step and step not in all_steps:
                            all_steps.append(step)
                manifest.features.append(
                    FeatureIndex(feature_name or feat_file.stem, rel, scenarios, all_steps)
                )
            except OSError:
                pass

    def _index_steps(self, manifest: ProjectManifest) -> None:
        steps_dir = self.root / "steps"
        if not steps_dir.exists():
            return
        _DECORATOR_RE = re.compile(
            r"@(given|when|then)\s*\(\s*(?:parsers\.parse\s*\()?['\"]([^'\"]+)['\"]",
            re.IGNORECASE,
        )
        for py_file in sorted(steps_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
                rel = str(py_file.relative_to(self.root))
                lines = text.splitlines()
                for i, line in enumerate(lines):
                    m = _DECORATOR_RE.search(line)
                    if not m:
                        continue
                    step_type = m.group(1).lower()
                    step_text = m.group(2)
                    # Find the function name on the next non-empty line
                    func_name = ""
                    for j in range(i + 1, min(i + 4, len(lines))):
                        fn_match = re.match(r"\s*def\s+(\w+)", lines[j])
                        if fn_match:
                            func_name = fn_match.group(1)
                            break
                    manifest.step_defs.append(
                        StepIndex(func_name, rel, step_text, step_type)
                    )
            except OSError:
                pass

    def save(self, manifest: ProjectManifest, path: Optional[Path] = None) -> Path:
        out = path or (self.root / ".phoenix" / "manifest.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return out

    def load(self, path: Optional[Path] = None) -> Optional[ProjectManifest]:
        src = path or (self.root / ".phoenix" / "manifest.json")
        if not src.exists():
            return None
        try:
            return ProjectManifest.from_dict(json.loads(src.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, KeyError):
            return None
