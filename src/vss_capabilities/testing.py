from __future__ import annotations

import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from vss_runtime import RuntimeController
from vss_runtime.policy import RuntimePolicy


class CapabilityTestHarness:
    """Exercise one built-in capability through the production Runtime Controller."""

    def __init__(self, capability_directory: Path, schema_path: Path, policy: RuntimePolicy | None = None) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        (self.root / "capabilities").mkdir()
        (self.root / "schemas").mkdir()
        shutil.copytree(capability_directory, self.root / "capabilities" / capability_directory.name)
        shutil.copy2(schema_path, self.root / "schemas/capability-manifest-v1.schema.json")
        self.controller = RuntimeController(root=self.root, policy=policy)

    def close(self) -> None:
        self._temporary.cleanup()

    def __enter__(self) -> "CapabilityTestHarness":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def manifest(self):
        return next(iter(self.controller.registry.discover().values())).manifest

    def execute(
        self,
        command: str,
        input_data: dict[str, Any],
        *,
        environment: str = "development",
        correlation_id: str | None = None,
    ) -> tuple[dict[str, Any], int]:
        correlation = correlation_id or uuid.uuid4().hex
        return self.controller.run(
            command=command,
            environment=environment,
            configuration={"schema_version": "1"},
            input_data=input_data,
            correlation_id=correlation,
            started_at="2026-01-01T00:00:00.000Z",
            started_clock=time.monotonic(),
        )

    def audit_records(self) -> list[dict[str, Any]]:
        path = self.root / ".local/runtime/audit/executions.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def deterministic_outcome(response: dict[str, Any]) -> dict[str, Any]:
        return {key: response[key] for key in ("schema_version", "command", "status", "exit_code", "output", "errors")}
