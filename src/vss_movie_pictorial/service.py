from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_movie_contracts.errors import MovieContractError
from vss_movie_storyboard import admit_storyboard_inputs
from vss_movie_storyboard_render import admit_storyboard_render
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json

_ADMISSION_KEY = object()

CREATIVE_DEGREES_OF_FREEDOM = (
    "composition",
    "focal_hierarchy",
    "depth_of_field",
    "negative_space",
    "time_consistent_lighting_nuance",
    "atmospheric_treatment",
    "non_semantic_texture",
    "camera_interpretation_within_shot_scale",
)

_SHOT_SCALE_BY_PURPOSE = {
    "scene_orientation": "wide",
    "primary_action": "medium",
    "detail_or_transition": "close_detail",
}


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _texts(items: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item["text"] for item in items))


def _depiction_projection(scene: Mapping[str, Any], shot: Mapping[str, Any]) -> Mapping[str, Any]:
    """Project validated story semantics into pixels without forwarding control-plane prose."""
    observations = _texts(scene["source_observations"])
    events = _texts(scene["events"])
    purpose = shot["shot_purpose"]
    if purpose not in _SHOT_SCALE_BY_PURPOSE:
        raise MovieContractError("pictorial shot purpose has no depiction mapping")
    emphasis = observations if purpose == "scene_orientation" else events
    if not emphasis:
        emphasis = observations
    material = {
        "depictable_facts": tuple(dict.fromkeys((*observations, *events))),
        "required_narrative_emphasis": emphasis,
        "narrative_context": {
            "characters": tuple(scene["declared_characters"]),
            "locations": tuple(scene["declared_locations"]),
            "time_indicators": tuple(scene["time_indicators"]),
        },
        "deliberate_ambiguities": tuple(scene["unknowns"]),
        "creative_degrees_of_freedom": CREATIVE_DEGREES_OF_FREEDOM,
        "shot": {"purpose": purpose, "scale_constraint": _SHOT_SCALE_BY_PURPOSE[purpose]},
        "prohibited_contradictions": (
            "Do not contradict the depictable facts or required narrative relationship.",
            "Do not invent new characters, plot actions, or narratively significant objects.",
            "Do not resolve deliberate ambiguities or imply a specific canonical answer.",
        ),
        "depiction_instructions": (
            "Create one clean cinematic image, not a document.",
            "Make the required narrative relationship legible; use narrative context only where appropriate for this shot.",
            "Use the bounded creative degrees of freedom for candidate-only artistic interpretation.",
            "Show no text, captions, labels, user interface, borders, storyboard sheets or templates, production forms, watermarks, or metadata representations.",
        ),
        "output": {
            "media_type": "image/png", "width": 640, "height": 360,
            "purpose": "cinematic_image_candidate",
        },
    }
    return _freeze(material)


@dataclass(frozen=True, slots=True, init=False)
class AdmittedPictorialFrame:
    admission_id: str
    project_id: str
    scene_id: str
    storyboard_specification_digest: str
    frame_id: str
    frame_specification_digest: str
    knowledge_lineage_digest: str
    semantic_request_digest: str
    provider_visible_digest: str
    projection: Mapping[str, Any]

    def __init__(self, key: object, **values: Any) -> None:
        if key is not _ADMISSION_KEY:
            raise TypeError("pictorial frame requests require authoritative movie admission")
        for name in self.__slots__:
            object.__setattr__(self, name, values[name])


def admit_pictorial_frame(decision_data: Any, packet_data: Any, option_set_data: Any,
                          breakdown_data: Any, shot_plan_data: Any, storyboard_data: Any,
                          *, frame_id: str, environment: str) -> AdmittedPictorialFrame:
    if environment != "development" or not isinstance(frame_id, str):
        raise MovieContractError("pictorial frame generation is development-only")
    _, _, _, _, _, scene, shot_plan = admit_storyboard_inputs(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
        request_id=storyboard_data.get("request_id", "") if isinstance(storyboard_data, dict) else "",
        correlation_id=storyboard_data.get("correlation_id", "") if isinstance(storyboard_data, dict) else "",
        environment=environment,
    )
    admitted_storyboard = admit_storyboard_render(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
        storyboard_data, environment=environment,
    )
    selected = tuple(frame for frame in admitted_storyboard.frames if frame["frame_id"] == frame_id)
    if len(selected) != 1:
        raise MovieContractError("pictorial execution target is not present exactly once")
    frame = selected[0]
    shots = tuple(
        shot for shot in thaw_json(shot_plan.value["payload"]["ordered_shots"])
        if shot["shot_id"] == frame["source_shot_id"]
    )
    if len(shots) != 1:
        raise MovieContractError("pictorial source shot is not present exactly once")
    projection = _depiction_projection(thaw_json(scene), shots[0])
    provider_visible_digest = canonical_digest(projection)
    payload = storyboard_data["payload"]
    knowledge_lineage_digest = canonical_digest({
        "source_knowledge_bindings": payload["source_knowledge_bindings"],
        "knowledge_influence": payload["knowledge_influence"],
    })
    semantic = {
        "operation": "generate_one_pictorial_storyboard_frame/1",
        "project_id": admitted_storyboard.project_id, "scene_id": admitted_storyboard.scene_id,
        "storyboard_specification_digest": admitted_storyboard.storyboard_specification_digest,
        "frame_id": frame_id, "frame_specification_digest": frame["frame_specification_digest"],
        "knowledge_lineage_digest": knowledge_lineage_digest,
        "provider_visible_digest": provider_visible_digest,
        "bounds": {"maximum_provider_calls": 1, "maximum_images": 1,
                   "maximum_output_bytes": 2097152},
    }
    semantic_request_digest = canonical_digest(semantic)
    return AdmittedPictorialFrame(
        _ADMISSION_KEY, admission_id=semantic_request_digest,
        project_id=admitted_storyboard.project_id, scene_id=admitted_storyboard.scene_id,
        storyboard_specification_digest=admitted_storyboard.storyboard_specification_digest,
        frame_id=frame_id, frame_specification_digest=frame["frame_specification_digest"],
        knowledge_lineage_digest=knowledge_lineage_digest,
        semantic_request_digest=semantic_request_digest,
        provider_visible_digest=provider_visible_digest, projection=projection,
    )
