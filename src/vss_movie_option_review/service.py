from __future__ import annotations

from typing import Any

from vss_movie_contracts import (
    ValidatedMovieArtifact,
    validate_production_option_set_v2,
    validate_scene_option_review_packet,
    validate_scene_option_review_task,
)
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json

SHARED_REVIEW_PROMPTS = (
    "Which source claims and assumptions require human interpretation?",
    "Which feasibility, people, location, asset, effects, audio, rights, permit, cost, duration, and quality checks remain unresolved?",
    "Does this alternative serve human creative intent without treating Knowledge as truth or authority?",
    "What additional evidence is needed before any separate selection or approval decision?",
)
LIMITATIONS = (
    "This packet prepares neutral alternatives for human review; it does not rank, score, recommend, select, approve, or authorize them.",
    "Review preparation does not establish feasibility, availability, cost, schedule, quality, rights, permits, artistic correctness, or cultural authority.",
    "Stable source order is preserved for traceability and is not ranking or preference.",
)
CONSIDERATION_FIELDS = (
    "approach_category", "complexity_qualification", "qualified_rationale",
    "source_supported_considerations", "rule_derived_considerations",
    "performer_requirement_categories", "location_approach_category",
    "asset_requirement_categories", "effects_intensity_category",
    "audio_considerations", "prototype_suitability", "evidence_references",
    "qualified_confidence",
)


def create_review_task(option_set: ValidatedMovieArtifact, *, request_id: str, correlation_id: str,
                       environment: str = "development") -> ValidatedMovieArtifact:
    if not isinstance(option_set, ValidatedMovieArtifact):
        raise ValueError("review preparation requires a validated Option Set")
    source = option_set.value
    value = {
        "schema_version": "1", "task_identity": "prepare_scene_option_review", "task_version": "1",
        "request_id": request_id, "correlation_id": correlation_id,
        "project_id": source["project_id"], "scene_id": source["scene_id"],
        "environment": environment, "purpose": "scene_option_human_review_preparation",
        "expected_input_family": "scene_production_option_set", "expected_input_version": "2",
        "expected_result_family": "scene_option_review_packet", "expected_result_version": "1",
        "option_set_digest": option_set.digest,
        "option_set_complete_digest": source["integrity"]["complete_result_sha256"],
        "lifecycle": "active", "task_content_digest": "0" * 64,
    }
    value["task_content_digest"] = canonical_digest({key: item for key, item in value.items() if key != "task_content_digest"})
    return validate_scene_option_review_task(value, option_set)


def _review_entry(option: Any) -> dict[str, Any]:
    raw = thaw_json(option)
    considerations = {field: raw[field] for field in CONSIDERATION_FIELDS}
    unresolved = []
    for field in ("assumptions", "unknowns", "conflicts", "limitations", "external_validation_requirements"):
        unresolved.extend(raw[field])
    material = {
        "option_id": raw["option_id"], "option_content_digest": raw["option_content_digest"],
        "profile_identity": raw["profile_identity"], "source_ordinal": raw["ordinal"],
        "considerations": considerations, "unresolved_checks": unresolved,
        "knowledge_influence": raw.get("knowledge_influence"),
    }
    return {**material, "entry_digest": canonical_digest(material)}


def expected_review_payload(option_set: ValidatedMovieArtifact) -> dict[str, Any]:
    if not isinstance(option_set, ValidatedMovieArtifact) or option_set.value.get("result_family") != "scene_production_option_set" or option_set.value.get("result_version") != "2":
        raise ValueError("review preparation requires a validated v2 Option Set")
    entries = [_review_entry(option) for option in option_set.value["payload"]["options"]]
    payload = {
        "source_knowledge_bindings": thaw_json(option_set.value["knowledge_bindings"]),
        "stable_order_is_not_ranking": True,
        "review_entries": entries,
        "shared_review_prompts": list(SHARED_REVIEW_PROMPTS),
        "limitations": list(LIMITATIONS),
        "review_packet_digest": None,
    }
    payload["review_packet_digest"] = canonical_digest(payload)
    return payload


def prepare_option_review(option_set_data: dict[str, Any], *, request_id: str, correlation_id: str,
                          environment: str = "development") -> dict[str, Any]:
    option_set = validate_production_option_set_v2(option_set_data)
    task = create_review_task(option_set, request_id=request_id, correlation_id=correlation_id, environment=environment)
    payload = expected_review_payload(option_set)
    source = option_set.value
    packet = {
        "schema_version": "1", "result_family": "scene_option_review_packet", "result_version": "1",
        "request_id": request_id, "correlation_id": correlation_id,
        "project_id": source["project_id"], "scene_id": source["scene_id"],
        "option_set_digest": option_set.digest,
        "option_set_complete_digest": source["integrity"]["complete_result_sha256"],
        "payload": payload,
        "integrity": {"payload_sha256": canonical_digest(payload), "complete_result_sha256": "0" * 64},
    }
    packet["integrity"]["complete_result_sha256"] = canonical_digest({**packet, "integrity": {"payload_sha256": packet["integrity"]["payload_sha256"]}})
    return validate_scene_option_review_packet(packet, task=task, option_set=option_set).to_json_value()
