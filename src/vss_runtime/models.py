from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class CapabilityManifest:
    schema_version: str
    namespace: str
    name: str
    version: str
    description: str
    runtime_api_version: str
    sdk_api_version: str | None
    entry_point: str
    commands: tuple[dict[str, Any], ...]
    permissions: tuple[str, ...]
    compatibility: dict[str, Any]
    lifecycle_status: str

    @property
    def identity(self) -> str:
        return f"{self.namespace}.{self.name}"

    def command(self, name: str) -> dict[str, Any] | None:
        return next((item for item in self.commands if item["name"] == name), None)


@dataclass(frozen=True)
class RegisteredCapability:
    manifest: CapabilityManifest
    manifest_path: Path
    capability_root: Path
    manifest_sha256: str


@dataclass(frozen=True)
class ExecutionContext:
    environment: str
    configuration: dict[str, Any]
    correlation_id: str
    declared_permissions: tuple[str, ...]
    authorized_permissions: tuple[str, ...]
    source_commit: str | None
    verbose: bool = False
    ask_become_pass: bool = False


CapabilityHandler = Callable[[ExecutionContext, dict[str, Any], bool], dict[str, Any]]
