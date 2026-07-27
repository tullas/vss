from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

from ..exit_codes import ExitCode
from ..models import SafeCommandError
from ._bootstrap_support import bootstrap_report, repository_root, run_capture, sanitize_text

REQUIRED_LOCAL_SECRET_KEYS = ("minio_root_user", "minio_root_password")
_ASSIGNMENT = re.compile(
    r'^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>"(?:[^"\\]|\\.)*")\s*(?:(?:#|//).*)?$'
)


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


def _validate_secret_content(path: Path) -> tuple[dict[str, bool], list[str]]:
    present = {key: False for key in REQUIRED_LOCAL_SECRET_KEYS}
    invalid: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return present, list(REQUIRED_LOCAL_SECRET_KEYS)
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        match = _ASSIGNMENT.fullmatch(stripped)
        if match is None:
            for key in REQUIRED_LOCAL_SECRET_KEYS:
                if re.match(rf"^{re.escape(key)}\s*=", stripped):
                    invalid.add(key)
            continue
        key = match.group("key")
        if key not in present:
            continue
        if key in seen:
            invalid.add(key)
            continue
        seen.add(key)
        try:
            value = json.loads(match.group("value"))
        except json.JSONDecodeError:
            invalid.add(key)
            continue
        if not isinstance(value, str) or not value or "${" in value or "%{" in value:
            invalid.add(key)
            continue
        present[key] = True
    invalid.update(key for key, found in present.items() if not found)
    return present, [key for key in REQUIRED_LOCAL_SECRET_KEYS if key in invalid]


def secrets_metadata(environment: str) -> dict[str, Any]:
    path = secrets_path(environment)
    file_exists = path.is_file()
    mode = path.stat().st_mode & 0o777 if file_exists else None
    required_keys_present, validation_errors = (
        _validate_secret_content(path)
        if file_exists
        else ({key: False for key in REQUIRED_LOCAL_SECRET_KEYS}, list(REQUIRED_LOCAL_SECRET_KEYS))
    )
    git_ignored = ignored_by_git(path)
    permissions = format(mode, "04o") if mode is not None else None
    initialized = (
        file_exists
        and not validation_errors
        and permissions == "0600"
        and git_ignored
    )
    return {
        "file_exists": file_exists,
        "initialized": initialized,
        "required_keys_present": required_keys_present,
        "permissions": permissions,
        "git_ignored": git_ignored,
        "validation_errors": validation_errors,
    }


def require_ready(environment: str) -> None:
    metadata = secrets_metadata(environment)
    if not metadata["initialized"]:
        raise SafeCommandError(
            f"local secrets are incomplete; run vss secrets init --environment {environment} --rotate",
            metadata,
            ExitCode.NOT_READY,
        )
    report = bootstrap_report()
    if not report["docker"]["daemon_accessible"] or not report["opentofu"]["available"]:
        raise SafeCommandError("platform bootstrap is not ready; run ./scripts/bootstrap-host.sh", exit_code=ExitCode.NOT_READY)


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
