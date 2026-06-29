"""CLI commands"""

import re as _re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click
from phoenix import PhoenixClient
from phoenix.cli.output import (
    err_console,
    print_execution_results,
    print_error,
    print_generate_results,
    print_header,
    print_info,
    print_report_summary,
    print_success,
    print_warning,
)
from phoenix.sdk.config import PhoenixConfig


def _module_from_file(path: Path) -> str:
    """Derive a module name from a file path stem.

    user_stories/login.txt      → "login"
    manual_tests/checkout.md    → "checkout"
    tests/employee_mgmt.py      → "employee_mgmt"
    """
    stem = path.stem.lower()
    return _re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "generated"


def _dict_to_manual_case(data: dict):
    """Convert a manual test dict (from intelligence or generator) to a ManualCase."""
    from phoenix.generators.writer import ManualCase

    return ManualCase(
        case_id=data.get("case_id", data.get("name", "TC-000")),
        name=data.get("name", ""),
        description=data.get("description", ""),
        steps=data.get("steps", []),
        expected_result=data.get("expected_result", ""),
        preconditions=data.get("preconditions", ""),
        postconditions=data.get("postconditions", ""),
        tags=data.get("tags", []),
        risk_level=data.get("risk_level", "regression"),
    )


def _write_module_artifacts(
    module: str,
    all_manual: list,
    all_automation: list,
    project_root: Path,
    verbose: bool = False,
) -> None:
    """Write consolidated module files via ModuleAwareWriter and generate test data."""
    try:
        from phoenix.generators.writer import (
            ModuleAwareWriter,
            LocatorElement,
            TestFunction,
            _extract_test_functions,
        )
        from phoenix.test_data.engine import TestDataEngine
    except ImportError as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("Module-aware writing unavailable: %s", exc)
        return

    writer = ModuleAwareWriter(project_root=project_root)

    # Manual test cases
    if all_manual:
        cases = [_dict_to_manual_case(t) for t in all_manual]
        path = writer.write_manual(module, cases)
        if verbose:
            print_info(f"  Module manual:  {path}")

    # Collect all unique tags from the manual tests for this module (excluding "manual")
    _module_tags = sorted({
        t for m in (all_manual or [])
        for t in m.get("tags", [])
        if t != "manual"
    })

    # Automation test functions (extracted from already-written individual scripts)
    test_funcs: list[TestFunction] = []
    for test in all_automation:
        script_path = test.get("script_path", "")
        if script_path and Path(script_path).exists():
            try:
                code = Path(script_path).read_text(encoding="utf-8")
                for name, body in _extract_test_functions(code).items():
                    test_funcs.append(TestFunction(name=name, body=body, marks=_module_tags))
            except Exception:
                pass
    if test_funcs:
        path = writer.write_tests(module, test_funcs)
        if verbose:
            print_info(f"  Module tests:   {path}")

    # Locators from v2.0 structured output
    locator_elements: list[LocatorElement] = []
    for test in all_automation:
        for entry in test.get("locators", []):
            element_id = entry.get("element_id", "")
            if element_id:
                locator_elements.append(LocatorElement(element_id=element_id, data=entry))
    if locator_elements:
        path = writer.write_locators(module, locator_elements)
        if verbose:
            print_info(f"  Module locators:{path}")

    # Test data — extract step text from manual tests so field names are derived
    # from what the steps actually say, not from a hardcoded module-name map.
    try:
        engine = TestDataEngine(project_root=project_root)
        _steps = [
            step if isinstance(step, str) else step.get("step", "")
            for test in all_manual
            for step in (test.get("steps") or [])
        ]
        data_path = engine.generate(module, steps=_steps or None)
        if verbose:
            print_info(f"  Test data:      {data_path}")
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("TestDataEngine failed: %s", exc)


def _write_bdd_feature(
    story_file: Path,
    manual_tests: list,
    project_root: Path,
    verbose: bool = False,
) -> None:
    """Write a plain-English Gherkin feature file from generated manual tests."""
    features_dir = project_root / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    module = _module_from_file(story_file)
    feature_path = features_dir / f"{module}.feature"

    # Build Gherkin from manual test names and steps
    lines = [f"Feature: {module.replace('_', ' ').title()}", ""]
    for test in manual_tests:
        name = test.get("name", "Test case")
        lines += [f"  Scenario: {name}", ""]
        steps = test.get("steps", [])
        for i, step in enumerate(steps):
            action = step.get("action", "") if isinstance(step, dict) else str(step)
            if not action:
                continue
            keyword = "Given" if i == 0 else ("Then" if i == len(steps) - 1 else "When")
            lines.append(f"    {keyword} {action}")
        lines.append("")

    content = "\n".join(lines)
    if feature_path.exists():
        # Append new scenarios only
        existing = feature_path.read_text(encoding="utf-8")
        for test in manual_tests:
            scenario_title = f"Scenario: {test.get('name', '')}"
            if scenario_title not in existing:
                # Append just this scenario
                extra_lines = ["", f"  {scenario_title}", ""]
                for i, step in enumerate(test.get("steps", [])):
                    action = step.get("action", "") if isinstance(step, dict) else str(step)
                    if action:
                        kw = "Given" if i == 0 else ("Then" if i == len(test.get("steps", [])) - 1 else "When")
                        extra_lines.append(f"    {kw} {action}")
                extra_lines.append("")
                existing += "\n".join(extra_lines)
        feature_path.write_text(existing, encoding="utf-8")
    else:
        feature_path.write_text(content, encoding="utf-8")

    if verbose:
        print_info(f"  Feature file: {feature_path.relative_to(project_root)}")


def _print_intelligence_metadata_warnings(metadata: dict | None) -> None:
    if not metadata:
        return
    for warning in metadata.get("warnings", []):
        print_warning(warning)


def _load_domain_knowledge(project_root: Path) -> str:
    """Read all .md files from domain_knowledge/ and concatenate them.

    Returns an empty string if the directory doesn't exist or is empty.
    Skips README.md (it's instructions, not knowledge).
    """
    knowledge_dir = project_root / "domain_knowledge"
    if not knowledge_dir.is_dir():
        return ""
    parts: List[str] = []
    for f in sorted(knowledge_dir.glob("*.md")):
        if f.name.lower() == "readme.md":
            continue
        try:
            text = f.read_text(encoding="utf-8").strip()
            if text and "[Add your observations here]" not in text:
                parts.append(f"## {f.stem}\n\n{text}")
        except OSError:
            pass
    return "\n\n".join(parts)


def _clean_project_directory(manual_dir: Path, test_dir: Path, verbose: bool = False) -> bool:
    """Remove all generated artifacts from previous runs.

    Deletes only the two generated-output directories, then re-creates them
    as empty folders.  Returns True if cleanup was fully successful.
    If any deletion fails the run is aborted — never proceed with a mixed
    artifact set (RC-06).
    """
    dirs_to_clean = [manual_dir, test_dir]
    failed: List[Tuple[Path, str]] = []

    for dir_path in dirs_to_clean:
        if not dir_path.exists():
            continue
        try:
            shutil.rmtree(dir_path)
            if verbose:
                click.echo(f"  Cleaned: {dir_path}")
        except OSError as exc:
            failed.append((dir_path, str(exc)))

    # Verify deletion succeeded
    for dir_path in dirs_to_clean:
        if dir_path.exists() and any(dir_path.iterdir()):
            failed.append((dir_path, "Directory still contains files after rmtree"))

    if failed:
        click.echo("WARNING: Some files could not be removed:", err=True)
        for path, reason in failed:
            click.echo(f"  {path}: {reason}", err=True)
        click.echo(
            "Aborting to prevent stale artifact contamination. Fix the above errors and try again.",
            err=True,
        )
        return False

    # Re-create empty directories for the generator
    for dir_path in dirs_to_clean:
        dir_path.mkdir(parents=True, exist_ok=True)
        if verbose:
            click.echo(f"  Re-created: {dir_path}")

    return True


def _doctor_fix_filenames(ctx) -> None:
    """Rename generated files to the canonical convention with whole-word slugs."""
    from phoenix.utils.slugify import slugify as _slug
    import re as _re

    cwd = Path.cwd()
    renamed = 0

    # test_NNN_*.py and manual_test_NNN_*.md patterns
    patterns = [
        ("tests", _re.compile(r"^test_(\d{3})_(.+)\.py$"), "test", ".py"),
        ("manual_tests", _re.compile(r"^manual_test_(\d{3})_(.+)\.md$"), "manual_test", ".md"),
    ]

    for dir_name, pat, prefix, ext in patterns:
        d = cwd / dir_name
        if not d.exists():
            continue
        for f in sorted(d.rglob(f"*{ext}")):
            m = pat.match(f.name)
            if not m:
                continue
            idx, old_slug = m.group(1), m.group(2)
            # Reconstruct title from existing slug (underscores → spaces)
            title = old_slug.replace("_", " ")
            canonical_slug = _slug(title, max_len=80)
            canonical_name = f"{prefix}_{idx}_{canonical_slug}{ext}"
            if canonical_name != f.name:
                new_path = f.parent / canonical_name
                if not new_path.exists():
                    f.rename(new_path)
                    print_info(f"  Renamed: {f.name}  →  {canonical_name}")
                    renamed += 1
                else:
                    print_warning(f"  Skipped (target exists): {canonical_name}")

    if renamed:
        print_success(f"Fixed {renamed} filename(s).")
    else:
        print_info("No filename fixes needed — all names already follow the convention.")


@click.command()
@click.option("--fix", is_flag=True, default=False, help="Repair truncated/inconsistent generated filenames")
@click.pass_context
def doctor(ctx, fix):
    """Check Phoenix configuration and connectivity (API keys, intelligence server, DB)."""
    if fix:
        _doctor_fix_filenames(ctx)
        return
    config_path = ctx.obj.get("config_path")
    config = PhoenixConfig.load(config_path)

    all_ok = True

    # 1. LLM API key check
    import os

    _providers = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "ollama": None,
    }
    configured_providers = [
        name for name, var in _providers.items() if var is None or os.environ.get(var, "")
    ]
    if configured_providers:
        print_success(f"LLM API key(s) found for: {', '.join(configured_providers)}")
    else:
        all_ok = False
        print_error("No LLM API key configured. Phoenix cannot generate real automation scripts.")
        click.echo("  Set one of:")
        click.echo("    export ANTHROPIC_API_KEY=sk-ant-...")
        click.echo("    export OPENAI_API_KEY=sk-...")
        click.echo("    export GOOGLE_API_KEY=AIza...")

    # 2. Intelligence server connectivity + LLM status
    import requests as _requests

    intel_url = config.intelligence.base_url.rstrip("/")
    # Health endpoint is always at the server root, not under /api/v1
    from urllib.parse import urlparse
    _parsed = urlparse(intel_url)
    _server_root = f"{_parsed.scheme}://{_parsed.netloc}"
    health_url = f"{_server_root}/health"
    try:
        resp = _requests.get(health_url, timeout=5)
        data = resp.json()
        if data.get("llm", {}).get("configured"):
            provider = data["llm"]["provider"]
            model = data["llm"].get("model", "unknown")
            print_success(f"Intelligence server: OK  (LLM={provider}/{model})")
        else:
            all_ok = False
            warning = data.get("llm", {}).get("warning", "LLM not configured on server.")
            print_warning(f"Intelligence server reachable but LLM not configured: {warning}")
    except _requests.ConnectionError:
        all_ok = False
        print_error(
            f"Cannot reach intelligence server at {intel_url}. "
            "Start it with: cd phoenix-intelligence && uvicorn api.server:app --port 8001"
        )
    except Exception as exc:
        all_ok = False
        print_error(f"Intelligence server health check failed: {exc}")

    # 3. Database write access
    from phoenix.storage.database import check_db_write_access

    db_url = config.database.url
    if check_db_write_access(db_url):
        print_success(f"Database write access: OK  ({db_url})")
    else:
        all_ok = False
        print_error(f"Database not writable: {db_url}. Check permissions and disk space.")

    # 4. pytest plugin availability
    from phoenix.execution.runner import _preflight_check

    missing = _preflight_check()
    if missing:
        all_ok = False
        print_error(f"Missing pytest plugin(s): {', '.join(missing)}")
        click.echo(f"  Fix: pip install {' '.join(missing)}")
    else:
        print_success("pytest plugins: pytest-json-report, pytest-html — installed")

    # 5. Browser installation check
    _BROWSERS = {
        "chromium": None,
        "firefox":  None,
        "webkit":   None,
        "chrome":   "chrome",
        "msedge":   "msedge",
    }
    import subprocess as _sp
    for _bname, _channel in _BROWSERS.items():
        try:
            _args = ["playwright", "install", "--dry-run"]
            _args += (["--channel", _channel] if _channel else [])
            _args.append(_bname if not _channel else "chromium")
            _r = _sp.run(_args, capture_output=True, text=True, timeout=10)
            # Playwright prints "browser is already installed" or an error
            if "already" in _r.stdout.lower() or _r.returncode == 0:
                print_success(f"Browser {_bname}: installed")
            else:
                _install_cmd = f"playwright install {_channel or _bname}"
                print_warning(f"Browser {_bname}: not found → run: {_install_cmd}")
        except Exception:
            pass  # playwright CLI not available — skip

    click.echo("")
    if all_ok:
        print_success("Phoenix doctor: all checks passed.")
    else:
        print_warning("Phoenix doctor: some checks failed. See above for details.")


@click.command()
@click.argument("name", default="")
@click.option("--project-name", "-p", default="", help="Project name (alias for NAME argument)")
@click.option("--base-url", "-u", default="", help="Default application URL")
@click.option(
    "--browser",
    "-b",
    default="chromium",
    type=click.Choice(["chromium", "firefox", "webkit"], case_sensitive=False),
    help="Default browser for generated conftest.py",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config/conftest files")
@click.option("--dry-run", is_flag=True, help="Show what would be created without writing files")
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Skip all prompts and use provided options / defaults",
)
@click.option(
    "--dir",
    "-d",
    "target_dir",
    default=".",
    type=click.Path(),
    help="Target directory (default: current directory)",
)
@click.option(
    "--bdd",
    "use_bdd",
    is_flag=True,
    default=False,
    help="Scaffold a keyword-driven BDD layer (features/ + steps/ + keyword catalog)",
)
@click.pass_context
def init(ctx, name, project_name, base_url, browser, force, dry_run, non_interactive, target_dir, use_bdd):
    """Initialise a new Phoenix project with canonical layout.

    NAME  Optional project name. Falls back to --project-name or directory name.
    """
    config_path = ctx.obj.get("config_path")
    config = PhoenixConfig.load(config_path)

    # Resolve project name
    resolved_name = name or project_name or Path(target_dir).resolve().name or "default"

    # Resolve base_url
    resolved_url = base_url or config.project.resolved_base_url or ""

    # Interactive prompts (unless --non-interactive)
    if not non_interactive and not dry_run:
        if not resolved_url:
            resolved_url = click.prompt(
                "Application base URL (leave blank to set later)", default="", show_default=False
            )

    resolved_dir = Path(target_dir).resolve()

    if dry_run:
        print_info(f"[dry-run] Would scaffold project '{resolved_name}' in: {resolved_dir}")

    from phoenix.scaffold import scaffold_project as _scaffold

    result = _scaffold(
        name=resolved_name,
        target_dir=resolved_dir,
        base_url=resolved_url,
        browser=browser,
        force=force,
        dry_run=dry_run,
        bdd=use_bdd,
    )
    if use_bdd:
        print_info("BDD layer enabled — features/ and steps/ scaffolded.")

    if not result.ok:
        for err in result.errors:
            print_error(err)
        raise click.Abort()

    prefix = "[dry-run] " if dry_run else ""
    for path in result.created_dirs:
        if ctx.obj.get("verbose"):
            print_info(f"{prefix}Created dir:  {path}")
    for path in result.created_files:
        print_info(f"{prefix}Created:  {path}")
    for path in result.skipped_files:
        print_warning(f"{prefix}Skipped (exists): {path}")

    print_success(
        f"{prefix}Phoenix project '{resolved_name}' initialised in {resolved_dir}"
    )
    if not dry_run and result.created_files:
        rc = resolved_dir / ".phoenixrc"
        if rc.exists():
            print_info(f"Config: {rc}")
        print_info("Next: phoenix generate --story-file user_story.txt --url <app-url>")


@click.command()
@click.option(
    "--dir",
    "-d",
    "target_dir",
    default=".",
    type=click.Path(exists=True),
    help="Project directory to migrate (default: current directory)",
)
@click.option("--dry-run", is_flag=True, help="Show what would change without writing files")
@click.pass_context
def migrate(ctx, target_dir, dry_run):
    """Migrate an existing project to the current canonical Phoenix layout.

    Adds missing directories and template files without overwriting existing ones.
    """
    from phoenix.scaffold import migrate_project

    source = Path(target_dir).resolve()
    if dry_run:
        print_info(f"[dry-run] Migrating project in: {source}")

    result = migrate_project(source_dir=source, dry_run=dry_run)

    prefix = "[dry-run] " if dry_run else ""
    for path in result.created_files:
        print_info(f"{prefix}Added: {path}")
    for path in result.skipped_files:
        print_warning(f"{prefix}Already exists (skipped): {path}")

    if result.ok:
        print_success(f"{prefix}Migration complete for: {source}")
    else:
        for err in result.errors:
            print_error(err)


@click.command()
@click.option("--story", "-s", help="User story text")
@click.option(
    "--story-file", "-f", type=click.Path(exists=True), help="Path to user story text file"
)
@click.option(
    "--jira", "-j", default=None, metavar="ISSUE_KEY",
    help="Jira issue key (e.g. PROJ-123). Fetches story, criteria and attachments from Jira.",
)
@click.option("--url", "-u", help="Application URL to test (required for automation tests)")
@click.option(
    "--criteria", "-c", multiple=True, help="Acceptance criteria (can be specified multiple times)"
)
@click.option("--project", "-p", help="Project name (uses default if not specified)")
@click.option(
    "--type",
    "-t",
    type=click.Choice(["manual", "automation", "both"], case_sensitive=False),
    default="manual",
    help="Type of tests to generate (default: manual)",
)
@click.option(
    "--risk",
    "-r",
    type=click.Choice(["smoke", "regression", "edge"], case_sensitive=False),
    help="Risk level for tests",
)
@click.option(
    "--docs",
    "-d",
    type=click.Path(),
    default=None,
    help=(
        "Path to a file or folder of supporting documents (PDF, DOCX, XLSX, JSON, CSV…). "
        "If omitted, auto-discovers a folder named after the story file "
        "(e.g. user_stories/apply_leave/ for apply_leave.txt)."
    ),
)
@click.option(
    "--clean",
    is_flag=True,
    help="Delete existing manual_tests/ files before generating",
)
@click.option(
    "--no-gate",
    "no_gate",
    is_flag=True,
    default=False,
    help=(
        "Disable the quality gate — save all generated tests even if they have "
        "short descriptions or few steps. Useful when iterating on prompts."
    ),
)
@click.option(
    "--strict-gate",
    "strict_gate",
    is_flag=True,
    default=False,
    help=(
        "Enable strict quality gate thresholds (≥ 2 steps, ≥ 10-char description). "
        "Suitable for CI pipelines."
    ),
)
@click.pass_context
def generate(ctx, story, story_file, jira, url, criteria, project, type, risk, docs, clean, no_gate, strict_gate):
    """Generate test cases from user story and application URL"""
    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)

    client = PhoenixClient(config_path=config_path)

    if project:
        client.set_project(project)

    # Use default application URL from config if not provided
    if not url:
        url = client.config.project.resolved_base_url

    # ---------------------------------------------------------------------------
    # Jira source: fetch story + criteria + attachments from a Jira issue
    # ---------------------------------------------------------------------------
    _jira_docs: list = []
    if jira:
        story, criteria, _jira_docs = _fetch_from_jira(
            issue_key=jira,
            jira_config=client.config.jira,
            verbose=verbose,
        )

    # Validate URL for automation tests
    if type in ["automation", "both"] and not url:
        click.echo("[ERROR] --url is required for automation test generation", err=True)
        raise click.Abort()

    if not story and not story_file and not jira:
        click.echo("[ERROR] Provide --story, --story-file, or --jira ISSUE_KEY", err=True)
        raise click.Abort()

    if clean:
        manual_dir = Path(client.config.project.manual_output_dir)
        if not _clean_project_directory(manual_dir, manual_dir, verbose=verbose):
            sys.exit(1)
        print_success("Clean completed — manual_tests/ is empty.")

    print_header("Generating test cases...")

    # Load project-specific domain knowledge
    _gen_project_root = Path(config_path).parent if config_path else Path.cwd()
    _domain_knowledge = _load_domain_knowledge(_gen_project_root)
    if _domain_knowledge:
        print_info("Domain knowledge loaded from domain_knowledge/")

    # Load supporting documents (wireframes, specs, data schemas, etc.)
    from phoenix.documents.loader import DocumentLoader
    _doc_loader = DocumentLoader()
    _supporting_docs = []
    if docs:
        _docs_path = Path(docs)
        if _docs_path.is_dir():
            _supporting_docs = _doc_loader.load_directory(_docs_path)
        elif _docs_path.is_file():
            _doc = _doc_loader.load_file(_docs_path)
            if _doc:
                _supporting_docs = [_doc]
    elif story_file:
        # Auto-discover: user_stories/apply_leave.txt → user_stories/apply_leave/
        _auto_docs_dir = _doc_loader.supporting_docs_dir_for_story(Path(story_file))
        if _auto_docs_dir.is_dir():
            _supporting_docs = _doc_loader.load_directory(_auto_docs_dir)
    # Merge Jira attachments with any explicitly loaded docs
    _supporting_docs = _jira_docs + _supporting_docs
    if _supporting_docs:
        print_info(f"{len(_supporting_docs)} supporting document(s) loaded")

    _gate_kwargs = dict(gate=not no_gate, strict_gate=strict_gate)
    if no_gate:
        print_warning("Quality gate disabled (--no-gate): all generated tests will be saved.")
    elif strict_gate:
        print_info("Strict quality gate enabled: tests must meet CI-grade thresholds.")

    try:
        results = []
        if jira:
            # Jira path: story and criteria are already resolved above
            results.append(
                client.generate_tests(
                    user_story=story,
                    application_url=url,
                    acceptance_criteria=list(criteria) if criteria else [],
                    test_type=type,
                    risk_level=risk,
                    domain_knowledge=_domain_knowledge,
                    supporting_documents=_supporting_docs,
                    **_gate_kwargs,
                )
            )
        elif story_file:
            from phoenix.sdk.story_parser import parse_user_story_file

            with open(story_file, "r", encoding="utf-8") as f:
                parsed_stories = parse_user_story_file(f.read())
            if not parsed_stories:
                raise ValueError("No user stories found in story file")
            for parsed in parsed_stories:
                results.append(
                    client.generate_tests(
                        user_story=parsed.title,
                        application_url=url,
                        acceptance_criteria=parsed.acceptance_criteria,
                        test_type=type,
                        risk_level=risk,
                        domain_knowledge=_domain_knowledge,
                        supporting_documents=_supporting_docs,
                        **_gate_kwargs,
                    )
                )
        else:
            results.append(
                client.generate_tests(
                    user_story=story,
                    application_url=url,
                    acceptance_criteria=list(criteria) if criteria else [],
                    test_type=type,
                    risk_level=risk,
                    domain_knowledge=_domain_knowledge,
                    supporting_documents=_supporting_docs,
                    **_gate_kwargs,
                )
            )

        all_manual = [t for r in results for t in r.get("manual_tests", [])]
        all_automation = [t for r in results for t in r.get("automation_tests", [])]
        total_locators = sum(r.get("metadata", {}).get("locators_saved", 0) for r in results)
        for result in results:
            _print_intelligence_metadata_warnings(result.get("metadata"))
        print_generate_results(all_manual, all_automation, verbose=verbose)

        # BDD mode: also write a feature file from the manual tests
        _gen_project_root_local = Path(config_path).parent if config_path else Path.cwd()
        if getattr(client.config.project, "bdd", False) and all_manual and story_file:
            try:
                _write_bdd_feature(
                    story_file=Path(story_file),
                    manual_tests=all_manual,
                    project_root=_gen_project_root_local,
                    verbose=verbose,
                )
            except Exception as _exc:
                print_warning(f"Feature file generation skipped: {_exc}")
        if total_locators:
            locators_dir = Path(client.config.project.test_output_dir).parent / "locators"
            print_info(
                f"Locators: {total_locators} bundle(s) saved to {locators_dir}"
                " — run 'phoenix locators' to inspect them."
            )

        # Module-aware consolidated output
        if story_file:
            _write_module_artifacts(
                module=_module_from_file(Path(story_file)),
                all_manual=all_manual,
                all_automation=all_automation,
                project_root=Path(config_path).parent if config_path else Path.cwd(),
                verbose=verbose,
            )

    except Exception as exc:
        print_error(f"Error generating tests: {exc}")
        if verbose:
            import traceback

            err_console.print(traceback.format_exc())
        raise click.Abort() from exc


@click.command()
@click.option(
    "--manual-dir",
    "-m",
    default="manual_tests",
    type=click.Path(),
    help="Directory containing manual test Markdown files (default: manual_tests/)",
)
@click.option(
    "--file",
    "-f",
    "manual_file",
    default=None,
    type=click.Path(exists=True),
    help="Automate a single manual test file instead of the whole manual_tests/ directory",
)
@click.option(
    "--test-case",
    "-tc",
    "test_case",
    default=None,
    help="Automate only the test case whose name contains this string (case-insensitive)",
)
@click.option("--url", "-u", default=None, help="Application URL (passed to LLM for context)")
@click.option("--project", "-p", default=None, help="Project name")
@click.option(
    "--clean",
    is_flag=True,
    help="Delete existing tests/ scripts before generating",
)
@click.pass_context
def automate(ctx, manual_dir, manual_file, test_case, url, project, clean):
    """Generate automation scripts from reviewed manual test cases.

    Reads every manual_test_*.md file from the manual_tests/ directory,
    then generates exactly one pytest + Playwright script per manual test.

    Workflow:

    \b
      1. phoenix generate --story-file user_story.txt --url <app>
         (review / edit manual_tests/*.md as needed)
      2. phoenix automate --url <app>
      3. phoenix run

    Examples:

    \b
      # Automate all manual tests
      phoenix automate --url https://app.com

      # Automate a single file
      phoenix automate --file manual_tests/login.md --url https://app.com

      # Automate one specific test case by name
      phoenix automate --test-case "valid login" --url https://app.com
    """
    from phoenix.generators.automation import AutomationTestGenerator
    from phoenix.generators.manual_parser import load_manual_tests_from_dir, load_manual_tests_from_file
    from phoenix.locators.extractor import extract_locators_from_script, page_name_from_script_path
    from phoenix.locators.registry import LocatorRegistry
    from phoenix.sdk.config import PhoenixConfig
    from phoenix.sdk.intelligence_client import IntelligenceClient

    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)
    config = PhoenixConfig.load(config_path)

    # Load from a single file or the whole directory
    if manual_file:
        manual_path = Path(manual_file)
        manual_tests = load_manual_tests_from_file(manual_path)
        source_label = manual_file
    else:
        manual_path = Path(manual_dir)
        if not manual_path.is_absolute() and config_path:
            manual_path = Path(config_path).parent / manual_dir
        manual_tests = load_manual_tests_from_dir(manual_path)
        source_label = str(manual_path)

    if not manual_tests:
        print_warning(
            f"No manual test files found in '{source_label}'. "
            "Run 'phoenix generate' first to create manual tests."
        )
        return

    # Filter by test case name if --test-case was given
    if test_case:
        filtered = [t for t in manual_tests if test_case.lower() in t.get("name", "").lower()]
        if not filtered:
            available = "\n  ".join(t.get("name", "") for t in manual_tests)
            print_error(
                f"No test case matching '{test_case}' found.\n"
                f"Available test cases:\n  {available}"
            )
            raise click.Abort()
        manual_tests = filtered
        print_info(f"Filtered to {len(manual_tests)} test case(s) matching '{test_case}'")

    print_header(f"Automating {len(manual_tests)} manual test(s) from '{source_label}'")
    for t in manual_tests:
        src = Path(t.get("source_file", "")).name
        print_info(f"  {t['name']}  ({src})")

    # Optional clean
    if clean:
        test_dir = Path(config.project.test_output_dir)
        if not _clean_project_directory(test_dir, test_dir, verbose=verbose):
            import sys
            sys.exit(1)
        print_success("Clean completed.")

    # Use application URL from flag or config
    application_url = url or config.project.resolved_base_url
    if not application_url:
        print_warning(
            "No application URL provided. Pass --url https://your-app.com or set "
            "'base_url' in .phoenixrc.\n"
            "Without a real URL the generated tests will contain placeholder navigation "
            "and locators cannot be grounded against a live DOM snapshot."
        )

    # Load project-specific domain knowledge
    project_root = Path(config_path).parent if config_path else Path.cwd()
    domain_knowledge = _load_domain_knowledge(project_root)
    if domain_knowledge:
        print_info("Domain knowledge loaded from domain_knowledge/")

    # Detect layout and mode
    _use_pom = getattr(config.project, "layout", "flat") == "pom-v1"
    _use_bdd = _use_pom and getattr(config.project, "bdd", False)
    _manifest_context = ""
    _keywords_context = ""

    if _use_pom:
        try:
            from phoenix.intelligence.manifest import ProjectIndexer
            indexer = ProjectIndexer(project_root)
            manifest_obj = indexer.build()
            manifest_path = indexer.save(manifest_obj)
            _manifest_context = manifest_obj.to_prompt_context()
            print_info(f"Manifest built → {manifest_path.relative_to(project_root)}")
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger(__name__).warning("Manifest build failed (non-fatal): %s", _exc)

    if _use_bdd:
        try:
            from phoenix.intelligence.keyword_catalog import KeywordCatalog
            _catalog_path = project_root / ".phoenix" / "keywords.json"
            _catalog = KeywordCatalog(_catalog_path)
            _keywords_context = _catalog.to_prompt_summary()
            print_info(f"Keyword catalog loaded — {len(_catalog)} keyword(s) available")
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger(__name__).warning("Keyword catalog load failed (non-fatal): %s", _exc)

    # Call intelligence server
    intel_client = IntelligenceClient(config)
    try:
        click.echo("")
        _mode_label = "BDD" if _use_bdd else ("POM" if _use_pom else "flat")
        print_info(f"Calling intelligence server to generate automation scripts [{_mode_label} mode]…")
        result = intel_client.automate_from_manual(
            manual_tests=manual_tests,
            application_url=application_url,
            domain_knowledge=domain_knowledge,
            manifest=_manifest_context,
            use_pom=_use_pom,
            use_bdd=_use_bdd,
            keywords=_keywords_context,
        )
    except Exception as exc:
        print_error(f"Intelligence server error: {exc}")
        raise click.Abort() from exc

    automation_tests = result.get("automation_tests", [])
    if not automation_tests:
        print_warning("No automation scripts were generated.")
        return
    _print_intelligence_metadata_warnings(result.get("metadata"))
    for test in automation_tests:
        for warning in test.get("warnings", []):
            print_warning(f"{test.get('name', 'automation_test')}: {warning}")

    # BDD mode: apply BDD delta bundles and register keywords
    if _use_bdd:
        try:
            from phoenix.output.coordinator import OutputManager
            from phoenix.intelligence.keyword_catalog import KeywordCatalog, Keyword
            manager = OutputManager(project_root)
            bdd_written: List[str] = []
            keywords_reused = 0
            keywords_added = 0
            _catalog_path = project_root / ".phoenix" / "keywords.json"
            _catalog = KeywordCatalog(_catalog_path)

            for test in automation_tests:
                bundle = test.get("bdd_bundle")
                if not bundle:
                    continue
                # Apply file delta (features, steps, page objects, locators)
                bdd_bundle_for_output = {
                    "page_objects": bundle.get("page_objects", []),
                    "locators": bundle.get("locators", []),
                    "tests": [
                        {"action": s["action"], "file": s["file"], "code": s["code"]}
                        for s in bundle.get("steps", [])
                    ],
                    "test_data": bundle.get("test_data", []),
                }
                # Write feature files
                for feat in bundle.get("features", []):
                    feat_path = project_root / feat["file"]
                    feat_path.parent.mkdir(parents=True, exist_ok=True)
                    if feat["action"] == "create" or not feat_path.exists():
                        feat_path.write_text(feat["content"], encoding="utf-8")
                        bdd_written.append(str(feat_path))
                    elif feat["action"] == "extend" and feat_path.exists():
                        existing = feat_path.read_text(encoding="utf-8")
                        for line in feat["content"].splitlines():
                            if line.strip().startswith("Scenario:") and line not in existing:
                                existing += f"\n{line}\n"
                        feat_path.write_text(existing, encoding="utf-8")
                        bdd_written.append(str(feat_path))

                files = manager.apply(bdd_bundle_for_output)
                bdd_written.extend(files)

                # Register new keywords; count reused
                for kw_data in bundle.get("keywords", []):
                    kw_id = kw_data.get("id", "")
                    if not kw_id:
                        continue
                    match = _catalog.find_match(kw_data.get("canonical", ""))
                    if match:
                        keywords_reused += 1
                        if kw_data.get("canonical", "") not in [match.canonical] + match.aliases:
                            _catalog.add_alias(match.id, kw_data["canonical"])
                    else:
                        try:
                            _catalog.add(Keyword.from_dict(kw_data))
                            keywords_added += 1
                        except Exception:
                            pass

            if bdd_written:
                click.echo("")
                print_success(
                    f"BDD delta applied — {len(set(bdd_written))} file(s) written/updated. "
                    f"Reused {keywords_reused} keywords, added {keywords_added} new."
                )
                for f in sorted(set(bdd_written)):
                    try:
                        rel = Path(f).relative_to(project_root)
                    except ValueError:
                        rel = Path(f)
                    print_info(f"  {rel}")
                print_info("Next: phoenix run")
                return
        except Exception as _exc:
            print_warning(f"BDD delta apply failed, falling back to flat output: {_exc}")

    # POM mode: apply delta bundles via OutputManager (pom-v1 projects)
    if _use_pom:
        try:
            from phoenix.output.coordinator import OutputManager
            manager = OutputManager(project_root)
            pom_written: List[str] = []
            for test in automation_tests:
                bundle = test.get("pom_bundle")
                if bundle:
                    files = manager.apply(bundle)
                    pom_written.extend(files)
            if pom_written:
                click.echo("")
                print_success(f"POM delta applied — {len(pom_written)} file(s) written/updated:")
                for f in pom_written:
                    try:
                        rel = Path(f).relative_to(project_root)
                    except ValueError:
                        rel = Path(f)
                    print_info(f"  {rel}")

                # Persist locators from PAGE OBJECT files (test files are thin wrappers —
                # all real Playwright locator calls are in the page object class body)
                locators_dir = Path(config.project.test_output_dir).parent / "locators"
                from phoenix.locators.persist import persist_locators
                pom_scripts = []
                for test in automation_tests:
                    bundle = test.get("pom_bundle") or {}
                    for node in bundle.get("page_objects", []):
                        fp = str(project_root / node["file"])
                        # Page name: pages/login_page.py → login
                        page_name = Path(node["file"]).stem.removesuffix("_page") or "global"
                        pom_scripts.append({
                            "script_path": fp,
                            "page": page_name,
                            "locators": test.get("locators", []),
                        })
                total_locators = persist_locators(pom_scripts, locators_dir)
                if total_locators:
                    print_info(
                        f"Locators: {total_locators} bundle(s) saved to {locators_dir}/ "
                        "— run 'phoenix locators' to inspect."
                    )
                print_info("Next: phoenix run")
                return
        except Exception as _exc:
            print_warning(f"POM delta apply failed, falling back to flat output: {_exc}")

    # Flat mode: write scripts via AutomationTestGenerator
    from phoenix.exceptions import QualityGateFailedError
    auto_gen = AutomationTestGenerator(
        output_dir=config.project.test_output_dir,
        intel_client=intel_client,
        repair_attempts=config.intelligence.repair_attempts,
        collect_only_gate=config.intelligence.collect_only_gate,
    )
    try:
        written = auto_gen.generate(
            automation_tests=automation_tests,
            user_story="",
            application_url=application_url,
            acceptance_criteria=[],
        )
    except QualityGateFailedError as exc:
        print_error("Quality gate blocked script generation. Blocking issues:")
        for err in exc.errors:
            print_error(f"  • {err}")
        print_info(
            "Fix the manual test steps that trigger these issues, "
            "then re-run 'phoenix automate'."
        )
        raise click.Abort() from exc

    # Extract and save locators (shared helper: LLM + regex, ranked, page-wise)
    locators_dir = Path(config.project.test_output_dir).parent / "locators"
    from phoenix.locators.persist import persist_locators
    # Enrich the written list: carry LLM locators[] and use the module-derived
    # page name (e.g. "login") so files are saved as locators/login.json rather
    # than locators/001_login_valid_credentials.json  (B6).
    module_page = _module_from_file(manual_path)
    for w, t in zip(written, automation_tests):
        w.setdefault("locators", t.get("locators", []))
        w.setdefault("page", module_page)
    total_locators = persist_locators(written, locators_dir)

    # Module-aware consolidated output (groups by module derived from manual file path)
    project_root = Path(config_path).parent if config_path else Path.cwd()
    _write_module_artifacts(
        module=_module_from_file(manual_path),
        all_manual=manual_tests,  # pass manual tests so tags flow into @pytest.mark decorators
        all_automation=written,
        project_root=project_root,
        verbose=verbose,
    )

    # Summary
    click.echo("")
    print_success(
        f"Generated {len(written)} automation script(s) → {config.project.test_output_dir}/"
    )
    for test in written:
        manual_name = test.get("manual_test_name", "")
        script = Path(test.get("script_path", "")).name
        print_info(f"  {manual_name}  →  {script}")

    if total_locators:
        print_info(
            f"Locators: {total_locators} bundle(s) saved to {locators_dir}/ "
            "— run 'phoenix locators' to inspect."
        )

    click.echo("")
    print_info("Next: phoenix run")


@click.command()
@click.option(
    "--logs-dir",
    "-l",
    default="logs",
    type=click.Path(),
    help="Directory containing JSONL execution logs (default: logs/)",
)
@click.option("--run-id", "-r", default=None, help="Show attempts for a specific run ID")
@click.option(
    "--limit",
    "-n",
    default=10,
    type=int,
    help="Number of recent runs to list (default: 10)",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
)
@click.pass_context
def logs(ctx, logs_dir, run_id, limit, output):
    """Show execution logs from previous test runs."""
    import json as _json
    from phoenix.execution.logger import ExecutionLogger

    logger = ExecutionLogger(logs_dir=logs_dir)

    if run_id:
        attempts = logger.get_attempts(run_id)
        if not attempts:
            print_warning(f"No attempts found for run {run_id!r}")
            return
        if output == "json":
            click.echo(_json.dumps([a.model_dump() for a in attempts], indent=2))
            return
        click.echo(f"Attempts for run {run_id}:")
        for a in attempts:
            status_sym = "✓" if a.status == "passed" else "✗"
            click.echo(
                f"  {status_sym} [{a.attempt}] {a.test_name} — {a.status}"
                + (f" ({a.error_type})" if a.error_type else "")
                + f"  {a.duration_seconds:.1f}s"
            )
        return

    runs = logger.list_runs()[:limit]
    if not runs:
        print_warning(f"No execution logs found in '{logs_dir}'.")
        return

    if output == "json":
        click.echo(_json.dumps(runs, indent=2))
        return

    header = f"{'Run ID':<12} {'Started':<24} {'Status':<8} {'T':>4} {'P':>4} {'F':>4} {'s':>6}"
    click.echo(header)
    click.echo("-" * len(header))
    for run in runs:
        started = run.get("started_at", "")[:19].replace("T", " ")
        click.echo(
            f"{run.get('run_id', ''):<12} {started:<24} {run.get('status', ''):<8} "
            f"{run.get('total', 0):>4} {run.get('passed', 0):>4} {run.get('failed', 0):>4} "
            f"{run.get('duration_seconds', 0):>6.1f}"
        )


@click.command()
@click.option("--project", "-p", help="Project name (uses default if not specified)")
@click.option(
    "--test-ids",
    "-t",
    multiple=True,
    help="Specific test IDs to execute (can be specified multiple times)",
)
@click.option(
    "--browser",
    "-b",
    type=click.Choice(["chromium", "firefox", "webkit"], case_sensitive=False),
    help="Browser to use for UI tests",
)
@click.pass_context
def execute(ctx, project, test_ids, browser):
    """Execute test cases"""
    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)

    client = PhoenixClient(config_path=config_path)

    if project:
        client.set_project(project)

    print_header("Executing tests...")

    try:
        result = client.execute_tests(
            test_ids=list(test_ids) if test_ids else None,
            browser=browser,
        )
        print_execution_results(result, verbose=verbose)

    except Exception as exc:
        print_error(f"Error executing tests: {exc}")
        if verbose:
            import traceback

            err_console.print(traceback.format_exc())
        raise click.Abort() from exc


@click.command()
@click.argument("test_path", default="", required=False, metavar="[TEST_PATH]")
@click.option("--project", "-p", help="Project name (uses default if not specified)")
@click.option(
    "--test-ids",
    "-t",
    multiple=True,
    help="Specific test IDs to execute (can be specified multiple times)",
)
@click.option(
    "--file", "-f", "run_file",
    default=None,
    type=click.Path(),
    help="Run only this test file (e.g. tests/login/test_login.py)",
)
@click.option(
    "--test",
    "run_test",
    default=None,
    help="Run tests whose name contains this substring (maps to pytest -k)",
)
@click.option(
    "-k",
    "run_keyword",
    default=None,
    help="pytest -k expression (substring match across collected test IDs)",
)
@click.option(
    "-m",
    "run_marker",
    default=None,
    help="Run only tests with this pytest marker (e.g. smoke, regression)",
)
@click.option(
    "--scenario",
    "run_scenario",
    default=None,
    help="(BDD) Run the scenario whose title contains this text",
)
@click.option(
    "--feature",
    "run_feature",
    default=None,
    type=click.Path(),
    help="(BDD) Run all scenarios in this .feature file",
)
@click.option(
    "--browser",
    "-b",
    default="chromium",
    help=(
        "Browser: chromium (default), firefox, webkit, chrome, msedge. "
        "Use 'all' to run sequentially on chromium + firefox + webkit."
    ),
)
@click.option(
    "--heal",
    is_flag=True,
    default=True,
    help="Enable self-healing retries on failure (default: enabled)",
)
@click.option(
    "--max-attempts",
    default=3,
    type=int,
    help="Maximum healing attempts per failing test (default: 3)",
)
@click.option(
    "--logs-dir",
    default="logs",
    type=click.Path(),
    help="Directory for JSONL execution logs (default: logs/)",
)
@click.option(
    "--locators-dir",
    default="locators",
    type=click.Path(),
    help="Directory for LocatorBundle JSON files (default: locators/)",
)
@click.option(
    "--failed-only",
    is_flag=True,
    help="Only re-run tests that failed in the previous run (requires --logs-dir)",
)
@click.option(
    "--headed",
    is_flag=True,
    default=False,
    help="Run tests in headed (visible) browser mode — useful for debugging",
)
@click.option(
    "--slow-mo",
    "slow_mo",
    default=0,
    type=int,
    help="Slow down each Playwright action by N milliseconds (headed debug mode)",
)
@click.option(
    "--viewport",
    "viewport",
    default=None,
    help="Override viewport size for this run — format: WIDTHxHEIGHT (e.g. 1366x768)",
)
@click.pass_context
def run(ctx, test_path, project, test_ids, run_file, run_test, run_keyword, run_marker,
        run_scenario, run_feature, browser, heal, max_attempts, logs_dir, locators_dir,
        failed_only, headed, slow_mo, viewport):
    """Run tests with self-healing retries and execution logging.

    Examples:

    \b
      phoenix run                                   # whole suite
      phoenix run tests/login/test_login.py         # single file (positional)
      phoenix run --file tests/login/test_login.py  # same, explicit flag
      phoenix run -k "duplicate_group"              # -k substring
      phoenix run --test test_007_duplicate          # test name substring
      phoenix run -m smoke                          # marker
      phoenix run --scenario "Successful login"     # BDD scenario title
      phoenix run --feature features/login.feature  # BDD feature file
      phoenix run --browser chrome                  # real Chrome
      phoenix run --browser all                     # chromium + firefox + webkit

    Failures are classified by error type and healed automatically before
    each retry.  Every attempt is logged to logs/<run_id>.jsonl for
    post-run analysis with ``phoenix logs``.
    """
    from phoenix.execution.healing import HealingEngine
    from phoenix.execution.logger import ExecutionLogger
    from phoenix.locators.registry import LocatorRegistry

    config_path = ctx.obj.get("config_path")

    client = PhoenixClient(config_path=config_path)
    if project:
        client.set_project(project)

    # Build extra pytest args from targeting flags
    extra_pytest_args: List[str] = []

    # --file / positional path
    _resolved_file = run_file or (test_path if test_path else None)
    if _resolved_file:
        fp = Path(_resolved_file)
        if not fp.exists():
            test_dir = Path(client.config.project.test_output_dir)
            available = sorted(test_dir.rglob("test_*.py"))
            print_error(f"File not found: {_resolved_file}")
            if available:
                print_info("Available test files:")
                for f in available:
                    print_info(f"  {f}")
            raise click.Abort()

    # --feature (BDD): run a .feature file
    if run_feature:
        fp2 = Path(run_feature)
        if not fp2.exists():
            print_error(f"Feature file not found: {run_feature}")
            raise click.Abort()
        _resolved_file = str(fp2)

    # -k / --test / --scenario → pytest -k expression
    _k_parts = []
    if run_keyword:
        _k_parts.append(run_keyword)
    if run_test:
        _k_parts.append(run_test)
    if run_scenario:
        _k_parts.append(run_scenario)
    if _k_parts:
        extra_pytest_args += ["-k", " and ".join(_k_parts)]

    # -m marker
    if run_marker:
        extra_pytest_args += ["-m", run_marker]

    # Resolve test paths
    test_paths: List[str] = []
    if _resolved_file:
        test_paths = [str(_resolved_file)]
    elif test_ids:
        from phoenix.storage.models import TestCase as _TC, TestType as _TT
        with client._database.get_session() as session:
            tcs = session.query(_TC).filter(
                _TC.id.in_([int(tid) for tid in test_ids]),
                _TC.test_type == _TT.AUTOMATION,
            ).all()
            test_paths = [tc.script_path for tc in tcs if tc.script_path]
    else:
        test_dir = Path(client.config.project.test_output_dir)
        test_paths = [str(p) for p in sorted(test_dir.glob("test_*.py"))]

    if not test_paths:
        print_warning("No test scripts found to run.")
        return

    # --failed-only: filter to tests that failed in previous run
    if failed_only:
        logger_check = ExecutionLogger(logs_dir=logs_dir)
        prev_runs = logger_check.list_runs()
        if prev_runs:
            failed_names = logger_check.failed_tests(prev_runs[0]["run_id"])
            if failed_names:
                test_paths = [
                    p for p in test_paths
                    if any(Path(p).stem in name for name in failed_names)
                ]
                print_info(f"Re-running {len(test_paths)} previously failing test(s).")

    # Load locator registry
    locator_registry = None
    if Path(locators_dir).exists():
        locator_registry = LocatorRegistry.load_all(locators_dir)

    # Set up logger + engine
    exec_logger = ExecutionLogger(logs_dir=logs_dir)
    run_id = exec_logger.start_run(test_paths=test_paths)

    engine = HealingEngine(
        logger=exec_logger,
        max_attempts=max_attempts if heal else 1,
        locator_registry=locator_registry,
    )

    # Propagate headed/slow_mo to the subprocess environment
    import os as _os
    if headed:
        _os.environ["PWHEADED"] = "1"
        print_info("Running in headed mode (browser visible).")
    if slow_mo:
        _os.environ["PWSLOWMO"] = str(slow_mo)
        print_info(f"Slow-mo: {slow_mo}ms per action.")

    # Validate and propagate viewport
    if viewport:
        import re as _re
        if not _re.match(r"^\d+x\d+$", viewport):
            print_error(f"Invalid viewport format '{viewport}' — use WIDTHxHEIGHT e.g. 1920x1080")
            raise click.Abort()
        w, h = viewport.split("x")
        _os.environ["PW_VIEWPORT_W"] = w
        _os.environ["PW_VIEWPORT_H"] = h
    _vp_w = _os.environ.get("PW_VIEWPORT_W", "1920")
    _vp_h = _os.environ.get("PW_VIEWPORT_H", "1080")
    print_info(f"Viewport: {_vp_w}x{_vp_h}")

    # Resolve browsers for --browser all
    _browser_lower = browser.lower()
    if _browser_lower == "all":
        _browsers_to_run = ["chromium", "firefox", "webkit"]
    else:
        _browsers_to_run = [_browser_lower]

    print_header(
        f"Running {len(test_paths)} test(s) — "
        f"healing={'on' if heal else 'off'}, max_attempts={max_attempts}"
        + (f", browsers={','.join(_browsers_to_run)}" if len(_browsers_to_run) > 1 else f", browser={_browsers_to_run[0]}")
        + (f", k={extra_pytest_args[extra_pytest_args.index('-k')+1]}" if "-k" in extra_pytest_args else "")
        + (f", m={extra_pytest_args[extra_pytest_args.index('-m')+1]}" if "-m" in extra_pytest_args else "")
    )

    import time as _time

    total = len(test_paths) * len(_browsers_to_run)
    passed = failed = healed = 0
    start_all = _time.monotonic()

    for _cur_browser in _browsers_to_run:
        if len(_browsers_to_run) > 1:
            click.echo(f"\n  === {_cur_browser.upper()} ===")
        for _tp in test_paths:
            result = engine.run(
                test_path=_tp,
                run_id=run_id,
                browser=_cur_browser,
            )
            if result.final_status == "passed":
                passed += 1
                sym = "✓"
            else:
                failed += 1
                sym = "✗"
            if result.healed:
                healed += 1
            msg = f"  {sym} {Path(_tp).name}  ({result.attempts} attempt(s)"
            if result.healed:
                msg += f", healed via {result.error_class}"
            msg += f")  {result.duration_seconds:.1f}s"
            click.echo(msg)

    duration = _time.monotonic() - start_all
    run_record = exec_logger.finish_run(
        run_id,
        passed=passed,
        failed=failed,
        total=total,
        duration_seconds=round(duration, 2),
    )

    # Generate HTML report in reports/
    try:
        from phoenix.execution.reporter import generate_html_report

        reports_dir = Path("reports")
        if config_path:
            reports_dir = Path(config_path).parent / "reports"
        attempts = exec_logger.get_attempts(run_id)
        html_path = generate_html_report(run_id, run_record.model_dump(), attempts, reports_dir)
        print_info(f"HTML report: {html_path}")
    except Exception:
        pass  # Report generation is best-effort; never block the run

    print_info(f"\nRun ID: {run_id}  |  logs/{run_id}")
    if healed:
        print_success(f"Self-healed: {healed} test(s) recovered after retry")
    if failed == 0:
        print_success(f"All {total} test(s) passed in {duration:.1f}s")
    else:
        print_error(f"{failed}/{total} test(s) failed after {max_attempts} attempt(s)")
    print_info("Review details: phoenix logs --run-id " + run_id)


@click.command()
@click.option(
    "--locators-dir",
    "-l",
    default="locators",
    type=click.Path(),
    help="Directory containing LocatorBundle JSON files (default: locators/)",
)
@click.option("--page", "-p", default=None, help="Filter by logical page name")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
@click.pass_context
def locators(ctx, locators_dir, page, output):
    """List registered LocatorBundles from locators/<page>.json files."""
    from phoenix.locators.registry import LocatorRegistry
    import json as _json

    registry = LocatorRegistry.load_all(locators_dir)
    if len(registry) == 0:
        print_warning(f"No LocatorBundles found in '{locators_dir}'. Run phoenix generate first.")
        return

    rows = registry.summary()
    if page:
        rows = [r for r in rows if r["page"] == page]

    if output == "json":
        click.echo(_json.dumps(rows, indent=2))
        return

    # Table output
    header = f"{'Element':<35} {'Page':<20} {'Strategy':<14} {'Conf':>5} {'Alt':>4}"
    click.echo(header)
    click.echo("-" * len(header))
    for row in rows:
        click.echo(
            f"{row['element']:<35} {row['page']:<20} {row['primary_strategy']:<14} "
            f"{row['confidence']:>5.2f} {row['alternates']:>4}"
        )
    click.echo(f"\n{len(rows)} bundle(s) loaded from '{locators_dir}'")


@click.command()
@click.option(
    "--logs-dir",
    "-l",
    default="logs",
    type=click.Path(),
    help="Directory containing JSONL execution logs (default: logs/)",
)
@click.option(
    "--test-dir",
    "-t",
    default="tests",
    type=click.Path(),
    help="Directory containing automation scripts (default: tests/)",
)
@click.option(
    "--locators-dir",
    default="locators",
    type=click.Path(),
    help="Directory containing locator JSON files (default: locators/)",
)
@click.option("--run-id", "-r", default=None, help="Fix failures from a specific run (default: most recent)")
@click.option("--dry-run", is_flag=True, help="Show what would be fixed without writing files")
@click.option("--url", "-u", default=None, help="Application URL (for context in fix prompt)")
@click.pass_context
def fix(ctx, logs_dir, test_dir, locators_dir, run_id, dry_run, url):
    """Fix failing automation scripts using the error output from the last run.

    Reads failure logs, sends each broken script + its exact error to the
    intelligence server, and writes the corrected script back to disk.

    After fixing, re-run with: phoenix run --failed-only
    """
    import requests as _requests
    from phoenix.execution.logger import ExecutionLogger
    from phoenix.sdk.config import PhoenixConfig

    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)
    config = PhoenixConfig.load(config_path)
    intel_base = config.intelligence.base_url.rstrip("/")
    if intel_base.endswith("/api/v1"):
        intel_base = intel_base[: -len("/api/v1")]
    intel_url = intel_base

    exec_logger = ExecutionLogger(logs_dir=logs_dir)

    # Resolve which run to fix
    if run_id:
        target_run_id = run_id
    else:
        runs = exec_logger.list_runs()
        failed_runs = [r for r in runs if r.get("status") in ("failed", "error")]
        if not failed_runs:
            print_warning("No failed runs found in logs. Nothing to fix.")
            return
        target_run_id = failed_runs[0]["run_id"]

    attempts = exec_logger.get_attempts(target_run_id)
    failed_attempts = [
        a for a in attempts
        if a.status in ("failed", "error") and a.error_message
    ]

    if not failed_attempts:
        print_warning(f"No failures with error messages found in run {target_run_id!r}.")
        return

    print_header(f"Fixing {len(failed_attempts)} failed test(s) from run {target_run_id}")

    test_dir_path = Path(test_dir)
    fixed = skipped = unchanged = 0

    for attempt in failed_attempts:
        # Find the script file — match by test_name stem or test_path
        script_path: Optional[Path] = None
        if attempt.test_path and Path(attempt.test_path).exists():
            script_path = Path(attempt.test_path)
        else:
            # Search test_dir for a file whose stem matches the test name
            stem = attempt.test_name.replace("::", "_").replace("/", "_")
            candidates = list(test_dir_path.glob(f"*{stem}*.py"))
            if not candidates:
                # Try a looser match: any file containing the test function name
                for py_file in sorted(test_dir_path.glob("test_*.py")):
                    try:
                        if attempt.test_name in py_file.read_text(encoding="utf-8"):
                            candidates.append(py_file)
                            break
                    except OSError:
                        pass
            if candidates:
                script_path = candidates[0]

        if not script_path or not script_path.exists():
            print_warning(f"  Script not found for test '{attempt.test_name}' — skipping")
            skipped += 1
            continue

        script_code = script_path.read_text(encoding="utf-8")
        error_type = attempt.error_type or "unknown"
        error_message = attempt.error_message or ""

        click.echo(
            f"  Fixing: {script_path.name}  [{error_type}]"
            + ("  [dry-run]" if dry_run else "")
        )
        if verbose:
            click.echo(f"    Error: {error_message[:120]}")

        if dry_run:
            # For dry-run: report whether a registry fix is available
            if error_type in ("locator_not_found", "unknown"):
                _loc_dir = Path(locators_dir)
                if _loc_dir.exists():
                    try:
                        from phoenix.locators.registry import LocatorRegistry
                        from phoenix.execution.healing import LocatorHealingStrategy
                        _reg = LocatorRegistry.load_all(_loc_dir)
                        if len(_reg) > 0:
                            click.echo("    [dry-run] Registry alternate available — would skip LLM call")
                    except Exception:
                        pass
            fixed += 1
            continue

        # ── Try registry-first locator swap before calling the LLM ───────────
        registry_fixed = False
        if error_type in ("locator_not_found", "unknown"):
            _loc_dir = Path(locators_dir)
            if _loc_dir.exists():
                try:
                    from phoenix.locators.registry import LocatorRegistry
                    from phoenix.execution.healing import LocatorHealingStrategy
                    from phoenix.healing.audit import append_heal_record
                    _reg = LocatorRegistry.load_all(_loc_dir)
                    if len(_reg) > 0:
                        _pending: list = []
                        _healer = LocatorHealingStrategy()
                        _swapped = _healer.apply(
                            script_path,
                            error_message,
                            locator_registry=_reg,
                            _pending_heals=_pending,
                        )
                        if _swapped and _pending:
                            click.echo(f"    Fixed via registry alternate (no LLM call)")
                            for h in _pending:
                                append_heal_record(
                                    logs_dir=Path(logs_dir),
                                    page=h.get("page", "global"),
                                    element_name=h["element_name"],
                                    old_value=h.get("old_value", ""),
                                    new_value=h["new_value"],
                                    new_strategy=h["new_strategy"],
                                    confidence=h.get("confidence", 0.0),
                                    outcome="registry_fix",
                                    script=str(script_path),
                                )
                            registry_fixed = True
                            fixed += 1
                except Exception as _reg_exc:
                    if verbose:
                        click.echo(f"    Registry fix attempt failed: {_reg_exc}")

        if registry_fixed:
            continue

        # Call intelligence server
        try:
            resp = _requests.post(
                f"{intel_url}/api/v1/tests/fix",
                json={
                    "script_code": script_code,
                    "error_message": error_message,
                    "error_type": error_type,
                    "test_name": attempt.test_name,
                    "application_url": url,
                },
                timeout=config.intelligence.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except _requests.ConnectionError:
            print_error(
                f"Cannot reach intelligence server at {intel_url}. "
                "Start it with: uvicorn api.server:app --port 8001"
            )
            return
        except Exception as exc:
            print_error(f"    Fix request failed for '{attempt.test_name}': {exc}")
            skipped += 1
            continue

        if not data.get("changed"):
            click.echo(f"    No change — {data.get('fix_summary', 'script unchanged')}")
            unchanged += 1
            continue

        script_path.write_text(data["fixed_script"], encoding="utf-8")
        click.echo(f"    Fixed ({data.get('fix_summary', '')})")
        fixed += 1

    click.echo("")
    if dry_run:
        print_info(f"[dry-run] Would fix {fixed} script(s). No files written.")
    else:
        if fixed:
            print_success(f"Fixed {fixed} script(s).")
        if unchanged:
            print_warning(f"{unchanged} script(s) had no applicable fix (error type not matched)")
        if skipped:
            print_warning(f"{skipped} script(s) skipped (script file not found)")
        if fixed:
            print_info("Re-run fixed tests with: phoenix run --failed-only")


@click.command()
@click.option("--run-id", "-r", default=None, help="Run ID to report on (default: latest run)")
@click.option(
    "--logs-dir",
    "-l",
    default="logs",
    type=click.Path(),
    help="Directory containing JSONL execution logs (default: logs/)",
)
@click.option(
    "--reports-dir",
    default="reports",
    type=click.Path(),
    help="Output directory for HTML reports (default: reports/)",
)
@click.option(
    "--open",
    "open_browser",
    is_flag=True,
    default=False,
    help="Open the HTML report in the default browser after generating",
)
@click.option(
    "--trend",
    is_flag=True,
    default=False,
    help="Generate a trend report across the last N runs",
)
@click.option(
    "--last",
    default=20,
    type=int,
    help="Number of runs to include in trend report (default: 20)",
)
@click.option(
    "--env",
    "environment",
    default="",
    help="Environment label shown in the report header (e.g. QA, staging, prod)",
)
@click.option(
    "--project",
    "project_name",
    default="Phoenix Project",
    help="Project name shown in the report header",
)
@click.pass_context
def report(ctx, run_id, logs_dir, reports_dir, open_browser, trend, last, environment, project_name):
    """Generate an HTML report for the latest (or specified) test run."""
    import webbrowser as _wb
    from phoenix.execution.logger import ExecutionLogger
    from rich.table import Table
    from rich import box as rich_box

    exec_logger = ExecutionLogger(logs_dir=logs_dir)
    runs = exec_logger.list_runs()

    if not runs:
        print_warning("No execution results found. Run 'phoenix run' first.")
        return

    # ------------------------------------------------------------------ #
    # Trend report mode
    # ------------------------------------------------------------------ #
    if trend:
        try:
            from phoenix.reporting.generator import ReportGenerator
            gen = ReportGenerator(logs_dir=Path(logs_dir), reports_dir=Path(reports_dir))
            html_path = gen.generate_trend_report(last_n_runs=last)
            print_success(f"Trend report generated: {html_path}")
            if open_browser:
                _wb.open(html_path.resolve().as_uri())
        except Exception as exc:
            print_error(f"Failed to generate trend report: {exc}")
        return

    # ------------------------------------------------------------------ #
    # Single-run mode
    # ------------------------------------------------------------------ #
    # Pick the target run
    if run_id:
        run = next((r for r in runs if r.get("run_id") == run_id), None)
        if not run:
            print_error(f"Run ID '{run_id}' not found in {logs_dir}/")
            return
    else:
        run = runs[0]

    # Header
    rid      = run.get("run_id", "—")
    total    = run.get("total", 0)
    passed   = run.get("passed", 0)
    failed   = run.get("failed", 0)
    skipped  = run.get("skipped", 0)
    duration = run.get("duration_seconds", 0.0)
    status   = run.get("status", "unknown")
    started  = run.get("started_at", "")[:19].replace("T", " ")

    click.echo("")
    print_header(f"Run Report  —  {rid}")
    click.echo(f"  Started : {started}")
    click.echo(f"  Duration: {duration:.1f}s")
    click.echo("")

    status_line = (
        f"[green]PASSED[/green]" if status == "passed"
        else f"[red]FAILED[/red]" if status == "failed"
        else status.upper()
    )
    from rich.console import Console as _Console
    _con = _Console(highlight=False)
    _con.print(
        f"  Result  : {status_line}   "
        f"[green]{passed} passed[/green]  "
        f"[red]{failed} failed[/red]  "
        f"[yellow]{skipped} skipped[/yellow]  "
        f"(total: {total})"
    )
    click.echo("")

    # Per-test Rich table (existing terminal output preserved)
    attempts = exec_logger.get_attempts(rid)
    if attempts:
        # Keep only the final attempt per test
        final: dict = {}
        for a in attempts:
            if a.test_name not in final or a.attempt > final[a.test_name].attempt:
                final[a.test_name] = a

        table = Table(box=rich_box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("", width=4)
        table.add_column("Test", no_wrap=False)
        table.add_column("Attempts", justify="right", width=9)
        table.add_column("Duration", justify="right", width=9)
        table.add_column("Error", style="dim red", no_wrap=False)

        for a in sorted(final.values(), key=lambda x: x.test_name):
            icon = "[green]✓[/green]" if a.status == "passed" else "[red]✗[/red]"
            err  = (a.error_message or "")[:80] if a.status != "passed" else ""
            table.add_row(icon, a.test_name, str(a.attempt), f"{a.duration_seconds:.1f}s", err)

        _con.print(table)

    # ------------------------------------------------------------------ #
    # HTML report — generate via ReportGenerator (additive to terminal)
    # ------------------------------------------------------------------ #
    try:
        from phoenix.reporting.generator import ReportGenerator
        gen = ReportGenerator(logs_dir=Path(logs_dir), reports_dir=Path(reports_dir))
        html_path = gen.generate_run_report(
            run_id=rid,
            open_browser=open_browser,
            project_name=project_name,
            environment=environment,
        )
        print_info(f"HTML report: {html_path}")
    except Exception as exc:
        # Fall back to simple reporter if new system fails
        try:
            from phoenix.execution.reporter import generate_html_report
            html_path = generate_html_report(rid, run, attempts or [], Path(reports_dir))
            print_info(f"HTML report: {html_path}")
            if open_browser:
                _wb.open(html_path.resolve().as_uri())
        except Exception:
            print_warning(f"Could not generate HTML report: {exc}")

    click.echo("")
    if len(runs) > 1:
        print_info(f"Showing run {rid}. Use --run-id to pick a different run.")


# =============================================================================
# Clean command
# =============================================================================

@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed without deleting")
@click.pass_context
def clean(ctx, dry_run):
    """Remove all generated artifacts from the current project directory.

    Deletes generated test scripts, manual test cases, reports, locators,
    and cache files produced by previous phoenix generate / automate runs.
    """
    import glob as _glob

    config_path = ctx.obj.get("config_path") if ctx.obj else None
    project_root = Path(config_path).parent if config_path else Path.cwd()

    prefix = "[dry-run] " if dry_run else ""

    ARTIFACT_DIRS = [
        "test_scripts",
        "manual_test_cases",
        "reports",
        "locators",
        ".phoenix_cache",
        "generated",
        "output",
        "manual_tests",
        "tests",
        "test_data",
        "logs",
    ]

    ARTIFACT_PATTERNS = [
        "test_*.py",
        "manual_test_*.md",
        "*_locators.json",
        "run_*.jsonl",
        "_syntax_error_dump_*.py",
    ]

    removed_count = 0

    for dir_name in ARTIFACT_DIRS:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            if dry_run:
                print_info(f"{prefix}Would remove directory: {dir_path}")
            else:
                try:
                    shutil.rmtree(dir_path)
                    click.echo(f"Removed: {dir_path}/")
                    removed_count += 1
                except OSError as exc:
                    print_warning(f"Could not remove {dir_path}: {exc}")

    for pattern in ARTIFACT_PATTERNS:
        for file in sorted(project_root.glob(f"**/{pattern}")):
            # Skip files inside venv / .git / __pycache__
            parts = set(file.parts)
            if parts & {".git", "venv", ".venv", "__pycache__", "node_modules"}:
                continue
            if dry_run:
                print_info(f"{prefix}Would remove: {file}")
            else:
                try:
                    file.unlink()
                    click.echo(f"Removed: {file}")
                    removed_count += 1
                except OSError as exc:
                    print_warning(f"Could not remove {file}: {exc}")

    if dry_run:
        print_info("[dry-run] No files were deleted.")
    elif removed_count:
        print_success(f"Clean complete — removed {removed_count} item(s).")
    else:
        print_info("Nothing to clean — project directory is already empty.")


# =============================================================================
# Jira integration helpers + command group
# =============================================================================

def _fetch_from_jira(
    issue_key: str,
    jira_config,
    verbose: bool = False,
) -> tuple:
    """Fetch user story, acceptance criteria and attachment docs from a Jira issue.

    Returns (story_text, acceptance_criteria_list, supporting_documents_list).
    Raises SystemExit with a clear message if Jira is not configured or unreachable.
    """
    from phoenix.integrations.jira.client import JiraClient, JiraAuthError, JiraConnectionError, JiraNotFoundError

    if not jira_config.is_configured:
        missing = ", ".join(jira_config.missing_fields())
        print_error(
            f"Jira integration is not configured. Missing: {missing}\n"
            "  1. Set JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN as environment variables.\n"
            "  2. Uncomment and fill in the [jira] section in .phoenixrc.\n"
            "  Run 'phoenix jira health' to verify the configuration."
        )
        sys.exit(1)

    try:
        jira_client = JiraClient(jira_config)
        print_info(f"Fetching Jira issue: {issue_key}")
        issue = jira_client.get_issue(issue_key)
    except JiraAuthError as exc:
        print_error(f"Jira authentication failed: {exc}")
        sys.exit(1)
    except JiraConnectionError as exc:
        print_error(f"Cannot connect to Jira: {exc}")
        sys.exit(1)
    except JiraNotFoundError:
        print_error(f"Jira issue '{issue_key}' not found. Check the key and your project permissions.")
        sys.exit(1)

    if verbose:
        print_info(f"  Summary  : {issue.summary}")
        print_info(f"  Type     : {issue.issue_type}  |  Priority: {issue.priority}")
        print_info(f"  Status   : {issue.status}")
        print_info(f"  Criteria : {len(issue.acceptance_criteria)} item(s)")
        print_info(f"  Attachments: {len(issue.attachments)} file(s)")

    story_text = issue.as_user_story()
    acceptance_criteria = issue.acceptance_criteria

    supporting_docs = []
    if issue.attachments:
        supporting_docs = issue.as_supporting_documents(jira_client)
        if supporting_docs:
            print_info(f"  {len(supporting_docs)} attachment(s) loaded as supporting documents")

    return story_text, acceptance_criteria, supporting_docs


# ---------------------------------------------------------------------------
# phoenix jira <subcommand>
# ---------------------------------------------------------------------------

@click.group()
def jira():
    """Jira integration commands - check connectivity, preview issues."""


@jira.command(name="health")
@click.pass_context
def jira_health(ctx):
    """Check Jira connectivity and verify credentials.

    Reads configuration from the [jira] section in .phoenixrc and the
    JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN environment variables.
    """
    from phoenix.integrations.jira.client import JiraClient, JiraAuthError, JiraConnectionError

    config_path = ctx.obj.get("config_path") if ctx.obj else None
    phoenix_config = PhoenixConfig.load(config_path)
    jira_config = phoenix_config.jira

    print_header("Jira Integration Health Check")

    # Show current config (mask token)
    token = jira_config.api_token
    token_display = f"{token[:6]}...{token[-4:]}" if token and len(token) > 10 else ("set" if token else "NOT SET")

    click.echo(f"  URL        : {jira_config.resolved_url or 'NOT SET'}")
    click.echo(f"  Email      : {jira_config.resolved_email or 'NOT SET'}")
    click.echo(f"  API Token  : {token_display}")
    click.echo(f"  Project Key: {jira_config.project_key or '(not set — any project key will work)'}")
    click.echo(f"  Board ID   : {jira_config.board_id or '(not set)'}")
    click.echo(f"  AC Field   : {jira_config.acceptance_criteria_field}")
    click.echo(f"  Attachments: {'enabled' if jira_config.download_attachments else 'disabled'}")
    click.echo("")

    if not jira_config.is_configured:
        missing = "\n    ".join(jira_config.missing_fields())
        print_error(f"Configuration incomplete. Missing:\n    {missing}")
        click.echo("")
        click.echo("  How to fix:")
        click.echo("    1. export JIRA_URL=https://yourcompany.atlassian.net")
        click.echo("    2. export JIRA_EMAIL=your.email@company.com")
        click.echo("    3. export JIRA_API_TOKEN=<token from id.atlassian.com>")
        click.echo("    4. Uncomment [jira] url in .phoenixrc")
        sys.exit(1)

    try:
        jira_client = JiraClient(jira_config)
        info = jira_client.health_check()
    except JiraAuthError as exc:
        print_error(f"Authentication failed: {exc}")
        sys.exit(1)
    except JiraConnectionError as exc:
        print_error(f"Connection failed: {exc}")
        sys.exit(1)

    print_success("Connected to Jira successfully")
    click.echo(f"  Account    : {info['account']} ({info['email']})")
    click.echo(f"  Server     : {info['server_title']}")
    click.echo(f"  Version    : {info['version']}")
    click.echo(f"  Deployment : {info['deployment_type']}")
    click.echo(f"  API Version: v{info['api_version']}")
    click.echo("")
    click.echo("Usage:")
    click.echo("  phoenix generate --jira PROJ-123 --url https://your-app.com")


@jira.command(name="show")
@click.argument("issue_key")
@click.pass_context
def jira_show(ctx, issue_key: str):
    """Preview what Phoenix would extract from a Jira issue.

    Shows summary, acceptance criteria and attachments without generating tests.
    """
    from phoenix.integrations.jira.client import JiraClient, JiraAuthError, JiraConnectionError, JiraNotFoundError

    config_path = ctx.obj.get("config_path") if ctx.obj else None
    phoenix_config = PhoenixConfig.load(config_path)
    jira_config = phoenix_config.jira

    if not jira_config.is_configured:
        print_error("Jira not configured. Run 'phoenix jira health' for setup instructions.")
        sys.exit(1)

    try:
        jira_client = JiraClient(jira_config)
        issue = jira_client.get_issue(issue_key)
    except JiraAuthError as exc:
        print_error(f"Authentication failed: {exc}")
        sys.exit(1)
    except JiraConnectionError as exc:
        print_error(f"Connection failed: {exc}")
        sys.exit(1)
    except JiraNotFoundError:
        print_error(f"Issue '{issue_key}' not found.")
        sys.exit(1)

    print_header(f"Jira Issue: {issue.key}")
    click.echo(f"  Summary  : {issue.summary}")
    click.echo(f"  Type     : {issue.issue_type}")
    click.echo(f"  Priority : {issue.priority}")
    click.echo(f"  Status   : {issue.status}")
    click.echo(f"  Labels   : {', '.join(issue.labels) or '(none)'}")
    click.echo("")

    if issue.description:
        click.echo("Description:")
        for line in issue.description.splitlines()[:15]:
            click.echo(f"  {line}")
        if len(issue.description.splitlines()) > 15:
            click.echo(f"  ... ({len(issue.description.splitlines()) - 15} more lines)")
        click.echo("")

    if issue.acceptance_criteria:
        click.echo("Acceptance Criteria (will become test criteria):")
        for i, ac in enumerate(issue.acceptance_criteria, 1):
            click.echo(f"  {i}. {ac}")
        click.echo("")
    else:
        print_warning("No acceptance criteria found. Add an 'Acceptance Criteria' section to the description.")

    if issue.attachments:
        click.echo("Attachments:")
        for att in issue.attachments:
            size_kb = att.get("size", 0) // 1024
            click.echo(f"  - {att['filename']}  ({size_kb} KB)")
    else:
        click.echo("No attachments.")

    click.echo("")
    click.echo(f"To generate tests: phoenix generate --jira {issue_key} --url https://your-app.com")
