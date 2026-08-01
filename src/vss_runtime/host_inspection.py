from __future__ import annotations

import platform
import re
import shutil
import socket
import stat
import subprocess
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


_APPROVED_EXECUTABLES = MappingProxyType(
    {
        "systemctl": (("is-system-running",),),
        "docker": (("--version",), ("info", "--format", "{{.ServerVersion}}")),
        "tofu": (("version",),),
    }
)
_APPROVED_EXECUTABLE_ROOTS = tuple(
    Path(value).resolve() for value in ("/bin", "/usr/bin", "/usr/local/bin", "/snap/bin")
)
_APPROVED_PORTS = frozenset({9000, 9001})
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,+_/-]{0,119}$")


class HostInspectionError(RuntimeError):
    """A safe failure raised by the runtime-owned inspection boundary."""


class HostInspector:
    """Expose only the fixed, read-only probes needed by bootstrap.check."""

    __slots__ = ()

    @staticmethod
    def _safe_version(value: str) -> str | None:
        candidate = value.strip()
        return candidate if _SAFE_VERSION.fullmatch(candidate) else None

    @staticmethod
    def _resolve_executable(name: str) -> Path | None:
        if name not in _APPROVED_EXECUTABLES:
            raise HostInspectionError("host probe executable is not approved")
        candidate = shutil.which(name)
        if candidate is None:
            return None
        path = Path(candidate)
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return None
        if not resolved.is_file() or not any(resolved.is_relative_to(root) for root in _APPROVED_EXECUTABLE_ROOTS):
            raise HostInspectionError("host probe executable resolved outside approved system paths")
        try:
            metadata = resolved.stat()
        except OSError as exc:
            raise HostInspectionError("host probe executable metadata is unavailable") from exc
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise HostInspectionError("host probe executable is not owned and protected by the system")
        return resolved

    @classmethod
    def _run(cls, name: str, arguments: tuple[str, ...], timeout: float = 10.0) -> tuple[bool, str]:
        allowed_shapes = _APPROVED_EXECUTABLES.get(name)
        if allowed_shapes is None or arguments not in allowed_shapes:
            raise HostInspectionError("host probe arguments are not approved")
        executable = cls._resolve_executable(name)
        if executable is None:
            return False, ""
        try:
            result = subprocess.run(
                [str(executable), *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env={},
            )
        except subprocess.TimeoutExpired:
            return False, ""
        except OSError as exc:
            raise HostInspectionError("host probe could not be executed") from exc
        return result.returncode == 0, result.stdout.strip()

    @staticmethod
    def _pid1_name() -> str:
        try:
            value = Path("/proc/1/comm").read_text(encoding="utf-8").strip().lower()
        except OSError:
            return "unavailable"
        return "systemd" if value == "systemd" else (value or "unknown")

    @classmethod
    def systemd_status(cls) -> dict[str, Any]:
        pid1 = cls._pid1_name()
        available, value = cls._run("systemctl", ("is-system-running",))
        # systemctl reports the usable "degraded" state with a non-zero code.
        status = value if value else "unavailable"
        state = status.splitlines()[0].strip().lower()
        return {
            "active": pid1 == "systemd" and state in {"running", "degraded"},
            "status": state,
            "pid1": pid1,
        }

    @classmethod
    def docker_status(cls) -> dict[str, Any]:
        executable = cls._resolve_executable("docker")
        if executable is None:
            return {"cli_available": False, "version": None, "daemon_accessible": False, "daemon_version": None}
        version_ok, version_output = cls._run("docker", ("--version",))
        daemon_ok, daemon_version = cls._run("docker", ("info", "--format", "{{.ServerVersion}}"))
        return {
            "cli_available": True,
            "version": cls._safe_version(version_output.split(",", 1)[0]) if version_ok else None,
            "daemon_accessible": daemon_ok,
            "daemon_version": cls._safe_version(daemon_version) if daemon_ok else None,
        }

    @classmethod
    def tofu_status(cls) -> dict[str, Any]:
        executable = cls._resolve_executable("tofu")
        if executable is None:
            return {"available": False, "version": None}
        ok, output = cls._run("tofu", ("version",))
        first_line = output.splitlines()[0] if output else ""
        return {"available": ok, "version": cls._safe_version(first_line) if first_line else None}

    @staticmethod
    def port_status(port: int) -> dict[str, Any]:
        if port not in _APPROVED_PORTS:
            raise HostInspectionError("host probe port is not approved")
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

    @classmethod
    def bootstrap_check(cls) -> Mapping[str, Any]:
        release = platform.release()
        return MappingProxyType(
            {
                "platform": {
                    "system": platform.system(),
                    "release": release,
                    "is_wsl": "microsoft" in release.lower() or "wsl" in release.lower(),
                },
                "systemd": cls.systemd_status(),
                "docker": cls.docker_status(),
                "opentofu": cls.tofu_status(),
                "ports": {"9000": cls.port_status(9000), "9001": cls.port_status(9001)},
            }
        )


def bootstrap_report() -> dict[str, Any]:
    """Compatibility helper for legacy readiness consumers."""
    return dict(HostInspector.bootstrap_check())


systemd_status = HostInspector.systemd_status
docker_status = HostInspector.docker_status
tofu_status = HostInspector.tofu_status
port_status = HostInspector.port_status
