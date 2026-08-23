from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_movie_contracts import validate_scene_storyboard_specification
from vss_movie_contracts.errors import MovieContractError
from vss_movie_storyboard import admit_storyboard_inputs
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json

_ADMISSION_KEY = object()


@dataclass(frozen=True, slots=True, init=False)
class AdmittedStoryboardRender:
    admission_id: str
    project_id: str
    scene_id: str
    storyboard_specification_digest: str
    frames: tuple[Mapping[str, Any], ...]

    def __init__(self, key: object, *, admission_id: str, project_id: str, scene_id: str,
                 storyboard_specification_digest: str, frames: tuple[Mapping[str, Any], ...]) -> None:
        if key is not _ADMISSION_KEY:
            raise TypeError("storyboard render requests require authoritative movie admission")
        object.__setattr__(self, "admission_id", admission_id)
        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "scene_id", scene_id)
        object.__setattr__(self, "storyboard_specification_digest", storyboard_specification_digest)
        object.__setattr__(self, "frames", frames)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def admit_storyboard_render(decision_data: Any, packet_data: Any, option_set_data: Any,
                            breakdown_data: Any, shot_plan_data: Any, storyboard_data: Any,
                            *, environment: str) -> AdmittedStoryboardRender:
    if environment != "development" or not isinstance(storyboard_data, dict):
        raise MovieContractError("storyboard rendering is development-only and requires an artifact object")
    task, decision, packet, option_set, breakdown, _, shot_plan = admit_storyboard_inputs(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
        request_id=storyboard_data.get("request_id", ""),
        correlation_id=storyboard_data.get("correlation_id", ""), environment=environment,
    )
    storyboard = validate_scene_storyboard_specification(
        storyboard_data, task=task, decision=decision, packet=packet, option_set=option_set,
        breakdown=breakdown, shot_plan=shot_plan,
    )
    boundary = thaw_json(storyboard.value["payload"]["authority_boundary"])
    if any(value is not False for key, value in boundary.items() if key != "scope") or boundary.get("scope") != "specification_only":
        raise MovieContractError("storyboard authority boundary is not inert")
    frames = tuple(_freeze(thaw_json(frame)) for frame in storyboard.value["payload"]["ordered_frames"])
    material = {
        "project_id": storyboard.value["project_id"], "scene_id": storyboard.value["scene_id"],
        "storyboard_specification_digest": storyboard.value["payload"]["storyboard_specification_digest"],
        "frame_bindings": [{"frame_id": f["frame_id"], "frame_specification_digest": f["frame_specification_digest"]} for f in frames],
    }
    return AdmittedStoryboardRender(
        _ADMISSION_KEY, admission_id=canonical_digest(material), project_id=material["project_id"],
        scene_id=material["scene_id"], storyboard_specification_digest=material["storyboard_specification_digest"],
        frames=frames,
    )
