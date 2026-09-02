"""Deterministic, inert collection of authoritative M10.6 shot bindings."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import ResourceContractError

from .shot_binding import GroundedStoryboardShotBinding, AUTHORITY as BINDING_AUTHORITY, LIMITATIONS as BINDING_LIMITATIONS

AUTHORITY = {"set_approval": False, "production_use": False, "production_approval": False,
             "final_shot_selection": False, "provider_execution": False, "runtime_execution": False,
             "generation": False, "regeneration": False, "publication": False, "export": False,
             "scheduling": False, "workflow_activation": False, "canon_decision": False,
             "rights_decision": False}
LIMITATIONS = ["ordered_multi_shot_visual_basis_reference_only", "no_media_copying_or_storage",
               "not_motion_or_video_generation", "not_production_or_generation_authority",
               "not_provider_or_runtime_authority", "not_publication_export_scheduling_or_workflow_authority",
               "not_canon_or_rights_authority"]


@dataclass(frozen=True, slots=True, init=False)
class SceneVisualProductionSet:
    _value: Any

    def __init__(self, key: object, value: dict[str, Any]):
        if key is not _KEY:
            raise TypeError("visual production set requires authoritative construction")
        object.__setattr__(self, "_value", freeze_json(value))

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self._value)


_KEY = object()


def _schema() -> dict[str, Any]:
    return json.loads((Path(__file__).resolve().parents[2] / "schemas/scene-visual-production-set-v1.schema.json").read_text())


def _checked_binding(binding: Any) -> dict[str, Any]:
    if type(binding) is not GroundedStoryboardShotBinding:
        raise ResourceContractError("visual production set requires authoritative M10.6 shot bindings")
    value = binding.to_json_value()
    if (value.get("authority") != BINDING_AUTHORITY or value.get("limitations") != BINDING_LIMITATIONS
            or value.get("binding_sha256") != canonical_digest({**value, "binding_sha256": "0" * 64})):
        raise ResourceContractError("shot binding integrity or authority mismatch")
    if list(Draft202012Validator(json.loads((Path(__file__).resolve().parents[2] / "schemas/grounded-storyboard-shot-binding-v1.schema.json").read_text())).iter_errors(value)):
        raise ResourceContractError("shot binding contract is invalid")
    return value


def _ordered_plan(plan: Any) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
    if not isinstance(plan, dict) or plan.get("result_family") != "scene_shot_plan_draft":
        raise ResourceContractError("visual production set requires an authoritative shot plan")
    if plan.get("result_version") == "1":
        ordered = plan.get("payload", {}).get("ordered_shots")
        if (not isinstance(ordered, list) or plan.get("integrity", {}).get("payload_sha256") != canonical_digest(plan["payload"])
                or plan.get("payload", {}).get("shot_plan_digest") != canonical_digest({**plan["payload"], "shot_plan_digest": None})):
            raise ResourceContractError("shot plan integrity is invalid")
    elif plan.get("result_version") == "2":
        ordered = plan.get("ordered_shot_grounding")
        semantic = {key: item for key, item in plan.items() if key not in {"schema_version", "result_family", "result_version", "project_id", "scene_id", "integrity"}}
        if (not isinstance(ordered, list) or plan.get("integrity", {}).get("payload_sha256") != canonical_digest(semantic)):
            raise ResourceContractError("grounded shot plan integrity is invalid")
    else:
        raise ResourceContractError("unsupported shot plan version")
    complete = plan.get("integrity", {}).get("complete_result_sha256")
    expected_complete = canonical_digest({**plan, "integrity": {"payload_sha256": plan["integrity"]["payload_sha256"]}})
    if complete != expected_complete or len(ordered) > 16 or len({item.get("shot_id") for item in ordered}) != len(ordered):
        raise ResourceContractError("shot plan complete integrity is invalid")
    return plan, ordered, canonical_digest(plan), complete


def create_scene_visual_production_set(bindings: list[GroundedStoryboardShotBinding], shot_plan_data: Any, *,
                                       approver_accountability_id: str, rationale: str) -> SceneVisualProductionSet:
    if type(bindings) is not list or not 2 <= len(bindings) <= 16:
        raise ResourceContractError("visual production set requires two to sixteen shot bindings")
    if not isinstance(approver_accountability_id, str) or not approver_accountability_id.strip() or len(approver_accountability_id) > 128:
        raise ResourceContractError("visual production set approver is invalid")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 1024:
        raise ResourceContractError("visual production set rationale is invalid")
    plan, ordered, plan_digest, plan_complete = _ordered_plan(shot_plan_data)
    ordered_ids = [item["shot_id"] for item in ordered]
    values = [_checked_binding(binding) for binding in bindings]
    if [value["shot_id"] for value in values] != ordered_ids:
        raise ResourceContractError("shot bindings are missing, duplicated, stale, or reordered")
    if len({value["shot_id"] for value in values}) != len(values):
        raise ResourceContractError("duplicate shot binding")
    if any(value["shot_card_digest"] != item.get("shot_card_digest")
           for value, item in zip(values, ordered)):
        raise ResourceContractError("shot binding does not match the authoritative shot card")
    if any(value["project_id"] != plan["project_id"] or value["scene_id"] != plan["scene_id"]
           or value["shot_plan_digest"] != plan_digest or value["shot_plan_complete_digest"] != plan_complete
           for value in values):
        raise ResourceContractError("shot binding project, scene, or shot-plan lineage mismatch")
    refs = [{key: value[key] for key in ("shot_id", "binding_sha256", "asset_id", "asset_sha256", "shot_card_digest", "frame_id", "frame_grounding_sha256", "source_repository_lineage")} for value in values]
    value = {"schema_version": "1", "contract_identity": "scene_visual_production_set", "contract_version": "1",
             "set_id": "scene-visual-set-" + canonical_digest({"project_id": plan["project_id"], "scene_id": plan["scene_id"], "shot_plan_complete_digest": plan_complete, "bindings": refs})[:32],
             "set_status": "sealed_ordered_visual_basis_reference_only", "project_id": plan["project_id"], "scene_id": plan["scene_id"],
             "shot_plan_digest": plan_digest, "shot_plan_complete_digest": plan_complete, "ordered_shot_bindings": refs,
             "approver_accountability_id": approver_accountability_id, "rationale": rationale,
             "authority": dict(AUTHORITY), "limitations": list(LIMITATIONS), "set_sha256": "0" * 64}
    value["set_sha256"] = canonical_digest(value)
    if list(Draft202012Validator(_schema()).iter_errors(value)):
        raise ResourceContractError("visual production set contract validation failed")
    return SceneVisualProductionSet(_KEY, value)


def validate_scene_visual_production_set(value: Any, shot_plan_data: Any, bindings: list[GroundedStoryboardShotBinding]) -> dict[str, Any]:
    if type(value) is not SceneVisualProductionSet:
        raise ResourceContractError("visual production set requires authoritative construction")
    raw = value.to_json_value()
    expected = create_scene_visual_production_set(bindings, shot_plan_data,
        approver_accountability_id=raw.get("approver_accountability_id", ""),
        rationale=raw.get("rationale", "")).to_json_value()
    if raw != expected:
        raise ResourceContractError("visual production set substitution or seal mismatch")
    return raw
