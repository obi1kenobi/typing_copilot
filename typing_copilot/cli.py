from os import path
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
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
def cli(verbose: bool) -> None:
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")


@cli.command()
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging.")
@click.option(
    "--overwrite", is_flag=True, default=False, help="Overwrite existing mypy.ini, if any"
)
def init(verbose: bool, overwrite: bool) -> None:
    click.echo(f"typing_copilot v{__version__}\n")
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")

    if path.exists("mypy.ini"):
        if overwrite:
            click.echo(
                "A mypy.ini file already exists, and will be overwritten since '--overwrite' "
                "was set.\n"
            )
        else:
            click.echo(
                "A mypy.ini file already exists, and cannot be overwritten since '--overwrite' was "
                "not set. Please either move or rename the file, or use the '--overwrite' command."
            )
            sys.exit(1)

    click.echo("Running mypy once with laxest settings to establish a baseline. Please wait...\n")

    completed_process = run_mypy_with_config(LAX_BASELINE_MYPY_CONFIG)
    errors = get_mypy_errors_from_completed_process(completed_process)
    if errors:
        click.echo("Mypy found errors during our baseline run. Executed mypy with config:\n")
        click.echo(LAX_BASELINE_MYPY_CONFIG)
        click.echo("Mypy output:\n")
        click.echo(completed_process.stdout)
        click.echo(
            "Since these errors happen at mypy's most permissive settings, they cannot "
            "be suppressed. Please resolve them, then run this command again."
        )
        sys.exit(0)

    click.echo("Collecting mypy errors from strictest check configuration. Please wait...\n")
    strict_errors = get_mypy_errors_for_run_with_config(STRICT_BASELINE_MYPY_CONFIG)
    if not strict_errors:
        with open("mypy.ini", "w") as f:
            f.write(STRICT_BASELINE_MYPY_CONFIG)
        click.echo(
            "Strict run completed, no errors found. Updated your mypy.ini file with the strictest "
            "settings supported by typing_copilot. Congratulations and happy type-safe coding!"
        )
        sys.exit(0)

    click.echo(
        f"Strict run completed and uncovered {len(strict_errors)} mypy errors. Building "
        f"the strictest mypy config such that all configured mypy checks still pass...\n"
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
        click.echo(f"    Affected modules: {sorted(list(imported_modules_missing_type_hints))}\n")

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
            f"across {len(first_party_suppressions)} modules.\n"
        )
        final_config_first_party_modules = "# First party per-module rule relaxations" + "".join(
            make_1st_party_module_rule_block(module_name, first_party_suppressions[module_name])
            for module_name in sorted(first_party_suppressions.keys())
        )

    final_config = "\n\n".join(
        [final_config_global, final_config_first_party_modules, final_config_third_party_modules]
    )
    config_file_length = len(final_config.split("\n"))
    click.echo(
        f"Config generated ({config_file_length} lines). Validating the new "
        f"setup before updating your mypy.ini file. Please wait...\n"
    )

    completed_process = run_mypy_with_config(final_config)
    validation_run_errors = get_mypy_errors_from_completed_process(completed_process)
    if not validation_run_errors:
        with open("mypy.ini", "w") as f:
            f.write(final_config)
        click.echo(
            "Validation complete. Your mypy.ini file has been updated. " "Happy type-safe coding!"
        )
        sys.exit(0)
    else:
        raise AssertionError(
            f"Validation failed: mypy reported {len(validation_run_errors)} more errors. "
            f"Please re-run this command with the '--verbose' flag and then submit "
            f"the produced logs so we can update mypy-copilot to fix this issue."
            f"Apologies for the inconvenience, and thank you for supporting mypy-copilot."
        )


if __name__ == "__main__":
    cli()
