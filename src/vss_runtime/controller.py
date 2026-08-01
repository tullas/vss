from __future__ import annotations

import concurrent.futures
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vss_commands.exit_codes import ExitCode
from .audit import AuditLogger
from .errors import (
    CapabilityExecutionFailure,
    InvalidCapabilityInput,
    RuntimeFailure,
    RuntimeInternalFailure,
    RuntimeTimeout,
)
from .loader import CapabilityLoader
from .models import ExecutionContext
from .policy import RuntimePolicy
from .registry import CapabilityRegistry


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class RuntimeController:
    def __init__(
        self,
        root: Path | None = None,
        policy: RuntimePolicy | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.root = (root or repository_root()).resolve()
        builtins_root = self.root / "capabilities"
        self.registry = CapabilityRegistry(builtins_root, self.root / "schemas/capability-manifest-v1.schema.json")
        self.loader = CapabilityLoader(builtins_root)
        self.policy = policy or RuntimePolicy()
        self.audit = audit_logger or AuditLogger(self.root / ".local/runtime/audit", trusted_root=self.root)

    def _source_commit(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.root, text=True, capture_output=True, check=False, timeout=2
            )
        except (OSError, subprocess.SubprocessError):
            return None
        value = result.stdout.strip()
        return value if result.returncode == 0 and len(value) == 40 else None

    def run(
        self,
        command: str,
        environment: str,
        configuration: dict[str, Any],
        input_data: dict[str, Any],
        correlation_id: str,
        started_at: str,
        started_clock: float,
        dry_run: bool = False,
        timeout_seconds: float | None = None,
        verbose: bool = False,
        ask_become_pass: bool = False,
    ) -> tuple[dict[str, Any], int]:
        capability_identity = command
        permissions: tuple[str, ...] = ()
        authorization = "not_evaluated"
        manifest_digest: str | None = None
        source_commit = self._source_commit()
        output: dict[str, Any] = {}
        errors: list[str] = []
        status = "error"
        exit_code: ExitCode = ExitCode.INTERNAL_ERROR
        try:
            capability = self.registry.resolve_command(command)
            capability_identity = capability.manifest.identity
            manifest_digest = capability.manifest_sha256
            command_record = capability.manifest.command(command)
            if command_record is None:
                raise RuntimeInternalFailure("capability command resolution failed")
            validation_errors = sorted(
                Draft202012Validator(command_record["input_schema"]).iter_errors(input_data),
                key=lambda error: list(error.path),
            )
            if validation_errors:
                raise InvalidCapabilityInput(f"invalid input: {validation_errors[0].message}")
            if dry_run and not command_record["supports_dry_run"]:
                raise InvalidCapabilityInput("command does not support dry-run")
            permissions = capability.manifest.permissions
            authorized = self.policy.authorize(permissions)
            authorization = "approved"
            context = ExecutionContext(
                environment=environment,
                configuration=configuration,
                correlation_id=correlation_id,
                declared_permissions=permissions,
                authorized_permissions=authorized,
                source_commit=source_commit,
                verbose=verbose,
                ask_become_pass=ask_become_pass,
            )
            handler = self.loader.load(capability)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(handler, context, input_data, dry_run)
            try:
                result = future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError as exc:
                future.cancel()
                raise RuntimeTimeout("command timed out") from exc
            except Exception as exc:
                raise CapabilityExecutionFailure("capability execution failed") from exc
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            if not isinstance(result, dict):
                raise CapabilityExecutionFailure("capability returned an invalid result")
            output_errors = sorted(
                Draft202012Validator(command_record["output_schema"]).iter_errors(result),
                key=lambda error: list(error.path),
            )
            if output_errors:
                raise CapabilityExecutionFailure("capability returned an invalid result")
            output = result
            status = "success"
            exit_code = ExitCode.SUCCESS
        except RuntimeFailure as exc:
            exit_code = exc.exit_code
            errors = [str(exc)]
            if exc.category == "permission_denied":
                authorization = "denied"
        except Exception:
            exit_code = ExitCode.INTERNAL_ERROR
            errors = ["runtime internal failure"]

        completed_at = utc_now()
        duration_ms = int((time.monotonic() - started_clock) * 1000)
        response = {
            "schema_version": "1",
            "command": command,
            "correlation_id": correlation_id,
            "started_at": started_at,
            "status": status,
            "exit_code": int(exit_code),
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output": output,
            "errors": errors,
        }
        audit_record = {
            "schema_version": "1",
            "timestamp": completed_at,
            "correlation_id": correlation_id,
            "capability": capability_identity,
            "command": command,
            "status": status,
            "exit_code": int(exit_code),
            "duration_ms": duration_ms,
            "declared_permissions": list(permissions),
            "authorization": authorization,
            "manifest_sha256": manifest_digest,
            "source_commit": source_commit,
        }
        try:
            self.audit.append(audit_record)
        except RuntimeInternalFailure as exc:
            response["status"] = "error"
            response["exit_code"] = int(ExitCode.INTERNAL_ERROR)
            response["output"] = {}
            response["errors"] = [str(exc)]
            return response, int(ExitCode.INTERNAL_ERROR)
        return response, int(exit_code)
