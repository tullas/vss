from __future__ import annotations

from typing import Any

from vss_movie_contracts import (
    ValidatedMovieArtifact,
    validate_production_option_set_v2,
    validate_scene_option_review_decision,
    validate_scene_option_review_decision_task,
    validate_scene_option_review_packet,
    validate_scene_option_review_task,
)
from vss_movie_contracts.errors import MovieContractError
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


AUTHORITY_BOUNDARY = {
    "scope": "review_stage_assessment_only",
    "production_approval": False,
    "production_plan": False,
    "scheduling": False,
    "workflow_activation": False,
    "capability_grant": False,
    "runtime_execution": False,
}


def create_decision_task(
    packet: ValidatedMovieArtifact,
    option_set: ValidatedMovieArtifact,
    *,
    option_id: str,
    reviewer_id: str,
    outcome: str,
    rationale: str,
    deferred_review_conditions: list[str] | None,
    request_id: str,
    correlation_id: str,
    environment: str = "development",
) -> ValidatedMovieArtifact:
    if not isinstance(packet, ValidatedMovieArtifact) or not isinstance(option_set, ValidatedMovieArtifact):
        raise MovieContractError("decision recording requires a validated review packet and Option Set")
    if deferred_review_conditions is not None and not isinstance(deferred_review_conditions, list):
        raise MovieContractError("deferred review conditions must be a list")
    entries = [entry for entry in packet.value["payload"]["review_entries"] if entry["option_id"] == option_id]
    if len(entries) != 1:
        raise MovieContractError("decision option is not present exactly once in the review packet")
    conditions = list(deferred_review_conditions or [])
    value = {
        "schema_version": "1", "task_identity": "record_scene_option_review_decision", "task_version": "1",
        "request_id": request_id, "correlation_id": correlation_id,
        "project_id": packet.value["project_id"], "scene_id": packet.value["scene_id"],
        "environment": environment, "purpose": "accountable_human_scene_option_review_assessment",
        "expected_input_family": "scene_option_review_packet", "expected_input_version": "1",
        "expected_result_family": "scene_option_review_decision", "expected_result_version": "1",
        "review_packet_digest": packet.value["payload"]["review_packet_digest"],
        "review_packet_complete_digest": packet.value["integrity"]["complete_result_sha256"],
        "option_set_digest": packet.value["option_set_digest"],
        "option_set_complete_digest": packet.value["option_set_complete_digest"],
        "option_id": option_id, "option_content_digest": entries[0]["option_content_digest"],
        "reviewer_id": reviewer_id, "outcome": outcome, "rationale": rationale,
        "deferred_review_conditions": conditions, "lifecycle": "active", "task_content_digest": "0" * 64,
    }
    value["task_content_digest"] = canonical_digest({key: item for key, item in value.items() if key != "task_content_digest"})
    return validate_scene_option_review_decision_task(value, packet=packet, option_set=option_set)


def expected_decision_payload(task: ValidatedMovieArtifact, packet: ValidatedMovieArtifact) -> dict[str, Any]:
    decision = {
        "option_id": task.value["option_id"], "option_content_digest": task.value["option_content_digest"],
        "reviewer_id": task.value["reviewer_id"], "outcome": task.value["outcome"],
        "rationale": task.value["rationale"],
        "deferred_review_conditions": list(task.value["deferred_review_conditions"]),
    }
    decision["decision_digest"] = canonical_digest(decision)
    entry = next(entry for entry in packet.value["payload"]["review_entries"] if entry["option_id"] == task.value["option_id"])
    payload = {
        "decisions": [decision],
        "source_knowledge_bindings": thaw_json(packet.value["payload"]["source_knowledge_bindings"]),
        "knowledge_influence": thaw_json(entry["knowledge_influence"]),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "decision_record_digest": None,
    }
    payload["decision_record_digest"] = canonical_digest(payload)
    return payload


def record_option_review_decision(
    packet_data: dict[str, Any], option_set_data: dict[str, Any], *, option_id: str,
    reviewer_id: str, outcome: str, rationale: str, deferred_review_conditions: list[str] | None = None,
    request_id: str, correlation_id: str, environment: str = "development",
) -> dict[str, Any]:
    if not isinstance(packet_data, dict) or not isinstance(option_set_data, dict):
        raise MovieContractError("decision recording inputs must be objects")
    option_set = validate_production_option_set_v2(option_set_data)
    preparation_task = create_review_task(
        option_set, request_id=packet_data.get("request_id", ""),
        correlation_id=packet_data.get("correlation_id", ""), environment=environment,
    )
    packet = validate_scene_option_review_packet(packet_data, task=preparation_task, option_set=option_set)
    task = create_decision_task(
        packet, option_set, option_id=option_id, reviewer_id=reviewer_id, outcome=outcome,
        rationale=rationale, deferred_review_conditions=deferred_review_conditions,
        request_id=request_id, correlation_id=correlation_id, environment=environment,
    )
    payload = expected_decision_payload(task, packet)
    result = {
        "schema_version": "1", "result_family": "scene_option_review_decision", "result_version": "1",
        "request_id": request_id, "correlation_id": correlation_id,
        "project_id": packet.value["project_id"], "scene_id": packet.value["scene_id"],
        "review_packet_digest": packet.value["payload"]["review_packet_digest"],
        "review_packet_complete_digest": packet.value["integrity"]["complete_result_sha256"],
        "option_set_digest": packet.value["option_set_digest"],
        "option_set_complete_digest": packet.value["option_set_complete_digest"],
        "payload": payload,
        "integrity": {"payload_sha256": canonical_digest(payload), "complete_result_sha256": "0" * 64},
    }
    result["integrity"]["complete_result_sha256"] = canonical_digest(
        {**result, "integrity": {"payload_sha256": result["integrity"]["payload_sha256"]}}
    )
    return validate_scene_option_review_decision(
        result, task=task, packet=packet, option_set=option_set
    ).to_json_value()
