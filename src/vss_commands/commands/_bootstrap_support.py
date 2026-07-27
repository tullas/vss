from __future__ import annotations

import platform
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
    if not shutil.which("systemctl"):
        return {"active": False, "status": "unavailable"}
    available, value = _run(["systemctl", "is-system-running"])
    status = value if value else "inactive"
    return {"active": available and value == "active", "status": status}


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


def run_quiet(command: list[str], cwd: Path, timeout: float = 120.0) -> bool:
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
