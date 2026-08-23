from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION
from vss_movie_storyboard_render import AdmittedStoryboardRender
from vss_providers import StoryboardRenderRequest


AUTHORITY = {
    "production_approval": False, "production_asset_admission": False,
    "final_selection": False, "publication_authority": False,
    "scheduling_authority": False, "workflow_authority": False,
    "autonomous_authority": False,
}


def execute(context: CapabilityExecutionContext, input_data: dict[str, Any], dry_run: bool) -> CapabilityResult:
    admitted = context.admitted_request
    if type(admitted) is not AdmittedStoryboardRender or input_data != {"admission_id": admitted.admission_id}:
        raise ValueError("storyboard render admission boundary mismatch")
    bindings = [{"frame_id": f["frame_id"], "frame_specification_digest": f["frame_specification_digest"]}
                for f in admitted.frames]
    common = {
        "storyboard_specification_digest": admitted.storyboard_specification_digest,
        "frame_bindings": bindings, "authority_boundary": AUTHORITY,
    }
    if dry_run:
        return CapabilityResult.success({**common, "review_media_status": "validation_only",
                                         "artifact_path": None, "media_type": None, "content_sha256": None})
    if context.providers is None or context.artifact_publisher is None:
        raise ValueError("authorized render resources are unavailable")
    media = context.providers.get_storyboard_renderer().render(StoryboardRenderRequest(
        admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest, admitted.frames,
    ))
    path = context.artifact_publisher.stage(admitted.storyboard_specification_digest, media.content)
    return CapabilityResult.success({**common, "review_media_status": "development_review_media",
                                     "artifact_path": path, "media_type": media.media_type,
                                     "content_sha256": media.content_sha256})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.storyboard-render"
execute.command_identity = "movie.storyboard-render"
