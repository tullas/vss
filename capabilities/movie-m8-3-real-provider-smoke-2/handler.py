from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION
from vss_movie_creative_smoke import (
    MAXIMUM_ESTIMATED_COST_USD,
    MODEL_IDENTITY,
    PROVIDER_IDENTITY,
    AdmittedCreativeSmoke,
    SmokeProviderRequest,
)


AUTHORITY = {
    "production_approval": False,
    "production_asset_admission": False,
    "final_frame_selection": False,
    "publication_authority": False,
    "workflow_authority": False,
    "autonomous_authority": False,
    "reusable_execution_authority": False,
}


def execute(context: CapabilityExecutionContext, input_data: dict[str, Any], dry_run: bool) -> CapabilityResult:
    admitted = context.admitted_request
    if (context.environment != "development" or type(admitted) is not AdmittedCreativeSmoke
            or input_data != {"admission_id": admitted.admission_id}):
        raise ValueError("creative smoke admission boundary mismatch")
    common = {
        "experiment_status": "validation_only" if dry_run else "generated_awaiting_human_review",
        "attempt_identity": context.execution_id,
        "project_id": admitted.project_id,
        "scene_id": admitted.scene_id,
        "storyboard_specification_digest": admitted.storyboard_specification_digest,
        "frame_id": admitted.frame_id,
        "frame_specification_digest": admitted.frame_specification_digest,
        "knowledge_lineage_digest": admitted.knowledge_lineage_digest,
        "base_semantic_request_digest": admitted.base_semantic_request_digest,
        "depiction_projection_digest": admitted.depiction_projection_digest,
        "provider_request_digest": admitted.provider_request_digest,
        "provider_identity": PROVIDER_IDENTITY,
        "model_identity": MODEL_IDENTITY,
        "maximum_provider_attempts": 1,
        "maximum_estimated_cost_usd": MAXIMUM_ESTIMATED_COST_USD,
        "authority_boundary": AUTHORITY,
    }
    if dry_run:
        return CapabilityResult.success({
            **common,
            "artifact_path": None,
            "evidence_path": None,
            "review_path": None,
            "media_type": None,
            "width": None,
            "height": None,
            "byte_count": None,
            "content_sha256": None,
            "latency_ms": None,
            "provider_call_count": 0,
            "sanitized_usage": {},
            "estimated_cost_usd": None,
            "png": None,
        })
    if context.creative_smoke_access is None or context.creative_smoke_artifact_publisher is None:
        raise ValueError("authorized creative smoke resources are unavailable")
    result = context.creative_smoke_access.generate(SmokeProviderRequest(
        prompt=admitted.prompt,
        provider_request_digest=admitted.provider_request_digest,
        depiction_projection_digest=admitted.depiction_projection_digest,
    ))
    paths = context.creative_smoke_artifact_publisher.stage(admitted, result, context.execution_id)
    return CapabilityResult.success({
        **common,
        **paths,
        "media_type": result.media.media_type,
        "width": result.media.width,
        "height": result.media.height,
        "byte_count": len(result.media.content),
        "content_sha256": result.media.content_sha256,
        "latency_ms": result.latency_ms,
        "provider_call_count": result.provider_call_count,
        "sanitized_usage": dict(result.usage),
        "estimated_cost_usd": result.estimated_cost_usd,
        "png": result.png.as_dict(),
    })


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.m8-3-real-provider-smoke-2"
execute.command_identity = "movie.m8-3-real-provider-smoke-2-generate"
