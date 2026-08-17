from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from vss_movie_contracts import (
    MovieContractRegistry,
    ValidatedMovieArtifact,
    validate_shot_cinematography_admitted_knowledge,
    validate_shot_cinematography_knowledge_admission,
    validate_shot_cinematography_knowledge_lifecycle_event,
    validate_shot_cinematography_lesson_candidate_set,
    validate_shot_cinematography_pattern_set,
)
from vss_movie_cinematic_observation import validate_shot_cinematography_context
from vss_movie_cinematic_lessons import expected_lesson_candidate_payload
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json

KNOWLEDGE_DOMAIN = "shot_cinematography"
KNOWLEDGE_PURPOSE = "shot_cinematography_local_knowledge"
ADMISSION_POLICY_IDENTITY = "vss.shot-cinematography.knowledge-admission"
ADMISSION_POLICY_VERSION = "1.0.0"
LIMITATIONS = (
    "exact_project_scope", "exact_source_context", "local_manual_or_synthetic_lineage",
    "human_admission_required", "no_causal_interpretation", "no_evaluative_interpretation",
    "no_recommendation", "not_universal_truth", "not_runtime_authority",
)
_PROVENANCE = {
    ("manual_observation", "manual_declaration"),
    ("synthetic_test_observation", "synthetic_fixture"),
}


def _timestamp(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("knowledge timestamp is invalid") from exc


def _source_binding(candidate: dict[str, Any]) -> dict[str, Any]:
    return {key: candidate[key] for key in (
        "candidate_id", "candidate_digest", "candidate_type", "source_pattern_id",
        "source_pattern_digest", "supporting_evidence_digest", "pattern_set_digest",
        "pattern_set_complete_digest", "context_id", "context_content_digest",
        "complete_context_digest",
    )}


def _decision_material(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "decision_content_digest"}


def _knowledge_content_material(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in (
        "knowledge_type", "project_id", "domain", "purpose", "classification",
        "source_candidate", "proposition", "scope", "limitations", "lifecycle_status",
    )}


def _complete_material(value: dict[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material["complete_knowledge_sha256"] = "0" * 64
    return material


def _validate_source(candidate_set: Any, *, lesson_task: Any, pattern_set: Any,
                     pattern_task: Any, context: Any,
                     pattern_invocation_binding_digest: str,
                     candidate_invocation_binding_digest: str,
                     candidate_id: str) -> tuple[ValidatedMovieArtifact, dict[str, Any], Any]:
    if not all(isinstance(item, ValidatedMovieArtifact) for item in (candidate_set, pattern_set, pattern_task)) or not all(hasattr(context, attr) for attr in ("value", "digest", "to_json_value")):
        raise ValueError("knowledge admission requires validated upstream artifacts")
    if candidate_set.value.get("result_family") != "shot_cinematography_lesson_candidate_set":
        raise ValueError("knowledge admission requires a validated Lesson Candidate Set")
    pattern_rebound = validate_shot_cinematography_pattern_set(
        pattern_set.to_json_value(), task=pattern_task, context=context,
        invocation_binding_digest=pattern_invocation_binding_digest,
    )
    if pattern_rebound.digest != pattern_set.digest:
        raise ValueError("Pattern Set substitution rejected")
    rebound = validate_shot_cinematography_lesson_candidate_set(
        candidate_set.to_json_value(), task=lesson_task, pattern_set=pattern_set,
        invocation_binding_digest=candidate_invocation_binding_digest,
    )
    if rebound.digest != candidate_set.digest:
        raise ValueError("Lesson Candidate Set substitution rejected")
    context_rebound = validate_shot_cinematography_context(context.to_json_value())
    if context_rebound.digest != context.digest:
        raise ValueError("Context substitution rejected")
    expected = expected_lesson_candidate_payload(pattern_set)
    candidates = [item for item in expected["candidates"] if item["candidate_id"] == candidate_id]
    if len(candidates) != 1:
        raise ValueError("candidate identity is unknown or duplicated")
    candidate = candidates[0]
    if thaw_json(rebound.value["payload"]) != expected:
        raise ValueError("Lesson Candidate lineage is not exact")
    if any((item["provenance"]["kind"], item["provenance"]["method_identity"]) not in _PROVENANCE for item in context.value["payload"]["observations"]):
        raise ValueError("only local manual or synthetic provenance is admitted")
    if candidate["scope"] != "exact_source_context" or "not_admitted_knowledge" not in candidate["limitations"]:
        raise ValueError("Lesson Candidate scope or limitations are not admitted")
    return rebound, candidate, context_rebound


@dataclass(frozen=True, slots=True)
class ShotCinematographyKnowledgeAdmission:
    decision: ValidatedMovieArtifact
    knowledge: ValidatedMovieArtifact


def create_admission_decision(*, candidate: dict[str, Any], actor_identity: str,
                              decision_id: str, decision_at: str,
                              project_id: str, classification: str) -> ValidatedMovieArtifact:
    if not isinstance(candidate, Mapping):
        raise ValueError("admission candidate must be structured data")
    candidate = thaw_json(candidate)
    source = _source_binding(candidate)
    value = {
        "schema_version": "1", "contract_identity": "shot_cinematography_knowledge_admission",
        "contract_version": "1", "decision_id": decision_id, "decision": "admit",
        "actor_kind": "human", "actor_identity": actor_identity, "project_id": project_id,
        "domain": KNOWLEDGE_DOMAIN, "purpose": KNOWLEDGE_PURPOSE, "classification": classification,
        "policy_identity": ADMISSION_POLICY_IDENTITY, "policy_version": ADMISSION_POLICY_VERSION,
        "decision_at": decision_at, "source_candidate": source, "decision_content_digest": "0" * 64,
    }
    value["decision_content_digest"] = canonical_digest(_decision_material(value))
    return validate_shot_cinematography_knowledge_admission(value)


def admit_lesson_candidate(candidate_set: Any, *, lesson_task: Any, pattern_set: Any,
                           pattern_task: Any, context: Any,
                           pattern_invocation_binding_digest: str,
                           candidate_invocation_binding_digest: str,
                           admission_decision: ValidatedMovieArtifact | dict[str, Any],
                           effective_until: str, retention_until: str,
                           prior_admissions: Iterable[Any] = ()) -> ShotCinematographyKnowledgeAdmission:
    _, candidate, context_rebound = _validate_source(
        candidate_set, lesson_task=lesson_task, pattern_set=pattern_set, pattern_task=pattern_task,
        context=context, pattern_invocation_binding_digest=pattern_invocation_binding_digest,
        candidate_invocation_binding_digest=candidate_invocation_binding_digest,
        candidate_id=(admission_decision.value["source_candidate"]["candidate_id"] if isinstance(admission_decision, ValidatedMovieArtifact) else admission_decision.get("source_candidate", {}).get("candidate_id", "")),
    )
    decision = admission_decision if isinstance(admission_decision, ValidatedMovieArtifact) else validate_shot_cinematography_knowledge_admission(admission_decision)
    decision_value = decision.value
    if decision_value["source_candidate"] != _source_binding(candidate):
        raise ValueError("admission decision source substitution rejected")
    if decision_value["project_id"] != context_rebound.value["project_id"] or decision_value["classification"] != context_rebound.value["classification"]:
        raise ValueError("admission decision scope mismatch")
    for previous in prior_admissions:
        previous_artifact = validate_shot_cinematography_admitted_knowledge(
            previous.to_json_value() if isinstance(previous, ValidatedMovieArtifact) else previous
        )
        previous_value = previous_artifact.value
        if previous_value.get("source_candidate", {}).get("candidate_id") == candidate["candidate_id"] and previous_value.get("policy_identity") == ADMISSION_POLICY_IDENTITY:
            raise ValueError("duplicate admission for candidate and policy")
    admitted_at = decision_value["decision_at"]
    if not (_timestamp(effective_until) > _timestamp(admitted_at) and _timestamp(retention_until) >= _timestamp(effective_until)):
        raise ValueError("knowledge validity interval is invalid")
    proposition = candidate["proposition"]
    material = {
        "knowledge_type": "shot_cinematography_admitted_knowledge", "project_id": context_rebound.value["project_id"],
        "domain": KNOWLEDGE_DOMAIN, "purpose": KNOWLEDGE_PURPOSE, "classification": context_rebound.value["classification"],
        "source_candidate": _source_binding(candidate), "proposition": proposition,
        "scope": "exact_project_shot_cinematography", "limitations": list(LIMITATIONS), "lifecycle_status": "active",
    }
    content_digest = canonical_digest(material)
    value = {
        "schema_version": "1", "contract_identity": "shot_cinematography_admitted_knowledge", "contract_version": "1",
        "knowledge_id": "shot-knowledge-" + content_digest[:32], **material,
        "admission_decision_id": decision_value["decision_id"],
        "admission_decision_digest": decision.digest, "admitted_at": admitted_at,
        "effective_from": admitted_at, "effective_until": effective_until, "retention_until": retention_until,
        "knowledge_content_digest": content_digest, "complete_knowledge_sha256": "0" * 64,
    }
    value["complete_knowledge_sha256"] = canonical_digest(_complete_material(value))
    knowledge = validate_shot_cinematography_admitted_knowledge(value)
    return ShotCinematographyKnowledgeAdmission(decision, knowledge)


def create_lifecycle_event(*, event_id: str, event_kind: str, actor_identity: str,
                           target_knowledge_id: str, target_knowledge_digest: str,
                           event_at: str, reason_code: str,
                           replacement: dict[str, str] | None = None) -> ValidatedMovieArtifact:
    value = {
        "schema_version": "1", "contract_identity": "shot_cinematography_knowledge_lifecycle_event",
        "contract_version": "1", "event_id": event_id, "event_kind": event_kind,
        "actor_kind": "human", "actor_identity": actor_identity,
        "target_knowledge_id": target_knowledge_id, "target_knowledge_digest": target_knowledge_digest,
        "event_at": event_at, "reason_code": reason_code,
    }
    if replacement is not None:
        value["replacement"] = replacement
    value["event_content_digest"] = canonical_digest(value)
    return validate_shot_cinematography_knowledge_lifecycle_event(value)


def current_use_eligible(knowledge: Any, *, lifecycle_events: Iterable[Any] = (),
                         replacements: Iterable[Any] = (), validation_time: str) -> ValidatedMovieArtifact:
    artifact = validate_shot_cinematography_admitted_knowledge(
        knowledge.to_json_value() if isinstance(knowledge, ValidatedMovieArtifact) else knowledge,
    )
    now = _timestamp(validation_time)
    value = artifact.value
    if not (_timestamp(value["effective_from"]) <= now < _timestamp(value["effective_until"])):
        raise ValueError("knowledge is outside its governed validity interval")
    events = [validate_shot_cinematography_knowledge_lifecycle_event(event.to_json_value() if isinstance(event, ValidatedMovieArtifact) else event) for event in lifecycle_events]
    if len({event.value["event_id"] for event in events}) != len(events):
        raise ValueError("duplicate lifecycle event")
    if events != sorted(events, key=lambda event: (event.value["event_at"], event.value["event_id"])):
        raise ValueError("lifecycle events are not canonical")
    for event in events:
        if event.value["target_knowledge_id"] != value["knowledge_id"] or event.value["target_knowledge_digest"] != artifact.digest:
            raise ValueError("lifecycle target binding mismatch")
        if _timestamp(event.value["event_at"]) > now:
            raise ValueError("future lifecycle event is ambiguous")
        if _timestamp(event.value["event_at"]) < _timestamp(value["admitted_at"]):
            raise ValueError("lifecycle event predates admission")
    if any(event.value["event_kind"] in {"challenge", "withdraw", "revoke", "archive"} for event in events):
        raise ValueError("knowledge is not currently eligible")
    supersedes = [event for event in events if event.value["event_kind"] == "supersede"]
    if supersedes:
        if len(supersedes) != 1:
            raise ValueError("ambiguous supersession chain")
        replacement = supersedes[0].value.get("replacement")
        candidates = [item for item in replacements if (item.value if isinstance(item, ValidatedMovieArtifact) else item).get("knowledge_id") == replacement["knowledge_id"]]
        if len(candidates) != 1:
            raise ValueError("supersession replacement is unavailable")
        replacement_artifact = validate_shot_cinematography_admitted_knowledge(candidates[0].to_json_value() if isinstance(candidates[0], ValidatedMovieArtifact) else candidates[0])
        if replacement_artifact.value["knowledge_id"] != replacement["knowledge_id"] or replacement_artifact.digest != replacement["knowledge_digest"] or replacement_artifact.value["project_id"] != value["project_id"]:
            raise ValueError("supersession replacement binding mismatch")
        raise ValueError("knowledge is superseded")
    return artifact
