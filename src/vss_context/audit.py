from pathlib import Path
from typing import Any, Protocol

from vss_runtime.audit import AuditLogger

class ContextAuditFailure(Exception):
    pass

class ContextAuditSink(Protocol):
    def append(self, record: dict[str, Any]) -> None: ...

class DevelopmentContextAudit:
    def __init__(self, root: Path) -> None:
        self._logger = AuditLogger(root / ".local/runtime/audit", trusted_root=root)

    def append(self, record: dict[str, Any]) -> None:
        try:
            self._logger.append(record)
        except Exception as exc:
            raise ContextAuditFailure("context audit record could not be written") from exc
