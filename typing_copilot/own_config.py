from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, Mapping, Optional, Type, TypeVar


ConfigT = TypeVar("ConfigT", bound="TypingCopilotConfig")


def find_pyproject_toml(search_path: Path) -> Optional[Path]:
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


@dataclass(frozen=True)
class TypingCopilotConfig:
    mypy_global_config: Mapping[str, Any]

    @classmethod
    def from_toml(cls: Type[ConfigT], toml_content: Mapping[str, Any]) -> ConfigT:
        own_config_prefix = "tool-typing_copilot"
        typing_copilot_config: Mapping[str, Any] = toml_content.get(own_config_prefix, {})

        mypy_global_config: Mapping[str, Any] = typing_copilot_config.get("mypy_global_config", {})

        return cls(mypy_global_config=mypy_global_config)

    @classmethod
    def empty(cls: Type[ConfigT]) -> ConfigT:
        return cls(mypy_global_config=dict())
