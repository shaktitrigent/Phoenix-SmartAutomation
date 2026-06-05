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

    # Automation test functions (extracted from already-written individual scripts)
    test_funcs: list[TestFunction] = []
    for test in all_automation:
        script_path = test.get("script_path", "")
        if script_path and Path(script_path).exists():
            try:
                code = Path(script_path).read_text(encoding="utf-8")
                for name, body in _extract_test_functions(code).items():
                    test_funcs.append(TestFunction(name=name, body=body))
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


@click.command()
@click.pass_context
def doctor(ctx):
    """Check Phoenix configuration and connectivity (API keys, intelligence server, DB)."""
    config_path = ctx.obj.get("config_path")
    config = PhoenixConfig.load(config_path) if config_path else PhoenixConfig.from_env()

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
@click.pass_context
def init(ctx, name, project_name, base_url, browser, force, dry_run, non_interactive, target_dir):
    """Initialise a new Phoenix project with canonical layout.

    NAME  Optional project name. Falls back to --project-name or directory name.
    """
    config_path = ctx.obj.get("config_path")
    config = PhoenixConfig.load(config_path) if config_path else PhoenixConfig.from_env()

    # Resolve project name
    resolved_name = name or project_name or Path(target_dir).resolve().name or "default"

    # Resolve base_url
    resolved_url = base_url or config.project.application_url or ""

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
    )

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
        url = client.config.project.application_url

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
    config = PhoenixConfig.load(config_path) if config_path else PhoenixConfig.from_env()

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
    application_url = url or config.project.application_url

    # Load project-specific domain knowledge
    project_root = Path(config_path).parent if config_path else Path.cwd()
    domain_knowledge = _load_domain_knowledge(project_root)
    if domain_knowledge:
        print_info("Domain knowledge loaded from domain_knowledge/")

    # Call intelligence server
    intel_client = IntelligenceClient(config)
    try:
        click.echo("")
        print_info("Calling intelligence server to generate automation scripts…")
        result = intel_client.automate_from_manual(
            manual_tests=manual_tests,
            application_url=application_url,
            domain_knowledge=domain_knowledge,
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

    # Write scripts — individual files for legacy runner + consolidated via ModuleAwareWriter
    from phoenix.exceptions import QualityGateFailedError
    auto_gen = AutomationTestGenerator(output_dir=config.project.test_output_dir)
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

    # Extract and save locators
    locators_dir = Path(config.project.test_output_dir).parent / "locators"
    locators_dir.mkdir(parents=True, exist_ok=True)
    registry = LocatorRegistry()
    total_locators = 0
    for test in written:
        script_path = test.get("script_path")
        if not script_path or not Path(script_path).exists():
            continue
        try:
            code = Path(script_path).read_text(encoding="utf-8")
            page = page_name_from_script_path(script_path)
            bundles = extract_locators_from_script(code, page_name=page)
            for b in bundles:
                registry.upsert(b)
            total_locators += len(bundles)
        except Exception:
            pass
    if total_locators:
        registry.save_all(locators_dir)

    # Module-aware consolidated output (groups by module derived from manual file path)
    project_root = Path(config_path).parent if config_path else Path.cwd()
    _write_module_artifacts(
        module=_module_from_file(manual_path),
        all_manual=[],
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
    default="chromium",
    help="Browser to use for UI tests",
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
@click.pass_context
def run(ctx, project, test_ids, browser, heal, max_attempts, logs_dir, locators_dir, failed_only, headed, slow_mo):
    """Run tests with self-healing retries and execution logging.

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

    # Resolve test paths
    test_paths: List[str] = []
    if test_ids:
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

    print_header(
        f"Running {len(test_paths)} test(s) — "
        f"healing={'on' if heal else 'off'}, max_attempts={max_attempts}"
    )

    import time as _time

    total = len(test_paths)
    passed = failed = healed = 0
    start_all = _time.monotonic()

    for test_path in test_paths:
        result = engine.run(
            test_path=test_path,
            run_id=run_id,
            browser=browser,
        )
        if result.final_status == "passed":
            passed += 1
            sym = "✓"
        else:
            failed += 1
            sym = "✗"
        if result.healed:
            healed += 1

        msg = f"  {sym} {Path(test_path).name}  ({result.attempts} attempt(s)"
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
@click.option("--run-id", "-r", default=None, help="Fix failures from a specific run (default: most recent)")
@click.option("--dry-run", is_flag=True, help="Show what would be fixed without writing files")
@click.option("--url", "-u", default=None, help="Application URL (for context in fix prompt)")
@click.pass_context
def fix(ctx, logs_dir, test_dir, run_id, dry_run, url):
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
    config = PhoenixConfig.load(config_path) if config_path else PhoenixConfig.from_env()
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
            fixed += 1
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
        dir_path = Path(dir_name)
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
        for file in sorted(Path(".").glob(f"**/{pattern}")):
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
    """Jira integration commands — check connectivity, preview issues."""


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
