from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vss_movie_canon import (
    bind_production_input_to_canon,
    create_canon_snapshot,
    create_creative_decision_revision,
)
from vss_movie_contracts import MovieContractRegistry, ValidatedMovieArtifact
from vss_movie_contracts.errors import MovieContractError
from vss_movie_shot_plan import (
    admit_shot_plan_inputs,
    create_shot_cards,
    create_shot_plan_result,
    shot_plan_provider_view,
)
from vss_movie_storyboard import (
    admit_storyboard_inputs,
    create_frame_specifications,
    create_storyboard_result,
    storyboard_provider_view,
)
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json
from vss_resource_contracts import (
    ResourceContractError,
    ValidatedResourceArtifact,
    canon_snapshot_seal_material,
    creative_decision_seal_material,
    grounded_canon_snapshot_identity_material,
    grounded_creative_decision_identity_material,
    grounded_production_canon_binding_identity_material,
    production_canon_binding_seal_material,
    validate_grounded_canon_snapshot,
    validate_grounded_creative_decision_revision,
    validate_grounded_production_canon_binding,
    validate_production_visual_grounding_profile,
    validate_production_visual_grounding_review,
    visual_grounding_profile_seal_material,
    visual_grounding_review_seal_material,
)


DECISION_LIMITATIONS = [
    "inert_creative_decision", "production_owned_visual_grounding",
    "opaque_constraint_semantics", "not_production_approval", "not_runtime_authority",
    "not_provider_authority", "not_workflow_authority", "not_rights_authority",
    "exact_revision_only",
]
CANON_LIMITATIONS = [
    "inert_canon_snapshot", "not_mutable_global_truth", "production_owned_visual_grounding",
    "opaque_constraint_semantics", "not_production_approval", "not_runtime_authority",
    "not_workflow_authority", "not_rights_authority",
    "exact_decision_and_profile_revisions_only",
]
BINDING_LIMITATIONS = [
    "inert_production_input_binding", "production_owned_visual_grounding",
    "opaque_constraint_semantics", "not_production_approval", "not_runtime_authority",
    "not_provider_authority", "not_workflow_authority", "not_scheduling_authority",
    "not_regeneration_authority", "not_publication_authority", "no_storage_authority",
    "not_rights_authority", "exact_canon_decision_and_profile_revisions_only",
]
SHOT_LIMITATIONS = [
    "grounding_overlay_only", "base_shot_plan_remains_authoritative",
    "production_owned_visual_grounding", "opaque_constraint_semantics",
    "not_production_approval", "not_runtime_authority", "not_provider_authority",
]
STORYBOARD_LIMITATIONS = [
    "grounding_overlay_only", "base_storyboard_remains_authoritative",
    "production_owned_visual_grounding", "opaque_constraint_semantics", "not_a_render",
    "not_production_approval", "not_runtime_authority", "not_provider_authority",
]


def _reference(profile: ValidatedResourceArtifact) -> dict[str, Any]:
    return {key: profile.value[key] for key in (
        "profile_id", "revision", "profile_sha256", "mode")}


def create_production_visual_grounding_profile(
    *, profile_id: str, revision: int, tenant_id: str, universe_id: str,
    production_id: str, mode: str, groups: list[dict[str, Any]],
    reviewer_accountability_id: str, scene_ids: list[str] | None = None,
    character_ids: list[str] | None = None, uncertainty: list[str] | None = None,
    conflicts: list[str] | None = None, limitations: list[str] | None = None,
    evidence_references: list[str] | None = None, lifecycle: str = "active",
) -> ValidatedResourceArtifact:
    value = {
        "schema_version": "1", "contract_identity": "production_visual_grounding_profile",
        "contract_version": "1", "profile_id": profile_id, "revision": revision,
        "scope": {"tenant_id": tenant_id, "universe_id": universe_id,
                  "production_id": production_id},
        "applicability": {"scene_ids": sorted(scene_ids or []),
                          "character_ids": sorted(character_ids or [])},
        "mode": mode, "groups": sorted(groups, key=lambda item: item.get("ordinal", 0)),
        "uncertainty": sorted(uncertainty or []), "conflicts": sorted(conflicts or []),
        "limitations": sorted(limitations or [
            "production_owned_data", "opaque_constraint_semantics",
            "not_domain_truth", "not_provider_or_runtime_authority",
        ]),
        "evidence_references": sorted(evidence_references or []), "lifecycle": lifecycle,
        "reviewer_accountability_id": reviewer_accountability_id,
        "profile_sha256": "0" * 64,
    }
    value["profile_sha256"] = canonical_digest(visual_grounding_profile_seal_material(value))
    return validate_production_visual_grounding_profile(value)


def record_production_visual_grounding_review(
    *, generation: Any, candidate: Any, disposition: str, defects: list[dict[str, Any]],
    reviewer_accountability_id: str,
) -> ValidatedResourceArtifact:
    from vss_movie_controlled_generation import AdmittedControlledGeneration, AdmittedGeneratedCandidate
    from vss_movie_controlled_generation.contracts import validate_generation_request

    if type(generation) is not AdmittedControlledGeneration or type(candidate) is not AdmittedGeneratedCandidate:
        raise ResourceContractError("visual grounding review requires authoritative admitted evidence")
    request = validate_generation_request(generation.request_json())
    profile_data = generation.grounding_profile_json()
    if profile_data is None:
        raise ResourceContractError("visual grounding review requires a grounded generation admission")
    profile = validate_production_visual_grounding_profile(profile_data)
    candidate_data = candidate.candidate_json()
    if (request["contract_version"] != "3"
            or candidate_data["request_sha256"] != request["request_sha256"]
            or candidate_data["lineage"] != request["lineage"]
            or request["projection"]["visual_grounding_profile_sha256"]
            != profile.value["profile_sha256"]
            or request["projection"]["frame_grounding_sha256"]
            != request["lineage"]["storyboard_frame"]):
        raise ResourceContractError("visual grounding review authoritative binding mismatch")
    group_ids = {group["group_id"] for group in profile.value["groups"]}
    if any(defect.get("group_id") is not None and defect["group_id"] not in group_ids
           for defect in defects if isinstance(defect, dict)):
        raise ResourceContractError("visual grounding review defect group is absent from its bound profile")
    value = {
        "schema_version": "1", "contract_identity": "production_visual_grounding_review",
        "contract_version": "1", "review_id": "visual-grounding-review-" + "0" * 32,
        "candidate_sha256": candidate_data["candidate_sha256"],
        "frame_grounding_sha256": request["projection"]["frame_grounding_sha256"],
        "visual_grounding_profile_sha256": profile.value["profile_sha256"],
        "disposition": disposition,
        "defects": sorted(defects, key=lambda item: (item.get("defect_code", ""),
                                                     item.get("group_id") or "")),
        "reviewer_accountability_id": reviewer_accountability_id,
        "authority": {"profile_mutation": False, "prompt_edit": False,
                      "provider_execution": False, "runtime_execution": False,
                      "approval": False, "reservation": False, "regeneration": False},
        "limitations": ["accountability_evidence_only", "production_defined_defect_codes",
                        "not_truth_by_itself", "not_profile_mutation", "not_prompt_authority",
                        "not_provider_or_runtime_authority"],
        "review_sha256": "0" * 64,
    }
    value["review_id"] = "visual-grounding-review-" + canonical_digest({
        key: item for key, item in value.items() if key not in {"review_id", "review_sha256"}
    })[:32]
    value["review_sha256"] = canonical_digest(visual_grounding_review_seal_material(value))
    return validate_production_visual_grounding_review(value)


def _resolve_applicability(profile: ValidatedResourceArtifact, *, scope: dict[str, Any],
                           scene_id: str, declared_character_ids: list[str]) -> dict[str, Any]:
    value = profile.value
    expected_scope = {key: scope[key] for key in ("tenant_id", "universe_id", "production_id")}
    if thaw_json(value["scope"]) != expected_scope:
        raise ResourceContractError("visual grounding profile scope mismatch")
    scenes = set(value["applicability"]["scene_ids"])
    characters = set(value["applicability"]["character_ids"])
    declared = set(declared_character_ids)
    if scenes and scene_id not in scenes:
        raise ResourceContractError("visual grounding profile scene is not applicable")
    if not characters.issubset(declared):
        raise ResourceContractError("visual grounding profile character applicability mismatch")
    if (value["mode"] == "required"
            and (value["lifecycle"] != "active" or value["conflicts"] or not value["groups"])):
        raise ResourceContractError("required visual grounding is unavailable")
    material = {
        "scene_id": scene_id, "declared_character_ids": sorted(declared),
        "applicable_group_ids": [group["group_id"] for group in value["groups"]],
    }
    return {**material, "applicability_sha256": canonical_digest(material)}


def _constraint_material(profile: ValidatedResourceArtifact) -> dict[str, list[str]]:
    groups = profile.value["groups"]
    return {
        "applicable_group_ids": [item["group_id"] for item in groups],
        "positive_constraints": [value for item in groups for value in item["positive_constraints"]],
        "negative_constraints": [value for item in groups for value in item["negative_constraints"]],
        "explicit_unknowns": ([value for item in groups for value in item["explicit_unknowns"]]
                              + list(profile.value["uncertainty"])),
        "limitations": ([value for item in groups for value in item["limitations"]]
                        + list(profile.value["limitations"])),
    }


def _movie_overlay(value: Any, identity: str, seal_name: str) -> ValidatedMovieArtifact:
    if not isinstance(value, dict):
        raise MovieContractError("visual grounding overlay must be an object")
    errors = list(MovieContractRegistry.built_in().iter_errors(identity, value))
    if errors:
        raise MovieContractError("visual grounding overlay does not match its contract")
    semantic = {
        key: item for key, item in value.items()
        if key not in {"schema_version", "result_family", "result_version", "project_id",
                       "scene_id", "integrity"}
    }
    if value["integrity"]["payload_sha256"] != canonical_digest(semantic):
        raise MovieContractError("visual grounding overlay payload seal mismatch")
    complete = {**value, "integrity": {"payload_sha256": value["integrity"]["payload_sha256"]}}
    if value["integrity"][seal_name] != canonical_digest(complete):
        raise MovieContractError("visual grounding overlay complete seal mismatch")
    return ValidatedMovieArtifact._create(value)


def validate_grounded_scene_shot_plan(value: Any) -> ValidatedMovieArtifact:
    return _movie_overlay(value, "scene_shot_plan_draft/2", "complete_result_sha256")


def validate_grounded_scene_storyboard(value: Any) -> ValidatedMovieArtifact:
    return _movie_overlay(value, "scene_storyboard_specification/2", "complete_result_sha256")


@dataclass(frozen=True)
class GroundedMovieRoute:
    profile: ValidatedResourceArtifact
    creative_decision: ValidatedResourceArtifact
    canon_snapshot: ValidatedResourceArtifact
    canon_binding: ValidatedResourceArtifact
    shot_plan: ValidatedMovieArtifact
    storyboard: ValidatedMovieArtifact


def create_grounded_movie_route(
    decision_data: dict[str, Any], packet_data: dict[str, Any], option_set_data: dict[str, Any],
    breakdown_data: dict[str, Any], base_creative_decision_data: dict[str, Any],
    base_canon_snapshot_data: dict[str, Any], base_canon_binding_data: dict[str, Any],
    base_shot_plan_data: dict[str, Any], base_storyboard_data: dict[str, Any], *,
    profile_data: dict[str, Any], environment: str = "development",
) -> GroundedMovieRoute:
    if environment != "development":
        raise ResourceContractError("visual grounding route is development-only")
    profile = validate_production_visual_grounding_profile(profile_data)
    base_scope = base_creative_decision_data.get("scope", {})
    tenant_id, universe_id = base_scope.get("tenant_id"), base_scope.get("universe_id")
    base_decision = create_creative_decision_revision(
        decision_data, packet_data, option_set_data, breakdown_data,
        tenant_id=tenant_id, universe_id=universe_id,
        revision=base_creative_decision_data.get("revision", 0),
        status=base_creative_decision_data.get("status"),
    )
    if base_decision.to_json_value() != base_creative_decision_data:
        raise ResourceContractError("base creative decision reconstruction mismatch")
    base_canon = create_canon_snapshot(
        decisions=[base_decision], snapshot_version=base_canon_snapshot_data.get("snapshot_version", 0))
    if base_canon.to_json_value() != base_canon_snapshot_data:
        raise ResourceContractError("base canon reconstruction mismatch")
    base_binding = bind_production_input_to_canon(
        decision_data, packet_data, option_set_data, breakdown_data,
        tenant_id=tenant_id, universe_id=universe_id, decisions=[base_decision],
        canon_snapshot=base_canon,
    )
    if base_binding.to_json_value() != base_canon_binding_data:
        raise ResourceContractError("base canon binding reconstruction mismatch")

    scenes = [item for item in breakdown_data["payload"]["ordered_scenes"]
              if item["scene_id"] == base_scope.get("scene_id")]
    if len(scenes) != 1:
        raise ResourceContractError("visual grounding scene is not present exactly once")
    applicability = _resolve_applicability(
        profile, scope=base_scope, scene_id=scenes[0]["scene_id"],
        declared_character_ids=scenes[0]["declared_characters"],
    )

    grounding = _reference(profile)
    grounded_decision_value = {
        "schema_version": "1", "contract_identity": "creative_decision_revision",
        "contract_version": "2", "decision_id": "decision-" + "0" * 32,
        "revision": base_decision.value["revision"],
        "decision_kind": "scene_production_option_selection_with_visual_grounding",
        "scope": thaw_json(base_decision.value["scope"]), "status": "accepted",
        "base_decision": {key: base_decision.value[key] for key in (
            "decision_id", "revision", "decision_sha256")},
        "visual_grounding": grounding, "limitations": DECISION_LIMITATIONS,
        "decision_sha256": "0" * 64,
    }
    grounded_decision_value["decision_id"] = "decision-" + canonical_digest(
        grounded_creative_decision_identity_material(grounded_decision_value))[:32]
    grounded_decision_value["decision_sha256"] = canonical_digest(
        creative_decision_seal_material(grounded_decision_value))
    grounded_decision = validate_grounded_creative_decision_revision(
        grounded_decision_value, base_decision=base_decision, profile=profile)

    grounded_canon_value = {
        "schema_version": "1", "contract_identity": "canon_snapshot", "contract_version": "2",
        "canon_snapshot_id": "canon-" + "0" * 32,
        "snapshot_version": base_canon.value["snapshot_version"],
        "scope": {"tenant_id": tenant_id, "universe_id": universe_id,
                  "production_id": base_scope["production_id"], "scope_kind": "production"},
        "base_canon_snapshot": {key: base_canon.value[key] for key in (
            "canon_snapshot_id", "snapshot_version", "canon_sha256")},
        "decision": {"decision_id": grounded_decision.value["decision_id"],
                     "revision": grounded_decision.value["revision"],
                     "decision_sha256": grounded_decision.value["decision_sha256"],
                     "scene_id": base_scope["scene_id"]},
        "visual_grounding": grounding, "limitations": CANON_LIMITATIONS,
        "canon_sha256": "0" * 64,
    }
    grounded_canon_value["canon_snapshot_id"] = "canon-" + canonical_digest(
        grounded_canon_snapshot_identity_material(grounded_canon_value))[:32]
    grounded_canon_value["canon_sha256"] = canonical_digest(
        canon_snapshot_seal_material(grounded_canon_value))
    grounded_canon = validate_grounded_canon_snapshot(
        grounded_canon_value, base_canon_snapshot=base_canon, decision=grounded_decision,
        profile=profile)

    grounded_binding_value = {
        "schema_version": "1", "contract_identity": "production_canon_binding",
        "contract_version": "2", "binding_id": "production-canon-binding-" + "0" * 32,
        "operation_identity": "bind_scene_visual_grounding_to_exact_canon",
        "operation_version": "1", "scope": thaw_json(base_binding.value["scope"]),
        "purpose": "scene_visual_grounding_input",
        "base_binding": {key: base_binding.value[key] for key in ("binding_id", "result_sha256")},
        "canon_snapshot": {key: grounded_canon.value[key] for key in (
            "canon_snapshot_id", "snapshot_version", "canon_sha256")},
        "decision": {key: grounded_decision.value[key] for key in (
            "decision_id", "revision", "decision_sha256")},
        "visual_grounding": grounding, "applicability": applicability,
        "limitations": BINDING_LIMITATIONS, "result_sha256": "0" * 64,
    }
    grounded_binding_value["binding_id"] = "production-canon-binding-" + canonical_digest(
        grounded_production_canon_binding_identity_material(grounded_binding_value))[:32]
    grounded_binding_value["result_sha256"] = canonical_digest(
        production_canon_binding_seal_material(grounded_binding_value))
    grounded_binding = validate_grounded_production_canon_binding(
        grounded_binding_value, base_binding=base_binding, canon_snapshot=grounded_canon,
        decision=grounded_decision, profile=profile, applicability=applicability)

    shot_task, shot_decision, shot_packet, shot_options, shot_breakdown, shot_scene = admit_shot_plan_inputs(
        decision_data, packet_data, option_set_data, breakdown_data,
        request_id=base_shot_plan_data.get("request_id", ""),
        correlation_id=base_shot_plan_data.get("correlation_id", ""), environment=environment)
    shot_view = shot_plan_provider_view(shot_task, shot_decision, shot_options, shot_scene)
    expected_base_shot = create_shot_plan_result(
        shot_task, shot_decision, shot_packet, shot_options, shot_breakdown, shot_scene,
        create_shot_cards(shot_view))
    if expected_base_shot != base_shot_plan_data:
        raise MovieContractError("base shot plan reconstruction mismatch")
    constraints = _constraint_material(profile)
    grounded_shots = []
    for card in base_shot_plan_data["payload"]["ordered_shots"]:
        material = {"shot_id": card["shot_id"], "shot_card_digest": card["shot_card_digest"],
                    **constraints}
        grounded_shots.append({**material, "shot_grounding_sha256": canonical_digest(material)})
    shot_semantic = {
        "base_shot_plan_complete_digest": base_shot_plan_data["integrity"]["complete_result_sha256"],
        "production_canon_binding_digest": grounded_binding.digest,
        "visual_grounding_profile_digest": profile.digest,
        "ordered_shot_grounding": grounded_shots, "limitations": SHOT_LIMITATIONS,
    }
    shot_value = {
        "schema_version": "1", "result_family": "scene_shot_plan_draft", "result_version": "2",
        "project_id": base_shot_plan_data["project_id"], "scene_id": base_shot_plan_data["scene_id"],
        **shot_semantic, "integrity": {"payload_sha256": canonical_digest(shot_semantic),
                                      "complete_result_sha256": "0" * 64},
    }
    shot_value["integrity"]["complete_result_sha256"] = canonical_digest(
        {**shot_value, "integrity": {"payload_sha256": shot_value["integrity"]["payload_sha256"]}})
    grounded_shot = validate_grounded_scene_shot_plan(shot_value)

    (story_task, story_decision, story_packet, story_options, story_breakdown,
     story_scene, validated_base_shot) = admit_storyboard_inputs(
        decision_data, packet_data, option_set_data, breakdown_data, base_shot_plan_data,
        request_id=base_storyboard_data.get("request_id", ""),
        correlation_id=base_storyboard_data.get("correlation_id", ""), environment=environment)
    story_view = storyboard_provider_view(story_task, story_options, story_scene, validated_base_shot)
    expected_base_story = create_storyboard_result(
        story_task, story_decision, story_packet, story_options, story_breakdown, story_scene,
        validated_base_shot, create_frame_specifications(story_view))
    if expected_base_story != base_storyboard_data:
        raise MovieContractError("base storyboard reconstruction mismatch")
    shots_by_id = {item["shot_id"]: item for item in grounded_shots}
    grounded_frames = []
    for frame in base_storyboard_data["payload"]["ordered_frames"]:
        shot = shots_by_id.get(frame["source_shot_id"])
        if shot is None:
            raise MovieContractError("grounded frame source shot is unavailable")
        material = {
            "frame_id": frame["frame_id"],
            "frame_specification_digest": frame["frame_specification_digest"],
            "source_shot_id": frame["source_shot_id"],
            "shot_grounding_sha256": shot["shot_grounding_sha256"],
            **constraints,
        }
        grounded_frames.append({**material, "frame_grounding_sha256": canonical_digest(material)})
    storyboard_semantic = {
        "base_storyboard_complete_digest": base_storyboard_data["integrity"]["complete_result_sha256"],
        "grounded_shot_plan_complete_digest": grounded_shot.value["integrity"]["complete_result_sha256"],
        "visual_grounding_profile_digest": profile.digest,
        "ordered_frame_grounding": grounded_frames, "limitations": STORYBOARD_LIMITATIONS,
    }
    storyboard_value = {
        "schema_version": "1", "result_family": "scene_storyboard_specification",
        "result_version": "2", "project_id": base_storyboard_data["project_id"],
        "scene_id": base_storyboard_data["scene_id"], **storyboard_semantic,
        "integrity": {"payload_sha256": canonical_digest(storyboard_semantic),
                      "complete_result_sha256": "0" * 64},
    }
    storyboard_value["integrity"]["complete_result_sha256"] = canonical_digest(
        {**storyboard_value,
         "integrity": {"payload_sha256": storyboard_value["integrity"]["payload_sha256"]}})
    grounded_storyboard = validate_grounded_scene_storyboard(storyboard_value)
    return GroundedMovieRoute(profile, grounded_decision, grounded_canon, grounded_binding,
                              grounded_shot, grounded_storyboard)


def admit_grounded_movie_route(*args: Any, grounded_creative_decision_data: dict[str, Any],
                               grounded_canon_snapshot_data: dict[str, Any],
                               grounded_canon_binding_data: dict[str, Any],
                               grounded_shot_plan_data: dict[str, Any],
                               grounded_storyboard_data: dict[str, Any], **kwargs: Any) -> GroundedMovieRoute:
    route = create_grounded_movie_route(*args, **kwargs)
    supplied = (
        grounded_creative_decision_data, grounded_canon_snapshot_data,
        grounded_canon_binding_data, grounded_shot_plan_data, grounded_storyboard_data,
    )
    expected = (
        route.creative_decision.to_json_value(), route.canon_snapshot.to_json_value(),
        route.canon_binding.to_json_value(), route.shot_plan.to_json_value(),
        route.storyboard.to_json_value(),
    )
    if supplied != expected:
        raise ResourceContractError("grounded route authoritative reconstruction mismatch")
    return route
