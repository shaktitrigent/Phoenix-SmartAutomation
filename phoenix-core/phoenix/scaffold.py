"""Project scaffolding — drives `phoenix init` and `phoenix migrate`.

Creates a canonical Phoenix project layout:

    <name>/
    ├── .phoenixrc            (TOML config)
    ├── conftest.py           (pytest + Playwright fixtures)
    ├── manual_tests/         (generated manual test docs)
    ├── test_results/         (generated automation scripts)
    ├── reports/              (HTML execution reports)
    ├── locators/             (per-page LocatorBundle JSON files)
    ├── logs/                 (JSONL execution logs)
    └── tests/
        └── test_example.py   (starter Playwright test)

The global project registry lives at ~/.phoenix/projects.json so that
`phoenix` can discover projects from any working directory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Jinja2 is optional — fall back to simple str.replace if not installed
try:
    from jinja2 import Environment, FileSystemLoader

    _JINJA2_AVAILABLE = True
except ImportError:
    _JINJA2_AVAILABLE = False

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "project"

# Canonical subdirectories created for every new project
_PROJECT_DIRS = [
    "manual_tests",
    "test_results",
    "reports",
    "locators",
    "logs",
    "tests",
]


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

def _registry_path() -> Path:
    registry = Path.home() / ".phoenix" / "projects.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    return registry


def _load_registry() -> Dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"projects": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"projects": []}


def _save_registry(data: Dict[str, Any]) -> None:
    _registry_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_project(name: str, project_dir: Path) -> None:
    """Add or update a project entry in the global registry."""
    data = _load_registry()
    projects: List[Dict[str, Any]] = data.get("projects", [])
    entry = next((p for p in projects if p.get("name") == name), None)
    if entry is None:
        projects.append(
            {
                "name": name,
                "path": str(project_dir.resolve()),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    else:
        entry["path"] = str(project_dir.resolve())
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["projects"] = projects
    _save_registry(data)


def list_projects() -> List[Dict[str, Any]]:
    """Return all registered projects."""
    return _load_registry().get("projects", [])


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render a Jinja2 template, falling back to simple substitution."""
    template_path = _TEMPLATES_DIR / template_name
    if not template_path.exists():
        return ""

    raw = template_path.read_text(encoding="utf-8")

    if _JINJA2_AVAILABLE:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )
        tmpl = env.get_template(template_name)
        return tmpl.render(**context)

    # Fallback: replace {{ key }} tokens manually
    for key, value in context.items():
        raw = raw.replace("{{ " + key + " }}", str(value))
    return raw


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------

class ScaffoldResult:
    """Result of a scaffold operation."""

    def __init__(self) -> None:
        self.created_dirs: List[str] = []
        self.created_files: List[str] = []
        self.skipped_files: List[str] = []
        self.errors: List[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors


def scaffold_project(
    name: str,
    target_dir: Path,
    base_url: str = "",
    browser: str = "chromium",
    force: bool = False,
    dry_run: bool = False,
) -> ScaffoldResult:
    """Create the canonical project layout under *target_dir*.

    Args:
        name:       Project name (used in templates and registry).
        target_dir: Directory to create the project in.
        base_url:   Default application URL to embed in config files.
        browser:    Default browser for conftest.py (chromium/firefox/webkit).
        force:      Overwrite existing files when True.
        dry_run:    Report what would be created without touching the filesystem.

    Returns:
        ScaffoldResult with lists of created/skipped files and any errors.
    """
    result = ScaffoldResult()
    context = {"project_name": name, "base_url": base_url, "browser": browser}

    # Create subdirectories
    for subdir in _PROJECT_DIRS:
        dir_path = target_dir / subdir
        if not dry_run:
            dir_path.mkdir(parents=True, exist_ok=True)
        result.created_dirs.append(str(dir_path))

    # Place a .gitkeep in each empty directory so git tracks them
    for subdir in _PROJECT_DIRS:
        keep_file = target_dir / subdir / ".gitkeep"
        if dry_run:
            result.created_files.append(str(keep_file))
            continue
        if not keep_file.exists():
            keep_file.write_text("", encoding="utf-8")
            result.created_files.append(str(keep_file))

    # Render and write template files
    template_map = {
        "phoenixrc.j2": target_dir / ".phoenixrc",
        "conftest.py.j2": target_dir / "conftest.py",
        "test_example.py.j2": target_dir / "tests" / "test_example.py",
    }

    for template_name, dest in template_map.items():
        if dest.exists() and not force:
            result.skipped_files.append(str(dest))
            continue
        content = _render_template(template_name, context)
        if not content:
            continue
        if dry_run:
            result.created_files.append(str(dest))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        result.created_files.append(str(dest))

    # Register in global projects.json
    if not dry_run:
        register_project(name, target_dir)

    return result


def migrate_project(source_dir: Path, dry_run: bool = False) -> ScaffoldResult:
    """Migrate an existing Phoenix project to the canonical layout.

    Adds any missing subdirectories and template files without touching
    files that already exist (equivalent to scaffold with force=False).
    """
    # Try to read project name from .phoenixrc
    rc_path = source_dir / ".phoenixrc"
    name = source_dir.name  # fallback
    base_url = ""
    browser = "chromium"

    if rc_path.exists():
        try:
            import sys

            if sys.version_info >= (3, 11):
                import tomllib

                with open(rc_path, "rb") as fh:
                    data = tomllib.load(fh)
            else:
                import tomli  # type: ignore[import]

                with open(rc_path, "rb") as fh:
                    data = tomli.load(fh)
            proj = data.get("project", {})
            name = proj.get("default_project", name)
            base_url = proj.get("application_url", "")
            exec_cfg = data.get("execution", {})
            browser = exec_cfg.get("default_browser", "chromium")
        except Exception:
            pass

    return scaffold_project(
        name=name,
        target_dir=source_dir,
        base_url=base_url,
        browser=browser,
        force=False,
        dry_run=dry_run,
    )
