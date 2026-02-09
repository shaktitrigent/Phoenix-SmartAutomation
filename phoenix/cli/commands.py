"""CLI commands"""

import click
from pathlib import Path
from phoenix import PhoenixClient
from phoenix.sdk.config import PhoenixConfig


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
    project_dir = Path.cwd() / ".phoenix"
    project_dir.mkdir(exist_ok=True)
    
    # Initialize database
    from phoenix.storage.database import Database
    db = Database(config)
    db.create_tables()
    
    click.echo(f"[OK] Phoenix project initialized: {project_name}")
    click.echo(f"[OK] Project directory: {project_dir}")
    click.echo(f"[OK] Database initialized")


@click.command()
@click.option(
    "--story",
    "-s",
    required=True,
    help="User story text"
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
@click.pass_context
def generate(ctx, story, url, criteria, project, type, risk):
    """Generate test cases from user story and application URL"""
    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", False)
    
    client = PhoenixClient(config_path=config_path)
    
    if project:
        client.set_project(project)
    
    # Validate URL for automation tests
    if type in ["automation", "both"] and not url:
        click.echo("[ERROR] --url is required for automation test generation", err=True)
        raise click.Abort()
    
    click.echo("Generating test cases...")
    
    try:
        result = client.generate_tests(
            user_story=story,
            application_url=url,
            acceptance_criteria=list(criteria) if criteria else [],
            test_type=type,
            risk_level=risk
        )
        
        manual_count = len(result.get("manual_tests", []))
        automation_count = len(result.get("automation_tests", []))
        
        click.echo(f"[OK] Generated {manual_count} manual test(s)")
        click.echo(f"[OK] Generated {automation_count} automation test(s)")
        
        # Show file paths
        for test in result.get("manual_tests", []):
            if test.get("file_path"):
                click.echo(f"  Manual test saved: {test['file_path']}")
        
        for test in result.get("automation_tests", []):
            if test.get("script_path"):
                click.echo(f"  Automation script saved: {test['script_path']}")
        
        if verbose:
            click.echo("\nManual Tests:")
            for test in result.get("manual_tests", []):
                click.echo(f"  - {test.get('name', 'Unknown')}")
            
            click.echo("\nAutomation Tests:")
            for test in result.get("automation_tests", []):
                click.echo(f"  - {test.get('name', 'Unknown')}")
                if test.get("script_path"):
                    click.echo(f"    Script: {test['script_path']}")
    
    except Exception as e:
        click.echo(f"[ERROR] Error generating tests: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
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
    
    click.echo("Executing tests...")
    
    try:
        result = client.execute_tests(
            test_ids=list(test_ids) if test_ids else None,
            browser=browser
        )
        
        status = result.get("status", "unknown")
        total = result.get("total_tests", 0)
        passed = result.get("passed_tests", 0)
        failed = result.get("failed_tests", 0)
        
        click.echo(f"[OK] Execution completed: {status}")
        click.echo(f"  Total: {total}, Passed: {passed}, Failed: {failed}")
        
        if result.get("report_path"):
            click.echo(f"[OK] Report: {result['report_path']}")
        
        if verbose and result.get("test_results"):
            click.echo("\nTest Results:")
            for test_result in result["test_results"]:
                status_icon = "[PASS]" if test_result.get("status") == "passed" else "[FAIL]"
                click.echo(f"  {status_icon} {test_result.get('name', 'Unknown')}")
    
    except Exception as e:
        click.echo(f"[ERROR] Error executing tests: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.Abort()
