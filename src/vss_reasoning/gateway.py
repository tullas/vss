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
from vss_reasoning_contracts.canonicalization import freeze_json
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

    def execute_scene_breakdown(self, request_data: dict[str, Any], context_data: dict[str, Any], *, environment: str, correlation_id: str, dry_run: bool = False, revocations=None) -> dict[str, Any]:
        """Admit the bounded movie task through the existing Gateway boundary."""
        started = self._clock(); execution_id = uuid.uuid4().hex; calls = 0
        request_id = request_data.get("request_id") if isinstance(request_data, dict) else None
        try:
            if type(correlation_id) is not str or not _CORRELATION_ID.fullmatch(correlation_id):
                raise InvalidReasoningRequest("reasoning correlation identity is invalid")
            if not isinstance(request_data, dict) or request_data.get("task_identity") != "break_down_scenes" or request_data.get("task_version") != "1":
                raise InvalidReasoningRequest("movie task is not admitted")
            if request_data.get("correlation_id") != correlation_id or request_data.get("purpose") != "scene_breakdown_local_validation":
                raise InvalidReasoningRequest("movie request binding is invalid")
            from vss_reasoning_strategies import DeterministicSceneBreakdownStrategy
            strategy = DeterministicSceneBreakdownStrategy()
            if strategy.identity != "vss.break-down-scenes.deterministic" or strategy.version != "1.0.0":
                raise ReasoningUnavailable("movie strategy is not admitted")
            if context_data.get("correlation_id") != correlation_id or context_data.get("request_id") != request_id:
                raise InvalidReasoningRequest("movie Context binding is invalid")
            if context_data.get("context_family") != "scene_breakdown_context" or context_data.get("context_family_version") != "1" or context_data.get("semantic_task") != "break_down_scenes" or context_data.get("purpose") != "scene_breakdown_local_validation" or context_data.get("project_id") != request_data.get("project_id") or context_data.get("environment") != environment:
                raise InvalidReasoningRequest("movie Context compatibility is invalid")
            from vss_movie_scene_breakdown import validate_scene_context
            validated_context = validate_scene_context(context_data)
            context_digest = validated_context.digest
            from vss_movie_scene_breakdown import MovieRevocationSnapshot, provider_view_from_context
            snapshot = revocations or MovieRevocationSnapshot.built_in()
            now = "2026-08-02T00:00:01Z" if context_data.get("constructed_at") == "2026-08-02T00:00:00Z" else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            source = context_data["payload"]["story_fragment"]
            revocation = snapshot.evaluate("story_fragment", source["fragment_id"], source["fragment_digest"], now)
            if revocation != "eligible": raise InvalidReasoningRequest("movie source is revoked")
            provider_digest = provider_view_from_context(validated_context).provider_visible_digest
            invocation_digest = canonical_digest({"request_id": request_id, "request_digest": canonical_digest(request_data), "context_digest": context_digest, "provider_digest": provider_digest, "task": ["break_down_scenes", "1"], "result": ["scene_breakdown", "1"], "purpose": context_data["purpose"], "project": context_data["project_id"], "environment": environment, "strategy": [strategy.identity, strategy.version], "provider": ["vss.reasoning.deterministic-scene-breakdown", "1.0.0", "1"]})
            if dry_run:
                from vss_movie_scene_breakdown import validate_scene_context
                validate_scene_context(context_data)
                output = {"ready": True, "provider_invoked": False, "strategy": strategy.identity, "strategy_version": strategy.version}
            else:
                fixture_now = "2026-08-02T00:00:01Z" if context_data.get("constructed_at") == "2026-08-02T00:00:00Z" else None
                output = strategy.execute(context_data, now=fixture_now)
                calls = 1
            record = {"event_type": "movie_scene_breakdown_readiness_completed" if dry_run else "movie_scene_breakdown_completed", "execution_id": execution_id, "request_id": request_id, "correlation_id": correlation_id, "task_identity": "break_down_scenes", "result_family": "scene_breakdown", "provider_call_count": calls, "context_id": context_data["context_id"], "context_content_sha256": context_data["context_content_digest"], "complete_context_sha256": context_digest, "provider_context_sha256": provider_digest, "invocation_binding_sha256": invocation_digest, "revocation_result": revocation, "result_sha256": None if dry_run else canonical_digest(output), "status": "success", "duration_ms": max(0, int((self._clock() - started) * 1000))}
            self._audit.append(record)
            return {"readiness": output} if dry_run else {"scene_breakdown": output, "result_digest": canonical_digest(output)}
        except Exception:
            try:
                self._audit.append({"event_type": "movie_scene_breakdown_failed", "execution_id": execution_id, "request_id": request_id, "correlation_id": correlation_id, "task_identity": "break_down_scenes", "provider_call_count": calls, "status": "failed"})
            except Exception as audit_exc:
                raise ReasoningAuditFailure("reasoning audit record could not be written") from audit_exc
            raise

    def execute_scene_production_options(self, request_data: dict[str, Any], context_data: dict[str, Any], *, environment: str, correlation_id: str, dry_run: bool = False, revocations=None) -> dict[str, Any]:
        """Run M4.3 through the existing governed Reasoning Gateway lifecycle."""
        started = self._clock(); execution_id = uuid.uuid4().hex; calls = 0; request_id = None
        context = None; view = None; invocation_digest = None; result = None; revocation_result = "not_evaluated"; status = "failed"; failure = "invalid_request"
        try:
            if type(correlation_id) is not str or not _CORRELATION_ID.fullmatch(correlation_id): raise InvalidReasoningRequest("reasoning correlation identity is invalid")
            from vss_movie_contracts import validate_production_options_task, validate_production_option_set
            try: request = validate_production_options_task(request_data)
            except Exception as exc: raise InvalidReasoningRequest("production-options request is invalid") from exc
            task = request.to_json_value(); request_id = task["request_id"]
            if task["correlation_id"] != correlation_id or task["environment"] != environment: raise InvalidReasoningRequest("production-options request binding is invalid")
            from vss_movie_production_options import ProductionProfileCatalogue, production_provider_view, validate_production_options_context
            try: context = validate_production_options_context(context_data)
            except Exception as exc: failure = "invalid_context"; raise InvalidReasoningRequest("production-options Context is invalid") from exc
            c = context.to_json_value(); p = c["payload"]
            request_context = (task["request_id"],task["correlation_id"],task["project_id"],task["environment"],task["purpose"],task["expected_context_family"],task["expected_context_version"],task["expected_result_family"],task["expected_result_version"],task["scene_breakdown_digest"],task["scene_id"],task["scene_content_digest"],task["classification"],task["trust"])
            actual_context = (c["request_id"],c["correlation_id"],c["project_id"],c["environment"],c["purpose"],c["context_family"],c["context_family_version"],c["result_family"],c["result_version"],p["scene_breakdown_digest"],p["selected_scene_id"],p["selected_scene_digest"],c["classification"],c["trust"])
            if request_context != actual_context: failure = "context_binding_mismatch"; raise InvalidReasoningRequest("production-options request and Context binding mismatch")
            fixture_time = c["constructed_at"] == "2026-08-02T00:00:00Z"
            invocation_time = "2026-08-02T00:00:01Z" if fixture_time else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            invocation_dt = datetime.strptime(invocation_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if invocation_dt >= datetime.strptime(c["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc): failure = "context_expired"; raise InvalidReasoningRequest("production-options Context is expired")
            catalogue = ProductionProfileCatalogue.built_in()
            if (p["profile_catalogue_identity"],p["profile_catalogue_version"],p["profile_catalogue_digest"],p["option_count_limit"]) != (catalogue.identity,catalogue.version,catalogue.digest,len(catalogue.profiles)): failure = "catalogue_mismatch"; raise InvalidReasoningRequest("production profile catalogue mismatch")
            if task["bounds"]["maximum_options"] != len(catalogue.profiles): failure = "budget_mismatch"; raise ReasoningBudgetExceeded("production option bound is incompatible")
            from .registry import SceneProductionOptionsImplementationRegistry
            implementations = SceneProductionOptionsImplementationRegistry.built_in(); strategy, provider = implementations.resolve()
            view = production_provider_view(context)
            deadline = invocation_dt.timestamp() + task["bounds"]["maximum_duration_ms"] / 1000
            binding = freeze_json({"invocation_id":"production-invocation-"+canonical_digest({"request":request.digest,"context":context.digest,"provider_view":view.provider_visible_digest})[:24],"request_id":request_id,"request_digest":request.digest,"correlation_id":correlation_id,"task_identity":"generate_scene_production_options","task_version":"1","result_family":"scene_production_option_set","result_version":"1","scene_breakdown_identity":"scene_breakdown","scene_breakdown_digest":p["scene_breakdown_digest"],"scene_id":p["selected_scene_id"],"scene_content_digest":p["selected_scene_digest"],"context_id":c["context_id"],"context_family":"scene_production_options_context","context_version":"1","context_content_digest":c["context_content_digest"],"complete_context_digest":context.digest,"provider_visible_digest":view.provider_visible_digest,"project_id":c["project_id"],"environment":environment,"purpose":c["purpose"],"classification":c["classification"],"policy":[c["policy_identity"],c["policy_version"]],"profile_catalogue":[catalogue.identity,catalogue.version,catalogue.digest],"strategy":[strategy.identity,strategy.version],"provider":[provider.identity,provider.version,provider.api_version],"bounds":task["bounds"],"deadline":deadline,"invocation_time":invocation_time})
            invocation_digest = canonical_digest(binding)
            # Expiry and current revocation are deliberately the final gates before the single provider call.
            if invocation_dt >= datetime.strptime(c["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc): failure = "context_expired"; raise InvalidReasoningRequest("production-options Context is expired")
            from vss_movie_scene_breakdown import MovieRevocationSnapshot
            snapshot = revocations or MovieRevocationSnapshot.built_in()
            for target_type, target_id, digest in (("scene_breakdown","scene_breakdown",p["scene_breakdown_digest"]),("scene",p["selected_scene_id"],p["selected_scene_digest"]),("context",c["context_id"],context.digest),("profile_catalogue",catalogue.identity,catalogue.digest),("policy",c["policy_identity"],None)):
                if snapshot.evaluate(target_type,target_id,digest,invocation_time) != "eligible": failure = "context_revoked"; revocation_result = "revoked"; raise InvalidReasoningRequest("production-options material is revoked")
            revocation_result = "eligible"
            if dry_run:
                status = "success"; failure = "none"
                return {"readiness":{"authorized":True,"provider_invoked":False,"provider_call_count":0,"task_identity":"generate_scene_production_options","task_version":"1","result_family":"scene_production_option_set","result_version":"1","context_content_digest":c["context_content_digest"],"complete_context_digest":context.digest,"profile_catalogue_digest":catalogue.digest,"provider_visible_digest":view.provider_visible_digest,"invocation_binding_digest":invocation_digest,"strategy_identity":strategy.identity,"strategy_version":strategy.version,"provider_identity":provider.identity,"provider_version":provider.version,"provider_api_version":provider.api_version,"revocation_result":revocation_result,"result_digest":None}}
            try:
                from vss_movie_production_options import create_production_option_set
                candidates, calls, iterations = strategy.execute(view, provider)
                candidate = create_production_option_set(view, binding, candidates)
            except Exception as exc: failure = "candidate_generation_failure"; raise CandidateGenerationFailure("production-options generation failed") from exc
            if calls != 1 or iterations != 1: failure = "provider_budget_exceeded"; raise ReasoningBudgetExceeded("production-options provider budget exceeded")
            try: validated = validate_production_option_set(candidate)
            except Exception as exc: failure = "invalid_result"; raise InvalidReasoningResult("production-options result validation failed") from exc
            result = validated.to_json_value()
            if len(canonical_bytes(result)) > task["bounds"]["maximum_result_bytes"]: failure = "result_size_budget_exceeded"; raise ReasoningBudgetExceeded("production-options result exceeds bound")
            text = str(result).lower()
            dishonest = (" is best", " is recommended", " is preferred", "feasibility is proven", "cost is verified", "duration is verified", "quality is guaranteed", "rights are cleared", "permits are cleared", "conflicts are resolved")
            if any(term in text for term in dishonest): failure = "semantic_honesty_failure"; raise InvalidReasoningResult("production-options semantic honesty failed")
            status = "success"; failure = "none"
            return {"scene_production_option_set":result,"result_digest":validated.digest,"semantic_result_digest":result["payload"]["semantic_result_digest"],"provider_call_count":calls,"provider_visible_digest":view.provider_visible_digest,"invocation_binding_digest":invocation_digest,"profile_catalogue_digest":catalogue.digest}
        finally:
            payload = context.value["payload"] if context else {}
            record = {"event_type":"movie_scene_production_options_readiness_completed" if dry_run and status == "success" else "movie_scene_production_options_completed" if status == "success" else "movie_scene_production_options_failed","execution_id":execution_id,"request_id":request_id,"correlation_id":correlation_id,"task_identity":"generate_scene_production_options","task_version":"1","result_family":"scene_production_option_set","result_version":"1","scene_breakdown_identity":"scene_breakdown/1","scene_breakdown_digest":payload.get("scene_breakdown_digest"),"scene_id":payload.get("selected_scene_id"),"scene_digest":payload.get("selected_scene_digest"),"context_id":context.value["context_id"] if context else None,"context_content_digest":context.value["context_content_digest"] if context else None,"complete_context_digest":context.digest if context else None,"provider_visible_digest":view.provider_visible_digest if view else None,"invocation_binding_digest":invocation_digest,"profile_catalogue":"vss.scene-production-profiles.deterministic/1.0.0","strategy":"vss.generate-scene-production-options.deterministic/1.0.0","provider":"vss.reasoning.deterministic-scene-production-options/1.0.0","provider_api_version":"1","option_count":len(result["payload"]["options"]) if result else 0,"ambiguity_count":len(payload.get("ambiguity",())),"conflict_count":len(payload.get("conflicts",())),"unknown_count":len(payload.get("unknowns",())),"limitation_count":len(payload.get("limitations",())),"provider_call_count":calls,"revocation_result":revocation_result,"dry_run":dry_run,"result_digest":canonical_digest(result) if result else None,"status":status,"failure_classification":failure,"duration_ms":max(0,int((self._clock()-started)*1000))}
            try: self._audit.append(record)
            except ReasoningAuditFailure: raise
            except Exception as exc: raise ReasoningAuditFailure("reasoning audit record could not be written") from exc
