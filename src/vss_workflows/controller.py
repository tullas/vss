from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from vss_commands.exit_codes import ExitCode
from vss_runtime.audit import AuditLogger
from vss_runtime.controller import repository_root, utc_now
from vss_runtime.errors import RuntimeInternalFailure

from .errors import WorkflowFailure
from .models import WorkflowStatus
from .operations import ALLOWED_OPERATIONS, OperationRegistry
from .registry import WorkflowRegistry


class WorkflowController:
    def __init__(
        self,
        root: Path | None = None,
        operations: OperationRegistry | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.root = (root or repository_root()).resolve()
        self.operations = operations or OperationRegistry()
        self.registry = WorkflowRegistry(
            self.root / "workflows/builtin",
            self.root / "schemas/workflow-v1.schema.json",
            ALLOWED_OPERATIONS,
        )
        self.audit = audit_logger or AuditLogger(self.root / ".local/runtime/audit", trusted_root=self.root)

    def list_workflows(self) -> list[dict[str, Any]]:
        return [
            {
                "name": registered.manifest.name,
                "version": registered.manifest.version,
                "description": registered.manifest.description,
            }
            for registered in self.registry.list()
        ]

    def describe_workflow(self, name: str) -> dict[str, Any]:
        registered = self.registry.resolve(name)
        manifest = registered.manifest
        return {
            "schema_version": manifest.schema_version,
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "runtime_api_version": manifest.runtime_api_version,
            "execution_policy": manifest.execution_policy,
            "steps": [
                {
                    "id": step["id"],
                    "operation": step["operation"],
                    "timeout_seconds": step["timeout_seconds"],
                    "continue_on_error": step["continue_on_error"],
                }
                for step in manifest.steps
            ],
            "manifest_sha256": registered.manifest_sha256,
        }

    def _event(
        self,
        event_type: str,
        execution_id: str,
        correlation_id: str,
        workflow: str,
        version: str | None,
        digest: str | None,
        status: str,
        exit_code: int,
        duration_ms: int,
        step_id: str | None = None,
        operation: str | None = None,
        authorization: str = "not_applicable",
    ) -> None:
        self.audit.append({
            "schema_version": "1",
            "event_type": event_type,
            "timestamp": utc_now(),
            "workflow_execution_id": execution_id,
            "correlation_id": correlation_id,
            "workflow": workflow,
            "workflow_version": version,
            "step_id": step_id,
            "operation": operation,
            "authorization": authorization,
            "status": status,
            "exit_code": int(exit_code),
            "duration_ms": duration_ms,
            "manifest_sha256": digest,
        })

    def run(self, name: str, environment: str, correlation_id: str | None = None) -> tuple[dict[str, Any], int]:
        workflow_started_at = utc_now()
        workflow_clock = time.monotonic()
        execution_id = uuid.uuid4().hex
        correlation = correlation_id or uuid.uuid4().hex
        version: str | None = None
        digest: str | None = None
        step_results: list[dict[str, Any]] = []
        errors: list[str] = []
        status = WorkflowStatus.FAILED.value
        exit_code: int = int(ExitCode.WORKFLOW_INTERNAL_ERROR)
        try:
            registered = self.registry.resolve(name)
            self.registry.verify_integrity(registered)
            workflow = registered.manifest
            version = workflow.version
            digest = registered.manifest_sha256
            self._event(
                "workflow_started", execution_id, correlation, workflow.name, version, digest,
                WorkflowStatus.RUNNING.value, ExitCode.SUCCESS, 0,
            )
            failed = False
            for step in workflow.steps:
                if failed:
                    skipped = {
                        "id": step["id"], "operation": step["operation"], "status": WorkflowStatus.SKIPPED.value,
                        "exit_code": None, "started_at": None, "completed_at": None,
                        "duration_ms": 0, "output": {}, "errors": [],
                    }
                    step_results.append(skipped)
                    self._event(
                        "step_completed", execution_id, correlation, workflow.name, version, digest,
                        WorkflowStatus.SKIPPED.value, exit_code, 0, step["id"], step["operation"], "not_evaluated",
                    )
                    continue
                step_started_at = utc_now()
                step_clock = time.monotonic()
                self._event(
                    "step_started", execution_id, correlation, workflow.name, version, digest,
                    WorkflowStatus.RUNNING.value, ExitCode.SUCCESS, 0, step["id"], step["operation"], "approved",
                )
                response, operation_code = self.operations.execute(
                    step["operation"], environment, step["input"], correlation, step["timeout_seconds"]
                )
                step_duration = int((time.monotonic() - step_clock) * 1000)
                succeeded = operation_code == ExitCode.SUCCESS and response.get("status") == "success"
                step_status = WorkflowStatus.SUCCEEDED.value if succeeded else WorkflowStatus.FAILED.value
                safe_errors = [" ".join(str(error).replace("\n", " ").split())[:500] for error in response.get("errors", [])]
                step_results.append({
                    "id": step["id"],
                    "operation": step["operation"],
                    "status": step_status,
                    "exit_code": int(operation_code),
                    "started_at": step_started_at,
                    "completed_at": utc_now(),
                    "duration_ms": step_duration,
                    "output": self.operations.summarize(step["operation"], response.get("output", {})),
                    "errors": safe_errors,
                })
                self._event(
                    "step_completed" if succeeded else "step_failed",
                    execution_id, correlation, workflow.name, version, digest, step_status,
                    operation_code, step_duration, step["id"], step["operation"], "approved",
                )
                if not succeeded:
                    failed = True
                    errors = [f"workflow step failed: {step['id']}"]
                    exit_code = int(
                        ExitCode.WORKFLOW_TIMEOUT
                        if operation_code == ExitCode.TIMEOUT
                        else ExitCode.WORKFLOW_EXECUTION_FAILURE
                    )
            if not failed:
                status = WorkflowStatus.SUCCEEDED.value
                exit_code = int(ExitCode.SUCCESS)
        except WorkflowFailure as exc:
            errors = [str(exc)]
            exit_code = int(exc.exit_code)
        except RuntimeInternalFailure as exc:
            errors = [str(exc)]
            exit_code = int(ExitCode.WORKFLOW_INTERNAL_ERROR)
        except Exception:
            errors = ["internal workflow failure"]
            exit_code = int(ExitCode.WORKFLOW_INTERNAL_ERROR)

        completed_at = utc_now()
        duration_ms = int((time.monotonic() - workflow_clock) * 1000)
        result = {
            "schema_version": "1",
            "workflow": name,
            "workflow_version": version,
            "workflow_execution_id": execution_id,
            "correlation_id": correlation,
            "status": status,
            "started_at": workflow_started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "steps": step_results,
            "errors": errors,
        }
        try:
            self._event(
                "workflow_completed" if status == WorkflowStatus.SUCCEEDED.value else "workflow_failed",
                execution_id, correlation, name, version, digest, status, exit_code, duration_ms,
            )
        except RuntimeInternalFailure as exc:
            result["status"] = WorkflowStatus.FAILED.value
            result["errors"] = [str(exc)]
            return result, int(ExitCode.WORKFLOW_INTERNAL_ERROR)
        return result, exit_code
