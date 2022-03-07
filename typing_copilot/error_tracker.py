import importlib
import os
import pkgutil
import re
from typing import AbstractSet, Dict, FrozenSet, List, Optional, Set, Tuple

import click

from .mypy_runner import MypyError
from .validation import validate_module_name


_module_missing_type_hint_pattern = re.compile(
    r"error: Skipping analyzing [\"']([a-zA-Z0-9_\.]+)[\"']: "
    r"found module but no type hints or library stubs"
)
_module_missing_implementation_or_library_stub_pattern = re.compile(
    r"error: Cannot find implementation or library stub "
    r"for module named [\"']([a-zA-Z0-9_\.]+)[\"']"
)

MypyErrorSetting = Tuple[str, bool]

_warn_unused_ignores_error_setting: MypyErrorSetting = ("warn_unused_ignores", False)

# For each error code, store the message substrings that indicate the flag that is the cause of the
# given error and the flag value that will hide the error, in order of decreasing selectivity.
# If no error code or message matches, the error is assumed to originate from
# the "check_untyped_defs = True" setting and assumed to go away if setting that flag to False.
_remaining_error_setting: MypyErrorSetting = ("check_untyped_defs", False)
_code_and_message_to_error_setting: Dict[str, Dict[str, MypyErrorSetting]] = {
    "misc": {
        "error: Untyped decorator": ("disallow_untyped_decorators", False),
        "": _remaining_error_setting,
    },
    "no-untyped-def": {
        # Given in order of most-selective to least-selective. Note that these substrings overlap!
        "error: Function is missing a type annotation for one or more arguments": (
            "disallow_incomplete_defs",
            False,
        ),
        "error: Function is missing a type annotation": ("disallow_untyped_defs", False),
        "": ("disallow_incomplete_defs", False),
    },
    "no-untyped-call": {
        "": ("disallow_untyped_calls", False),
    },
    "": {
        "error: unused 'type: ignore' comment": _warn_unused_ignores_error_setting,
    },
}
_settings_that_require_other_settings: Dict[MypyErrorSetting, FrozenSet[MypyErrorSetting]] = {
    ("disallow_incomplete_defs", False): frozenset({("disallow_untyped_defs", False)})
}


def _find_minimum_covering_modules(module_names: AbstractSet[str]) -> FrozenSet[str]:
    """Given a set of modules, return the minimum set of ancestor modules of all others."""
    # Walk the list of modules in sorted order, exploiting the fact that "foo" always sorts
    # lexicographically before "foo.<anything>"
    sorted_module_names = sorted(module_names)

    module_prefixes: Set[str] = set()
    for module_name in sorted_module_names:
        module_path = module_name.split(".")

        covered = False
        for num_components in range(1, len(module_path)):
            ancestor_module_name = ".".join(module_path[:num_components])
            if ancestor_module_name in module_prefixes:
                # Already covered!
                covered = True
                break

        if not covered:
            module_prefixes.add(module_name)

    return frozenset(module_prefixes)


def _get_error_setting_for_error(error: MypyError) -> MypyErrorSetting:
    possible_error_settings = _code_and_message_to_error_setting.get(error.error_code, None)
    if possible_error_settings is None:
        return _remaining_error_setting

    error_setting: Optional[MypyErrorSetting] = None
    for error_message_pattern, possible_error_setting in possible_error_settings.items():
        if error_message_pattern in error.message:
            error_setting = possible_error_setting
            break

    if error_setting is None:
        raise AssertionError(
            f"Failed to deduce a matching error setting for an error with recognized "
            f"error code {error.error_code}: {error}. This is a bug, the error matching rules "
            f"within typing_copilot will need to be updated."
        )

    return error_setting


def _get_module_for_error(error: MypyError) -> str:
    # TODO: fix inspected_module_name being just the local module name
    #       and not the fully-qualified one
    # inspected_module_name = inspect.getmodulename(error.file_path)
    # if inspected_module_name is not None:
    #     validate_module_name(inspected_module_name)
    #     return inspected_module_name
    # else:
    #     raise AssertionError(
    #         f"File path {error.file_path} does not appear to belong to a module. Encountered in "
    #         f"mypy error: {error}"
    #     )

    error_in_file = error.file_path
    known_python_extensions = {".py", ".pyo", ".pyx", ".pyc"}
    for python_extension in known_python_extensions:
        if error_in_file.endswith(python_extension):
            error_in_file = error_in_file[: -len(python_extension)]

    if "." in error_in_file:
        raise AssertionError(
            f"Module name-finding heuristic failed due to unexpected '.' in file {error.file_path} "
            f"for mypy error: {error}"
        )

    # Errors appearing in an "__init__.py" appear in the module given by the path one step before,
    # instead of in a submodule named "__init__".
    suffixes_to_strip = {"__init__"}
    for suffix_to_strip in suffixes_to_strip:
        if error_in_file.endswith(suffix_to_strip):
            error_in_file = error_in_file[: -len(suffix_to_strip)]

    module_name = error_in_file.strip(os.sep).replace(os.sep, ".")
    validate_module_name(module_name)
    return module_name


def _get_child_module_names_for_module(module_name: str) -> Set[str]:
    module = importlib.import_module(module_name)

    result: Set[str] = set()
    module_path = module.__path__
    for module_info in pkgutil.walk_packages(module_path, module_name + "."):
        result.add(module_info.name)

    return result


def _consider_replacing_child_modules_with_parent(module_names: AbstractSet[str]) -> FrozenSet[str]:
    """If all child modules of a parent module X are present, replace them all with X itself."""
    # This is technically not exactly equivalent, since the parent module X includes all code
    # present in the __init__.py of the module, as well as all child modules. However, without this
    # transformation, the generated mypy config files are likely going to be absolutely massive!
    # Additionally, __init__.py files tend to be relatively small, so the risk of hiding
    # unexpected additional errors with this over-broad suppression is relatively small.
    # If we ever want to fix this "for good", we could just check the contents of the __init__.py
    # and only apply this transformation if the file is empty.
    original_module_names = frozenset(module_names)

    parentless_module_names: Set[str] = set()
    module_name_to_parent: Dict[str, str] = {}

    for module_name in module_names:
        if "." in module_name:
            parent_module, _ = module_name.rsplit(".", 1)
            module_name_to_parent[module_name] = parent_module
        else:
            parentless_module_names.add(module_name)

    # For any parent_name, if we see all its child modules (i.e. its set becomes empty),
    # we can replace all the child module names with the name of the parent module.
    unseen_child_modules_for_parent = {
        parent_name: _get_child_module_names_for_module(parent_name)
        for parent_name in set(module_name_to_parent.values())
    }

    for module_name, parent_name in module_name_to_parent.items():
        if module_name in unseen_child_modules_for_parent[parent_name]:
            unseen_child_modules_for_parent[parent_name].remove(module_name)

    final_modules = set(parentless_module_names)
    for parent_name, unseen_child_modules in unseen_child_modules_for_parent.items():
        if not unseen_child_modules:
            # Replacing all child modules with the parent module.
            final_modules.add(parent_name)
    for module_name, parent_name in module_name_to_parent.items():
        if unseen_child_modules_for_parent[parent_name]:
            # Not all child modules were seen, so the parent module cannot replace this module.
            final_modules.add(module_name)

    # Run to convergence.
    result = frozenset(final_modules)
    if result == original_module_names:
        # Fixed point reached.
        return result
    else:
        # Not yet at fixed point, try again.
        return _consider_replacing_child_modules_with_parent(result)


# ##############
# # Public API #
# ##############


def get_3rd_party_modules_missing_type_hints(errors: List[MypyError]) -> FrozenSet[str]:
    import_errors = [error for error in errors if error.error_code == "import"]

    module_names: Set[str] = set()
    for import_error in import_errors:
        module_name_match = _module_missing_type_hint_pattern.match(import_error.message)
        if module_name_match is None:
            module_name_match = _module_missing_implementation_or_library_stub_pattern.match(
                import_error.message
            )
            if module_name_match is None:
                raise AssertionError(
                    f"Unrecognized mypy [import]-coded error: {import_error} "
                    f"This should never happen."
                )
            else:
                click.echo(
                    f"WARNING: mypy was not able to find type hints for module "
                    f"'{module_name_match.group(1)}' since it does not seem to be installed "
                    f"in the current environment. Assuming it has no type hints available."
                )

        module_name = module_name_match.group(1)
        module_names.add(module_name)

    return _find_minimum_covering_modules(module_names)


def get_1st_party_modules_and_suppressions(
    errors: List[MypyError],
) -> Dict[str, List[MypyErrorSetting]]:
    non_import_errors = [error for error in errors if error.error_code != "import"]

    needed_setting_to_modules: Dict[MypyErrorSetting, Set[str]] = {}
    for error in non_import_errors:
        error_setting = _get_error_setting_for_error(error)
        module_name = _get_module_for_error(error)

        needed_setting_to_modules.setdefault(error_setting, set()).add(module_name)

    # Apply all settings that are dependencies of settings that are needed here.
    for dependent_setting, dependencies in _settings_that_require_other_settings.items():
        if dependent_setting in needed_setting_to_modules:
            for depended_setting in dependencies:
                if depended_setting in needed_setting_to_modules:
                    needed_setting_to_modules[depended_setting].update(
                        needed_setting_to_modules[dependent_setting]
                    )

    # Discard any modules for which the setting would be implied through an ancestor module.
    needed_setting_to_minimum_covering_modules: Dict[MypyErrorSetting, FrozenSet[str]] = {
        error_setting: _consider_replacing_child_modules_with_parent(
            _find_minimum_covering_modules(module_names)
        )
        for error_setting, module_names in needed_setting_to_modules.items()
    }

    module_to_error_settings: Dict[str, List[MypyErrorSetting]] = {}
    for error_setting, minimum_module_names in needed_setting_to_minimum_covering_modules.items():
        for module_name in minimum_module_names:
            module_to_error_settings.setdefault(module_name, []).append(error_setting)

    for error_settings in module_to_error_settings.values():
        error_settings.sort()

    return module_to_error_settings


def find_unused_ignores(errors: List[MypyError]) -> List[MypyError]:
    """Return the set of unused "type: ignore" suppressions that mypy has found."""
    result: List[MypyError] = []
    for error in errors:
        error_setting = _get_error_setting_for_error(error)
        if error_setting == _warn_unused_ignores_error_setting:
            result.append(error)

    return result
