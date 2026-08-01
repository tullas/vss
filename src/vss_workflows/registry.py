from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .errors import InvalidWorkflow, WorkflowNotFound
from .manifest import load_workflow
from .models import RegisteredWorkflow

REQUESTED_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class WorkflowRegistry:
    def __init__(self, builtins_root: Path, schema_path: Path, allowed_operations: frozenset[str]) -> None:
        self.builtins_root = builtins_root.resolve()
        self.schema_path = schema_path.resolve()
        self.allowed_operations = allowed_operations

    def discover(self) -> dict[str, RegisteredWorkflow]:
        workflows: dict[str, RegisteredWorkflow] = {}
        try:
            paths = sorted(self.builtins_root.glob("*.yaml"), key=lambda path: path.name)
        except OSError as exc:
            raise InvalidWorkflow("trusted workflow root is unavailable") from exc
        for path in paths:
            resolved = path.resolve()
            if not resolved.is_relative_to(self.builtins_root):
                raise InvalidWorkflow("workflow path escapes trusted root")
            workflow, digest = load_workflow(resolved, self.schema_path, self.allowed_operations)
            if workflow.name in workflows:
                raise InvalidWorkflow(f"duplicate workflow name: {workflow.name}")
            workflows[workflow.name] = RegisteredWorkflow(workflow, resolved, digest)
        return workflows

    def resolve(self, name: str) -> RegisteredWorkflow:
        if not REQUESTED_NAME.fullmatch(name):
            raise WorkflowNotFound(f"workflow not found: {name}")
        workflow = self.discover().get(name)
        if workflow is None:
            raise WorkflowNotFound(f"workflow not found: {name}")
        return workflow

    def list(self) -> tuple[RegisteredWorkflow, ...]:
        workflows = self.discover()
        return tuple(workflows[name] for name in sorted(workflows))

    @staticmethod
    def verify_integrity(workflow: RegisteredWorkflow) -> None:
        try:
            digest = hashlib.sha256(workflow.manifest_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise InvalidWorkflow("workflow changed before execution") from exc
        if digest != workflow.manifest_sha256:
            raise InvalidWorkflow("workflow changed before execution")
