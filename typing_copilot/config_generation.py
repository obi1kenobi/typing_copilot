from typing import List

from .error_tracker import MypyErrorSetting
from .validation import validate_module_name
from . import __package_name__, __version__


STRICT_BASELINE_MYPY_CONFIG = f"""
# Autogenerated by {__package_name__} v{__version__}
[mypy]
no_implicit_optional = True
strict_optional = True
warn_redundant_casts = True
check_untyped_defs = True
disallow_untyped_calls = True
disallow_incomplete_defs = True
disallow_untyped_defs = True
disallow_untyped_decorators = True
ignore_missing_imports = False
"""

LAX_BASELINE_MYPY_CONFIG = f"""
# Autogenerated by {__package_name__} v{__version__}
[mypy]
no_implicit_optional = False
strict_optional = False
warn_redundant_casts = False
check_untyped_defs = False
disallow_untyped_calls = False
disallow_incomplete_defs = False
disallow_untyped_defs = False
disallow_untyped_decorators = False
ignore_missing_imports = True
"""


def make_unused_ignores_config_line(unused_ignores_setting: bool) -> str:
    # N.B.: As of version 0.782, mypy only reports these errors if other checks pass.
    return f"warn_unused_ignores = {unused_ignores_setting}\n"


def make_ignore_missing_imports_block(module_name: str) -> str:
    validate_module_name(module_name)

    return f"""
[mypy-{module_name}.*]
ignore_missing_imports = True
"""


def make_1st_party_module_rule_block(module_name: str, rules: List[MypyErrorSetting]) -> str:
    validate_module_name(module_name)

    section_header = f"\n[mypy-{module_name}.*]\n"
    rule_lines = [f"{rule_name} = {value}" for (rule_name, value) in rules]

    return section_header + "\n".join(rule_lines) + "\n"
