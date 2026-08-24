from __future__ import annotations

from typing import Any

from vss_movie_contracts import validate_production_option_set_v2, validate_scene_breakdown
from vss_movie_option_review import record_option_review_decision
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json
from vss_resource_contracts import (
    ResourceContractError,
    ValidatedResourceArtifact,
    canon_snapshot_identity_material,
    canon_snapshot_seal_material,
    creative_decision_identity_material,
    creative_decision_seal_material,
    production_canon_binding_identity_material,
    production_canon_binding_seal_material,
    validate_canon_snapshot,
    validate_creative_decision_revision,
    validate_production_canon_binding,
)
from vss_resource_contracts.models import AdmittedCreativeDecision, _admit_creative_decision


DECISION_LIMITATIONS = [
    "inert_creative_decision", "not_production_approval", "not_runtime_authority",
    "not_provider_authority", "not_workflow_authority", "not_rights_authority",
    "exact_revision_only",
]
CANON_LIMITATIONS = [
    "inert_canon_snapshot", "not_mutable_global_truth", "not_production_approval",
    "not_runtime_authority", "not_workflow_authority", "not_rights_authority",
    "exact_decision_revisions_only",
]
BINDING_LIMITATIONS = [
    "inert_production_input_binding", "not_production_approval", "not_runtime_authority",
    "not_provider_authority", "not_workflow_authority", "not_scheduling_authority",
    "not_regeneration_authority", "not_publication_authority", "no_storage_authority",
    "not_rights_authority", "exact_canon_and_decision_revisions_only",
]


def _authoritative_movie_inputs(decision_data: Any, packet_data: Any, option_set_data: Any,
                                breakdown_data: Any):
    if not all(isinstance(item, dict) for item in (
            decision_data, packet_data, option_set_data, breakdown_data)):
        raise ResourceContractError("creative decision requires movie artifact objects")
    raw_items = decision_data.get("payload", {}).get("decisions", [])
    if len(raw_items) != 1 or not isinstance(raw_items[0], dict):
        raise ResourceContractError("creative decision requires exactly one review decision")
    raw = raw_items[0]
    try:
        reconstructed = record_option_review_decision(
            packet_data, option_set_data, option_id=raw.get("option_id", ""),
            reviewer_id=raw.get("reviewer_id", ""), outcome=raw.get("outcome", ""),
            rationale=raw.get("rationale", ""),
            deferred_review_conditions=raw.get("deferred_review_conditions"),
            request_id=decision_data.get("request_id", ""),
            correlation_id=decision_data.get("correlation_id", ""),
            environment="development",
        )
        if reconstructed != decision_data:
            raise ResourceContractError("review decision is not authoritative")
        option_set = validate_production_option_set_v2(option_set_data)
        breakdown = validate_scene_breakdown(breakdown_data)
    except ResourceContractError:
        raise
    except Exception as exc:
        raise ResourceContractError("movie decision chain is invalid") from exc
    if (breakdown.value["project_id"] != option_set.value["project_id"]
            or breakdown.digest != option_set.value["scene_breakdown_digest"]):
        raise ResourceContractError("scene breakdown binding mismatch")
    scenes = [item for item in breakdown.value["payload"]["ordered_scenes"]
              if item["scene_id"] == option_set.value["scene_id"]]
    options = [item for item in option_set.value["payload"]["options"]
               if item["option_id"] == raw["option_id"]]
    if len(scenes) != 1 or len(options) != 1:
        raise ResourceContractError("selected movie input is not present exactly once")
    return raw, decision_data, packet_data, option_set, breakdown, scenes[0], options[0]


def create_creative_decision_revision(
    decision_data: dict[str, Any], packet_data: dict[str, Any],
    option_set_data: dict[str, Any], breakdown_data: dict[str, Any], *,
    tenant_id: str, universe_id: str, revision: int = 1,
    status: str | None = None,
    previous_revision: AdmittedCreativeDecision | None = None,
) -> AdmittedCreativeDecision:
    raw, decision, packet, option_set, breakdown, scene, option = _authoritative_movie_inputs(
        decision_data, packet_data, option_set_data, breakdown_data)
    derived_status = "accepted" if raw["outcome"] == "accept" else "rejected"
    selected_status = status or derived_status
    scope = {"tenant_id": tenant_id, "universe_id": universe_id,
             "production_id": option_set.value["project_id"],
             "scene_id": option_set.value["scene_id"], "scope_kind": "production_scene"}
    value = {
        "schema_version": "1", "contract_identity": "creative_decision_revision",
        "contract_version": "1", "decision_id": "decision-" + "0" * 32,
        "revision": revision, "decision_kind": "scene_production_option_selection",
        "scope": scope, "status": selected_status,
        "semantic_payload": {
            "option_id": raw["option_id"], "option_content_digest": raw["option_content_digest"],
            "review_outcome": raw["outcome"],
            "reviewer_accountability_id": raw["reviewer_id"],
            "decision_record_digest": decision["payload"]["decision_record_digest"],
            "decision_complete_digest": decision["integrity"]["complete_result_sha256"],
            "review_packet_digest": packet["payload"]["review_packet_digest"],
            "review_packet_complete_digest": packet["integrity"]["complete_result_sha256"],
            "option_set_digest": option_set.digest,
            "option_set_complete_digest": option_set.value["integrity"]["complete_result_sha256"],
            "scene_breakdown_digest": breakdown.digest,
            "scene_breakdown_payload_digest": breakdown.value["integrity"]["payload_sha256"],
            "scene_content_digest": scene["scene_content_digest"],
        },
        "previous_revision": None,
        "dependencies": sorted([
            {"kind": "scene_breakdown", "identity": breakdown.value["result_family"],
             "digest": breakdown.digest},
            {"kind": "production_option_set", "identity": option_set.value["result_family"],
             "digest": option_set.digest},
            {"kind": "review_packet", "identity": packet["result_family"],
             "digest": packet["integrity"]["complete_result_sha256"]},
            {"kind": "review_decision", "identity": decision["result_family"],
             "digest": decision["integrity"]["complete_result_sha256"]},
        ], key=lambda item: item["kind"]),
        "evidence_references": sorted(set(
            list(scene["evidence_references"]) + list(option["evidence_references"]))),
        "limitations": DECISION_LIMITATIONS, "decision_sha256": "0" * 64,
    }
    value["decision_id"] = "decision-" + canonical_digest(
        creative_decision_identity_material(value))[:32]
    if previous_revision is not None:
        if not isinstance(previous_revision, AdmittedCreativeDecision):
            raise ResourceContractError("creative decision predecessor is not authoritative")
        checked = validate_creative_decision_revision(previous_revision.to_json_value())
        value["previous_revision"] = {key: checked.value[key] for key in (
            "decision_id", "revision", "decision_sha256")}
    value["decision_sha256"] = canonical_digest(creative_decision_seal_material(value))
    artifact = validate_creative_decision_revision(value)
    return _admit_creative_decision(artifact)


def create_canon_snapshot(*, decisions: list[AdmittedCreativeDecision],
                          snapshot_version: int) -> ValidatedResourceArtifact:
    if not decisions:
        raise ResourceContractError("canon snapshot requires a decision revision")
    if not all(isinstance(item, AdmittedCreativeDecision) for item in decisions):
        raise ResourceContractError("canon snapshot requires authoritative decision revisions")
    checked = [validate_creative_decision_revision(item.to_json_value()) for item in decisions]
    scope = {key: checked[0].value["scope"][key]
             for key in ("tenant_id", "universe_id", "production_id")}
    scope["scope_kind"] = "production"
    bindings = sorted(({
        "decision_id": item.value["decision_id"], "revision": item.value["revision"],
        "decision_sha256": item.value["decision_sha256"], "status": item.value["status"],
        "scene_id": item.value["scope"]["scene_id"],
    } for item in checked), key=lambda item: (item["decision_id"], item["revision"]))
    value = {
        "schema_version": "1", "contract_identity": "canon_snapshot",
        "contract_version": "1", "canon_snapshot_id": "canon-" + "0" * 32,
        "snapshot_version": snapshot_version, "scope": scope, "decisions": bindings,
        "limitations": CANON_LIMITATIONS, "canon_sha256": "0" * 64,
    }
    value["canon_snapshot_id"] = "canon-" + canonical_digest(
        canon_snapshot_identity_material(value))[:32]
    value["canon_sha256"] = canonical_digest(canon_snapshot_seal_material(value))
    return validate_canon_snapshot(value, decisions=decisions)


def bind_production_input_to_canon(
    decision_data: dict[str, Any], packet_data: dict[str, Any],
    option_set_data: dict[str, Any], breakdown_data: dict[str, Any], *,
    tenant_id: str, universe_id: str, decisions: list[AdmittedCreativeDecision],
    canon_snapshot: ValidatedResourceArtifact,
    previous_revision: AdmittedCreativeDecision | None = None,
) -> ValidatedResourceArtifact:
    raw, decision, packet, option_set, breakdown, scene, _ = _authoritative_movie_inputs(
        decision_data, packet_data, option_set_data, breakdown_data)
    if len(decisions) != 1:
        raise ResourceContractError("scene input binding requires exactly one decision revision")
    candidate = decisions[0]
    if not isinstance(candidate, AdmittedCreativeDecision):
        raise ResourceContractError("production binding requires an authoritative decision revision")
    expected = create_creative_decision_revision(
        decision_data, packet_data, option_set_data, breakdown_data,
        tenant_id=tenant_id, universe_id=universe_id, revision=candidate.value["revision"],
        status=candidate.value["status"], previous_revision=previous_revision)
    if candidate != expected:
        raise ResourceContractError("creative decision authoritative reconstruction mismatch")
    checked_canon = validate_canon_snapshot(canon_snapshot.to_json_value(), decisions=decisions)
    scope = {"tenant_id": tenant_id, "universe_id": universe_id,
             "production_id": option_set.value["project_id"],
             "scene_id": option_set.value["scene_id"], "scope_kind": "production_scene"}
    production_input = {
        "selected_option_id": raw["option_id"],
        "selected_option_content_digest": raw["option_content_digest"],
        "decision_complete_digest": decision["integrity"]["complete_result_sha256"],
        "review_packet_complete_digest": packet["integrity"]["complete_result_sha256"],
        "option_set_complete_digest": option_set.value["integrity"]["complete_result_sha256"],
        "scene_breakdown_digest": breakdown.digest,
        "scene_breakdown_payload_digest": breakdown.value["integrity"]["payload_sha256"],
        "scene_content_digest": scene["scene_content_digest"],
    }
    value = {
        "schema_version": "1", "contract_identity": "production_canon_binding",
        "contract_version": "1", "binding_id": "production-canon-binding-" + "0" * 32,
        "operation_identity": "bind_scene_shot_plan_input_to_exact_canon",
        "operation_version": "1", "scope": scope, "purpose": "scene_shot_plan_input",
        "canon_snapshot": {key: checked_canon.value[key] for key in (
            "canon_snapshot_id", "snapshot_version", "canon_sha256")},
        "decisions": thaw_json(checked_canon.value["decisions"]),
        "production_input": production_input, "limitations": BINDING_LIMITATIONS,
        "result_sha256": "0" * 64,
    }
    value["binding_id"] = "production-canon-binding-" + canonical_digest(
        production_canon_binding_identity_material(value))[:32]
    value["result_sha256"] = canonical_digest(production_canon_binding_seal_material(value))
    return validate_production_canon_binding(
        value, canon_snapshot=checked_canon, decisions=decisions,
        production_input=production_input, scope=scope)
