"""Provider-neutral, deterministic shot production lifecycle.

This module is deliberately an offline rehearsal boundary.  It models the
state and identity rules that must hold before an external adapter is allowed
to run; it does not contain credentials, transport, retry, or spend logic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .foundation import FailureClass, FlightRecorder


class LifecycleState(str, Enum):
    PLANNED = "planned"
    REHEARSED = "rehearsed"
    AUTHORIZED = "authorized"
    EXECUTION_RESERVED = "execution_reserved"
    PROVIDER_SUBMISSION_ATTEMPTED = "provider_submission_attempted"
    PROVIDER_ACCEPTED = "provider_accepted"
    PROVIDER_PROCESSING = "provider_processing"
    PROVIDER_TERMINAL = "provider_terminal"
    ARTIFACT_RECOVERED = "artifact_recovered"
    TECHNICALLY_ADMITTED = "technically_admitted"
    CREATIVELY_REVIEWED = "creatively_reviewed"


class LifecycleFailure(str, Enum):
    CREDENTIAL_READINESS = "credential_readiness"
    PRE_PROVIDER = "pre_provider"
    POLLING = "polling"
    TERMINAL_PROVIDER = "terminal_provider"
    MALFORMED_TERMINAL = "malformed_terminal"
    MEDIA_ADMISSION = "media_admission"
    DUPLICATE_EXECUTION = "duplicate_execution"
    REQUEST_IDENTITY = "request_identity"
    EXECUTION_NAMESPACE = "execution_namespace"


@dataclass(frozen=True, slots=True)
class ApprovedShotPackage:
    """Minimal shot input consumed by the generic rehearsal."""

    shot_id: str
    scene_id: str
    prompt: str
    request_digest: str
    execution_namespace: str

    @classmethod
    def build(cls, shot_id: str, scene_id: str, prompt: str) -> "ApprovedShotPackage":
        material = {"scene_id": scene_id, "shot_id": shot_id, "prompt": prompt}
        digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(shot_id, scene_id, prompt, digest, f"film1/{scene_id}/{shot_id}")

    @classmethod
    def from_moving_shot_request(cls, request: Mapping[str, Any]) -> "ApprovedShotPackage":
        """Bind the lifecycle rehearsal to an admitted moving-shot request."""
        if not isinstance(request, Mapping):
            raise ValueError("moving-shot request is invalid")
        scope = request.get("scope")
        if not isinstance(scope, Mapping):
            raise ValueError("moving-shot request scope is invalid")
        shot_id, scene_id, production_id = scope.get("shot_id"), scope.get("scene_id"), scope.get("production_id")
        digest, prompt = request.get("request_sha256"), request.get("prompt")
        if not all(isinstance(value, str) and value for value in (shot_id, scene_id, production_id, digest, prompt)):
            raise ValueError("moving-shot request identity is incomplete")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("moving-shot request digest is invalid")
        return cls(shot_id, scene_id, prompt, digest, f"{production_id}/{shot_id}")


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    state: LifecycleState
    states: tuple[str, ...]
    provider_call_count: int
    operation_name: str | None
    request_digest: str
    execution_namespace: str
    failure: str | None
    recovery_used_same_operation: bool
    duplicate_submission_prevented: bool
    flight_recorder: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {
            "state": self.state.value, "states": list(self.states),
            "provider_call_count": self.provider_call_count,
            "operation_name": self.operation_name, "request_digest": self.request_digest,
            "execution_namespace": self.execution_namespace, "failure": self.failure,
            "recovery_used_same_operation": self.recovery_used_same_operation,
            "duplicate_submission_prevented": self.duplicate_submission_prevented,
            "flight_recorder": self.flight_recorder,
        }


class OfflineProductionLifecycle:
    """Runs the approved-shot lifecycle without any external side effect."""

    authority_by_transition = {
        "planned->rehearsed": "development-only",
        "rehearsed->authorized": "human approval",
        "authorized->execution_reserved": "Runtime reservation",
        "execution_reserved->provider_submission_attempted": "Runtime transport",
        "provider_submission_attempted->provider_accepted": "provider evidence",
        "provider_accepted->provider_processing": "provider evidence",
        "provider_processing->provider_terminal": "provider evidence",
        "provider_terminal->artifact_recovered": "Runtime recovery",
        "artifact_recovered->technically_admitted": "media admission",
        "technically_admitted->creatively_reviewed": "human review",
    }

    def run(self, package: ApprovedShotPackage, *, failure: LifecycleFailure | None = None,
            supplied_request_digest: str | None = None, supplied_namespace: str | None = None) -> LifecycleResult:
        expected_digest = package.request_digest
        namespace = supplied_namespace or package.execution_namespace
        recorder = FlightRecorder({"shot_id": package.shot_id, "scene_id": package.scene_id,
                                   "request_digest": expected_digest, "execution_namespace": namespace})
        states = [LifecycleState.PLANNED, LifecycleState.REHEARSED]
        recorder.record("planned", status="accepted")
        recorder.record("rehearsed", status="accepted")

        def result(state: LifecycleState, calls: int = 0, operation: str | None = None,
                   reason: str | None = None, recovered: bool = False, duplicate: bool = False) -> LifecycleResult:
            recorder.record(state.value, status="failed" if reason else "accepted",
                            failure_class=FailureClass.REQUEST_CONTRACT if reason in {LifecycleFailure.REQUEST_IDENTITY.value, LifecycleFailure.EXECUTION_NAMESPACE.value} else None)
            return LifecycleResult(state, tuple(item.value for item in states), calls, operation, expected_digest,
                                   namespace, reason, recovered, duplicate, recorder.freeze())

        if supplied_request_digest is not None and supplied_request_digest != expected_digest:
            return result(LifecycleState.REHEARSED, reason=LifecycleFailure.REQUEST_IDENTITY.value)
        if supplied_namespace is not None and supplied_namespace != package.execution_namespace:
            return result(LifecycleState.REHEARSED, reason=LifecycleFailure.EXECUTION_NAMESPACE.value)
        states.append(LifecycleState.AUTHORIZED)
        states.append(LifecycleState.EXECUTION_RESERVED)
        recorder.record("authorized", status="accepted")
        recorder.record("execution_reserved", status="accepted")
        if failure == LifecycleFailure.CREDENTIAL_READINESS:
            return result(LifecycleState.EXECUTION_RESERVED, reason=LifecycleFailure.CREDENTIAL_READINESS.value)
        if failure == LifecycleFailure.DUPLICATE_EXECUTION:
            return result(LifecycleState.EXECUTION_RESERVED, reason=LifecycleFailure.DUPLICATE_EXECUTION.value, duplicate=True)

        states.append(LifecycleState.PROVIDER_SUBMISSION_ATTEMPTED)
        recorder.record("provider_submission_attempted", status="accepted")
        if failure == LifecycleFailure.PRE_PROVIDER:
            return result(LifecycleState.PROVIDER_SUBMISSION_ATTEMPTED, reason=LifecycleFailure.PRE_PROVIDER.value)
        operation = f"offline/{namespace}/operations/{expected_digest[:16]}"
        states.append(LifecycleState.PROVIDER_ACCEPTED)
        states.append(LifecycleState.PROVIDER_PROCESSING)
        recorder.record("provider_accepted", status="accepted", metadata={"operation": operation})
        recorder.record("provider_processing", status="accepted")
        if failure == LifecycleFailure.POLLING:
            return result(LifecycleState.PROVIDER_PROCESSING, calls=1, operation=operation, reason=LifecycleFailure.POLLING.value)
        states.append(LifecycleState.PROVIDER_TERMINAL)
        recorder.record("provider_terminal", status="failed" if failure == LifecycleFailure.TERMINAL_PROVIDER else "accepted")
        if failure == LifecycleFailure.TERMINAL_PROVIDER:
            return result(LifecycleState.PROVIDER_TERMINAL, calls=1, operation=operation, reason=LifecycleFailure.TERMINAL_PROVIDER.value)
        states.append(LifecycleState.ARTIFACT_RECOVERED)
        recorder.record("artifact_recovered", status="accepted", metadata={"operation": operation})
        if failure == LifecycleFailure.MALFORMED_TERMINAL:
            return result(LifecycleState.PROVIDER_TERMINAL, calls=1, operation=operation, reason=LifecycleFailure.MALFORMED_TERMINAL.value, recovered=True)
        if failure == LifecycleFailure.MEDIA_ADMISSION:
            return result(LifecycleState.ARTIFACT_RECOVERED, calls=1, operation=operation, reason=LifecycleFailure.MEDIA_ADMISSION.value, recovered=True)
        states.extend((LifecycleState.TECHNICALLY_ADMITTED, LifecycleState.CREATIVELY_REVIEWED))
        recorder.record("technically_admitted", status="accepted", metadata={"media": "inline_video"})
        recorder.record("creatively_reviewed", status="accepted", metadata={"disposition": "USE"})
        return result(LifecycleState.CREATIVELY_REVIEWED, calls=1, operation=operation, recovered=True, duplicate=True)

    def recover_accepted(self, package: ApprovedShotPackage, operation_name: str) -> LifecycleResult:
        """Recover an already accepted operation without submitting it again."""
        expected = f"offline/{package.execution_namespace}/operations/{package.request_digest[:16]}"
        recorder = FlightRecorder({"shot_id": package.shot_id, "scene_id": package.scene_id,
                                   "request_digest": package.request_digest,
                                   "execution_namespace": package.execution_namespace})
        states = [state for state in LifecycleState]
        for state in states[:7]:
            recorder.record(state.value, status="recovered" if state in {LifecycleState.PROVIDER_ACCEPTED, LifecycleState.PROVIDER_PROCESSING} else "evidenced")
        if operation_name != expected:
            recorder.record("recovery", status="failed", failure_class=FailureClass.REQUEST_CONTRACT)
            return LifecycleResult(LifecycleState.PROVIDER_PROCESSING, tuple(state.value for state in states[:7]), 0,
                                   operation_name, package.request_digest, package.execution_namespace,
                                   LifecycleFailure.REQUEST_IDENTITY.value, False, True, recorder.freeze())
        for state in states[7:]:
            recorder.record(state.value, status="recovered" if state == LifecycleState.ARTIFACT_RECOVERED else "accepted")
        return LifecycleResult(LifecycleState.CREATIVELY_REVIEWED, tuple(state.value for state in states), 0,
                               operation_name, package.request_digest, package.execution_namespace, None, True, True,
                               recorder.freeze())


def kpis(results: list[LifecycleResult], *, source_changes: int = 0, handoffs: int = 0, prs: int = 0,
         wall_clock_seconds: int = 0, provider_cost_usd: str = "0.000000") -> dict[str, Any]:
    """Extract lightweight metrics from durable lifecycle evidence."""
    return {"schema_version": "1", "contract_identity": "vss.production-development-kpis", "shot_count": len(results),
            "source_code_changes_per_shot": source_changes, "human_interventions_per_shot": sum(r.failure is not None for r in results),
            "codex_manual_handoffs_per_shot": handoffs, "prs_needed_to_unblock": prs,
            "pre_provider_failures": sum(r.provider_call_count == 0 and r.failure is not None for r in results),
            "accepted_provider_submissions": sum(r.provider_call_count == 1 and "provider_accepted" in r.states for r in results),
            "recovery_events": sum(r.recovery_used_same_operation for r in results), "provider_cost_usd": provider_cost_usd,
            "approved_shot_to_reviewable_video_wall_clock_seconds": wall_clock_seconds}
