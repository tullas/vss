from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from vss_runtime.host_inspection import bootstrap_report, docker_status, port_status, systemd_status, tofu_status


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_capture(command: list[str], cwd: Path, timeout: float = 120.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_interactive(command: list[str], cwd: Path) -> subprocess.CompletedProcess[bytes] | None:
    """Run with the caller's terminal descriptors; never capture interactive input."""
    try:
        return subprocess.run(command, cwd=cwd, check=False)
    except KeyboardInterrupt:
        return subprocess.CompletedProcess(command, 130)
    except OSError:
        return None


def run_quiet(command: list[str], cwd: Path, timeout: float = 120.0) -> bool:
    result = run_capture(command, cwd, timeout)
    return result is not None and result.returncode == 0


_SECRET_PATTERN = re.compile(r"(?i)(password|secret|token|api[_-]?key|private[_-]?key)(\s*[:=]\s*)([^\s,}]+)")
_ANSI_PATTERN = re.compile(r"(?:\x1B\][^\x07]*(?:\x07|\x1B\\)|\x1B\[[0-?]*[ -/]*[@-~])")


def sanitize_text(value: str, limit: int = 4000) -> str:
    without_ansi = _ANSI_PATTERN.sub("", value)
    redacted = _SECRET_PATTERN.sub(r"\1\2[REDACTED]", without_ansi)
    return " ".join(redacted.split())[:limit]


def ansible_failure_summary(result: subprocess.CompletedProcess[str] | None) -> dict[str, Any]:
    if result is None:
        return {"return_code": 20, "failed_task": "unknown", "message": "Ansible could not be started"}
    combined = f"{result.stdout}\n{result.stderr}"
    tasks = re.findall(r"TASK \[([^]]+)\]", combined)
    messages = re.findall(r'"msg"\s*:\s*"([^"\n]+)', combined)
    message = messages[-1] if messages else (next((line for line in reversed(combined.splitlines()) if line.strip()), "Ansible failed"))
    return {
        "return_code": result.returncode,
        "failed_task": sanitize_text(tasks[-1] if tasks else "unknown", 240),
        "message": sanitize_text(message, 400),
    }
