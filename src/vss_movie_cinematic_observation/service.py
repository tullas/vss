from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_context_contracts import ContextContractRegistry, ValidatedContext
from vss_context_contracts.limits import MAX_CONTEXT_BYTES
from vss_movie_contracts import (
    MovieContractRegistry,
    ValidatedMovieArtifact,
    validate_shot_cinematography_observation,
    validate_shot_cinematography_observation_set,
)
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json, validate_json_value

PURPOSE = "shot_cinematography_local_analysis"
POLICY_IDENTITY = "shot_cinematography_context_local"
POLICY_VERSION = "1"
MIN_OBSERVATIONS = 2
MAX_OBSERVATIONS = 8
MAX_FUTURE_PAIRWISE_COMPARISONS = 28


@dataclass(frozen=True, slots=True)
class ShotCinematographyAssemblyResult:
    context: ValidatedContext
    report: Mapping[str, Any]
    summary: Mapping[str, Any]


def _admit_observations(observations: Any) -> tuple[ValidatedMovieArtifact, ...]:
    if not isinstance(observations, (list, tuple)):
        raise ValueError("shot observations must be a bounded sequence")
    if not MIN_OBSERVATIONS <= len(observations) <= MAX_OBSERVATIONS:
        raise ValueError("shot observation count is outside its bound")
    registry = MovieContractRegistry.built_in()
    admitted = tuple(validate_shot_cinematography_observation(value, registry) for value in observations)
    ids = [item.value["observation_id"] for item in admitted]
    shots = [item.value["shot_id"] for item in admitted]
    if len(ids) != len(set(ids)) or len(shots) != len(set(shots)):
        raise ValueError("shot observation or shot identity is duplicated")
    scopes = {(item.value["project_id"], item.value["scene_id"], item.value["classification"]) for item in admitted}
    if len(scopes) != 1:
        raise ValueError("shot observations do not have one exact scope")
    return tuple(sorted(admitted, key=lambda item: item.value["observation_id"]))


def create_shot_cinematography_observation_set(observations: Any) -> ValidatedMovieArtifact:
    admitted = _admit_observations(observations)
    first = admitted[0].value
    bindings = [
        {
            "observation_identity": item.value["contract_identity"],
            "observation_version": item.value["contract_version"],
            "observation_id": item.value["observation_id"],
            "observation_content_digest": item.value["observation_content_digest"],
            "shot_id": item.value["shot_id"],
        }
        for item in admitted
    ]
    identity_seed = canonical_digest({
        "project_id": first["project_id"], "scene_id": first["scene_id"],
        "classification": first["classification"], "observations": bindings,
    })
    value = {
        "schema_version": "1", "contract_identity": "shot_cinematography_observation_set",
        "contract_version": "1", "observation_set_id": "shot-observation-set-" + identity_seed[:32],
        "project_id": first["project_id"], "scene_id": first["scene_id"], "purpose": PURPOSE,
        "classification": first["classification"], "set_semantics": "unordered_exact",
        "bounds": {"minimum_observations": MIN_OBSERVATIONS, "maximum_observations": MAX_OBSERVATIONS},
        "observations": bindings,
        "limitations": [
            "Array order is canonical representation, not chronology.",
            "This set aggregates observations without reasoning or promotion.",
        ],
        "content_digest": "0" * 64,
    }
    value["content_digest"] = canonical_digest({key: item for key, item in value.items() if key != "content_digest"})
    return validate_shot_cinematography_observation_set(value, [item.to_json_value() for item in admitted])


def validate_shot_cinematography_context(
    value: Any,
    *,
    registry: ContextContractRegistry | None = None,
    observation_set: ValidatedMovieArtifact | None = None,
    observations: Any = (),
) -> ValidatedContext:
    try:
        validate_json_value(value, maximum_bytes=MAX_CONTEXT_BYTES)
    except Exception as exc:
        raise ValueError("shot cinematography Context is unsafe") from exc
    if not isinstance(value, dict):
        raise ValueError("shot cinematography Context must be an object")
    registry = registry or ContextContractRegistry.built_in()
    errors = list(registry.iter_errors("vss.shot_cinematography_context/1", value))
    if errors:
        raise ValueError("shot cinematography Context does not match its contract")
    payload = value["payload"]
    expected = sorted(payload["observations"], key=lambda item: item["observation_id"])
    if payload["observations"] != expected:
        raise ValueError("shot cinematography Context order is not canonical")
    if len({item["observation_id"] for item in expected}) != len(expected) or len({item["shot_id"] for item in expected}) != len(expected):
        raise ValueError("shot cinematography Context identity is duplicated")
    for projection in expected:
        reconstructed = {
            "schema_version": "1",
            "contract_identity": projection["observation_identity"],
            "contract_version": projection["observation_version"],
            "observation_id": projection["observation_id"],
            "project_id": value["project_id"],
            "scene_id": value["scene_id"],
            "shot_id": projection["shot_id"],
            "evidence_reference": projection["evidence_reference"],
            "purpose": "cinematic_observation_local_validation",
            "classification": value["classification"],
            "attributes": projection["attributes"],
            "provenance": projection["provenance"],
            "limitations": projection["limitations"],
            "observation_content_digest": projection["observation_content_digest"],
        }
        validate_shot_cinematography_observation(reconstructed)
    if value["context_content_digest"] != canonical_digest(payload):
        raise ValueError("shot cinematography Context content digest mismatch")
    selection = canonical_digest([
        {key: item[key] for key in ("observation_identity", "observation_version", "observation_id", "observation_content_digest", "shot_id")}
        for item in expected
    ])
    if value["selection_digest"] != selection or value["context_id"] != "shot-context-" + value["context_content_digest"][:32]:
        raise ValueError("shot cinematography Context identity binding mismatch")
    material = dict(value)
    material["integrity"] = {}
    if value["integrity"]["complete_context_sha256"] != canonical_digest(material):
        raise ValueError("shot cinematography Context integrity mismatch")
    if observation_set is not None:
        if not isinstance(observation_set, ValidatedMovieArtifact) or observation_set.value.get("contract_identity") != "shot_cinematography_observation_set":
            raise ValueError("shot cinematography Context requires a validated observation set")
        rebound = validate_shot_cinematography_observation_set(observation_set.to_json_value(), observations)
        if rebound.digest != observation_set.digest or (value["observation_set_id"], value["observation_set_digest"]) != (observation_set.value["observation_set_id"], observation_set.value["content_digest"]):
            raise ValueError("shot cinematography Context set substitution rejected")
        if (value["project_id"], value["scene_id"], value["classification"]) != (
            rebound.value["project_id"],
            rebound.value["scene_id"],
            rebound.value["classification"],
        ):
            raise ValueError("shot cinematography Context scope substitution rejected")
        admitted = _admit_observations(observations)
        projections = [_projection(item) for item in admitted]
        if payload["observations"] != projections:
            raise ValueError("shot cinematography Context projection substitution rejected")
    return ValidatedContext.create(value)


def _projection(artifact: ValidatedMovieArtifact) -> dict[str, Any]:
    item = artifact.to_json_value()
    return {
        "observation_identity": item["contract_identity"], "observation_version": item["contract_version"],
        "observation_id": item["observation_id"], "observation_content_digest": item["observation_content_digest"],
        "shot_id": item["shot_id"], "evidence_reference": item["evidence_reference"],
        "attributes": item["attributes"], "provenance": item["provenance"], "limitations": item["limitations"],
    }


def assemble_shot_cinematography_context(observation_set: Any, observations: Any) -> ShotCinematographyAssemblyResult:
    if not isinstance(observation_set, ValidatedMovieArtifact) or observation_set.value.get("contract_identity") != "shot_cinematography_observation_set":
        raise ValueError("Context Assembly requires an independently validated observation set")
    raw_set = observation_set.to_json_value()
    rebound = validate_shot_cinematography_observation_set(raw_set, observations)
    if rebound.digest != observation_set.digest:
        raise ValueError("observation set substitution rejected")
    admitted = _admit_observations(observations)
    data = observation_set.value
    projections = [_projection(item) for item in admitted]
    payload = {
        "set_semantics": "unordered_exact", "observations": projections,
        "unknowns": ["No chronology, relationship, recurrence, or missing value is inferred."],
        "limitations": [
            "Observation is not truth and this Context grants no authority.",
            "Assembly performs validation and binding only; no cinematic reasoning is performed.",
            "Pattern, Lesson, and Admitted Knowledge promotion are outside this Context.",
        ],
        "budget_summary": {
            "minimum_observations": MIN_OBSERVATIONS, "maximum_observations": MAX_OBSERVATIONS,
            "maximum_future_pairwise_comparisons": MAX_FUTURE_PAIRWISE_COMPARISONS,
            "maximum_context_bytes": MAX_CONTEXT_BYTES,
        },
    }
    content = canonical_digest(payload)
    selection = canonical_digest([
        {key: item[key] for key in ("observation_identity", "observation_version", "observation_id", "observation_content_digest", "shot_id")}
        for item in projections
    ])
    context_value = {
        "schema_version": "1", "context_id": "shot-context-" + content[:32],
        "context_family": "shot_cinematography_context", "context_family_version": "1",
        "purpose": PURPOSE, "project_id": data["project_id"], "scene_id": data["scene_id"],
        "classification": data["classification"], "policy_identity": POLICY_IDENTITY,
        "policy_version": POLICY_VERSION, "construction_basis": "deterministic_validated_inputs",
        "lifecycle": "validated", "observation_set_id": data["observation_set_id"],
        "observation_set_digest": data["content_digest"], "selection_digest": selection,
        "context_content_digest": content, "integrity": {"complete_context_sha256": "0" * 64},
        "payload": payload,
    }
    context_value["integrity"]["complete_context_sha256"] = canonical_digest({**context_value, "integrity": {}})
    context = validate_shot_cinematography_context(
        context_value, observation_set=observation_set, observations=observations
    )
    report_value = {
        "schema_version": "1", "report_family": "shot_cinematography_context_assembly_report",
        "report_version": "1", "context_id": context.value["context_id"],
        "context_family": "shot_cinematography_context", "context_version": "1",
        "project_id": data["project_id"], "scene_id": data["scene_id"], "purpose": PURPOSE,
        "classification": data["classification"], "observation_set_id": data["observation_set_id"],
        "observation_set_digest": data["content_digest"], "observation_count": len(projections),
        "context_content_digest": content, "complete_context_digest": context.digest,
        "status": "success",
    }
    report_value["report_digest"] = canonical_digest(report_value)
    report = freeze_json(report_value)
    summary = MappingProxyType({
        "context_id": context.value["context_id"], "observation_count": len(projections),
        "observation_set_digest": data["content_digest"], "selection_digest": selection,
        "context_content_digest": content, "complete_context_digest": context.digest,
        "report_digest": report["report_digest"], "context_registry_digest": ContextContractRegistry.built_in().digest,
    })
    return ShotCinematographyAssemblyResult(context, report, summary)
