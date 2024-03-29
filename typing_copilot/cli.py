from os import path
from pathlib import Path
import pprint
from subprocess import CompletedProcess
import sys
from typing import List, Optional, Tuple

import click
import toml

from .config_generation import (
    AUTOGENERATED_LINE_PREFIX,
    make_1st_party_module_rule_block,
    make_ignore_missing_imports_block,
    make_lax_baseline_mypy_config,
    make_strict_baseline_mypy_config,
    make_unused_ignores_config_line,
)
from .error_tracker import (
    find_unused_ignores,
    get_1st_party_modules_and_suppressions,
    get_3rd_party_modules_missing_type_hints,
)
from .mypy_runner import (
    MypyError,
    get_mypy_errors_for_run_with_config,
    get_mypy_errors_from_completed_process,
    run_mypy_with_config,
    run_mypy_with_config_file,
)
from .own_config import TypingCopilotConfig, find_pyproject_toml
from .verbosity import enable_verbose_mode, log_if_verbose
from . import __package_name__, __version__


def _make_strictest_mypy_config_components_from_errors(
    own_config: TypingCopilotConfig,
    strict_errors: List[MypyError],
    *,
    describe_constructed_config: bool = True,
) -> Tuple[str, str, str, str]:
    final_config_global = make_strict_baseline_mypy_config(own_config)
    final_config_unused_ignores = make_unused_ignores_config_line(True)
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
        if describe_constructed_config:
            click.echo(
                f"> Constructed {total_rule_module_suppressions} mypy error suppression rules "
                f"across {len(first_party_suppressions)} modules.\n"
            )
        final_config_first_party_modules = "# First party per-module rule relaxations" + "".join(
            make_1st_party_module_rule_block(module_name, first_party_suppressions[module_name])
            for module_name in sorted(first_party_suppressions.keys())
        )

    return (
        final_config_global,
        final_config_unused_ignores,
        final_config_first_party_modules,
        final_config_third_party_modules,
    )


def _generate_final_mypy_config_from_components(
    final_config_global: str,
    final_config_unused_ignores: str,
    final_config_first_party_modules: str,
    final_config_third_party_modules: str,
) -> str:
    return "\n\n".join(
        [
            final_config_global + final_config_unused_ignores,
            final_config_first_party_modules,
            final_config_third_party_modules,
        ]
    )


def _generate_final_mypy_config_with_unused_ignore_suppression(
    final_config_components: Tuple[str, str, str, str],
    unused_ignore_errors: List[MypyError],
) -> str:
    if not unused_ignore_errors:
        raise AssertionError(
            f"_generate_final_mypy_config_with_unused_ignore_suppression was called without any "
            f"reported unused_ignore_errors, this is a bug: {unused_ignore_errors}"
        )

    # This cannot be done during the normal "strict" check because "unused ignore" errors
    # are (at least as recently as mypy version 0.782) only reported if other checks pass.
    # This is why we check it during the validation stage.
    click.echo(
        f"> Mypy reported {len(unused_ignore_errors)} situation(s) where a 'type: ignore' is "
        f"specified but unnecessary. Configuring mypy to globally ignore such unnecessary "
        f"type check suppressions; please strongly consider resolving this issue ASAP.\n"
    )
    return _generate_final_mypy_config_from_components(
        final_config_components[0],
        make_unused_ignores_config_line(False),
        final_config_components[2],
        final_config_components[3],
    )


def _get_strict_run_mypy_errors(own_config: TypingCopilotConfig) -> List[MypyError]:
    return get_mypy_errors_for_run_with_config(
        make_strict_baseline_mypy_config(own_config) + make_unused_ignores_config_line(False)
    )


def _get_unused_ignore_errors_from_validation_run(mypy_config: str) -> List[MypyError]:
    completed_process = run_mypy_with_config(mypy_config)
    validation_run_errors = get_mypy_errors_from_completed_process(completed_process)
    unused_ignore_errors = find_unused_ignores(validation_run_errors)
    other_errors = set(validation_run_errors) - set(unused_ignore_errors)

    if other_errors:
        click.echo("Validation failed due to unexpected error(s):")
        click.echo(pprint.pformat(list(other_errors)))

        raise AssertionError(
            f"Validation failed: mypy reported {len(other_errors)} unexpected error(s). "
            f"Please submit the produced logs so we can update typing-copilot to fix this issue. "
            f"Apologies for the inconvenience, and thank you for supporting typing-copilot."
        )

    return unused_ignore_errors


def _work_around_mypy_strict_optional_bug(
    completed_process: CompletedProcess,
    full_lax_config: str,
) -> Tuple[CompletedProcess, str]:
    # Workaround for failed lax mypy run due to:
    # https://github.com/obi1kenobi/typing-copilot/issues/1
    # https://github.com/python/mypy/issues/9437
    if completed_process.returncode != 2:  # mypy exits 2 when it crashes
        return completed_process, full_lax_config

    if "INTERNAL ERROR" not in completed_process.stderr:
        return completed_process, full_lax_config

    click.echo("Ran into a known issue with mypy.")
    click.echo("If this GitHub issue is resolved, try upgrading your mypy version:")
    click.echo("  https://github.com/python/mypy/issues/9437")
    click.echo("For now, going to attempt a workaround, please wait...\n")

    problematic_line = "strict_optional = False\n"
    workaround_line = "strict_optional = True\n"
    if problematic_line not in full_lax_config:
        raise AssertionError(
            "The lax baseline mypy config does not contain the suspected culprit line. "
            "This is a bug."
        )
    workaround_lax_config = full_lax_config.replace(problematic_line, workaround_line)
    completed_process = run_mypy_with_config(workaround_lax_config)
    return completed_process, workaround_lax_config


def _get_own_config() -> TypingCopilotConfig:
    search_path = Path.cwd().resolve()
    pyproject_toml_config = _fetch_config_from_pyproject_toml(search_path)

    if pyproject_toml_config is not None:
        return pyproject_toml_config

    return TypingCopilotConfig.empty()


def _fetch_config_from_pyproject_toml(search_path: Path) -> Optional[TypingCopilotConfig]:
    pyproject_toml_path = find_pyproject_toml(search_path)
    if pyproject_toml_path is not None:
        try:
            with open(pyproject_toml_path) as f:
                return TypingCopilotConfig.from_toml(toml.load(f))
        except OSError as e:
            click.secho(
                f"Failed to open pyproject.toml file at path {pyproject_toml_path} "
                f"due to error {e}.",
                fg="red",
            )
            sys.exit(1)
        except toml.TomlDecodeError:
            click.secho(
                f"Failed to read config from pyproject.toml file at path {pyproject_toml_path} "
                f"since it does not appear to be valid TOML. Please check the pyproject.toml "
                f"file syntax and try again."
            )
            sys.exit(1)

    return None


@click.group()
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
@click.option("--version", is_flag=True, default=False)  # just to avoid erroring on --version arg
def cli(verbose: bool, version: bool) -> None:
    click.echo(f"typing_copilot v{__version__}\n")
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")


@cli.command()
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging.")
@click.option(
    "--overwrite", is_flag=True, default=False, help="Overwrite existing mypy.ini, if any"
)
def init(verbose: bool, overwrite: bool) -> None:
    """Generate an initial mypy.ini file for your project."""
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

    own_config = _get_own_config()

    click.echo("Running mypy once with laxest settings to establish a baseline. Please wait...\n")

    full_lax_config = make_lax_baseline_mypy_config(own_config) + make_unused_ignores_config_line(
        False
    )
    completed_process = run_mypy_with_config(full_lax_config)
    completed_process, full_lax_config = _work_around_mypy_strict_optional_bug(
        completed_process, full_lax_config
    )
    errors = get_mypy_errors_from_completed_process(completed_process)
    if errors:
        click.echo("Mypy found errors during our baseline run. Executed mypy with config:\n")
        click.echo(full_lax_config)
        click.echo("Mypy output:\n")
        click.echo(completed_process.stdout)
        click.echo(
            "Since these errors happen at mypy's most permissive settings, they cannot "
            "be suppressed. Please resolve them, then run this command again."
        )
        sys.exit(0)

    click.echo("Collecting mypy errors from strictest check configuration. Please wait...\n")
    strict_errors = _get_strict_run_mypy_errors(own_config)
    if not strict_errors:
        with open("mypy.ini", "w") as f:
            f.write(make_strict_baseline_mypy_config(own_config))
        click.echo(
            "Strict run completed, no errors found. Updated your mypy.ini file with the strictest "
            "settings supported by typing_copilot. Congratulations and happy type-safe coding!"
        )
        sys.exit(0)

    click.echo(
        f"Strict run completed and uncovered {len(strict_errors)} mypy errors. Building "
        f"the strictest mypy config such that all configured mypy checks still pass...\n"
    )

    final_config_components = _make_strictest_mypy_config_components_from_errors(
        own_config, strict_errors
    )
    final_config = _generate_final_mypy_config_from_components(*final_config_components)

    config_file_length = len(final_config.split("\n"))
    click.echo(
        f"Config generated ({config_file_length} lines). Verifying the last few mypy settings "
        f"and validating that the new configuration does not produce mypy errors. Please wait...\n"
    )

    unused_ignore_errors = _get_unused_ignore_errors_from_validation_run(final_config)
    if unused_ignore_errors:
        final_config = _generate_final_mypy_config_with_unused_ignore_suppression(
            final_config_components, unused_ignore_errors
        )

    with open("mypy.ini", "w") as f:
        f.write(final_config)
    click.echo("Validation complete. Your mypy.ini file has been updated. Happy type-safe coding!")
    sys.exit(0)


def _are_mypy_configs_equal(mypy_config_a: str, mypy_config_b: str) -> bool:
    lines_in_a = mypy_config_a.strip().split("\n")
    lines_in_b = mypy_config_b.strip().split("\n")

    nonempty_lines_in_a_minus_comments = [
        line for line in lines_in_a if line and not line.lstrip().startswith("#")
    ]
    nonempty_lines_in_b_minus_comments = [
        line for line in lines_in_b if line and not line.lstrip().startswith("#")
    ]
    return nonempty_lines_in_a_minus_comments == nonempty_lines_in_b_minus_comments


@cli.command()
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging.")
@click.option(
    "--error-if-can-tighten",
    is_flag=True,
    default=False,
    help=(
        "Exit 1 if a tighter configuration is available and print it to stdout, "
        "instead of overwriting the mypy.ini file. Intended for use in CI environments."
    ),
)
def tighten(verbose: bool, error_if_can_tighten: bool) -> None:
    """Attempt to tighten your project's existing mypy.ini file."""
    if verbose:
        enable_verbose_mode()
        log_if_verbose("Verbose mode enabled.")

    # Ensure we have a valid mypy.ini file that was autogenerated by us.
    # This command does not support tigtening arbitrary mypy.ini files.
    current_config = ""
    try:
        with open("mypy.ini", "r") as mypy_config_file:
            current_config = mypy_config_file.read()
            split_outputs = current_config.split("\n", 1)
            first_non_empty_line = split_outputs[0]
            while first_non_empty_line == "" and len(split_outputs) > 1:
                split_outputs = split_outputs[1].split("\n", 1)
                first_non_empty_line = split_outputs[0]

            if not first_non_empty_line.startswith(AUTOGENERATED_LINE_PREFIX):
                click.echo(
                    f"Cannot tighten mypy config: the mypy.ini file does not appear to have been "
                    f"generated by {__package_name__} and is therefore unsupported."
                )
                sys.exit(1)
    except FileNotFoundError:
        click.echo("Cannot tighten mypy config: no mypy.ini was found in the current directory.")
        sys.exit(1)

    own_config = _get_own_config()

    # By this point, we know a mypy.ini file exists and is a product of this program.
    # Next, ensure that mypy passes with no errors with the current mypy.ini config.
    completed_process = run_mypy_with_config_file("mypy.ini")
    errors = get_mypy_errors_from_completed_process(completed_process)
    if errors:
        click.echo(
            "Cannot tighten mypy config: mypy found errors with the current mypy.ini config. "
            "Please fix these errors before attempting to find a tighter configuration:\n"
        )
        click.echo(completed_process.stdout)
        sys.exit(1)

    # Now we're ready to attempt to find a tighter configuration. We do this with a trick:
    # we reuse our existing way of finding the tightest-known mypy.ini configuration
    # (same as in the "init" command) and then simply compare if the produced tightest configuration
    # is the same or different compared to the existing mypy.ini. Our mypy.ini file generation
    # is deterministic, and we know that mypy passes with the original mypy.ini file, so therefore
    # any changes that can be made to the mypy.ini file from the new generation process can only
    # make it tighter than it was before.
    #
    # At the end of this block, the final_config variable holds the configuration we've determined
    # is the tightest available passing configuration.
    final_config: str
    strict_errors = _get_strict_run_mypy_errors(own_config)
    if not strict_errors:
        # The strict mypy run didn't find any errors. The tightest passing mypy configuration is
        # our tightest available configuration! Hurray!
        final_config = make_strict_baseline_mypy_config(own_config)
    else:
        final_config_components = _make_strictest_mypy_config_components_from_errors(
            own_config, strict_errors, describe_constructed_config=False
        )
        final_config = _generate_final_mypy_config_from_components(*final_config_components)

        unused_ignore_errors = _get_unused_ignore_errors_from_validation_run(final_config)
        if unused_ignore_errors:
            final_config = _generate_final_mypy_config_with_unused_ignore_suppression(
                final_config_components, unused_ignore_errors
            )

    if _are_mypy_configs_equal(current_config, final_config):
        click.echo("Success: the current mypy config is already the tightest available.")
        sys.exit(0)

    if error_if_can_tighten:
        click.echo(
            "Error: The current mypy.ini does not contain the tightest available "
            "configuration:\n"
        )
        click.echo(final_config)
        sys.exit(1)

    config_file_length = len(final_config.split("\n"))
    click.echo(
        f"Found a tighter mypy configuration ({config_file_length} lines), "
        f"updating your mypy.ini file."
    )
    with open("mypy.ini", "w") as f:
        f.write(final_config)
    click.echo("Your mypy.ini file has been updated. Happy type-safe coding!")
    sys.exit(0)


if __name__ == "__main__":
    cli()
