from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_movie_contracts.errors import MovieContractError
from vss_movie_pictorial import admit_pictorial_frame
from vss_reasoning_contracts import canonical_digest

EXPERIMENT_IDENTITY = "m8-3-real-provider-smoke-2"
SMOKE_3_EXPERIMENT_IDENTITY = "m8-3-real-provider-smoke-3"
EXPERIMENT_FRAME_ID = "frame-55a9d7015fdf1f72571b74c5"
EXPECTED_FRAME_SPECIFICATION_DIGEST = "019052d98e3db5862a8199993e29c5199b5df44c466aecda02f3128fa0867d7b"  # pragma: allowlist secret
EXPECTED_DEPICTION_PROJECTION_DIGEST = "3aa69cfccff612188bfd8d5820be1e691891d583074aff1e5205be986ed4c554"  # pragma: allowlist secret
PROVIDER_IDENTITY = "openai"
MODEL_IDENTITY = "gpt-image-2-2026-04-21"
ENDPOINT = "https://api.openai.com/v1/images/generations"
OUTPUT_WIDTH = 1280
OUTPUT_HEIGHT = 720
OUTPUT_QUALITY = "medium"
OUTPUT_FORMAT = "png"
MAXIMUM_ESTIMATED_COST_USD = "0.07"
AUTHORIZED_COST_CEILING_USD = "0.07"
RUNTIME_TIMEOUT_SECONDS = 150.0

_KEY = object()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _lines(heading: str, values: tuple[str, ...]) -> list[str]:
    return [heading, *(f"- {value}" for value in values)]


def project_openai_prompt(projection: Mapping[str, Any]) -> str:
    """Adapt the admitted M8.3 depiction plane without adding story semantics."""
    expected = {
        "depictable_facts", "required_narrative_emphasis", "narrative_context",
        "deliberate_ambiguities", "creative_degrees_of_freedom", "shot",
        "prohibited_contradictions", "depiction_instructions", "output",
    }
    if set(projection) != expected:
        raise MovieContractError("creative smoke depiction projection is incompatible")
    context = projection["narrative_context"]
    shot = projection["shot"]
    output = projection["output"]
    if (set(context) != {"characters", "locations", "time_indicators"}
            or set(shot) != {"purpose", "scale_constraint"}
            or set(output) != {"media_type", "width", "height", "purpose"}):
        raise MovieContractError("creative smoke depiction projection is incompatible")
    sections = ["Create one clean cinematic image from the depiction information below."]
    sections.extend(_lines("Depictable facts:", tuple(projection["depictable_facts"])))
    sections.extend(_lines("Required narrative emphasis:", tuple(projection["required_narrative_emphasis"])))
    sections.extend((
        "Narrative context; include only where appropriate for this detail shot:",
        f"- Characters: {', '.join(context['characters']) or 'none'}",
        f"- Locations: {', '.join(context['locations']) or 'none'}",
        f"- Time indicators: {', '.join(context['time_indicators']) or 'none'}",
    ))
    sections.extend(_lines("Deliberate ambiguities to preserve without resolving:",
                           tuple(projection["deliberate_ambiguities"])))
    sections.extend(_lines("Candidate-only artistic choices permitted:",
                           tuple(projection["creative_degrees_of_freedom"])))
    sections.extend((
        "Shot intent:",
        f"- Purpose: {shot['purpose']}",
        f"- Scale constraint: {shot['scale_constraint']}",
    ))
    sections.extend(_lines("Prohibited contradictions:", tuple(projection["prohibited_contradictions"])))
    sections.extend(_lines("Image instructions:", tuple(projection["depiction_instructions"])))
    sections.extend((
        "Provider output requirements:",
        "- Return one clean cinematic PNG image in a 16:9 landscape composition.",
        "- Do not render this prompt, headings, lists, controls, or metadata as visible content.",
    ))
    return "\n".join(sections)


@dataclass(frozen=True, slots=True, init=False)
class AdmittedCreativeSmoke:
    experiment_identity: str
    admission_id: str
    project_id: str
    scene_id: str
    storyboard_specification_digest: str
    frame_id: str
    frame_specification_digest: str
    knowledge_lineage_digest: str
    base_semantic_request_digest: str
    depiction_projection_digest: str
    provider_request_digest: str
    prompt: str
    projection: Mapping[str, Any]

    def __init__(self, key: object, **values: Any) -> None:
        if key is not _KEY:
            raise TypeError("creative smoke requests require authoritative M8.3 admission")
        for name in self.__slots__:
            object.__setattr__(self, name, values[name])


def admit_creative_smoke(
    decision_data: Any,
    packet_data: Any,
    option_set_data: Any,
    breakdown_data: Any,
    shot_plan_data: Any,
    storyboard_data: Any,
    *,
    environment: str,
    experiment_identity: str = EXPERIMENT_IDENTITY,
) -> AdmittedCreativeSmoke:
    if environment != "development":
        raise MovieContractError("creative smoke validation is development-only")
    base = admit_pictorial_frame(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
        storyboard_data, frame_id=EXPERIMENT_FRAME_ID, environment=environment,
    )
    if (base.frame_specification_digest != EXPECTED_FRAME_SPECIFICATION_DIGEST
            or base.provider_visible_digest != EXPECTED_DEPICTION_PROJECTION_DIGEST):
        raise MovieContractError("creative smoke authoritative Mira frame does not match the fixed experiment")
    prompt = project_openai_prompt(base.projection)
    provider_request_digest = canonical_digest({
        "model": MODEL_IDENTITY,
        "prompt": prompt,
        "n": 1,
        "size": f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}",
        "quality": OUTPUT_QUALITY,
        "output_format": OUTPUT_FORMAT,
    })
    if experiment_identity not in {EXPERIMENT_IDENTITY, SMOKE_3_EXPERIMENT_IDENTITY}:
        raise MovieContractError("creative smoke experiment identity is unsupported")
    admission_id = canonical_digest({
        "experiment": experiment_identity,
        "base_semantic_request_digest": base.semantic_request_digest,
        "depiction_projection_digest": base.provider_visible_digest,
        "provider_request_digest": provider_request_digest,
        "provider": PROVIDER_IDENTITY,
        "model": MODEL_IDENTITY,
        "endpoint": ENDPOINT,
        "output": {
            "format": OUTPUT_FORMAT, "width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT,
            "quality": OUTPUT_QUALITY, "maximum_images": 1,
        },
        "maximum_provider_attempts": 1,
        "maximum_estimated_cost_usd": MAXIMUM_ESTIMATED_COST_USD,
        "authorized_cost_ceiling_usd": AUTHORIZED_COST_CEILING_USD,
        "runtime_timeout_seconds": RUNTIME_TIMEOUT_SECONDS,
    })
    return AdmittedCreativeSmoke(
        _KEY,
        experiment_identity=experiment_identity,
        admission_id=admission_id,
        project_id=base.project_id,
        scene_id=base.scene_id,
        storyboard_specification_digest=base.storyboard_specification_digest,
        frame_id=base.frame_id,
        frame_specification_digest=base.frame_specification_digest,
        knowledge_lineage_digest=base.knowledge_lineage_digest,
        base_semantic_request_digest=base.semantic_request_digest,
        depiction_projection_digest=base.provider_visible_digest,
        provider_request_digest=provider_request_digest,
        prompt=prompt,
        projection=_freeze(dict(base.projection)),
    )
