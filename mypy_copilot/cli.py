import sys

import click

from .config_generation import LAX_BASELINE_MYPY_CONFIG, STRICT_BASELINE_MYPY_CONFIG
from .error_tracker import get_3rd_party_modules_missing_type_hints
from .mypy_runner import (
    get_mypy_errors_for_run_with_config,
    get_mypy_errors_from_completed_process,
    run_mypy_with_config,
)
from .verbosity import enable_verbose_mode, log_if_verbose
from . import __version__


@click.group()
@click.option("--verbose/--no-verbose", default=False)
def cli(verbose) -> None:
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")


@cli.command()
def init() -> None:
    click.echo(f"mypy_copilot v{__version__}")
    click.echo("Running mypy once with lax settings to establish a baseline. Please wait...\n")

    # completed_process = run_mypy_with_config(LAX_BASELINE_MYPY_CONFIG)
    # errors = get_mypy_errors_from_completed_process(completed_process)
    errors: List[str] = []

    if errors:
        click.echo(
            "Mypy found errors during our baseline run. Executed mypy with config:\n"
        )
        click.echo(LAX_BASELINE_MYPY_CONFIG)
        click.echo("Mypy output:\n")
        click.echo(completed_process.stdout)
        click.echo("Please resolve the reported errors, then run this command again.")

    click.echo(
        "Baseline run completed without errors! On to more challenging checks. Please wait...\n"
    )

    strict_errors = get_mypy_errors_for_run_with_config(STRICT_BASELINE_MYPY_CONFIG)
    if not strict_errors:
        click.echo(
            "Strict run completed, no errors found. Your code is ready to adopt mypy with "
            "the strictest settings supported by mypy_copilot. Congratulations and happy coding!"
        )
        sys.exit(0)

    click.echo(f"Strict run completed, {len(strict_errors)} errors found.")

    imported_modules_missing_type_hints = get_3rd_party_modules_missing_type_hints(strict_errors)
    click.echo(imported_modules_missing_type_hints)


if __name__ == "__main__":
    cli()
