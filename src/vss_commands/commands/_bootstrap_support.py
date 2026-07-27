from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str], timeout: float = 10.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout.strip()


def systemd_status() -> dict[str, Any]:
    pid1 = _pid1_name()
    if not shutil.which("systemctl"):
        return {"active": False, "status": "unavailable", "pid1": pid1}
    available, value = _run(["systemctl", "is-system-running"])
    status = value if value else "unavailable"
    state = status.splitlines()[0].strip().lower()
    usable_state = state in {"running", "degraded"}
    return {"active": pid1 == "systemd" and usable_state, "status": state, "pid1": pid1}


def _pid1_name() -> str:
    try:
        value = Path("/proc/1/comm").read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "unavailable"
    return "systemd" if value == "systemd" else (value or "unknown")


def docker_status() -> dict[str, Any]:
    cli = shutil.which("docker")
    version_ok, version_output = _run(["docker", "--version"]) if cli else (False, "")
    daemon_ok, daemon_version = (
        _run(["docker", "info", "--format", "{{.ServerVersion}}"])
        if cli
        else (False, "")
    )
    return {
        "cli_available": cli is not None,
        "version": version_output.split(",", 1)[0] if version_ok else None,
        "daemon_accessible": daemon_ok,
        "daemon_version": daemon_version if daemon_ok else None,
    }


def tofu_status() -> dict[str, Any]:
    binary = shutil.which("tofu")
    ok, output = _run(["tofu", "version"]) if binary else (False, "")
    first_line = output.splitlines()[0] if output else ""
    return {"available": binary is not None and ok, "version": first_line or None}


def port_status(port: int) -> dict[str, Any]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        try:
            conflict = sock.connect_ex(("127.0.0.1", port)) == 0
        finally:
            sock.close()
    except OSError:
        return {"conflict": None, "available": None, "status": "unavailable"}
    return {"conflict": conflict, "available": not conflict}


def bootstrap_report() -> dict[str, Any]:
    release = platform.release()
    is_wsl = "microsoft" in release.lower() or "wsl" in release.lower()
    return {
        "platform": {"system": platform.system(), "release": release, "is_wsl": is_wsl},
        "systemd": systemd_status(),
        "docker": docker_status(),
        "opentofu": tofu_status(),
        "ports": {"9000": port_status(9000), "9001": port_status(9001)},
    }


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
