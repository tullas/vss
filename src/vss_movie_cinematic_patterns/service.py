from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from vss_context_contracts import ValidatedContext
from vss_movie_cinematic_observation import validate_shot_cinematography_context
from vss_movie_contracts import (
    MovieContractRegistry,
    validate_shot_cinematography_pattern_set,
    validate_shot_cinematography_pattern_task,
)
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json

CATALOGUE_IDENTITY = "vss.shot-cinematography.patterns.deterministic"
CATALOGUE_VERSION = "1.0.0"
STRATEGY_IDENTITY = "vss.analyze-shot-cinematography-patterns.deterministic"
STRATEGY_VERSION = "1.0.0"
PROVIDER_IDENTITY = "vss.reasoning.shot-cinematography-patterns.deterministic"
PROVIDER_VERSION = "1.0.0"
PROVIDER_API_VERSION = "1"
ATTRIBUTES = (
    "shot_scale", "camera_angle", "camera_elevation", "camera_movement",
    "composition", "screen_direction", "subject_count", "focal_length_mm",
)


@dataclass(frozen=True, slots=True)
class ShotCinematographyPatternRuleCatalogue:
    identity: str = CATALOGUE_IDENTITY
    version: str = CATALOGUE_VERSION
    pattern_types: tuple[str, ...] = ("repeated_value", "variation")
    admitted_attributes: tuple[str, ...] = ATTRIBUTES
    participating_qualification: str = "observed"
    excluded_qualifications: tuple[str, ...] = ("uncertain", "unknown", "not_observed", "not_applicable")
    recurrence_threshold: int = 2
    maximum_observations: int = 8
    maximum_patterns: int = 40
    combination_rules: str = "off"
    pairwise_comparison: str = "off"

    @property
    def digest(self) -> str:
        material = {field.name: list(value) if isinstance((value := getattr(self, field.name)), tuple) else value for field in fields(self)}
        return canonical_digest(material)

    @classmethod
    def built_in(cls) -> "ShotCinematographyPatternRuleCatalogue":
        return cls()


@dataclass(frozen=True, slots=True)
class ShotCinematographyPatternProviderView:
    context_id: str
    context_content_digest: str
    complete_context_digest: str
    observations: tuple[Any, ...]
    rule_catalogue_identity: str
    rule_catalogue_version: str
    rule_catalogue_digest: str
    provider_visible_digest: str


def _validated_context(context: Any) -> ValidatedContext:
    if not isinstance(context, ValidatedContext):
        raise ValueError("pattern analysis requires an independently validated Context")
    rebound = validate_shot_cinematography_context(context.to_json_value())
    if rebound.digest != context.digest:
        raise ValueError("pattern analysis Context substitution rejected")
    return rebound


def create_pattern_task(context: ValidatedContext, *, request_id: str, correlation_id: str) -> Any:
    context = _validated_context(context)
    cv = context.value
    catalogue = ShotCinematographyPatternRuleCatalogue.built_in()
    value = {
        "schema_version": "1", "task_identity": "analyze_shot_cinematography_patterns", "task_version": "1",
        "request_id": request_id, "correlation_id": correlation_id, "project_id": cv["project_id"],
        "scene_id": cv["scene_id"], "environment": "development", "purpose": "shot_cinematography_local_analysis",
        "classification": cv["classification"], "expected_context_family": "shot_cinematography_context",
        "expected_context_version": "1", "expected_result_family": "shot_cinematography_pattern_set",
        "expected_result_version": "1", "context_id": cv["context_id"],
        "context_content_digest": cv["context_content_digest"], "complete_context_digest": context.digest,
        "rule_catalogue_identity": catalogue.identity, "rule_catalogue_version": catalogue.version,
        "rule_catalogue_digest": catalogue.digest,
        "bounds": {"maximum_observations": 8, "maximum_attributes": 8, "maximum_patterns": 40, "maximum_result_bytes": 65536},
        "lifecycle": "active", "implementation_availability": "required", "task_content_digest": "0" * 64,
    }
    value["task_content_digest"] = canonical_digest({key: item for key, item in value.items() if key != "task_content_digest"})
    return validate_shot_cinematography_pattern_task(value, context, MovieContractRegistry.built_in())


def pattern_provider_view(context: ValidatedContext) -> ShotCinematographyPatternProviderView:
    context = _validated_context(context)
    catalogue = ShotCinematographyPatternRuleCatalogue.built_in()
    observations = tuple(freeze_json({
        "observation_id": item["observation_id"], "observation_content_digest": item["observation_content_digest"],
        "shot_id": item["shot_id"], "attributes": thaw_json(item["attributes"]),
    }) for item in context.value["payload"]["observations"])
    material = {
        "context_id": context.value["context_id"], "context_content_digest": context.value["context_content_digest"],
        "complete_context_digest": context.digest, "observations": [thaw_json(item) for item in observations],
        "rule_catalogue": [catalogue.identity, catalogue.version, catalogue.digest],
    }
    return ShotCinematographyPatternProviderView(
        context.value["context_id"], context.value["context_content_digest"], context.digest, observations,
        catalogue.identity, catalogue.version, catalogue.digest, canonical_digest(material),
    )


def _binding(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in ("observation_id", "observation_content_digest", "shot_id")}


def analyze_patterns(view: ShotCinematographyPatternProviderView) -> dict[str, Any]:
    if type(view) is not ShotCinematographyPatternProviderView:
        raise TypeError("pattern analysis requires exact provider view")
    observations = [thaw_json(item) for item in view.observations]
    summaries: list[dict[str, Any]] = []
    patterns: list[dict[str, Any]] = []
    for attribute in ATTRIBUTES:
        groups: dict[str, tuple[Any, list[dict[str, Any]]]] = {}
        excluded = []
        for item in observations:
            qualified = item["attributes"][attribute]
            if qualified["status"] != "observed":
                excluded.append({"observation_id": item["observation_id"], "observation_content_digest": item["observation_content_digest"], "qualification": qualified["status"]})
                continue
            value = qualified["value"]
            key = canonical_digest(value)
            groups.setdefault(key, (value, []))[1].append(_binding(item))
        value_counts = [
            {"value": value, "count": len(support), "supporting_observation_ids": sorted(item["observation_id"] for item in support)}
            for _, (value, support) in sorted(groups.items())
        ]
        eligible = sum(item["count"] for item in value_counts)
        for item in value_counts:
            if item["count"] >= 2:
                material = {"pattern_type": "repeated_value", "attribute": attribute, "values": [item["value"]],
                            "occurrence_count": item["count"], "eligible_observation_count": eligible,
                            "supporting_observation_ids": item["supporting_observation_ids"], "excluded_observations": excluded,
                            "qualification": "observed_recurrence"}
                digest = canonical_digest(material)
                patterns.append({"pattern_id": "shot-pattern-" + digest[:32], "pattern_digest": digest, **material})
        if len(value_counts) >= 2:
            support = sorted(observation_id for item in value_counts for observation_id in item["supporting_observation_ids"])
            material = {"pattern_type": "variation", "attribute": attribute, "values": [item["value"] for item in value_counts],
                        "occurrence_count": eligible, "eligible_observation_count": eligible,
                        "supporting_observation_ids": support, "excluded_observations": excluded,
                        "qualification": "observed_variation"}
            digest = canonical_digest(material)
            patterns.append({"pattern_id": "shot-pattern-" + digest[:32], "pattern_digest": digest, **material})
        attribute_patterns = [item for item in patterns if item["attribute"] == attribute]
        determination = "insufficient_comparable" if eligible < 2 else "patterns_found" if attribute_patterns else "no_pattern"
        summaries.append({"attribute": attribute, "eligible_observation_count": eligible, "observed_values": value_counts,
                          "excluded_observations": excluded, "determination": determination})
    patterns.sort(key=lambda item: (ATTRIBUTES.index(item["attribute"]), item["pattern_type"], item["pattern_digest"]))
    return {"attribute_summaries": summaries, "patterns": patterns}


def expected_pattern_payload(context: ValidatedContext) -> dict[str, Any]:
    view = pattern_provider_view(context)
    analysis = analyze_patterns(view)
    observations = [thaw_json(item) for item in view.observations]
    payload = {
        "observation_bindings": [_binding(item) for item in observations],
        "attribute_summaries": analysis["attribute_summaries"], "patterns": analysis["patterns"],
        "limitations": [
            "Patterns report bounded explicit recurrence or variation; Pattern is not Truth or Lesson.",
            "Frequency is an occurrence count, not confidence, authority, or recommendation.",
            "Uncertain and unavailable qualifications remain evidence but do not participate in value patterns.",
            "No causality, emotion, narrative intent, chronology, aesthetic quality, or missing value is inferred.",
        ], "semantic_result_digest": None,
    }
    payload["semantic_result_digest"] = canonical_digest(payload)
    return payload


def create_pattern_result(task: Any, context: ValidatedContext, invocation_binding_digest: str, analysis: dict[str, Any]) -> dict[str, Any]:
    context = _validated_context(context)
    expected = expected_pattern_payload(context)
    if analysis != {"attribute_summaries": expected["attribute_summaries"], "patterns": expected["patterns"]}:
        raise ValueError("provider pattern result substitution rejected")
    tv, cv = task.value, context.value
    value = {
        "schema_version": "1", "result_family": "shot_cinematography_pattern_set", "result_version": "1",
        "request_id": tv["request_id"], "correlation_id": tv["correlation_id"], "project_id": tv["project_id"],
        "scene_id": tv["scene_id"], "purpose": tv["purpose"], "classification": tv["classification"],
        "context_id": cv["context_id"], "context_content_digest": cv["context_content_digest"], "complete_context_digest": context.digest,
        "rule_catalogue_identity": tv["rule_catalogue_identity"], "rule_catalogue_version": tv["rule_catalogue_version"],
        "rule_catalogue_digest": tv["rule_catalogue_digest"], "invocation_binding_digest": invocation_binding_digest,
        "payload": expected, "integrity": {"payload_sha256": canonical_digest(expected), "complete_result_sha256": "0" * 64},
    }
    value["integrity"]["complete_result_sha256"] = canonical_digest({**value, "integrity": {"payload_sha256": value["integrity"]["payload_sha256"]}})
    validate_shot_cinematography_pattern_set(value, task=task, context=context, invocation_binding_digest=invocation_binding_digest)
    return value
