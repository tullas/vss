from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_movie_canon import bind_production_input_to_canon, create_canon_snapshot, create_creative_decision_revision
from vss_movie_contracts import validate_story_fragment
from vss_movie_contracts.errors import MovieContractError
from vss_movie_scene_breakdown import assemble_scene_context, break_down_scenes
from vss_movie_storyboard_render import admit_storyboard_render
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import ResourceContractError

from .contracts import validate_generation_request


PROVIDER_IDENTITY = "movie.storyboard-image.openai"
PROVIDER_VERSION = "1.0.0"
IMPLEMENTATION_IDENTITY = "vss.openai-gpt-image-2"
MODEL_SNAPSHOT = "gpt-image-2-2026-04-21"
ENDPOINT = "https://api.openai.com/v1/images/generations"
SECRET_NAME = "VSS_CONTROLLED_MEDIA_OPENAI_API_KEY"  # pragma: allowlist secret
PRICE_POLICY_IDENTITY = "openai-gpt-image-2-standard-2026-08-24/1"
DATA_POLICY_IDENTITY = "openai-images-generations-data-2026-08-24/1"
MAXIMUM_COST_USD = "0.100000"
MAXIMUM_ESTIMATED_COST_USD = "0.090000"
MAXIMUM_OUTPUT_BYTES = 10 * 1024 * 1024
RUNTIME_TIMEOUT_SECONDS = 150.0
SETTINGS = MappingProxyType({
    "n": 1, "size": "1280x720", "quality": "medium", "output_format": "png",
    "background": "opaque", "moderation": "auto", "stream": False,
})
PROMPT_PREFIX = (
    "Create one clean cinematic development storyboard review frame, not a document. "
    "Show no captions, labels, interface, borders, storyboard templates, production forms, "
    "watermarks, or control-plane text."
)
_ADMISSION_KEY = object()


def provider_request_body(prompt: str) -> dict[str, Any]:
    return {"model": MODEL_SNAPSHOT, "prompt": prompt, **dict(SETTINGS)}


def _digest(value: Any) -> str:
    return canonical_digest(value)


def _build_prompt(frame: Mapping[str, Any]) -> str:
    sections = [PROMPT_PREFIX, frame["generation_prompt"]]
    for label, key in (
        ("Continuity constraints", "continuity_constraints"),
        ("Do not resolve these deliberate unknowns", "explicit_unknowns"),
        ("Negative constraints", "negative_constraints"),
    ):
        values = frame[key]
        if values:
            sections.append(label + ": " + "; ".join(values))
    prompt = "\n".join(sections)
    if len(prompt.encode("utf-8")) > 4096:
        raise MovieContractError("controlled provider projection exceeds its bound")
    return prompt


@dataclass(frozen=True, slots=True, init=False)
class AdmittedControlledGeneration:
    request: Mapping[str, Any]
    prompt: str
    approval: Mapping[str, Any] | None

    def __init__(self, key: object, *, request: dict[str, Any], prompt: str,
                 approval: dict[str, Any] | None) -> None:
        if key is not _ADMISSION_KEY:
            raise TypeError("controlled generation requires authoritative admission")
        object.__setattr__(self, "request", freeze_json(request))
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "approval", freeze_json(approval) if approval is not None else None)

    def request_json(self) -> dict[str, Any]:
        return thaw_json(self.request)

    def approval_json(self) -> dict[str, Any] | None:
        return thaw_json(self.approval) if self.approval is not None else None


def admit_controlled_generation(
    story_data: Any, decision_data: Any, packet_data: Any, option_set_data: Any,
    breakdown_data: Any, creative_decision_data: Any, canon_snapshot_data: Any,
    canon_binding_data: Any, shot_plan_data: Any, storyboard_data: Any, *,
    frame_id: str, environment: str, approval: dict[str, Any] | None = None,
) -> AdmittedControlledGeneration:
    if environment != "development" or not isinstance(frame_id, str):
        raise MovieContractError("controlled generation is development-only")
    story = validate_story_fragment(story_data)
    story_value = story.to_json_value()
    if (story_value["classification"] != "public" or story_value["trust"] != "approved_fixture"
            or story_value["payload"]["rights_qualification"] not in {"original", "explicitly_authorized"}):
        raise MovieContractError("story is not eligible for controlled external processing")
    reconstructed_context = assemble_scene_context(
        story_value, request_id="m10-authoritative-breakdown", correlation_id="m10-authoritative-breakdown",
        project_id=story_value["project_id"], environment=environment,
    )
    reconstructed_breakdown = break_down_scenes(reconstructed_context)
    if reconstructed_breakdown != breakdown_data:
        raise MovieContractError("story and scene breakdown authoritative reconstruction mismatch")

    if not isinstance(creative_decision_data, dict):
        raise MovieContractError("controlled generation requires a creative decision")
    scope = creative_decision_data.get("scope", {})
    tenant_id, universe_id = scope.get("tenant_id"), scope.get("universe_id")
    try:
        creative_decision = create_creative_decision_revision(
            decision_data, packet_data, option_set_data, breakdown_data,
            tenant_id=tenant_id, universe_id=universe_id,
            revision=creative_decision_data.get("revision", 0), status=creative_decision_data.get("status"),
        )
        if creative_decision.to_json_value() != creative_decision_data:
            raise ResourceContractError("creative decision reconstruction mismatch")
        canon_snapshot = create_canon_snapshot(
            decisions=[creative_decision], snapshot_version=canon_snapshot_data.get("snapshot_version", 0))
        if canon_snapshot.to_json_value() != canon_snapshot_data:
            raise ResourceContractError("canon snapshot reconstruction mismatch")
        canon_binding = bind_production_input_to_canon(
            decision_data, packet_data, option_set_data, breakdown_data,
            tenant_id=tenant_id, universe_id=universe_id, decisions=[creative_decision],
            canon_snapshot=canon_snapshot,
        )
        if canon_binding.to_json_value() != canon_binding_data:
            raise ResourceContractError("canon binding reconstruction mismatch")
    except (ResourceContractError, AttributeError) as exc:
        raise MovieContractError("controlled canon chain is not authoritative") from exc

    storyboard = admit_storyboard_render(
        decision_data, packet_data, option_set_data, breakdown_data, shot_plan_data,
        storyboard_data, environment=environment,
    )
    selected = [item for item in storyboard.frames if item["frame_id"] == frame_id]
    if len(selected) != 1:
        raise MovieContractError("controlled generation frame is not present exactly once")
    frame = selected[0]
    if (scope.get("production_id") != storyboard.project_id
            or scope.get("scene_id") != storyboard.scene_id
            or canon_binding_data.get("scope") != scope):
        raise MovieContractError("controlled generation scope mismatch")
    prompt = _build_prompt(frame)
    projection_sha256 = _digest({
        "prefix": PROMPT_PREFIX, "generation_prompt": frame["generation_prompt"],
        "continuity_constraints": tuple(frame["continuity_constraints"]),
        "explicit_unknowns": tuple(frame["explicit_unknowns"]),
        "negative_constraints": tuple(frame["negative_constraints"]),
    })
    provider_request_sha256 = _digest(provider_request_body(prompt))
    request = {
        "schema_version": "1", "contract_identity": "controlled_storyboard_frame_generation_request",
        "contract_version": "1", "operation_identity": "generate_one_controlled_storyboard_review_frame",
        "operation_version": "1", "environment": "development",
        "purpose": "development_storyboard_review_candidate",
        "scope": {"tenant_id": tenant_id, "universe_id": universe_id,
                  "production_id": scope["production_id"], "project_id": storyboard.project_id,
                  "scene_id": storyboard.scene_id, "frame_id": frame_id},
        "lineage": {
            "story_fragment": story.digest, "scene_breakdown": _digest(breakdown_data),
            "production_option_set": _digest(option_set_data), "review_packet": _digest(packet_data),
            "review_decision": _digest(decision_data), "creative_decision_revision": _digest(creative_decision_data),
            "canon_snapshot": _digest(canon_snapshot_data), "production_canon_binding": _digest(canon_binding_data),
            "shot_plan_draft": _digest(shot_plan_data), "storyboard_specification": _digest(storyboard_data),
            "storyboard_frame": frame["frame_specification_digest"],
        },
        "eligibility": {"classification": "public", "trust": "approved_fixture",
                        "rights_qualification": story_value["payload"]["rights_qualification"],
                        "permissions": ["external_provider_processing", "generate_development_review_media"],
                        "restrictions": [], "policy_identity": "vss.controlled-media-input-eligibility",
                        "policy_version": "1.0.0"},
        "provider": {"identity": PROVIDER_IDENTITY, "version": PROVIDER_VERSION,
                     "implementation_identity": IMPLEMENTATION_IDENTITY, "model_snapshot": MODEL_SNAPSHOT,
                     "endpoint": ENDPOINT, "method": "POST", "settings": dict(SETTINGS),
                     "price_policy_identity": PRICE_POLICY_IDENTITY, "data_policy_identity": DATA_POLICY_IDENTITY,
                     "provider_request_sha256": provider_request_sha256},
        "projection": {"prompt": prompt, "projection_sha256": projection_sha256},
        "bounds": {"maximum_provider_attempts": 1, "maximum_images": 1,
                   "maximum_output_bytes": MAXIMUM_OUTPUT_BYTES, "maximum_cost_usd": MAXIMUM_COST_USD},
        "request_sha256": "0" * 64,
    }
    request["request_sha256"] = _digest(request)
    validate_generation_request(request)
    return AdmittedControlledGeneration(_ADMISSION_KEY, request=request, prompt=prompt, approval=approval)
