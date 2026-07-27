from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CommandMetadata:
    name: str
    version: str
    description: str
    input_schema: dict[str, Any]
    supports_dry_run: bool


@dataclass(frozen=True)
class CommandContext:
    environment: str
    configuration: dict[str, Any]
    correlation_id: str
    verbose: bool = False
    ask_become_pass: bool = False


CommandHandler = Callable[[CommandContext, dict[str, Any], bool], dict[str, Any]]


class SafeCommandError(RuntimeError):
    """Handler failure message approved for inclusion in the response envelope."""

    def __init__(self, message: str, output: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.output = output or {}


@dataclass(frozen=True)
class RegisteredCommand:
    metadata: CommandMetadata
    handler: CommandHandler
