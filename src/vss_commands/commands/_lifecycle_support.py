from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
from pathlib import Path
from typing import Any

from ..exit_codes import ExitCode
from ..models import SafeCommandError
from ._bootstrap_support import bootstrap_report, repository_root, run_capture, sanitize_text


def require_development(environment: str) -> None:
    if environment != "development":
        raise SafeCommandError("local lifecycle commands support development only", exit_code=ExitCode.INVALID_INPUT)


def secrets_path(environment: str) -> Path:
    return repository_root() / ".local" / "secrets" / f"{environment}.auto.tfvars"


def ignored_by_git(path: Path) -> bool:
    result = run_capture(["git", "check-ignore", "--quiet", str(path)], repository_root())
    return result is not None and result.returncode == 0


def safe_username() -> str:
    configured = os.environ.get("VSS_MINIO_USERNAME", "")
    if configured and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,31}", configured):
        return configured
    return f"vssadmin{secrets.token_hex(4)}"


def secrets_metadata(environment: str) -> dict[str, Any]:
    path = secrets_path(environment)
    mode = path.stat().st_mode & 0o777 if path.exists() else None
    return {
        "environment": environment,
        "initialized": path.is_file(),
        "git_ignored": ignored_by_git(path),
        "permissions": format(mode, "04o") if mode is not None else None,
        "path": str(path.relative_to(repository_root())),
    }


def require_ready(environment: str) -> None:
    report = bootstrap_report()
    if not report["docker"]["daemon_accessible"] or not report["opentofu"]["available"]:
        raise SafeCommandError("platform bootstrap is not ready; run ./scripts/bootstrap-host.sh", exit_code=ExitCode.NOT_READY)
    metadata = secrets_metadata(environment)
    if not metadata["initialized"] or not metadata["git_ignored"] or metadata["permissions"] != "0600":
        raise SafeCommandError("platform secrets are not ready; run vss secrets init", metadata, ExitCode.NOT_READY)


def run_iac(action: str, environment: str, *, non_interactive: bool = False) -> dict[str, Any]:
    command = [str(repository_root() / "scripts" / "iac-local.sh"), action]
    if non_interactive:
        command.append("--non-interactive")
    result = run_capture(command, repository_root(), timeout=900)
    if result is None:
        raise SafeCommandError("platform adapter could not be started")
    if result.returncode != 0:
        diagnostic = sanitize_text(f"{result.stdout}\n{result.stderr}", 1200)
        raise SafeCommandError(
            f"platform {action} failed",
            {"adapter": "scripts/iac-local.sh", "return_code": result.returncode, "diagnostic": diagnostic},
        )
    output: dict[str, Any] = {"adapter": "scripts/iac-local.sh", "action": action}
    for line in reversed(result.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            output.update(value)
            break
    return output
