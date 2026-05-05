"""CLI commands"""

import shutil
import sys
from pathlib import Path
from typing import List, Tuple

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


def _clean_project_directory(
    manual_dir: Path, test_dir: Path, verbose: bool = False
) -> bool:
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
            "Aborting to prevent stale artifact contamination. "
            "Fix the above errors and try again.",
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
    health_url = f"{intel_url}/health"
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
@click.option("--project-name", "-p", default="default", help="Project name")
@click.pass_context
def init(ctx, project_name):
    """Initialize a new Phoenix project"""
    config_path = ctx.obj.get("config_path")
    config = PhoenixConfig.load(config_path) if config_path else PhoenixConfig.from_env()

    # Create project directories
    Path(config.project.manual_output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.project.test_output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.project.report_output_dir).mkdir(parents=True, exist_ok=True)

    # Initialize database
    from phoenix.storage.database import Database

    db = Database(config)
    db.create_tables()

    # Write .phoenixrc (TOML) if neither .phoenixrc nor phoenix.yaml exists
    config_file = Path.cwd() / ".phoenixrc"
    legacy_yaml = Path.cwd() / "phoenix.yaml"
    if not config_file.exists() and not legacy_yaml.exists():
        toml_content = f"""\
# Phoenix project configuration
# https://github.com/your-org/Phoenix-SmartAutomation

[project]
default_project = "{project_name}"
manual_output_dir = "./manual_tests"
test_output_dir   = "./test_results"
report_output_dir = "./reports"

[intelligence]
base_url    = "{config.intelligence.base_url}"
timeout     = {config.intelligence.timeout}
retry_count = {config.intelligence.retry_count}

[database]
url = "{config.database.url}"
"""
        config_file.write_text(toml_content, encoding="utf-8")

    print_success(f"Phoenix project initialized: {project_name}")
    print_info(f"Config file: {config_file}")
    print_success("Database initialized")


@click.command()
@click.option("--story", "-s", help="User story text")
@click.option(
    "--story-file", "-f", type=click.Path(exists=True), help="Path to user story text file"
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
    default="both",
    help="Type of tests to generate",
)
@click.option(
    "--risk",
    "-r",
    type=click.Choice(["smoke", "regression", "edge"], case_sensitive=False),
    help="Risk level for tests",
)
@click.option(
    "--clean",
    is_flag=True,
    help="Delete existing generated manual_tests and test_results files before generating",
)
@click.pass_context
def generate(ctx, story, story_file, url, criteria, project, type, risk, clean):
    """Generate test cases from user story and application URL"""
    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)

    client = PhoenixClient(config_path=config_path)

    if project:
        client.set_project(project)

    # Use default application URL from config if not provided
    if not url:
        url = client.config.project.application_url

    # Validate URL for automation tests
    if type in ["automation", "both"] and not url:
        click.echo("[ERROR] --url is required for automation test generation", err=True)
        raise click.Abort()

    if not story and not story_file:
        click.echo("[ERROR] Provide --story or --story-file", err=True)
        raise click.Abort()

    if clean:
        manual_dir = Path(client.config.project.manual_output_dir)
        test_dir = Path(client.config.project.test_output_dir)
        verbose = ctx.obj.get("verbose", False)
        if not _clean_project_directory(manual_dir, test_dir, verbose=verbose):
            sys.exit(1)
        print_success("Clean completed — artifact directories are empty.")

    print_header("Generating test cases...")

    try:
        results = []
        if story_file:
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
                )
            )

        all_manual = [t for r in results for t in r.get("manual_tests", [])]
        all_automation = [t for r in results for t in r.get("automation_tests", [])]
        print_generate_results(all_manual, all_automation, verbose=verbose)

    except Exception as exc:
        print_error(f"Error generating tests: {exc}")
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
    help="Browser to use for UI tests",
)
@click.pass_context
def run(ctx, project, test_ids, browser):
    """Run test cases (alias for execute)"""
    return execute.callback(project, test_ids, browser)


@click.command()
@click.option("--project", "-p", help="Project name (uses default if not specified)")
@click.option(
    "--execution-id",
    "-e",
    help="Execution ID to show (default: latest)",
)
@click.pass_context
def report(ctx, project, execution_id):
    """Show execution report summary"""
    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)

    client = PhoenixClient(config_path=config_path)
    if project:
        client.set_project(project)

    try:
        result = client.get_execution_results(execution_id=execution_id)
        if not result:
            print_warning("No execution results found.")
            return
        print_report_summary(result)
        if result.get("report_path"):
            print_info(f"Full HTML report: {result['report_path']}")
    except Exception as exc:
        print_error(f"Error retrieving report: {exc}")
        if verbose:
            import traceback

            err_console.print(traceback.format_exc())
        raise click.Abort() from exc
