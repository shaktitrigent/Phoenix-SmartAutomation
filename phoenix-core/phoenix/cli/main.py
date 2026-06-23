"""CLI entry point"""

import click

try:
    from importlib.metadata import version as _pkg_version
    _PHOENIX_VERSION = _pkg_version("phoenix-core")
except Exception:
    _PHOENIX_VERSION = "0.0.0-dev"

from phoenix.cli.commands import clean, doctor, fix, generate, execute, init, jira, locators, logs, migrate, run, report, automate


@click.group()
@click.version_option(version=_PHOENIX_VERSION, prog_name="phoenix")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to configuration file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx, config, verbose):
    """Phoenix Enterprise QA Automation Platform CLI"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


# Register commands
main.add_command(doctor)
main.add_command(init)
main.add_command(migrate)
main.add_command(generate)
main.add_command(execute)
main.add_command(run)
main.add_command(report)
main.add_command(locators)
main.add_command(logs)
main.add_command(fix)
main.add_command(automate)
main.add_command(clean)
main.add_command(jira)


if __name__ == "__main__":
    main()
