import toml

from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, Mapping, Optional, Type, TypeVar

ConfigT = TypeVar("ConfigT", bound="TypingCopilotConfig")


@dataclass(frozen=True)
class TypingCopilotConfig:
    mypy_global_config: Mapping[str, Any]

    @classmethod
    def from_toml(cls: Type[ConfigT], toml_content: Mapping[str, Any]) -> ConfigT:
        pass

    @classmethod
    def empty(cls: Type[ConfigT]) -> ConfigT:
        return cls(dict())


def _find_pyproject_toml(search_path: Path) -> Optional[Path]:
    resolved_path = search_path.resolve()

    for current_path in chain((resolved_path,), resolved_path.parents):
        possible_pyproject_path = current_path / "pyproject.toml"
        if possible_pyproject_path.is_file():
            return possible_pyproject_path

        if (current_path / ".git").is_dir() or (current_path / ".hg").is_dir():
            # Reached the project root, didn't find a pyproject.toml so there probably isn't one.
            return None

    # Reached the root of the filesystem and didn't find a pyproject.toml.
    return None


def fetch_config_from_pyproject_toml(search_path: Path) -> Optional[TypingCopilotConfig]:
    pyproject_toml_path = _find_pyproject_toml(search_path)

    if pyproject_toml_path is not None:
        try:
            with open(pyproject_toml_path) as f:
                return TypingCopilotConfig.from_toml(toml.load(f))
        except OSError:
            return None
        except toml.TomlDecodeError:
            return None

    return None
