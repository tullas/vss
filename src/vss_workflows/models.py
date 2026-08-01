from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class WorkflowManifest:
    schema_version: str
    name: str
    version: str
    description: str
    runtime_api_version: str
    execution_policy: dict[str, Any]
    steps: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class RegisteredWorkflow:
    manifest: WorkflowManifest
    manifest_path: Path
    manifest_sha256: str
