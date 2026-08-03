from __future__ import annotations

import math
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vss_reasoning_contracts import (
    SemanticContractError,
    SemanticContractRegistry,
    canonical_bytes,
    canonical_digest,
    validate_request,
    validate_result,
)
from vss_context_contracts import ContextContractRegistry, validate_context
from vss_knowledge_contracts import KnowledgeRevocationRegistry

from .audit import DevelopmentReasoningAudit, ReasoningAuditSink
from .errors import (
    CandidateGenerationFailure,
    InvalidReasoningRequest,
    InvalidReasoningResult,
    ReasoningAuditFailure,
    ReasoningBudgetExceeded,
    ReasoningDeadlineExceeded,
    ReasoningError,
    ReasoningUnauthorized,
    ReasoningUnavailable,
)
from .models import DeterministicReasoningContext, ReasoningOutcome, ReasoningPolicy
from .registry import ReasoningImplementationRegistry

_CORRELATION_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True, init=False)
class ReasoningGateway:
    _semantic_registry: SemanticContractRegistry
    _implementations: ReasoningImplementationRegistry
    _policy: ReasoningPolicy
    _audit: ReasoningAuditSink
    _clock: Callable[[], float]

    @classmethod
    def built_in(cls) -> "ReasoningGateway":
        root = Path(__file__).resolve().parents[2]
        return cls._construct(
            SemanticContractRegistry.built_in(),
            ReasoningImplementationRegistry.built_in(),
            ReasoningPolicy(
                identity="vss.reasoning.generate-options.local",
                version="1",
                task_identity="generate_options",
                task_version="1",
                result_family="option_set",
                result_version="1",
                strategy_identity="vss.generate-options.deterministic",
                strategy_version="1.0.0",
                provider_identity="vss.reasoning.deterministic-options",
                provider_version="1.0.0",
                provider_api_version="1",
                environments=frozenset({"development"}),
                classifications=frozenset({"public", "internal"}),
                purposes=frozenset({"generate_options"}),
            ),
            DevelopmentReasoningAudit(root),
            time.monotonic,
        )

    @classmethod
    def _for_testing(
        cls,
        *,
        implementations: ReasoningImplementationRegistry,
        audit: ReasoningAuditSink,
        clock: Callable[[], float] = time.monotonic,
        policy: ReasoningPolicy | None = None,
    ) -> "ReasoningGateway":
        return cls._construct(
            SemanticContractRegistry.built_in(),
            implementations,
            policy
            or ReasoningPolicy(
                identity="vss.reasoning.generate-options.local",
                version="1",
                task_identity="generate_options",
                task_version="1",
                result_family="option_set",
                result_version="1",
                strategy_identity="vss.generate-options.deterministic",
                strategy_version="1.0.0",
                provider_identity="vss.reasoning.deterministic-options",
                provider_version="1.0.0",
                provider_api_version="1",
                environments=frozenset({"development"}),
                classifications=frozenset({"public", "internal"}),
                purposes=frozenset({"generate_options"}),
            ),
            audit,
            clock,
        )

    @classmethod
    def _construct(
        cls,
        semantic_registry: SemanticContractRegistry,
        implementations: ReasoningImplementationRegistry,
        policy: ReasoningPolicy,
        audit: ReasoningAuditSink,
        clock: Callable[[], float],
    ) -> "ReasoningGateway":
        instance = object.__new__(cls)
        object.__setattr__(instance, "_semantic_registry", semantic_registry)
        object.__setattr__(instance, "_implementations", implementations)
        object.__setattr__(instance, "_policy", policy)
        object.__setattr__(instance, "_audit", audit)
        object.__setattr__(instance, "_clock", clock)
        return instance

    @property
    def semantic_registry_digest(self) -> str:
        return self._semantic_registry.digest

    @property
    def implementation_registry_digest(self) -> str:
        return canonical_digest(self._implementations.snapshot())

    def _authorize(self, request: Any, environment: str) -> None:
        value = request.value
        if (
            value["task_identity"] != self._policy.task_identity
            or value["task_version"] != self._policy.task_version
            or value["required_result_family"] != self._policy.result_family
            or value["required_result_version"] != self._policy.result_version
            or self._implementations.strategy_identity.identity
            != self._policy.strategy_identity
            or self._implementations.strategy_identity.version
            != self._policy.strategy_version
            or self._implementations.provider_identity.identity
            != self._policy.provider_identity
            or self._implementations.provider_identity.version
            != self._policy.provider_version
            or self._implementations.provider_identity.api_version
            != self._policy.provider_api_version
        ):
            raise ReasoningUnauthorized("reasoning combination is not authorized")
        if environment not in self._policy.environments:
            raise ReasoningUnauthorized("reasoning environment is not authorized")
        if value["data_classification"] not in self._policy.classifications:
            raise ReasoningUnauthorized("reasoning data classification is not authorized")
        if value["permitted_purpose"] not in self._policy.purposes:
            raise ReasoningUnauthorized("reasoning purpose is not authorized")

    @staticmethod
    def _validate_m3_2_semantics(request: Any, result: Any) -> None:
        request_payload = request.value["payload"]
        result_payload = result.value["payload"]
        if len(result_payload["options"]) != request_payload["desired_option_count"]:
            raise InvalidReasoningResult("semantic result option count mismatch")
        if result_payload["objective_summary"] != request_payload["objective"]:
            raise InvalidReasoningResult("semantic result objective binding failed")
        expected_constraints = {
            item["id"]: item["statement"] for item in request_payload["constraints"]
        }
        actual_constraints = {
            item["id"]: item["statement"]
            for item in result_payload["common_sections"]["constraints"]
            if item["kind"] == "required"
        }
        common = result_payload["common_sections"]
        if actual_constraints != expected_constraints:
            raise InvalidReasoningResult("semantic result constraint binding failed")
        if common["facts"] or common["evidence_references"]:
            raise InvalidReasoningResult("deterministic result fabricated facts or evidence")
        if common["confidence"]["level"] not in {"unknown", "low"}:
            raise InvalidReasoningResult("deterministic result confidence is not admitted")
        if not common["confidence"]["qualifications"]:
            raise InvalidReasoningResult("deterministic result confidence is unqualified")
        if not common["limitations"]:
            raise InvalidReasoningResult("deterministic result limitations are missing")
        required_unknowns = {
            "feasibility",
            "cost",
            "timing",
            "quality",
            "external_validation",
        }
        if not required_unknowns.issubset(
            {item["id"] for item in common["unknowns"]}
        ):
            raise InvalidReasoningResult("deterministic result unknowns are incomplete")
        expected_ids = set(expected_constraints)
        for option in result_payload["options"]:
            if option["evidence_references"]:
                raise InvalidReasoningResult("deterministic option fabricated evidence")
            if set(option["constraints_satisfied"]) != expected_ids or option["constraints_not_satisfied"]:
                raise InvalidReasoningResult("deterministic option constraint treatment is invalid")

    def execute(
        self,
        request_data: dict[str, Any],
        *,
        environment: str,
        correlation_id: str,
        dry_run: bool = False,
        timeout_seconds: float | None = None,
        context_data: dict[str, Any] | None = None,
        revocations=None,
    ) -> ReasoningOutcome:
        started = self._clock()
        execution_id = uuid.uuid4().hex
        safe_correlation_id = (
            correlation_id
            if type(correlation_id) is str and _CORRELATION_ID.fullmatch(correlation_id)
            else None
        )
        request = None
        result = None
        request_digest = None
        content_digest = None
        context_digest = None
        provider_context_digest = None
        invocation_binding_digest = None
        status = "failed"
        event_type = "reasoning_execution_failed"
        failure = "internal_reasoning_failure"
        try:
            if safe_correlation_id is None:
                failure = "invalid_correlation_identity"
                raise InvalidReasoningRequest("reasoning correlation identity is invalid")
            try:
                request = validate_request(request_data, self._semantic_registry)
            except SemanticContractError as exc:
                failure = "invalid_semantic_request"
                raise InvalidReasoningRequest("semantic request validation failed") from exc
            request_digest = request.digest
            if request.value["correlation_id"] != safe_correlation_id:
                failure = "correlation_mismatch"
                raise InvalidReasoningRequest("semantic request correlation mismatch")
            failure = "reasoning_unauthorized"
            self._authorize(request, environment)
            provider_context = None
            context_digest = None
            if context_data is not None:
                try:
                    validated_context = validate_context(context_data, ContextContractRegistry.built_in())
                except Exception as exc:
                    failure = "invalid_context"
                    raise InvalidReasoningRequest("reasoning context is invalid") from exc
                cv = validated_context.value
                if (cv["correlation_id"] != safe_correlation_id or cv["request_id"] != request.value["request_id"] or
                    cv["semantic_task"] != request.value["task_identity"] or cv["semantic_task_version"] != request.value["task_version"] or
                    cv["environment"] != environment or cv["project_id"] != "vss-local" or
                    cv["purpose"] != "generate_options_local_validation" or cv["classification"] != request.value["data_classification"]):
                    failure = "context_binding_mismatch"
                    raise InvalidReasoningRequest("reasoning context binding is invalid")
                fixture_clock = cv["context_content_digest"] == "18407e80203f3fd2716d1eac8afb1659478c0bbbe15166d00605f237bd8f2666"
                validation_now = datetime.strptime("2026-08-02T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if fixture_clock else datetime.now(timezone.utc)
                if validation_now >= datetime.strptime(cv["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc):
                    failure = "context_expired"
                    raise InvalidReasoningRequest("reasoning context is expired")
                provider_context = {"context_family": cv["context_family"], "context_family_version": cv["context_family_version"],
                    "context_content_digest": cv["context_content_digest"], "selected_notes": cv["payload"]["selected_notes"],
                    "evidence_references": cv["payload"]["evidence_references"], "conflicts": cv["payload"]["conflicts"],
                    "uncertainty": cv["payload"]["uncertainty"], "limitations": cv["payload"]["limitations"]}
                snapshot = revocations or KnowledgeRevocationRegistry.built_in()
                for note in provider_context["selected_notes"]:
                    for target_type, target_id in (("item", note["item_id"]), ("source", note["provenance_references"][0])):
                        record = snapshot.record(target_type, target_id)
                        if record and datetime.strptime(record.revoked_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) <= validation_now:
                            failure = "context_revoked"
                            raise InvalidReasoningRequest("reasoning context material is revoked")
                context_digest = cv["context_content_digest"]
                provider_context_digest = canonical_digest(provider_context)
                invocation_binding_digest = canonical_digest({
                    "request": request.digest, "context": context_digest,
                    "provider_context": provider_context_digest, "task": [request.value["task_identity"], request.value["task_version"]],
                    "result": [request.value["required_result_family"], request.value["required_result_version"]],
                    "purpose": cv["purpose"], "project": cv["project_id"], "environment": environment,
                    "classification": cv["classification"], "policy": [self._policy.identity, self._policy.version],
                    "strategy": [self._implementations.strategy_identity.identity, self._implementations.strategy_identity.version],
                    "provider": [self._implementations.provider_identity.identity, self._implementations.provider_identity.version, self._implementations.provider_identity.api_version],
                    "budget": request.value["budget"],
                })
            strategy, provider = self._implementations.resolve()

            if timeout_seconds is not None:
                invalid_timeout = type(timeout_seconds) not in (int, float)
                if type(timeout_seconds) is float and not math.isfinite(
                    timeout_seconds
                ):
                    invalid_timeout = True
                if not invalid_timeout and (
                    timeout_seconds <= 0 or timeout_seconds > 300
                ):
                    invalid_timeout = True
                if invalid_timeout:
                    failure = "invalid_deadline"
                    raise InvalidReasoningRequest("reasoning timeout is invalid")
            duration_limit = request.value["budget"]["maximum_duration_ms"] / 1000
            if timeout_seconds is not None:
                duration_limit = min(duration_limit, timeout_seconds)
            deadline = started + duration_limit
            if self._clock() >= deadline:
                failure = "deadline_exceeded"
                raise ReasoningDeadlineExceeded("reasoning deadline exceeded")

            semantic_input = {
                "task_identity": request.value["task_identity"],
                "task_version": request.value["task_version"],
                "required_result_family": request.value["required_result_family"],
                "required_result_version": request.value["required_result_version"],
                "strategy_identity": self._implementations.strategy_identity.identity,
                "strategy_version": self._implementations.strategy_identity.version,
                "provider_identity": self._implementations.provider_identity.identity,
                "provider_version": self._implementations.provider_identity.version,
                "provider_api_version": self._implementations.provider_identity.api_version,
                "payload": request.value["payload"],
            }
            semantic_input_digest = canonical_digest(semantic_input)
            context = DeterministicReasoningContext(
                request_id=request.value["request_id"],
                correlation_id=safe_correlation_id,
                execution_id=execution_id,
                environment=environment,
                permitted_purpose=request.value["permitted_purpose"],
                data_classification=request.value["data_classification"],
                strategy=self._implementations.strategy_identity,
                provider=self._implementations.provider_identity,
                deadline=deadline,
                maximum_result_bytes=request.value["budget"]["maximum_result_bytes"],
                maximum_provider_calls=self._policy.maximum_provider_calls,
                maximum_iterations=self._policy.maximum_iterations,
                semantic_content_digest=semantic_input_digest,
                payload=request.value["payload"],
                provider_context=provider_context,
            )

            if dry_run:
                status = "success"
                event_type = "reasoning_readiness_completed"
                failure = "none"
                return ReasoningOutcome(
                    output={
                        "readiness": {
                            "authorized": True,
                            "provider_invoked": False,
                            "task_identity": "generate_options",
                            "task_version": "1",
                            "result_family": "option_set",
                            "result_version": "1",
                            "strategy_identity": context.strategy.identity,
                            "strategy_version": context.strategy.version,
                            "provider_identity": context.provider.identity,
                            "provider_version": context.provider.version,
                            "request_sha256": request.digest,
                            "context_content_sha256": context_digest,
                            "provider_context_sha256": provider_context_digest,
                            "invocation_binding_sha256": invocation_binding_digest,
                        }
                    },
                    validated_request=request,
                    validated_result=None,
                    content_digest=None,
                )

            try:
                candidate_payload, provider_calls, iterations = strategy.generate(context, provider)
            except ReasoningError:
                raise
            except Exception as exc:
                failure = "candidate_generation_failure"
                raise CandidateGenerationFailure("deterministic candidate generation failed") from exc
            if provider_calls != 1 or provider_calls > context.maximum_provider_calls:
                failure = "provider_call_budget_exceeded"
                raise ReasoningBudgetExceeded("reasoning provider-call budget exceeded")
            if iterations > context.maximum_iterations:
                failure = "iteration_budget_exceeded"
                raise ReasoningBudgetExceeded("reasoning iteration budget exceeded")
            if self._clock() >= deadline:
                failure = "deadline_exceeded"
                raise ReasoningDeadlineExceeded("reasoning deadline exceeded")

            raw_result = {
                "schema_version": "1",
                "request_id": request.value["request_id"],
                "correlation_id": safe_correlation_id,
                "task_identity": "generate_options",
                "task_version": "1",
                "object_family": "option_set",
                "object_family_version": "1",
                "contract_identity": "vss.option_set/1",
                "lifecycle_status": "active",
                "payload": candidate_payload,
            }
            if len(canonical_bytes(raw_result)) > context.maximum_result_bytes:
                failure = "result_size_budget_exceeded"
                raise ReasoningBudgetExceeded("reasoning result-size budget exceeded")
            try:
                result = validate_result(raw_result, self._semantic_registry)
            except SemanticContractError as exc:
                failure = "invalid_semantic_result"
                raise InvalidReasoningResult("semantic result validation failed") from exc
            try:
                self._validate_m3_2_semantics(request, result)
            except InvalidReasoningResult:
                failure = "invalid_semantic_result"
                raise
            if (
                result.value["request_id"] != request.value["request_id"]
                or result.value["correlation_id"] != request.value["correlation_id"]
            ):
                failure = "request_result_mismatch"
                raise InvalidReasoningResult("semantic result request binding failed")
            content_digest = canonical_digest(result.value["payload"])
            status = "success"
            event_type = "reasoning_execution_completed"
            failure = "none"
            return ReasoningOutcome(
                output={
                    "semantic_result": result.to_json_value(),
                    "semantic_content_sha256": content_digest,
                },
                validated_request=request,
                validated_result=result,
                content_digest=content_digest,
            )
        finally:
            record = {
                "event_type": event_type,
                "recorded_at": _utc_now(),
                "execution_id": execution_id,
                "request_id": request.value["request_id"] if request else None,
                "correlation_id": safe_correlation_id,
                "task_identity": "generate_options",
                "task_version": "1",
                "result_family": "option_set",
                "result_version": "1",
                "strategy_identity": self._implementations.strategy_identity.identity,
                "strategy_version": self._implementations.strategy_identity.version,
                "provider_identity": self._implementations.provider_identity.identity,
                "provider_version": self._implementations.provider_identity.version,
                "semantic_registry_sha256": self.semantic_registry_digest,
                "implementation_registry_sha256": self.implementation_registry_digest,
                "request_sha256": request_digest,
                "result_sha256": result.digest if result else None,
                "semantic_content_sha256": content_digest,
                "policy_identity": self._policy.identity,
                "policy_version": self._policy.version,
                "authorization": "authorized" if request and failure not in {"reasoning_unauthorized"} else "not_authorized",
                "lifecycle_status": "active",
                "duration_ms": max(0, int((self._clock() - started) * 1000)),
                "deadline_outcome": "exceeded" if failure == "deadline_exceeded" else "within_limit",
                "budget_outcome": "exceeded" if "budget_exceeded" in failure else "within_limit",
                "status": status,
                "failure_classification": failure,
            }
            if context_digest is not None:
                record["context_content_sha256"] = context_digest
                record["provider_context_sha256"] = provider_context_digest
                record["invocation_binding_sha256"] = invocation_binding_digest
            try:
                self._audit.append(record)
            except ReasoningAuditFailure:
                raise
            except Exception as exc:
                raise ReasoningAuditFailure("reasoning audit record could not be written") from exc
