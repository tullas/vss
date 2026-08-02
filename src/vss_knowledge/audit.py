from pathlib import Path
from typing import Any, Protocol

from vss_runtime.audit import AuditLogger

from .errors import KnowledgeAuditFailure


class KnowledgeAuditSink(Protocol):
    def append(self, record: dict[str, Any]) -> None: ...


class DevelopmentKnowledgeAudit:
    __slots__ = ("_logger",)

    def __init__(self, repository_root: Path) -> None:
        self._logger = AuditLogger(repository_root / ".local/runtime/audit", trusted_root=repository_root)

    def append(self, record: dict[str, Any]) -> None:
        try:
            self._logger.append(record)
        except Exception as exc:
            raise KnowledgeAuditFailure("knowledge audit record could not be written") from exc
