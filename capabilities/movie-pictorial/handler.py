from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION
from vss_movie_pictorial import AdmittedPictorialFrame
from vss_providers import PictorialFrameRequest

AUTHORITY = {
    "production_approval": False, "production_asset_admission": False,
    "final_frame_selection": False, "publication_authority": False,
    "scheduling_authority": False, "workflow_authority": False,
    "autonomous_authority": False, "reusable_execution_authority": False,
}


def execute(context: CapabilityExecutionContext, input_data: dict[str, Any], dry_run: bool) -> CapabilityResult:
    admitted = context.admitted_request
    if (context.environment != "development" or type(admitted) is not AdmittedPictorialFrame
            or input_data != {"admission_id": admitted.admission_id}):
        raise ValueError("pictorial frame admission boundary mismatch")
    common = {
        "execution_attempt_id": context.execution_id,
        "project_id": admitted.project_id, "scene_id": admitted.scene_id,
        "storyboard_specification_digest": admitted.storyboard_specification_digest,
        "frame_id": admitted.frame_id, "frame_specification_digest": admitted.frame_specification_digest,
        "knowledge_lineage_digest": admitted.knowledge_lineage_digest,
        "semantic_request_digest": admitted.semantic_request_digest,
        "provider_visible_digest": admitted.provider_visible_digest,
        "provider_identity": "movie.storyboard-image.local", "provider_version": "1.0.0",
        "authority_boundary": AUTHORITY,
    }
    if dry_run:
        return CapabilityResult.success({**common, "review_media_status": "validation_only",
            "artifact_path": None, "media_type": None, "width": None, "height": None,
            "content_sha256": None, "provider_call_count": 0})
    if context.providers is None or context.pictorial_artifact_publisher is None:
        raise ValueError("authorized pictorial resources are unavailable")
    media = context.providers.get_pictorial_frame_generator().generate(PictorialFrameRequest(
        admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest,
        admitted.frame_id, admitted.frame_specification_digest, admitted.semantic_request_digest,
        admitted.provider_visible_digest, admitted.projection,
    ))
    path = context.pictorial_artifact_publisher.stage(
        admitted.storyboard_specification_digest, admitted.frame_id, media.content_sha256, media.content,
    )
    return CapabilityResult.success({**common, "review_media_status": "development_review_media",
        "artifact_path": path, "media_type": media.media_type, "width": media.width,
        "height": media.height, "content_sha256": media.content_sha256, "provider_call_count": 1})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.pictorial-frame-generation"
execute.command_identity = "movie.pictorial-frame-generate"
