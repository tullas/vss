from __future__ import annotations

from vss_capabilities import CapabilityResult, SDK_API_VERSION
from vss_movie_creative_experiment import AdmittedCreativeExperiment
from vss_providers import CreativeExperimentRequest

MODEL = "gpt-image-2-2026-04-21"
PROVIDER = "movie.storyboard-image.openai-crc1"


def execute(context, input_data, dry_run):
    admitted = context.admitted_request
    if type(admitted) is not AdmittedCreativeExperiment or input_data != {"admission_id": admitted.admission_id}:
        return CapabilityResult.failure("invalid_input", "authoritative experiment admission is required", 2)
    common = {
        "experiment_status": "validation_only" if dry_run else "development_review_candidate",
        "candidate_label": context.creative_experiment_candidate_label,
        "plan_ordinal": context.creative_experiment_ordinal,
        "artifact_path": None, "review_path": None,
        "media_type": None, "width": None, "height": None, "content_sha256": None,
        "experiment_identity": "creative-reality-check-1",
        "execution_attempt_id": context.execution_id, "provider_identity": PROVIDER,
        "provider_version": "1.0.0", "model_identity": MODEL, "provider_call_count": 0,
        "latency_ms": None, "maximum_estimated_cost_usd": "0.07",
        "content_credentials_present": None, "content_credentials_chunk_bytes": None,
        "frame_id": admitted.frame_id, "frame_specification_digest": admitted.frame_specification_digest,
        "authority_boundary": {key: False for key in ("production_approval", "production_asset_admission",
            "final_frame_selection", "publication_authority", "workflow_authority", "autonomous_authority")},
    }
    if dry_run:
        return CapabilityResult.success(common)
    result = context.providers.get_creative_experiment_generator().generate(CreativeExperimentRequest(
        admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest,
        admitted.frame_id, admitted.frame_specification_digest, admitted.condition, admitted.prompt,
        admitted.prompt_digest, admitted.semantic_request_digest,
    ))
    media = result.media
    paths = context.creative_experiment_artifact_publisher.stage(
        admitted, common["candidate_label"], media.content, media.content_sha256, result.latency_ms,
        PROVIDER, MODEL, context.execution_id, dict(result.usage),
        result.content_credentials_present, result.content_credentials_chunk_bytes,
    )
    return CapabilityResult.success({**common, "artifact_path": paths["artifact_path"], "review_path": paths["review_path"], "media_type": media.media_type,
        "width": media.width, "height": media.height, "content_sha256": media.content_sha256,
        "provider_call_count": result.provider_call_count, "latency_ms": result.latency_ms,
        "content_credentials_present": result.content_credentials_present,
        "content_credentials_chunk_bytes": result.content_credentials_chunk_bytes})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.creative-reality-check-1"
execute.command_identity = "movie.creative-reality-check-1-generate"
