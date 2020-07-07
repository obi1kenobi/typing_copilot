import pprint
import sys
from typing import List

import click

from .config_generation import (
    LAX_BASELINE_MYPY_CONFIG,
    STRICT_BASELINE_MYPY_CONFIG,
    make_1st_party_module_rule_block,
    make_ignore_missing_imports_block,
)
from .error_tracker import (
    get_1st_party_modules_and_suppressions,
    get_3rd_party_modules_missing_type_hints,
)
from .mypy_runner import (
    get_mypy_errors_for_run_with_config,
    get_mypy_errors_from_completed_process,
    run_mypy_with_config,
)
from .verbosity import enable_verbose_mode, log_if_verbose
from . import __version__


@click.group()
@click.option("--verbose", is_flag=True)
def cli(verbose: bool) -> None:
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")


@cli.command()
@click.option("--verbose", is_flag=True)
def init(verbose: bool) -> None:
    click.echo(f"mypy_copilot v{__version__}")
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")

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

    click.echo(
        f"Strict run completed, {len(strict_errors)} errors found. Building the strictest "
        f"mypy config such that all mypy checks still pass...\n"
    )

    final_config_global = STRICT_BASELINE_MYPY_CONFIG
    final_config_first_party_modules = ""
    final_config_third_party_modules = ""

    imported_modules_missing_type_hints = get_3rd_party_modules_missing_type_hints(strict_errors)
    if imported_modules_missing_type_hints:
        click.echo(
            "> Mypy was unable to find type hints for some 3rd party modules, configuring mypy to "
            "ignore them."
        )
        click.echo(
            "    More info: https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports"
        )
        click.echo(
            f"    Affected modules: {sorted(list(imported_modules_missing_type_hints))}\n"
        )

        final_config_third_party_modules = "# Third-party module rule relaxations" + "".join(
            make_ignore_missing_imports_block(module_name)
            for module_name in sorted(imported_modules_missing_type_hints)
        )

    first_party_suppressions = get_1st_party_modules_and_suppressions(strict_errors)
    if first_party_suppressions:
        total_rule_module_suppressions = sum(
            len(value) for value in first_party_suppressions.values()
        )
        click.echo(
            f"> Constructed {total_rule_module_suppressions} mypy error suppression rules "
            f"for {len(first_party_suppressions)} modules."
        )
        final_config_first_party_modules = "# First party per-module rule relaxations" + "".join(
            make_1st_party_module_rule_block(module_name, first_party_suppressions[module_name])
            for module_name in sorted(first_party_suppressions.keys())
        )

    final_config = "\n\n".join(
        [final_config_global, final_config_first_party_modules, final_config_third_party_modules]
    )
    click.echo("Suggested mypy.ini file:")
    click.echo(final_config)

    completed_process = run_mypy_with_config(final_config)
    validation_run_errors = get_mypy_errors_from_completed_process(completed_process)
    if validation_run_errors:
        raise AssertionError(
            f"Validation of the proposed mypy configuration failed with "
            f"exit code {completed_process.returncode} and "
            f"output: {completed_process.stdout}"
        )


if __name__ == "__main__":
    cli()
