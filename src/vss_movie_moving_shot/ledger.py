from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AttemptLedgerError(ValueError):
    """The one-attempt moving-shot ledger cannot make the requested transition."""


@dataclass(frozen=True, slots=True)
class AttemptLedger:
    """Small local state machine separating approval, reservation, and use.

    ``attempts`` counts provider submissions, never approvals or preflight.
    Existing ledgers are intentionally not migrated by this class; callers must
    fail closed on an incompatible or already-consumed record.
    """

    path: Path
    request_sha256: str
    maximum_cost_usd: str = "5.000000"

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptLedgerError("attempt ledger is unavailable or invalid") from exc
        if (not isinstance(value, dict)
                or set(value) != {"request_sha256", "attempts", "maximum_cost_usd", "status"}
                or value["request_sha256"] != self.request_sha256
                or value["maximum_cost_usd"] != self.maximum_cost_usd
                or type(value["attempts"]) is not int
                or value["attempts"] not in (0, 1)
                or value["status"] not in {"authorized", "reserved", "submitted", "completed", "failed"}):
            raise AttemptLedgerError("attempt ledger shape is invalid")
        if value["status"] in {"authorized", "reserved"} and value["attempts"] != 0:
            raise AttemptLedgerError("unsubmitted ledger has consumed attempts")
        if value["status"] in {"submitted", "completed", "failed"} and value["attempts"] != 1:
            raise AttemptLedgerError("submitted ledger has invalid attempt count")
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def authorize(self) -> None:
        """Record approval only; it consumes no provider attempt."""
        if self.path.exists():
            raise AttemptLedgerError("attempt ledger already exists")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write({"request_sha256": self.request_sha256, "attempts": 0,
                     "maximum_cost_usd": self.maximum_cost_usd, "status": "authorized"})

    def reserve_execution(self) -> None:
        """Reserve the one execution slot without counting a submission."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write({"request_sha256": self.request_sha256, "attempts": 0,
                         "maximum_cost_usd": self.maximum_cost_usd, "status": "reserved"})
            return
        value = self._read()
        if value["status"] != "authorized":
            raise AttemptLedgerError("execution reservation is not available")
        value["status"] = "reserved"
        self._write(value)

    def mark_submitted(self) -> None:
        """Consume the slot at the provider-submission boundary."""
        value = self._read()
        if value["status"] != "reserved":
            raise AttemptLedgerError("provider submission is not available")
        value["attempts"] = 1
        value["status"] = "submitted"
        self._write(value)

    def terminal(self, status: str) -> None:
        """Close a submitted attempt without creating another attempt."""
        if status not in {"completed", "failed"}:
            raise AttemptLedgerError("terminal status is invalid")
        value = self._read()
        if value["status"] != "submitted":
            raise AttemptLedgerError("submitted attempt is not open")
        value["status"] = status
        self._write(value)
