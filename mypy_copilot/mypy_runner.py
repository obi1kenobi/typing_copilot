from dataclasses import dataclass
import os
from os import path
import subprocess
from tempfile import TemporaryDirectory
from typing import List, Type, TypeVar


def _run_mypy_with_config(mypy_config: str) -> subprocess.CompletedProcess:
    with TemporaryDirectory(prefix="mypy-copilot") as temp_dir:
        mypy_config_path = path.join(temp_dir, "mypy.ini")
        with open(mypy_config_path, "w") as mypy_config_file:
            mypy_config_file.write(mypy_config)
            mypy_config_file.flush()
            os.fsync(mypy_config_file.fileno())

        run_args = [
            "mypy",
            "--config-file",
            mypy_config_path,
            "--show-error-codes",
            "--error-summary",
            ".",
        ]
        completed_process = subprocess.run(run_args, capture_output=True, encoding="utf-8")
        return completed_process


MypyErrorT = TypeVar("MypyErrorT", bound="MypyError")


@dataclass
class MypyError:
    file_path: str
    line_number: int
    error_code: str
    message: str

    @classmethod
    def from_mypy_output_line(cls: Type[MypyErrorT], line: str) -> MypyErrorT:
        file_path, line_num, rest_of_line = line.split(":", 2)
        file_path = file_path.strip()
        line_number = int(line_num.strip())

        message, error_code = rest_of_line.rsplit("[", 1)
        message = message.strip()
        error_code = error_code.strip().strip("]").rstrip()

        return cls(file_path, line_number, error_code, message)


def get_mypy_errors_for_run_with_config(mypy_config: str) -> List[MypyError]:
    completed_process = _run_mypy_with_config(mypy_config)

    output_lines = completed_process.stdout.strip().split("\n")
    if completed_process.returncode == 0:
        if not output_lines[-1].startswith("Success: no issues found"):
            raise AssertionError(
                f"Unexpected output for mypy exit code 0: {output_lines}"
            )

        return []
    elif completed_process.returncode == 1:
        if not (output_lines[-1].startswith("Found ") and " error" in output_lines[-1]):
            raise AssertionError(
                f"Unexpected output for mypy exit code 1: {output_lines}"
            )

        error_lines = output_lines[:-1]
        return [
            MypyError.from_mypy_output_line(error_line)
            for error_line in error_lines
        ]
    else:
        raise AssertionError(
            f"Unexpected mypy exit code {completed_process.returncode}. "
            f"Process info: {completed_process}"
        )
