from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_movie_contracts.errors import MovieContractError
from vss_movie_storyboard_render import admit_storyboard_render
from vss_reasoning_contracts import canonical_digest

_ADMISSION_KEY = object()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


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
    admitted_storyboard = admit_storyboard_render(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
        storyboard_data, environment=environment,
    )
    selected = tuple(frame for frame in admitted_storyboard.frames if frame["frame_id"] == frame_id)
    if len(selected) != 1:
        raise MovieContractError("pictorial execution target is not present exactly once")
    frame = selected[0]
    projection = _freeze({
        "subject_focus": frame["subject_focus"], "action": frame["action"],
        "environment": frame["environment"], "time_and_lighting": frame["time_and_lighting"],
        "camera": frame["camera"], "visual_style": frame["visual_style"],
        "assumptions": frame["assumptions"], "explicit_unknowns": frame["explicit_unknowns"],
        "generation_prompt": frame["generation_prompt"],
        "negative_constraints": frame["negative_constraints"],
        "appearance_policy": "neutral_abstract_silhouette_for_unresolved_visual_facts",
        "output": {"media_type": "image/png", "width": 640, "height": 360,
                   "purpose": "development_review_candidate"},
    })
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
