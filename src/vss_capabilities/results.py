from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vss_commands.exit_codes import ExitCode
from .constants import MAX_OUTPUT_BYTES
from .validation import validate_json_value


def _safe_message(message: str) -> str:
    return " ".join(message.replace("\n", " ").replace("\r", " ").split())[:500]


@dataclass(frozen=True, slots=True)
class SafeCapabilityError:
    message: str
    exit_code: ExitCode = ExitCode.EXECUTION_FAILURE

    def __post_init__(self) -> None:
        if not isinstance(self.message, str):
            raise TypeError("safe capability error message must be a string")
        if not isinstance(self.exit_code, ExitCode):
            raise TypeError("safe capability errors require a named exit code")
        if self.exit_code in (ExitCode.SUCCESS, ExitCode.INTERNAL_ERROR):
            raise ValueError("safe capability errors require a non-success, non-internal named exit code")
        object.__setattr__(self, "message", _safe_message(self.message))
        if not self.message:
            raise ValueError("safe capability error message must not be empty")


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    output: dict[str, Any]
    error: SafeCapabilityError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output, dict):
            raise TypeError("capability result output must be an object")
        validate_json_value(self.output, maximum_bytes=MAX_OUTPUT_BYTES)
        if self.error is not None and not isinstance(self.error, SafeCapabilityError):
            raise TypeError("capability result error must be a SafeCapabilityError")
        if self.error is not None and self.output:
            raise ValueError("failed capability results cannot include output")

    @classmethod
    def success(cls, output: dict[str, Any]) -> "CapabilityResult":
        return cls(output=output)

    @classmethod
    def failure(cls, error: SafeCapabilityError) -> "CapabilityResult":
        return cls(output={}, error=error)
