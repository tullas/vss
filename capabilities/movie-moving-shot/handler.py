from __future__ import annotations

from vss_capabilities import CapabilityResult, SDK_API_VERSION
from vss_movie_moving_shot import AttemptLedger, IMAGE_MIME_TYPE, IMAGE_TO_VIDEO_DURATION_SECONDS, MovingShotAdmission, validate_moving_shot_admission
from vss_providers import ImageToVideoRequest

AUTHORITY = {"production": False, "publication": False, "retry": False, "fallback": False, "workflow_activation": False}


def execute(context, input_data, dry_run):
    admission = context.admitted_request
    if (context.environment != "development" or type(admission) is not MovingShotAdmission
            or input_data != {"admission_id": admission.request_sha256, "mode": "preflight" if dry_run else "generate"}):
        raise ValueError("moving-shot admission boundary mismatch")
    validate_moving_shot_admission(admission)
    common = {"request_sha256": admission.request_sha256, "authority": AUTHORITY}
    if dry_run:
        return CapabilityResult.success({**common, "status": "ready_for_paid_attempt", "provider_call_count": 0, "attempt_reserved": False, "artifact_root": None, "video": None, "evidence": None})
    if context.providers is None:
        raise ValueError("moving-shot provider access is unavailable")
    import hashlib, json
    from pathlib import Path
    root = context.safe_configuration.get("artifact_root")
    if not isinstance(root, str):
        raise ValueError("moving-shot artifact destination is unavailable")
    destination = Path(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    # Control records live beside the output directory so pre-recorded
    # authorization cannot make output allocation look already complete.
    # The authorization and attempt records are siblings of the output
    # namespace.  Keep the ledger beside ``authorization.json``; placing it
    # under ``output`` makes an already-authorized attempt appear unauthorized
    # and fails before the provider boundary.
    ledger = AttemptLedger(
        destination.parent.parent / f"{admission.request_sha256}.attempt.json",
        admission.request_sha256,
    )
    # The Runtime boundary has completed closed readiness and is now entering
    # the one execution slot. Reservation is not provider consumption.
    ledger.reserve_execution()
    try:
        # The provider handle's single generate call is the submission boundary.
        # Polling remains inside that call and cannot increment the ledger.
        ledger.mark_submitted()
        result = context.providers.get_image_to_video_generator().generate(ImageToVideoRequest(
            prompt=admission.request["prompt"], image=admission.image,
            request_sha256=admission.request_sha256,
            provider_request_sha256=admission.request_sha256,
            duration_seconds=IMAGE_TO_VIDEO_DURATION_SECONDS, resolution="720p", generate_audio=False,
            image_mime_type=IMAGE_MIME_TYPE,
        ))
    except Exception:
        ledger.terminal("failed")
        raise
    video = destination / "shot.mp4"; video.write_bytes(result.media.content)
    evidence = destination / "evidence.json"
    evidence.write_text(json.dumps({"request_sha256": admission.request_sha256, "shot_id": admission.request["scope"]["shot_id"], "visual_basis_sha256": admission.request["production_input"]["content_sha256"], "provider": "Google Vertex AI", "model": "veo-3.1-generate-001", "provider_request_id": result.provider_request_id, "response_sha256": result.response_sha256, "video_sha256": hashlib.sha256(result.media.content).hexdigest(), "byte_count": len(result.media.content), "estimated_cost_usd": result.estimated_cost_usd, "attempts": 1, "audio": False, "authority": AUTHORITY}, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    ledger.terminal("completed")
    return CapabilityResult.success({**common, "status": "generated_quarantined", "provider_call_count": 1, "attempt_reserved": True, "artifact_root": str(destination), "video": str(video), "evidence": str(evidence)})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.moving-shot"
execute.command_identity = "movie.moving-shot-generate"
