"""Inert, deterministic binding of one cataloged storyboard asset to one shot."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator

from vss_movie_contracts import validate_scene_shot_plan_draft, validate_scene_storyboard_specification
from vss_movie_contracts.errors import MovieContractError
from vss_movie_shot_plan import admit_shot_plan_inputs
from vss_movie_storyboard.service import admit_storyboard_inputs
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import ResourceContractError

from .asset_admission import _valid_selected_candidate
from .asset_catalog import GroundedStoryboardAssetCatalogEntry, _AUTHORITY as CATALOG_AUTHORITY, _LIMITATIONS as CATALOG_LIMITATIONS

_KEY = object()
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SHOT_ID = re.compile(r"^shot-[0-9a-f]{24}$")
_ACCOUNTABILITY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@/-]{0,127}$")

AUTHORITY = {
    "binding_approval": False, "production_use": False, "production_approval": False,
    "final_shot_selection": False, "provider_execution": False, "runtime_execution": False,
    "generation": False, "regeneration": False, "publication": False, "export": False,
    "scheduling": False, "workflow_activation": False, "canon_decision": False,
    "rights_decision": False,
}
LIMITATIONS = [
    "single_shot_visual_basis_reference_only", "no_media_copying_or_storage",
    "not_production_or_generation_authority", "not_provider_or_runtime_authority",
    "not_publication_export_scheduling_or_workflow_authority",
    "not_canon_or_rights_authority",
]


@dataclass(frozen=True, slots=True, init=False)
class GroundedStoryboardShotBinding:
    _value: Any

    def __init__(self, key: object, value: dict[str, Any]):
        if key is not _KEY:
            raise TypeError("shot binding requires authoritative construction")
        object.__setattr__(self, "_value", freeze_json(value))

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self._value)


def _digest(value: Any) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _checked_catalog(catalog: Any) -> dict[str, Any]:
    if type(catalog) is not GroundedStoryboardAssetCatalogEntry:
        raise ResourceContractError("shot binding requires an integrity-verified M10.5 catalog entry")
    value = catalog.to_json_value()
    admission = value.get("admission")
    if (set(value) != {"schema_version", "contract_identity", "contract_version", "asset_id", "asset_revision",
                       "registration_status", "admission", "authority", "limitations", "asset_sha256"}
            or value["schema_version"] != "1"
            or value["contract_identity"] != "grounded_storyboard_asset_catalog_entry"
            or value["contract_version"] != "1" or value["asset_revision"] != 1
            or value["registration_status"] != "registered_metadata_only"
            or not isinstance(admission, dict)
            or value["asset_sha256"] != canonical_digest({**value, "asset_sha256": "0" * 64})
            or not _digest(admission.get("admission_sha256"))
            or admission["admission_sha256"] != canonical_digest({**admission, "admission_sha256": "0" * 64})
            or value["asset_id"] != "asset-" + canonical_digest({"kind": "grounded_storyboard_asset",
                                                                    "admission_sha256": admission["admission_sha256"]})[:32]):
        raise ResourceContractError("catalog entry seal or identity mismatch")
    if value["authority"] != CATALOG_AUTHORITY or value["limitations"] != CATALOG_LIMITATIONS:
        raise ResourceContractError("catalog entry authority or limitation mismatch")
    candidate = admission.get("admitted_candidate")
    if not _valid_selected_candidate(candidate):
        raise ResourceContractError("catalog entry admission provenance is invalid")
    return value


def bind_grounded_storyboard_asset_to_shot(
    catalog: GroundedStoryboardAssetCatalogEntry, storyboard_data: Any,
    decision_data: Any, packet_data: Any, option_set_data: Any, breakdown_data: Any,
    shot_plan_data: Any, *, shot_id: str, approver_accountability_id: str, rationale: str,
    environment: str = "development", grounded_shot_plan_data: Any = None,
    grounded_storyboard_data: Any = None,
) -> GroundedStoryboardShotBinding:
    """Create one sealed reference binding; this function never reads or copies media."""
    catalog_value = _checked_catalog(catalog)
    if not isinstance(shot_id, str) or not _SHOT_ID.fullmatch(shot_id):
        raise ResourceContractError("shot binding shot identity is invalid")
    if (not isinstance(approver_accountability_id, str)
            or _ACCOUNTABILITY_ID.fullmatch(approver_accountability_id) is None):
        raise ResourceContractError("shot binding approver accountability identifier is invalid")
    if not isinstance(rationale, str) or not 1 <= len(rationale) <= 1024 or not rationale.strip():
        raise ResourceContractError("shot binding rationale is invalid")
    try:
        shot_task, decision, packet, option_set, breakdown, scene = admit_shot_plan_inputs(
            decision_data, packet_data, option_set_data, breakdown_data,
            request_id=shot_plan_data.get("request_id", ""),
            correlation_id=shot_plan_data.get("correlation_id", ""), environment=environment,
        )
        shot_plan = validate_scene_shot_plan_draft(
            shot_plan_data, task=shot_task, decision=decision, packet=packet,
            option_set=option_set, breakdown=breakdown,
        )
        storyboard_task, checked_decision, checked_packet, checked_options, checked_breakdown, _scene, checked_shot_plan = admit_storyboard_inputs(
            decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
            request_id=storyboard_data.get("request_id", ""), correlation_id=storyboard_data.get("correlation_id", ""),
            environment=environment,
        )
        storyboard = validate_scene_storyboard_specification(
            storyboard_data, task=storyboard_task, decision=checked_decision, packet=checked_packet,
            option_set=checked_options, breakdown=checked_breakdown, shot_plan=checked_shot_plan,
        )
        if (grounded_shot_plan_data is None) != (grounded_storyboard_data is None):
            raise ResourceContractError("grounded shot-plan and storyboard must be supplied together")
        grounded_shot = grounded_story = None
        if grounded_shot_plan_data is not None:
            from vss_movie_visual_grounding import validate_grounded_scene_shot_plan, validate_grounded_scene_storyboard
            grounded_shot = validate_grounded_scene_shot_plan(grounded_shot_plan_data)
            grounded_story = validate_grounded_scene_storyboard(grounded_storyboard_data)
            if (grounded_shot.value["base_shot_plan_complete_digest"] != shot_plan.value["integrity"]["complete_result_sha256"]
                    or grounded_story.value["grounded_shot_plan_complete_digest"] != grounded_shot.value["integrity"]["complete_result_sha256"]):
                raise ResourceContractError("grounded shot-plan lineage is stale or mismatched")
    except (MovieContractError, KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ResourceContractError("shot binding upstream evidence is invalid") from exc
    if shot_plan.digest != checked_shot_plan.digest:
        raise ResourceContractError("shot binding shot-plan substitution detected")
    cards = [card for card in shot_plan.value["payload"]["ordered_shots"] if card["shot_id"] == shot_id]
    if len(cards) != 1:
        raise ResourceContractError("shot binding requires exactly one existing authoritative shot")
    card = thaw_json(cards[0])
    candidate = catalog_value["admission"]["admitted_candidate"]
    scope = candidate["scope"]
    if (scope["project_id"] != shot_plan.value["project_id"]
            or scope["scene_id"] != shot_plan.value["scene_id"]):
        raise ResourceContractError("shot binding catalog scope does not match shot plan")
    frames = [frame for frame in storyboard.value["payload"]["ordered_frames"] if frame["frame_id"] == scope["frame_id"]]
    if len(frames) != 1 or frames[0]["source_ordinal"] != card["source_ordinal"]:
        raise ResourceContractError("shot binding visual evidence is for the wrong shot")
    if grounded_shot is not None:
        grounded_cards = [item for item in grounded_shot.value["ordered_shot_grounding"] if item["shot_id"] == shot_id]
        grounded_frames = [item for item in grounded_story.value["ordered_frame_grounding"] if item["frame_id"] == scope["frame_id"]]
        if (len(grounded_cards) != 1 or grounded_cards[0]["shot_card_digest"] != card["shot_card_digest"]
                or len(grounded_frames) != 1 or grounded_frames[0]["source_shot_id"] != shot_id
                or grounded_frames[0]["frame_grounding_sha256"] != candidate["frame_grounding_sha256"]):
            raise ResourceContractError("shot binding grounded evidence is for the wrong shot")
    lineage = candidate["source_repository_lineage"]
    expected_shot_lineage = grounded_shot.digest if grounded_shot is not None else shot_plan.digest
    expected_story_lineage = grounded_story.digest if grounded_story is not None else storyboard.digest
    if lineage["shot_plan_draft"] != expected_shot_lineage or lineage["storyboard_specification"] != expected_story_lineage:
        raise ResourceContractError("shot binding provenance is stale or mismatched")
    value = {
        "schema_version": "1", "contract_identity": "grounded_storyboard_shot_binding", "contract_version": "1",
        "binding_status": "sealed_visual_basis_reference_only", "asset_id": catalog_value["asset_id"],
        "asset_sha256": catalog_value["asset_sha256"], "admission_sha256": catalog_value["admission"]["admission_sha256"],
        "project_id": scope["project_id"], "scene_id": scope["scene_id"], "shot_id": shot_id,
        "shot_plan_digest": shot_plan.digest, "shot_plan_complete_digest": shot_plan.value["integrity"]["complete_result_sha256"],
        "shot_card_digest": card["shot_card_digest"], "frame_id": scope["frame_id"],
        "frame_grounding_sha256": candidate["frame_grounding_sha256"], "source_repository_lineage": lineage,
        "approver_accountability_id": approver_accountability_id, "rationale": rationale,
        "authority": dict(AUTHORITY), "limitations": list(LIMITATIONS), "binding_sha256": "0" * 64,
    }
    value["binding_sha256"] = canonical_digest(value)
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "grounded-storyboard-shot-binding-v1.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ResourceContractError("shot binding contract validation failed")
    return GroundedStoryboardShotBinding(_KEY, value)
