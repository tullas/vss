from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from vss_runtime.audit import AuditLogger

from .errors import ReasoningAuditFailure


class ReasoningAuditSink(Protocol):
    def append(self, record: dict[str, Any]) -> None: ...


class DevelopmentReasoningAudit:
    """Development-only append audit using the existing hardened local writer."""

    __slots__ = ("_logger",)

    def __init__(self, repository_root: Path) -> None:
        self._logger = AuditLogger(
            repository_root / ".local/runtime/audit", trusted_root=repository_root
        )

    def append(self, record: dict[str, Any]) -> None:
        try:
            self._logger.append(record)
        except Exception as exc:
            raise ReasoningAuditFailure("reasoning audit record could not be written") from exc
