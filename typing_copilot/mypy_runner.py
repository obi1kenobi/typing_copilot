from dataclasses import dataclass
import os
from os import path
import subprocess
from tempfile import TemporaryDirectory
from typing import List, Type, TypeVar, Optional

from .verbosity import log_if_verbose


def run_mypy_with_config_file(mypy_config_path: str) -> subprocess.CompletedProcess:
    run_args = [
        "mypy",
        "--config-file",
        mypy_config_path,
        "--show-error-codes",
        "--error-summary",
        ".",
    ]
    log_if_verbose(f"Running mypy with {run_args}")
    completed_process = subprocess.run(run_args, capture_output=True, encoding="utf-8")
    log_if_verbose(
        f"Run completed with exit code {completed_process.returncode}. "
        f"Stdout: ***\n{completed_process.stdout}\n***"
    )
    return completed_process


def run_mypy_with_config(mypy_config: str) -> subprocess.CompletedProcess:
    with TemporaryDirectory(prefix="mypy-copilot-") as temp_dir:
        mypy_config_path = path.join(temp_dir, "mypy.ini")
        with open(mypy_config_path, "w") as mypy_config_file:
            log_if_verbose(f"Writing temporary mypy config file:\n\n{mypy_config}\n")
            mypy_config_file.write(mypy_config)
            mypy_config_file.flush()
            os.fsync(mypy_config_file.fileno())

        return run_mypy_with_config_file(mypy_config_path)


MypyErrorT = TypeVar("MypyErrorT", bound="MypyError")


@dataclass(frozen=True, order=True)
class MypyError:
    file_path: str
    line_number: int
    error_code: str
    message: str

    @classmethod
    def from_mypy_output_line(cls: Type[MypyErrorT], line: str) -> Optional[MypyErrorT]:
        file_path, line_num, rest_of_line = line.split(":", 2)
        file_path = file_path.strip()
        line_number = int(line_num.strip())

        rest_of_line = rest_of_line.strip()
        if rest_of_line.startswith("note:"):
            # This is not an error, ignore it.
            return None

        if "[" not in rest_of_line:
            # It seems the errors emitted by the "warn_unused_ignores" check
            # do not have error codes. Use the empty string for their error code.
            message = rest_of_line
            error_code = ""
        else:
            message, error_code = rest_of_line.rsplit("[", 1)
            message = message.strip()
            error_code = error_code.strip().strip("]").rstrip()

        return cls(file_path, line_number, error_code, message)


def get_mypy_errors_from_completed_process(
    completed_process: subprocess.CompletedProcess,
) -> List[MypyError]:
    output_lines = completed_process.stdout.strip().split("\n")
    if completed_process.returncode == 0:
        if not output_lines[-1].startswith("Success: no issues found"):
            raise AssertionError(f"Unexpected output for mypy exit code 0: {output_lines}")

        return []
    elif completed_process.returncode == 1:
        if not (output_lines[-1].startswith("Found ") and " error" in output_lines[-1]):
            stderr_lines = completed_process.stderr.strip().split("\n")
            raise AssertionError(
                f"Unexpected output for mypy exit code 1. Mypy stdout: {output_lines}, "
                f"stderr: {stderr_lines}"
            )

        error_lines = output_lines[:-1]
        return [
            value
            for value in (MypyError.from_mypy_output_line(error_line) for error_line in error_lines)
            if value is not None
        ]
    else:
        raise AssertionError(
            f"Unexpected mypy exit code {completed_process.returncode}. "
            f"Process info: {completed_process}"
        )


def get_mypy_errors_for_run_with_config(mypy_config: str) -> List[MypyError]:
    completed_process = run_mypy_with_config(mypy_config)
    return get_mypy_errors_from_completed_process(completed_process)
