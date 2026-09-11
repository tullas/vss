from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


MAX_FLIGHT_RECORDER_BYTES = 64 * 1024
MAX_STRING_LENGTH = 1024
MAX_COLLECTION_ITEMS = 64
EXTERNAL_PROVIDER_ADMISSION_RULE = (
    "No paid or externally side-effecting provider capability may be admitted "
    "unless its request, asynchronous lifecycle, terminal response, artifact "
    "admission, and failure evidence can first be exercised deterministically "
    "without the provider."
)
_SECRET_KEY = re.compile(r"(?i)(token|secret|password|credential|authorization|api.?key)")
_BEARER = re.compile(r"(?i)(bearer\s+)[^\s,;]+")


class FailureClass(str, Enum):
    CONNECTIVITY = "connectivity"
    AUTHENTICATION = "authentication"
    AUTHORIZATION_IAM = "authorization_iam"
    QUOTA = "quota"
    REQUEST_CONTRACT = "request_contract"
    SUBMISSION = "submission"
    ASYNCHRONOUS_OPERATION = "asynchronous_operation"
    POLLING = "polling"
    TERMINAL_PROVIDER_FAILURE = "terminal_provider_failure"
    RESULT_REPRESENTATION = "result_representation"
    MEDIA_DECODING = "media_decoding"
    MEDIA_CONTAINER_ADMISSION = "media_container_admission"
    PERSISTENCE = "persistence"
    LEDGER_STATE = "ledger_state"
    LOCAL_EXECUTION = "local_execution"


def _safe_value(value: object, depth: int = 0) -> object:
    if depth > 4:
        return "[depth-limited]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        value = _BEARER.sub(r"\1[redacted]", value)
        value = re.sub(r"https?://[^\s]+", "[url redacted]", value)
        return value[:MAX_STRING_LENGTH]
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        items = sorted(((str(key), item) for key, item in value.items()), key=lambda pair: pair[0])[:MAX_COLLECTION_ITEMS]
        for key, item in items:
            if _SECRET_KEY.search(key):
                result[key[:128]] = "[redacted]"
            else:
                result[key[:128]] = _safe_value(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, depth + 1) for item in list(value)[:MAX_COLLECTION_ITEMS]]
    return f"[{type(value).__name__}]"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ProviderReadiness:
    checks: Mapping[str, bool]
    unresolved_known_risks: tuple[str, ...]
    paid_execution_recommended: bool
    provider_call_required_for_reproduction: bool

    def to_json_value(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "contract_identity": "vss.provider-reliability-readiness",
            "contract_version": "1",
            "checks": dict(self.checks),
            "paid_execution_recommended": self.paid_execution_recommended,
            "unresolved_known_risks": list(self.unresolved_known_risks),
            "provider_call_required_for_reproduction": self.provider_call_required_for_reproduction,
        }


class ProviderReliabilityEngineer:
    """Advisory analyzer; deliberately exposes no execution capability."""

    provider_execution_authority = False
    retry_authority = False
    production_authority = False
    publication_authority = False

    def readiness(self, checks: Mapping[str, bool], *, known_risks: tuple[str, ...] = ()) -> ProviderReadiness:
        return assess_readiness(checks, known_risks=known_risks)

    def diagnosis(self, failure_class: FailureClass, message: str) -> dict[str, object]:
        if not isinstance(failure_class, FailureClass) or not message:
            raise ValueError("reliability diagnosis is invalid")
        return {"advisory": True, "classification": failure_class.value, "message": message[:MAX_STRING_LENGTH],
                "provider_execution_authority": False, "retry_authority": False}


def assess_readiness(checks: Mapping[str, bool], *, known_risks: tuple[str, ...] = ()) -> ProviderReadiness:
    required = (
        "authentication_construction", "network_readiness", "request_contract",
        "submission_observability", "lro_persistence", "poll_observability",
        "terminal_result_observability", "result_parser", "media_admission",
        "historical_regression_coverage",
    )
    normalized = MappingProxyType({name: checks.get(name) is True for name in required})
    unresolved = tuple(sorted(set(known_risks) | {name for name, ready in normalized.items() if not ready}))
    return ProviderReadiness(normalized, unresolved, not unresolved, False)


class FlightRecorder:
    """Deterministic bounded lifecycle evidence with an explicit freeze point."""

    def __init__(self, request_summary: Mapping[str, object], *, recorder_id: str = "offline") -> None:
        self._value: dict[str, object] = {
            "schema_version": "1", "contract_identity": "vss.provider-flight-recorder",
            "contract_version": "1", "recorder_id": recorder_id[:128],
            "request_summary": _safe_value(request_summary), "events": [],
        }
        self._frozen = False

    def _append(self, event: Mapping[str, object]) -> None:
        if self._frozen:
            raise RuntimeError("provider flight recorder is frozen")
        events = self._value["events"]
        assert isinstance(events, list)
        events.append(_safe_value(event))
        if len(_canonical(self._value)) > MAX_FLIGHT_RECORDER_BYTES:
            events.pop()
            raise ValueError("provider flight recorder exceeds its bound")

    def record(self, phase: str, *, status: str, failure_class: FailureClass | None = None,
               metadata: Mapping[str, object] | None = None) -> None:
        event: dict[str, object] = {"ordinal": len(self._value["events"]) + 1, "phase": phase[:64], "status": status[:64]}
        if failure_class is not None:
            event["failure_class"] = failure_class.value
        if metadata:
            event["metadata"] = metadata
        self._append(event)

    def record_readiness(self, readiness: ProviderReadiness) -> None:
        self._value["readiness"] = readiness.to_json_value()

    def record_terminal(self, metadata: Mapping[str, object]) -> None:
        self._value["terminal_response"] = _safe_value(metadata)

    def record_media(self, metadata: Mapping[str, object]) -> None:
        self._value["media_admission"] = _safe_value(metadata)

    def record_diagnosis(self, *, classification: FailureClass, message: str,
                         underlying: BaseException | None = None) -> None:
        diagnosis: dict[str, object] = {
            "classification": classification.value, "message": message[:MAX_STRING_LENGTH],
        }
        if underlying is not None:
            diagnosis["underlying_exception"] = {
                "type": type(underlying).__name__, "message": str(underlying)[:MAX_STRING_LENGTH],
            }
        self._value["diagnosis"] = _safe_value(diagnosis)

    def freeze(self) -> dict[str, object]:
        if not self._frozen:
            body = _canonical(self._value)
            self._value["evidence_sha256"] = hashlib.sha256(body).hexdigest()
            if len(_canonical(self._value)) > MAX_FLIGHT_RECORDER_BYTES:
                raise ValueError("provider flight recorder exceeds its bound")
            self._frozen = True
        return json.loads(_canonical(self._value).decode("utf-8"))
