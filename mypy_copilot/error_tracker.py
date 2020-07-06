import re
from typing import FrozenSet, List, Set

from .mypy_runner import MypyError


_module_missing_type_hint_pattern = re.compile(
    r"error: Skipping analyzing '([a-zA-Z0-9_\.]+)': "
    r"found module but no type hints or library stubs"
)


def get_3rd_party_modules_missing_type_hints(
    errors: List[MypyError]
) -> FrozenSet[str]:
    import_errors = [
        error
        for error in errors
        if error.error_code == "import"
    ]

    module_names: Set[str] = set()
    for import_error in import_errors:
        module_name_match = _module_missing_type_hint_pattern.match(import_error.message)
        if module_name_match is None:
            raise AssertionError(
                f"Unrecognized mypy [import]-coded error: {import_error}"
                f"This should never happen."
            )

        module_name = module_name_match.group(1)
        module_names.add(module_name)

    return _find_minimum_covering_modules(module_names)


def _find_minimum_covering_modules(module_names: Set[str]) -> FrozenSet[str]:
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
