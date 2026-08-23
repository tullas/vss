from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vss_movie_contracts import ValidatedMovieArtifact, validate_scene_shot_plan_draft
from vss_movie_contracts.errors import MovieContractError
from vss_movie_shot_plan import admit_shot_plan_inputs
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json


AUTHORITY_BOUNDARY = {
    "scope": "specification_only", "production_approval": False,
    "final_frame_selection": False, "production_plan_authority": False,
    "scheduling_authority": False, "workflow_activation": False,
    "capability_grant": False, "provider_execution_authority": False,
    "runtime_execution_authority": False, "media_generation_authority": False,
}
LIMITATIONS = (
    "This artifact is an inert provider-neutral storyboard specification for human inspection.",
    "It does not approve production, select final frames, invoke an image provider, or generate media.",
    "Unspecified appearance, blocking, set dressing, color, lens, and rendering details require human determination.",
)


@dataclass(frozen=True, slots=True)
class StoryboardProviderView:
    project_id: str
    scene_id: str
    option_id: str
    option_profile: str
    approach_category: str
    characters: tuple[str, ...]
    locations: tuple[str, ...]
    time_indicators: tuple[str, ...]
    events: tuple[Any, ...]
    observations: tuple[Any, ...]
    shots: tuple[Any, ...]
    knowledge_bindings: tuple[Any, ...]
    knowledge_influence: Any
    provider_visible_digest: str


def _validated_chain(decision_data: Any, packet_data: Any, option_set_data: Any,
                     breakdown_data: Any, shot_plan_data: Any, environment: str):
    if environment != "development":
        raise MovieContractError("storyboard specification is development-only")
    if not isinstance(shot_plan_data, dict):
        raise MovieContractError("storyboard shot-plan input must be an object")
    shot_task, decision, packet, option_set, breakdown, scene = admit_shot_plan_inputs(
        decision_data, packet_data, option_set_data, breakdown_data,
        request_id=shot_plan_data.get("request_id", ""),
        correlation_id=shot_plan_data.get("correlation_id", ""), environment=environment,
    )
    shot_plan = validate_scene_shot_plan_draft(
        shot_plan_data, task=shot_task, decision=decision, packet=packet,
        option_set=option_set, breakdown=breakdown,
    )
    return decision, packet, option_set, breakdown, scene, shot_plan


def create_storyboard_task(decision: ValidatedMovieArtifact, packet: ValidatedMovieArtifact,
                           option_set: ValidatedMovieArtifact, breakdown: ValidatedMovieArtifact,
                           shot_plan: ValidatedMovieArtifact, *, request_id: str,
                           correlation_id: str, environment: str = "development"):
    from vss_movie_contracts import validate_scene_storyboard_task
    selected = decision.value["payload"]["decisions"][0]
    value = {
        "schema_version": "1", "task_identity": "create_scene_storyboard_specification",
        "task_version": "1", "request_id": request_id, "correlation_id": correlation_id,
        "project_id": decision.value["project_id"], "scene_id": decision.value["scene_id"],
        "environment": environment, "purpose": "scene_storyboard_specification_local_development",
        "expected_result_family": "scene_storyboard_specification", "expected_result_version": "1",
        "decision_digest": decision.digest,
        "decision_complete_digest": decision.value["integrity"]["complete_result_sha256"],
        "review_packet_digest": packet.value["payload"]["review_packet_digest"],
        "review_packet_complete_digest": packet.value["integrity"]["complete_result_sha256"],
        "option_set_digest": option_set.digest,
        "option_set_complete_digest": option_set.value["integrity"]["complete_result_sha256"],
        "selected_option_id": selected["option_id"],
        "selected_option_content_digest": selected["option_content_digest"],
        "scene_breakdown_digest": breakdown.digest,
        "scene_breakdown_payload_digest": breakdown.value["integrity"]["payload_sha256"],
        "shot_plan_digest": shot_plan.digest,
        "shot_plan_complete_digest": shot_plan.value["integrity"]["complete_result_sha256"],
        "shot_plan_semantic_digest": shot_plan.value["payload"]["shot_plan_digest"],
        "bounds": {"maximum_frames": 3, "maximum_result_bytes": 131072},
        "lifecycle": "active", "task_content_digest": "0" * 64,
    }
    value["task_content_digest"] = canonical_digest({k: v for k, v in value.items() if k != "task_content_digest"})
    return validate_scene_storyboard_task(
        value, decision=decision, packet=packet, option_set=option_set,
        breakdown=breakdown, shot_plan=shot_plan,
    )


def admit_storyboard_inputs(decision_data: Any, packet_data: Any, option_set_data: Any,
                            breakdown_data: Any, shot_plan_data: Any, *, request_id: str,
                            correlation_id: str, environment: str = "development"):
    chain = _validated_chain(decision_data, packet_data, option_set_data, breakdown_data,
                             shot_plan_data, environment)
    decision, packet, option_set, breakdown, scene, shot_plan = chain
    task = create_storyboard_task(
        decision, packet, option_set, breakdown, shot_plan, request_id=request_id,
        correlation_id=correlation_id, environment=environment,
    )
    return task, decision, packet, option_set, breakdown, scene, shot_plan


def storyboard_provider_view(task, option_set, scene, shot_plan) -> StoryboardProviderView:
    options = [thaw_json(o) for o in option_set.value["payload"]["options"]
               if o["option_id"] == task.value["selected_option_id"]]
    if len(options) != 1:
        raise MovieContractError("accepted storyboard option is not present exactly once")
    option, raw_scene = options[0], thaw_json(scene)
    material = {
        "project_id": task.value["project_id"], "scene_id": task.value["scene_id"],
        "option_id": option["option_id"], "option_profile": option["profile_identity"],
        "approach_category": option["approach_category"],
        "characters": raw_scene["declared_characters"], "locations": raw_scene["declared_locations"],
        "time_indicators": raw_scene["time_indicators"], "events": raw_scene["events"],
        "observations": raw_scene["source_observations"],
        "shots": thaw_json(shot_plan.value["payload"]["ordered_shots"]),
        "knowledge_bindings": thaw_json(shot_plan.value["payload"]["source_knowledge_bindings"]),
        "knowledge_influence": thaw_json(shot_plan.value["payload"]["knowledge_influence"]),
    }
    return StoryboardProviderView(
        material["project_id"], material["scene_id"], material["option_id"],
        material["option_profile"], material["approach_category"],
        tuple(material["characters"]), tuple(material["locations"]),
        tuple(material["time_indicators"]), tuple(freeze_json(x) for x in material["events"]),
        tuple(freeze_json(x) for x in material["observations"]),
        tuple(freeze_json(x) for x in material["shots"]),
        tuple(freeze_json(x) for x in material["knowledge_bindings"]),
        freeze_json(material["knowledge_influence"]) if material["knowledge_influence"] is not None else None,
        canonical_digest(material),
    )


def _text(items: tuple[str, ...], unknown: str) -> str:
    return ", ".join(items) if items else unknown


def _time_cue(view: StoryboardProviderView) -> str:
    if view.time_indicators:
        return ", ".join(view.time_indicators)
    source = " ".join(thaw_json(item)["text"] for item in view.observations).lower()
    # Closed, literal source-cue extraction; this does not infer weather, color, or illumination design.
    cues = tuple(cue for cue in ("dawn", "sunrise", "morning", "day", "dusk", "sunset", "evening", "night")
                 if cue in source.split(" ") or f"{cue}," in source or f"{cue}." in source)
    return ", ".join(cues) if cues else "Not specified by validated upstream artifacts"


def create_frame_specifications(view: StoryboardProviderView) -> tuple[Any, ...]:
    if type(view) is not StoryboardProviderView:
        raise TypeError("storyboard provider requires the exact provider view")
    characters = _text(view.characters, "Not specified by validated upstream artifacts")
    location = _text(view.locations, "Not specified by validated upstream artifacts")
    lighting = _time_cue(view)
    event = thaw_json(view.events[0])["text"] if view.events else "Not specified by validated upstream artifacts"
    observation = thaw_json(view.observations[0])["text"] if view.observations else event
    frames = []
    for shot in view.shots:
        card = thaw_json(shot)
        purpose = card["shot_purpose"]
        subject = location if purpose == "scene_orientation" else characters
        action = card["narrative_focus"]
        unknowns = list(dict.fromkeys(card["unresolved_unknowns"] + [
            "Exact character appearance is not specified by validated upstream artifacts.",
            "Exact blocking, lens, color palette, and set dressing are not specified by validated upstream artifacts.",
        ]))
        assumptions = list(card["assumptions"])
        style = (f"Apply accepted production option profile {view.option_profile} "
                 f"({view.approach_category}) as visual style direction only; do not infer undeclared aesthetics.")
        camera = {
            "framing_and_shot_scale": card["shot_scale_qualification"],
            "angle": card["camera_angle_qualification"],
            "elevation": card["camera_elevation_qualification"],
            "movement": card["camera_movement_qualification"],
            "composition": card["composition_qualification"],
        }
        continuity = [
            f"Preserve source scene identity {view.scene_id} and shot order {card['source_ordinal']}.",
            f"Keep declared location continuity limited to: {location}.",
            f"Keep declared character continuity limited to: {characters}.",
            card["screen_direction_qualification"],
        ]
        prompt = (f"Storyboard frame specification. Subject focus: {subject}. Action: {action}. "
                  f"Environment: {location}. Time or lighting cue: {lighting}. "
                  f"Framing: {camera['framing_and_shot_scale']} Camera angle: {camera['angle']} "
                  f"Camera elevation: {camera['elevation']} Camera movement: {camera['movement']} "
                  f"Composition: {camera['composition']} Visual style: {style} "
                  "Render only supported facts; leave unspecified details unresolved for human review.")
        avoid = [
            "Do not add characters, locations, actions, props, wardrobe, weather, or architecture not supported upstream.",
            "Do not imply production approval, final selection, provider execution, or generated media.",
        ]
        material = {
            "source_ordinal": card["source_ordinal"], "source_shot_id": card["shot_id"],
            "source_shot_card_digest": card["shot_card_digest"], "subject_focus": subject,
            "action": action, "environment": location, "time_and_lighting": lighting,
            "camera": camera, "visual_style": style, "continuity_constraints": continuity,
            "assumptions": assumptions, "explicit_unknowns": unknowns,
            "generation_prompt": prompt, "negative_constraints": avoid,
            "evidence_references": card["evidence_references"],
            "derivation_basis": "deterministic_provider_neutral_specification",
        }
        frame_id = "frame-" + canonical_digest({"scene": view.scene_id, "option": view.option_id, "frame": material})[:24]
        frame = {"frame_id": frame_id, **material}
        frame["frame_specification_digest"] = canonical_digest(frame)
        frames.append(freeze_json(frame))
    return tuple(frames)


def expected_storyboard_payload(view: StoryboardProviderView, frames=None) -> dict[str, Any]:
    authoritative = create_frame_specifications(view)
    supplied = authoritative if frames is None else frames
    if type(supplied) is not tuple or thaw_json(supplied) != thaw_json(authoritative):
        raise MovieContractError("storyboard frames do not match deterministic authoritative derivation")
    payload = {
        "specification_status": "specification_only", "stable_order_is_not_ranking": True,
        "ordered_frames": [thaw_json(x) for x in supplied],
        "source_knowledge_bindings": [thaw_json(x) for x in view.knowledge_bindings],
        "knowledge_influence": thaw_json(view.knowledge_influence) if view.knowledge_influence is not None else None,
        "authority_boundary": dict(AUTHORITY_BOUNDARY), "limitations": list(LIMITATIONS),
        "storyboard_specification_digest": None,
    }
    payload["storyboard_specification_digest"] = canonical_digest(payload)
    return payload


def create_storyboard_result(task, decision, packet, option_set, breakdown, scene,
                             shot_plan, frames):
    from vss_movie_contracts import validate_scene_storyboard_specification
    view = storyboard_provider_view(task, option_set, scene, shot_plan)
    payload = expected_storyboard_payload(view, frames)
    keys = (
        "request_id", "correlation_id", "project_id", "scene_id", "decision_digest",
        "decision_complete_digest", "review_packet_digest", "review_packet_complete_digest",
        "option_set_digest", "option_set_complete_digest", "selected_option_id",
        "selected_option_content_digest", "scene_breakdown_digest", "scene_breakdown_payload_digest",
        "shot_plan_digest", "shot_plan_complete_digest", "shot_plan_semantic_digest",
    )
    result = {
        "schema_version": "1", "result_family": "scene_storyboard_specification", "result_version": "1",
        **{key: task.value[key] for key in keys}, "payload": payload,
        "integrity": {"payload_sha256": canonical_digest(payload), "complete_result_sha256": "0" * 64},
    }
    result["integrity"]["complete_result_sha256"] = canonical_digest(
        {**result, "integrity": {"payload_sha256": result["integrity"]["payload_sha256"]}}
    )
    return validate_scene_storyboard_specification(
        result, task=task, decision=decision, packet=packet, option_set=option_set,
        breakdown=breakdown, shot_plan=shot_plan,
    ).to_json_value()
