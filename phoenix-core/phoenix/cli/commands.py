"""CLI commands"""

import click
from pathlib import Path
from phoenix import PhoenixClient
from phoenix.sdk.config import PhoenixConfig
from phoenix.cli.output import (
    console,
    err_console,
    print_success,
    print_error,
    print_info,
    print_warning,
    print_header,
    print_generate_results,
    print_execution_results,
    print_report_summary,
)


@click.command()
@click.option(
    "--project-name",
    "-p",
    default="default",
    help="Project name"
)
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
@click.option(
    "--story",
    "-s",
    help="User story text"
)
@click.option(
    "--story-file",
    "-f",
    type=click.Path(exists=True),
    help="Path to user story text file"
)
@click.option(
    "--url",
    "-u",
    help="Application URL to test (required for automation tests)"
)
@click.option(
    "--criteria",
    "-c",
    multiple=True,
    help="Acceptance criteria (can be specified multiple times)"
)
@click.option(
    "--project",
    "-p",
    help="Project name (uses default if not specified)"
)
@click.option(
    "--type",
    "-t",
    type=click.Choice(["manual", "automation", "both"], case_sensitive=False),
    default="both",
    help="Type of tests to generate"
)
@click.option(
    "--risk",
    "-r",
    type=click.Choice(["smoke", "regression", "edge"], case_sensitive=False),
    help="Risk level for tests"
)
@click.option(
    "--clean",
    is_flag=True,
    help="Delete existing generated manual_tests and test_results files before generating"
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
        # Delete only generated artifacts (safe patterns)
        manual_dir = Path(client.config.project.manual_output_dir)
        test_dir = Path(client.config.project.test_output_dir)
        manual_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        for p in manual_dir.glob("manual_test_*.md"):
            try:
                p.unlink()
            except Exception:
                pass
        for p in test_dir.glob("test_*.py"):
            try:
                p.unlink()
            except Exception:
                pass

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
                        risk_level=risk
                    )
                )
        else:
            results.append(
                client.generate_tests(
                    user_story=story,
                    application_url=url,
                    acceptance_criteria=list(criteria) if criteria else [],
                    test_type=type,
                    risk_level=risk
                )
            )

        all_manual = [t for r in results for t in r.get("manual_tests", [])]
        all_automation = [t for r in results for t in r.get("automation_tests", [])]
        print_generate_results(all_manual, all_automation, verbose=verbose)
    
    except Exception as e:
        print_error(f"Error generating tests: {e}")
        if verbose:
            import traceback
            err_console.print(traceback.format_exc())
        raise click.Abort()


@click.command()
@click.option(
    "--project",
    "-p",
    help="Project name (uses default if not specified)"
)
@click.option(
    "--test-ids",
    "-t",
    multiple=True,
    help="Specific test IDs to execute (can be specified multiple times)"
)
@click.option(
    "--browser",
    "-b",
    type=click.Choice(["chromium", "firefox", "webkit"], case_sensitive=False),
    help="Browser to use for UI tests"
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

    except Exception as e:
        print_error(f"Error executing tests: {e}")
        if verbose:
            import traceback
            err_console.print(traceback.format_exc())
        raise click.Abort()


@click.command()
@click.option(
    "--project",
    "-p",
    help="Project name (uses default if not specified)"
)
@click.option(
    "--test-ids",
    "-t",
    multiple=True,
    help="Specific test IDs to execute (can be specified multiple times)"
)
@click.option(
    "--browser",
    "-b",
    type=click.Choice(["chromium", "firefox", "webkit"], case_sensitive=False),
    help="Browser to use for UI tests"
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
    except Exception as e:
        print_error(f"Error retrieving report: {e}")
        if verbose:
            import traceback
            err_console.print(traceback.format_exc())
        raise click.Abort()
