import string


def validate_module_name(module_name: str) -> None:
    expected_chars = frozenset(string.ascii_letters + string.digits + "_" + ".")
    actual_chars = frozenset(module_name)

    expected_chars = frozenset(string.ascii_letters + string.digits + "_" + ".")
    actual_chars = frozenset(module_name)

    unexpected_chars = actual_chars - expected_chars
    if unexpected_chars:
        raise AssertionError(
            f"Invalid module name: found unexpected characters {unexpected_chars} in {module_name}"
        )

    if module_name.startswith(".") or module_name.endswith("."):
        raise AssertionError(
            f"Invalid module name: cannot start or end with a period character, got '{module_name}'"
        )
