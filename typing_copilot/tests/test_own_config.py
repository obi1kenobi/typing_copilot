from pathlib import Path
from unittest import TestCase

from ..own_config import find_pyproject_toml


class ConfigTests(TestCase):
    def test_can_find_pyproject_toml(self) -> None:
        search_path = Path(__file__).parent

        expected_pyproject_toml_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        self.assertEqual(expected_pyproject_toml_path, find_pyproject_toml(search_path))
