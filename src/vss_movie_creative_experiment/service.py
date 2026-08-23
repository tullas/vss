from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_movie_contracts.errors import MovieContractError
from vss_movie_pictorial import admit_pictorial_frame
from vss_reasoning_contracts import canonical_digest

EXPERIMENT_FRAME_ID = "frame-55a9d7015fdf1f72571b74c5"
MODEL = "gpt-image-2-2026-04-21"
ENDPOINT = "https://api.openai.com/v1/images/generations"
CREATIVE_BRIEF = (
    ("Dramatic purpose", "Turn discovery into a quiet threshold moment rather than an action climax."),
    ("Prior beat", "Mira has just crossed the courtyard and now encounters the lantern beside the locked gate."),
    ("Audience impression", "The viewer should immediately notice the relationship among Mira, the lantern, and the inaccessible gate, and feel an unanswered question."),
    ("Director intent", "Create cautious curiosity and stillness. Keep the lantern's meaning ambiguous—it may feel like an invitation or warning, but the image must not resolve which."),
    ("Visual emphasis", "Use framing and dawn light to guide attention toward the lantern and locked gate while retaining Mira's reaction or presence."),
    ("Creative freedom", "Composition, lens feeling, palette, and abstract character presentation may vary, provided no new story event or concrete character history is asserted."),
    ("Non-negotiables", "Mira, courtyard, dawn, lantern beside a locked gate; no additional people, text, logos, unsupported props, explicit supernatural event, or resolved explanation for the lantern. Do not add unsupported age, ethnicity, wardrobe, architecture, weather, geography, or historical period."),
)
_KEY = object()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _prompt(projection: Mapping[str, Any], condition: str) -> str:
    sections = [
        "Create one cinematic storyboard review image from this validated frame specification.",
        f"Subject: {projection['subject_focus']}", f"Action: {projection['action']}",
        f"Environment: {projection['environment']}", f"Time and lighting: {projection['time_and_lighting']}",
        f"Camera: {dict(projection['camera'])}", f"Visual style: {projection['visual_style']}",
        f"Explicit unknowns: {'; '.join(projection['explicit_unknowns'])}",
        f"Avoid: {'; '.join(projection['negative_constraints'])}",
        "Treat unresolved appearance neutrally. Do not add unsupported age, ethnicity, wardrobe, architecture, weather, geography, or historical period.",
    ]
    if condition == "B":
        sections.append("Temporary experimental creative direction (not canonical story fact):")
        sections.extend(f"{heading}: {value}" for heading, value in CREATIVE_BRIEF)
    return "\n".join(sections)


@dataclass(frozen=True, slots=True, init=False)
class AdmittedCreativeExperiment:
    admission_id: str
    project_id: str
    scene_id: str
    storyboard_specification_digest: str
    frame_id: str
    frame_specification_digest: str
    knowledge_lineage_digest: str
    condition: str
    prompt: str
    prompt_digest: str
    semantic_request_digest: str
    projection: Mapping[str, Any]

    def __init__(self, key: object, **values: Any) -> None:
        if key is not _KEY:
            raise TypeError("creative experiment requires authoritative movie admission")
        for name in self.__slots__:
            object.__setattr__(self, name, values[name])


@dataclass(frozen=True, slots=True)
class AdmittedCreativeExperimentPlan:
    by_condition: Mapping[str, AdmittedCreativeExperiment]

    def __post_init__(self) -> None:
        values = dict(self.by_condition)
        if set(values) != {"A", "B"} or any(type(value) is not AdmittedCreativeExperiment for value in values.values()):
            raise TypeError("creative experiment plan requires exact authoritative admissions")
        object.__setattr__(self, "by_condition", MappingProxyType(values))


def admit_creative_experiment(decision_data: Any, packet_data: Any, option_set_data: Any,
                              breakdown_data: Any, shot_plan_data: Any, storyboard_data: Any,
                              *, frame_id: str, condition: str, environment: str) -> AdmittedCreativeExperiment:
    if environment != "development" or frame_id != EXPERIMENT_FRAME_ID or condition not in {"A", "B"}:
        raise MovieContractError("creative reality check target is not authorized")
    base = admit_pictorial_frame(decision_data, packet_data, option_set_data, breakdown_data,
                                shot_plan_data, storyboard_data, frame_id=frame_id, environment=environment)
    prompt = _prompt(base.projection, condition)
    prompt_digest = canonical_digest({"prompt": prompt})
    semantic = canonical_digest({
        "experiment": "creative-reality-check-1", "condition": condition,
        "base_semantic_request_digest": base.semantic_request_digest, "prompt_digest": prompt_digest,
        "provider": ["movie.storyboard-image.openai-crc1", "1.0.0", MODEL],
        "output": ["image/png", 1536, 1024, "medium"], "maximum_calls": 1,
    })
    return AdmittedCreativeExperiment(
        _KEY, admission_id=semantic, project_id=base.project_id, scene_id=base.scene_id,
        storyboard_specification_digest=base.storyboard_specification_digest,
        frame_id=base.frame_id, frame_specification_digest=base.frame_specification_digest,
        knowledge_lineage_digest=base.knowledge_lineage_digest, condition=condition,
        prompt=prompt, prompt_digest=prompt_digest, semantic_request_digest=semantic,
        projection=_freeze(dict(base.projection)),
    )


def admit_creative_experiment_plan(decision_data: Any, packet_data: Any, option_set_data: Any,
                                   breakdown_data: Any, shot_plan_data: Any, storyboard_data: Any,
                                   *, frame_id: str, environment: str) -> AdmittedCreativeExperimentPlan:
    return AdmittedCreativeExperimentPlan({condition: admit_creative_experiment(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data, storyboard_data,
        frame_id=frame_id, condition=condition, environment=environment,
    ) for condition in ("A", "B")})
