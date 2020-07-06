import string


STRICT_BASELINE_MYPY_CONFIG = """
[mypy]
no_implicit_optional = True
strict_optional = True
warn_redundant_casts = True
check_untyped_defs = True
disallow_untyped_calls = True
disallow_incomplete_defs = True
disallow_untyped_defs = True
disallow_untyped_decorators = True
warn_unused_ignores = True
"""

LAX_BASELINE_MYPY_CONFIG = """
[mypy]
no_implicit_optional = False
strict_optional = False
warn_redundant_casts = False
check_untyped_defs = False
disallow_untyped_calls = False
disallow_incomplete_defs = False
disallow_untyped_defs = False
disallow_untyped_decorators = False
warn_unused_ignores = False
ignore_missing_imports = True
"""


def make_ignore_missing_imports_block(module_name: str) -> str:
    expected_chars = frozenset(string.ascii_letters + string.digits + "_" + ".")
    actual_chars = frozenset(module_name)

    unexpected_chars = actual_chars - expected_chars
    if unexpected_chars:
        raise ValueError(
            f"Invalid module name: found unexpected characters {unexpected_chars} in {module_name}"
        )

    if module_name.startswith(".") or module_name.endswith("."):
        raise ValueError(
            f"Invalid module name: cannot start or end with a period character, got '{module_name}'"
        )

    return f"""
[mypy-{module_name}.*]
ignore_missing_imports = True
"""



