"""CLI entry point"""

import click
from phoenix.cli.commands import generate, execute, init, run, report


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to configuration file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx, config, verbose):
    """Phoenix Enterprise QA Automation Platform CLI"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


# Register commands
main.add_command(init)
main.add_command(generate)
main.add_command(execute)
main.add_command(run)
main.add_command(report)


if __name__ == "__main__":
    main()
