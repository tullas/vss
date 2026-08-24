from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION
from vss_movie_controlled_generation import AdmittedControlledGeneration
from vss_providers import ControlledFrameRequest


AUTHORITY = {key: False for key in (
    "production", "asset", "publication", "export", "scheduling", "workflow",
    "provider_execution", "runtime_execution",
)}


def execute(context: CapabilityExecutionContext, input_data: dict[str, Any], dry_run: bool) -> CapabilityResult:
    admitted = context.admitted_request
    if (context.environment != "development" or type(admitted) is not AdmittedControlledGeneration
            or input_data != {"admission_id": admitted.request["request_sha256"],
                              "mode": "preflight" if dry_run else "generate"}):
        raise ValueError("controlled generation admission boundary mismatch")
    common = {
        "request_sha256": admitted.request["request_sha256"], "authority": AUTHORITY,
    }
    if dry_run:
        return CapabilityResult.success({
            **common, "status": "ready_for_approval", "provider_call_count": 0,
            "attempt_reserved": False, "artifact_root": None, "image": None,
            "candidate": None, "review": None, "estimated_cost_usd": None,
        })
    if context.providers is None or context.controlled_generation_artifact_publisher is None:
        raise ValueError("authorized controlled generation resources are unavailable")
    result = context.providers.get_controlled_frame_generator().generate(ControlledFrameRequest(
        prompt=admitted.prompt, request_sha256=admitted.request["request_sha256"],
        provider_request_sha256=admitted.request["provider"]["provider_request_sha256"],
    ))
    paths = context.controlled_generation_artifact_publisher.stage(result)
    return CapabilityResult.success({
        **common, **paths, "status": "generated_awaiting_human_review",
        "provider_call_count": 1, "attempt_reserved": True,
        "estimated_cost_usd": result.estimated_cost_usd,
    })


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.controlled-review-frame"
execute.command_identity = "movie.controlled-review-frame-generate"
