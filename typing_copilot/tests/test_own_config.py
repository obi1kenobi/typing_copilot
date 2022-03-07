from pathlib import Path
from unittest import TestCase

import toml

from ..own_config import TypingCopilotConfig, find_pyproject_toml


class ConfigTests(TestCase):
    def test_can_find_pyproject_toml(self) -> None:
        search_path = Path(__file__).parent

        expected_pyproject_toml_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        self.assertEqual(expected_pyproject_toml_path, find_pyproject_toml(search_path))

    def test_can_read_mypy_settings_from_pyproject_toml(self) -> None:
        toml_content = """\
[tool-typing_copilot.mypy_global_config]
warn_unused_ignores = true
plugins = ["mypy_django_plugin.main"]
"""
        config = TypingCopilotConfig.from_toml(toml.loads(toml_content))

        expected_config = {
            "warn_unused_ignores": True,
            "plugins": ["mypy_django_plugin.main"],
        }
        self.assertEqual(expected_config, config.mypy_global_config)
