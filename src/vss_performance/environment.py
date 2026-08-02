from __future__ import annotations

import os
import platform
import resource
import sys
import threading
from typing import Any


def _available_memory_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        value = pages * size
        return value if type(value) is int and value >= 0 else None
    except (AttributeError, OSError, ValueError):
        return None


def _fd_count() -> int | None:
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return None


def collect_environment() -> dict[str, Any]:
    release = platform.release()
    return {
        "operating_system": platform.system() or "unknown",
        "platform_release": release or "unknown",
        "architecture": platform.machine() or "unknown",
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "available_memory_bytes": _available_memory_bytes(),
        "wsl": "microsoft" in release.lower(),
        "ci": bool(os.environ.get("CI")),
    }


def collect_resources() -> dict[str, int | float | None]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "process_cpu_seconds": round(time_process(), 6),
        "maximum_resident_set_kib": int(usage.ru_maxrss),
        "active_thread_count": threading.active_count(),
        "open_file_descriptor_count": _fd_count(),
    }


def time_process() -> float:
    # Kept behind one function so tests can isolate platform observations.
    import time

    return time.process_time()
