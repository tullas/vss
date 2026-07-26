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


CommandHandler = Callable[[CommandContext, dict[str, Any], bool], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredCommand:
    metadata: CommandMetadata
    handler: CommandHandler
