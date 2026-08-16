from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from vss_movie_contracts import (
    MovieContractRegistry,
    ValidatedMovieArtifact,
    validate_shot_cinematography_lesson_candidate_set,
    validate_shot_cinematography_lesson_candidate_task,
    validate_shot_cinematography_pattern_set,
)
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json

CATALOGUE_IDENTITY = "vss.shot-cinematography.lessons.deterministic"
CATALOGUE_VERSION = "1.0.0"
STRATEGY_IDENTITY = "vss.derive-shot-cinematography-lesson-candidates.deterministic"
STRATEGY_VERSION = "1.0.0"
PROVIDER_IDENTITY = "vss.reasoning.shot-cinematography-lessons.deterministic"
PROVIDER_VERSION = "1.0.0"
PROVIDER_API_VERSION = "1"
LIMITATIONS = (
    "exact_context_scope", "observed_values_only", "uncertain_and_unavailable_evidence_excluded",
    "no_causal_interpretation", "no_evaluative_interpretation", "no_recommendation",
    "no_generalization", "not_admitted_knowledge",
)


@dataclass(frozen=True, slots=True)
class ShotCinematographyLessonRuleCatalogue:
    identity: str = CATALOGUE_IDENTITY
    version: str = CATALOGUE_VERSION
    eligible_pattern_types: tuple[str, ...] = ("repeated_value", "variation")
    candidate_types: tuple[str, ...] = ("recurrence_lesson_candidate", "variation_lesson_candidate")
    scope: str = "exact_source_context"
    one_candidate_per_pattern: bool = True
    cross_pattern_synthesis: str = "off"
    recommendation: str = "prohibited"
    causal_interpretation: str = "prohibited"
    knowledge_admission: str = "off"
    maximum_source_patterns: int = 40
    maximum_candidates: int = 40

    @property
    def digest(self) -> str:
        material = {field.name: list(value) if isinstance((value := getattr(self, field.name)), tuple) else value for field in fields(self)}
        return canonical_digest(material)

    @classmethod
    def built_in(cls) -> "ShotCinematographyLessonRuleCatalogue":
        return cls()


@dataclass(frozen=True, slots=True)
class ShotCinematographyLessonCandidateProviderView:
    pattern_set_digest: str
    pattern_set_complete_digest: str
    context_id: str
    context_content_digest: str
    complete_context_digest: str
    patterns: tuple[Any, ...]
    rule_catalogue_identity: str
    rule_catalogue_version: str
    rule_catalogue_digest: str
    provider_visible_digest: str


def _validated_pattern_set(pattern_set: Any, *, pattern_task: Any, context: Any, pattern_invocation_binding_digest: str) -> ValidatedMovieArtifact:
    if not isinstance(pattern_set, ValidatedMovieArtifact):
        raise ValueError("lesson derivation requires an independently validated Pattern Set")
    rebound = validate_shot_cinematography_pattern_set(
        pattern_set.to_json_value(), task=pattern_task, context=context,
        invocation_binding_digest=pattern_invocation_binding_digest,
    )
    if rebound.digest != pattern_set.digest:
        raise ValueError("lesson Pattern Set substitution rejected")
    return rebound


def create_lesson_candidate_task(pattern_set: ValidatedMovieArtifact, *, pattern_task: ValidatedMovieArtifact,
                                 context: Any, pattern_invocation_binding_digest: str,
                                 request_id: str, correlation_id: str) -> ValidatedMovieArtifact:
    pattern_set = _validated_pattern_set(pattern_set, pattern_task=pattern_task, context=context,
                                         pattern_invocation_binding_digest=pattern_invocation_binding_digest)
    pv = pattern_set.value
    catalogue = ShotCinematographyLessonRuleCatalogue.built_in()
    value = {
        "schema_version": "1", "task_identity": "derive_shot_cinematography_lesson_candidates", "task_version": "1",
        "request_id": request_id, "correlation_id": correlation_id, "project_id": pv["project_id"],
        "scene_id": pv["scene_id"], "environment": "development",
        "purpose": "shot_cinematography_local_lesson_candidate_derivation", "classification": pv["classification"],
        "expected_input_family": "shot_cinematography_pattern_set", "expected_input_version": "1",
        "expected_result_family": "shot_cinematography_lesson_candidate_set", "expected_result_version": "1",
        "pattern_set_digest": pattern_set.digest, "pattern_set_complete_digest": pv["integrity"]["complete_result_sha256"],
        "context_id": pv["context_id"], "context_content_digest": pv["context_content_digest"],
        "complete_context_digest": pv["complete_context_digest"],
        "rule_catalogue_identity": catalogue.identity, "rule_catalogue_version": catalogue.version,
        "rule_catalogue_digest": catalogue.digest,
        "bounds": {"maximum_source_patterns": 40, "maximum_candidates": 40, "maximum_result_bytes": 65536},
        "lifecycle": "active", "implementation_availability": "required", "task_content_digest": "0" * 64,
    }
    value["task_content_digest"] = canonical_digest({key: item for key, item in value.items() if key != "task_content_digest"})
    return validate_shot_cinematography_lesson_candidate_task(value, pattern_set, MovieContractRegistry.built_in())


def lesson_candidate_provider_view(pattern_set: ValidatedMovieArtifact) -> ShotCinematographyLessonCandidateProviderView:
    if not isinstance(pattern_set, ValidatedMovieArtifact) or pattern_set.value.get("result_family") != "shot_cinematography_pattern_set":
        raise ValueError("lesson provider view requires a validated Pattern Set")
    pv = pattern_set.value
    catalogue = ShotCinematographyLessonRuleCatalogue.built_in()
    patterns = tuple(freeze_json({
        "pattern_id": item["pattern_id"], "pattern_digest": item["pattern_digest"],
        "pattern_type": item["pattern_type"], "attribute": item["attribute"], "values": thaw_json(item["values"]),
        "occurrence_count": item["occurrence_count"], "supporting_evidence_digest": item["supporting_evidence_digest"],
    }) for item in pv["payload"]["patterns"])
    material = {
        "pattern_set_digest": pattern_set.digest, "pattern_set_complete_digest": pv["integrity"]["complete_result_sha256"],
        "context_id": pv["context_id"], "context_content_digest": pv["context_content_digest"],
        "complete_context_digest": pv["complete_context_digest"], "patterns": [thaw_json(item) for item in patterns],
        "rule_catalogue": [catalogue.identity, catalogue.version, catalogue.digest],
    }
    return ShotCinematographyLessonCandidateProviderView(
        pattern_set.digest, pv["integrity"]["complete_result_sha256"], pv["context_id"],
        pv["context_content_digest"], pv["complete_context_digest"], patterns,
        catalogue.identity, catalogue.version, catalogue.digest, canonical_digest(material),
    )


def _source_binding(pattern: dict[str, Any]) -> dict[str, Any]:
    return {key: pattern[key] for key in ("pattern_id", "pattern_digest", "supporting_evidence_digest")}


def derive_lesson_candidates(view: ShotCinematographyLessonCandidateProviderView) -> list[dict[str, Any]]:
    if type(view) is not ShotCinematographyLessonCandidateProviderView:
        raise TypeError("lesson derivation requires exact provider view")
    candidates = []
    for frozen_pattern in view.patterns:
        pattern = thaw_json(frozen_pattern)
        candidate_type = {
            "repeated_value": "recurrence_lesson_candidate",
            "variation": "variation_lesson_candidate",
        }[pattern["pattern_type"]]
        material = {
            "candidate_type": candidate_type, "source_pattern_id": pattern["pattern_id"],
            "source_pattern_digest": pattern["pattern_digest"],
            "supporting_evidence_digest": pattern["supporting_evidence_digest"],
            "context_id": view.context_id, "context_content_digest": view.context_content_digest,
            "proposition": {"attribute": pattern["attribute"], "values": pattern["values"],
                            "occurrence_count": pattern["occurrence_count"]},
            "scope": "exact_source_context", "limitations": list(LIMITATIONS),
        }
        digest = canonical_digest(material)
        candidates.append({"candidate_id": "shot-lesson-candidate-" + digest[:32], "candidate_digest": digest, **material})
    return sorted(candidates, key=lambda item: item["candidate_id"])


def expected_lesson_candidate_payload(pattern_set: ValidatedMovieArtifact) -> dict[str, Any]:
    view = lesson_candidate_provider_view(pattern_set)
    source_patterns = sorted((_source_binding(thaw_json(item)) for item in view.patterns), key=lambda item: item["pattern_id"])
    payload = {
        "source_pattern_bindings": source_patterns,
        "candidates": derive_lesson_candidates(view),
        "limitations": list(LIMITATIONS),
        "semantic_result_digest": None,
    }
    payload["semantic_result_digest"] = canonical_digest(payload)
    return payload


def create_lesson_candidate_result(task: ValidatedMovieArtifact, pattern_set: ValidatedMovieArtifact,
                                   invocation_binding_digest: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    expected = expected_lesson_candidate_payload(pattern_set)
    if candidates != expected["candidates"]:
        raise ValueError("provider lesson candidate substitution rejected")
    tv, pv = task.value, pattern_set.value
    value = {
        "schema_version": "1", "result_family": "shot_cinematography_lesson_candidate_set", "result_version": "1",
        "request_id": tv["request_id"], "correlation_id": tv["correlation_id"], "project_id": tv["project_id"],
        "scene_id": tv["scene_id"], "purpose": tv["purpose"], "classification": tv["classification"],
        "pattern_set_digest": pattern_set.digest, "pattern_set_complete_digest": pv["integrity"]["complete_result_sha256"],
        "context_id": pv["context_id"], "context_content_digest": pv["context_content_digest"],
        "complete_context_digest": pv["complete_context_digest"],
        "rule_catalogue_identity": tv["rule_catalogue_identity"], "rule_catalogue_version": tv["rule_catalogue_version"],
        "rule_catalogue_digest": tv["rule_catalogue_digest"], "invocation_binding_digest": invocation_binding_digest,
        "payload": expected, "integrity": {"payload_sha256": canonical_digest(expected), "complete_result_sha256": "0" * 64},
    }
    value["integrity"]["complete_result_sha256"] = canonical_digest({**value, "integrity": {"payload_sha256": value["integrity"]["payload_sha256"]}})
    return value
