from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._bootstrap_support import repository_root, run_capture

METADATA = CommandMetadata(
    name="bootstrap.verify",
    version="1.0.0",
    description="Verify the local toolchain and validate local IaC without applying it.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    return_code: int
    executable: str
    error_summary: str | None = None


def _return_code(result: subprocess.CompletedProcess[str] | None) -> int:
    if result is None:
        return 20
    return 128 + abs(result.returncode) if result.returncode < 0 else result.returncode


def _diagnostic(name: str, result: CheckResult) -> dict[str, Any]:
    return {
        "check": name,
        "executable": result.executable,
        "return_code": result.return_code,
        "error_summary": result.error_summary,
    }


def _repository_check(root: Path) -> CheckResult:
    required = (
        "ansible/playbooks/bootstrap-local.yml",
        "ansible/roles/local_toolchain/tasks/main.yml",
        "infrastructure/environments/development/local",
        ".local/secrets",
        ".local/state/development",
    )
    ok = all((root / path).exists() for path in required)
    return CheckResult(ok, 0 if ok else 2, "repository", None if ok else "required repository path is missing")


def _failure_message(failure: str) -> tuple[str, str]:
    messages = {
        "docker_cli_missing": (
            "Docker CLI is missing; rerun ./scripts/bootstrap-host.sh",
            "rerun bootstrap local",
        ),
        "docker_socket_permission_denied": (
            "Docker socket permission is denied; restart WSL and run ./scripts/bootstrap-host.sh --resume",
            "restart WSL and run bootstrap-host.sh --resume",
        ),
        "docker_daemon_stopped": (
            "Docker daemon is unavailable; start Docker, then run ./scripts/bootstrap-host.sh --resume",
            "start Docker",
        ),
        "opentofu_missing": (
            "OpenTofu is unavailable; rerun ./scripts/bootstrap-host.sh",
            "rerun bootstrap local",
        ),
        "repository_missing": (
            "a required repository path is missing; rerun ./scripts/bootstrap-host.sh from the VSS repository root",
            "rerun bootstrap local",
        ),
        "iac_validation_failed": (
            "IaC validation failed; inspect scripts/iac-local.sh validate, then rerun ./scripts/bootstrap-host.sh --resume",
            "inspect IaC validation",
        ),
    }
    return messages[failure]


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    root = repository_root()
    docker_path = shutil.which("docker")
    docker_cli = CheckResult(
        docker_path is not None,
        0 if docker_path else 127,
        "docker",
        None if docker_path else "Docker CLI executable is missing",
    )
    docker_result = run_capture([docker_path, "info"], root) if docker_path else None
    docker_combined = "" if docker_result is None else f"{docker_result.stdout}\n{docker_result.stderr}".lower()
    docker_permission_denied = any(
        marker in docker_combined for marker in ("permission denied", "access denied", "operation not permitted")
    )
    docker_info = CheckResult(
        docker_result is not None and docker_result.returncode == 0,
        _return_code(docker_result) if docker_path else 127,
        "docker info",
        None
        if docker_result is not None and docker_result.returncode == 0
        else ("Docker socket permission denied" if docker_permission_denied else "Docker daemon is unavailable"),
    )

    tofu_path = shutil.which("tofu")
    tofu_result = run_capture([tofu_path, "version"], root) if tofu_path else None
    tofu_version = CheckResult(
        tofu_result is not None and tofu_result.returncode == 0,
        _return_code(tofu_result) if tofu_path else 127,
        "tofu version",
        None if tofu_result is not None and tofu_result.returncode == 0 else "OpenTofu executable is unavailable",
    )
    repository = _repository_check(root)
    iac_result = run_capture([str(root / "scripts/iac-local.sh"), "validate"], root) if tofu_version.ok and repository.ok else None
    iac_validate = CheckResult(
        iac_result is not None and iac_result.returncode == 0,
        _return_code(iac_result) if tofu_version.ok and repository.ok else 125,
        "scripts/iac-local.sh validate",
        None if iac_result is not None and iac_result.returncode == 0 else "IaC validation command failed or was skipped",
    )
    results = {
        "docker_cli": docker_cli,
        "docker_info": docker_info,
        "tofu_version": tofu_version,
        "repository": repository,
        "iac_validate": iac_validate,
    }
    checks = {name: result.ok for name, result in results.items()}
    if not all(checks.values()):
        if not docker_cli.ok:
            failure = "docker_cli_missing"
        elif not docker_info.ok:
            failure = "docker_socket_permission_denied" if docker_permission_denied else "docker_daemon_stopped"
        elif not tofu_version.ok:
            failure = "opentofu_missing"
        elif not repository.ok:
            failure = "repository_missing"
        else:
            failure = "iac_validation_failed"
        message, next_action = _failure_message(failure)
        raise SafeCommandError(
            message,
            {
                "checks": checks,
                "failure": failure,
                "next_action": next_action,
                "diagnostics": [
                    _diagnostic(name, result) for name, result in results.items() if not result.ok
                ],
            },
        )
    return {"environment": context.environment, "dry_run": dry_run, "checks": checks, "apply_performed": False}
