from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .errors import RuntimeInternalFailure

_APPEND_LOCK = threading.Lock()


@contextmanager
def synchronized_audit_access() -> Iterator[None]:
    """Serialize publication and inspection of development JSONL records."""
    with _APPEND_LOCK:
        yield


class AuditLogger:
    def __init__(self, audit_root: Path, trusted_root: Path | None = None) -> None:
        self.audit_root = audit_root
        self.trusted_root = trusted_root.resolve() if trusted_root else None

    def append(self, record: dict[str, Any]) -> None:
        try:
            resolved_root = self.audit_root.resolve()
            if self.trusted_root is not None and not resolved_root.is_relative_to(self.trusted_root):
                raise RuntimeInternalFailure("runtime audit path escapes trusted root")
            self.audit_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.audit_root, 0o700)
            path = self.audit_root / "executions.jsonl"
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            payload = (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
            with synchronized_audit_access():
                descriptor = os.open(path, flags, 0o600)
                try:
                    os.chmod(path, 0o600)
                    written = 0
                    while written < len(payload):
                        count = os.write(descriptor, payload[written:])
                        if count <= 0:
                            raise RuntimeInternalFailure("runtime audit record could not be written")
                        written += count
                finally:
                    os.close(descriptor)
        except OSError as exc:
            raise RuntimeInternalFailure("runtime audit record could not be written") from exc
