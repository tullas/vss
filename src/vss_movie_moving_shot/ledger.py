from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AttemptLedgerError(ValueError):
    """The one-attempt moving-shot ledger cannot make the requested transition."""


def classify_legacy_record(path: Path, request_sha256: str) -> dict[str, Any]:
    """Classify the pre-6f52099 record without changing its historical bytes.

    The old handler wrote ``attempts: 1`` while reserving the slot.  That record
    is authoritative evidence of a consumed attempt, but is not a valid
    current execution state.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttemptLedgerError("legacy attempt record is unavailable or invalid") from exc
    if (not isinstance(value, dict)
            or set(value) != {"request_sha256", "attempts", "maximum_cost_usd", "status"}
            or value["request_sha256"] != request_sha256
            or value["maximum_cost_usd"] != "5.000000"
            or value["attempts"] != 1
            or value["status"] != "reserved"):
        raise AttemptLedgerError("legacy attempt record is not a recognized consumed reservation")
    return {"request_sha256": request_sha256, "attempts": 1,
            "maximum_cost_usd": "5.000000", "status": "consumed",
            "source_status": "reserved", "legacy": True}


def record_existing_authorization(path: Path, request_sha256: str) -> None:
    """Persist an already-granted approval without issuing a new one."""
    expected = {"request_sha256": request_sha256, "attempts": 0,
                "maximum_provider_attempts": 1, "status": "authorized",
                "source": "preexisting_human_authorization"}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptLedgerError("authorization record is unavailable or invalid") from exc
        if current != expected:
            raise AttemptLedgerError("authorization record does not match existing approval")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(expected, sort_keys=True, separators=(",", ":")), encoding="utf-8")


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

    def _authorization_path(self) -> Path:
        return self.path.with_name("authorization.json")

    def _require_authorization(self) -> None:
        try:
            value = json.loads(self._authorization_path().read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptLedgerError("current attempt authorization is unavailable or invalid") from exc
        if value != {"request_sha256": self.request_sha256, "attempts": 0,
                     "maximum_provider_attempts": 1, "status": "authorized",
                     "source": "preexisting_human_authorization"}:
            raise AttemptLedgerError("current attempt authorization is invalid")

    def _consume_authorization(self) -> None:
        path = self._authorization_path()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptLedgerError("current attempt authorization is unavailable or invalid") from exc
        authorized = {"request_sha256": self.request_sha256, "attempts": 0,
                      "maximum_provider_attempts": 1, "status": "authorized",
                      "source": "preexisting_human_authorization"}
        consumed = {**authorized, "attempts": 1, "status": "consumed"}
        if value == consumed:
            return
        if value != authorized:
            raise AttemptLedgerError("current attempt authorization cannot be consumed")
        path.write_text(json.dumps(consumed, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptLedgerError("attempt ledger is unavailable or invalid") from exc
        fields = {"request_sha256", "attempts", "maximum_cost_usd", "status"}
        operation_fields = {"operation_name", "execution_namespace"}
        if (not isinstance(value, dict)
                or set(value) not in (fields, fields | operation_fields)
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
        if set(value) == fields | operation_fields:
            if (value["status"] not in {"submitted", "completed", "failed"}
                    or not isinstance(value["operation_name"], str) or not value["operation_name"]
                    or len(value["operation_name"]) > 512
                    or not isinstance(value["execution_namespace"], str) or not value["execution_namespace"]
                    or len(value["execution_namespace"]) > 256):
                raise AttemptLedgerError("accepted operation identity is invalid")
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
        record_existing_authorization(self._authorization_path(), self.request_sha256)

    def reserve_execution(self) -> None:
        """Reserve the one execution slot without counting a submission."""
        self._require_authorization()
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

    def accept_operation(self, operation_name: str, execution_namespace: str) -> None:
        """Seal one accepted provider operation and consume its authorization."""
        if (not isinstance(operation_name, str) or not operation_name or len(operation_name) > 512
                or not isinstance(execution_namespace, str) or not execution_namespace
                or len(execution_namespace) > 256):
            raise AttemptLedgerError("accepted operation identity is invalid")
        value = self._read()
        identity = {"operation_name": operation_name, "execution_namespace": execution_namespace}
        if value["status"] == "reserved" and value["attempts"] == 0:
            value.update(identity)
            value["attempts"] = 1
            value["status"] = "submitted"
            self._write(value)
        elif (value["status"] in {"submitted", "failed", "completed"}
              and value.get("operation_name") == operation_name
              and value.get("execution_namespace") == execution_namespace):
            pass
        else:
            raise AttemptLedgerError("accepted operation does not match the reserved attempt")
        self._consume_authorization()

    def assert_operation(self, operation_name: str, execution_namespace: str) -> dict[str, Any]:
        """Fail closed unless recovery addresses this ledger's accepted operation."""
        value = self._read()
        if (value["status"] not in {"submitted", "failed", "completed"}
                or value["attempts"] != 1
                or value.get("operation_name") != operation_name
                or value.get("execution_namespace") != execution_namespace):
            raise AttemptLedgerError("accepted operation does not match the execution record")
        self._consume_authorization()
        return value

    def release_execution(self) -> None:
        """Release a reservation when provider acceptance was not evidenced."""
        self._require_authorization()
        value = self._read()
        if value["status"] != "reserved":
            raise AttemptLedgerError("execution reservation is not releasable")
        self._write({"request_sha256": self.request_sha256, "attempts": 0,
                     "maximum_cost_usd": self.maximum_cost_usd, "status": "authorized"})

    def terminal(self, status: str) -> None:
        """Close an accepted provider attempt without creating another."""
        if status not in {"completed", "failed"}:
            raise AttemptLedgerError("terminal status is invalid")
        value = self._read()
        if value["status"] == status:
            return
        if value["status"] not in {"submitted", "failed"}:
            raise AttemptLedgerError("submitted attempt is not open")
        value["status"] = status
        self._write(value)
