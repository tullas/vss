from __future__ import annotations

import json

from vss_capabilities import CapabilityResult, SDK_API_VERSION
from vss_movie_moving_shot import AttemptLedger, IMAGE_MIME_TYPE, IMAGE_TO_VIDEO_DURATION_SECONDS, MovingShotAdmission, validate_moving_shot_admission
from vss_providers import ImageToVideoRequest

AUTHORITY = {"production": False, "publication": False, "retry": False, "fallback": False, "workflow_activation": False}


def _provider_acceptance_evidenced(exc, evidence_path) -> bool:
    from vss_provider_reliability import provider_acceptance_evidenced
    diagnostic = getattr(exc, "diagnostic", None)
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        evidence = None
    return provider_acceptance_evidenced(diagnostic, evidence)


def execute(context, input_data, dry_run):
    admission = context.admitted_request
    mode = input_data.get("mode") if isinstance(input_data, dict) else None
    if (context.environment != "development" or type(admission) is not MovingShotAdmission
            or not isinstance(input_data, dict) or input_data.get("admission_id") != admission.request_sha256
            or mode not in ({"preflight"} if dry_run else {"generate", "recover"})):
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
    execution_namespace = f"{admission.request['scope']['production_id']}/{admission.request['scope']['shot_id']}"
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
    if mode == "recover":
        try:
            record = json.loads(ledger.path.read_text(encoding="utf-8"))
            evidence = json.loads((destination / "operation.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("accepted operation evidence is unavailable") from exc
        if (record.get("request_sha256") != admission.request_sha256 or record.get("attempts") != 1
                or record.get("status") not in {"submitted", "failed", "completed"}
                or evidence.get("request_sha256") != admission.request_sha256
                or evidence.get("execution_namespace") != execution_namespace
                or evidence.get("submission_accepted") is not True
                or not isinstance(evidence.get("operation_name"), str)):
            raise ValueError("accepted operation evidence does not match recovery")
        if record["status"] == "completed" and (destination / "shot.mp4").is_file() and (destination / "evidence.json").is_file():
            return CapabilityResult.success({**common, "status": "recovered_quarantined", "provider_call_count": 0,
                                             "attempt_reserved": True, "artifact_root": str(destination),
                                             "video": str(destination / "shot.mp4"), "evidence": str(destination / "evidence.json")})
        result = context.providers.get_image_to_video_generator().recover(ImageToVideoRequest(
            prompt=admission.request["prompt"], image=admission.image,
            request_sha256=admission.request_sha256, provider_request_sha256=admission.request_sha256,
            duration_seconds=IMAGE_TO_VIDEO_DURATION_SECONDS, resolution="720p", generate_audio=False,
            image_mime_type=IMAGE_MIME_TYPE, operation_evidence_path=destination / "operation.json"), evidence["operation_name"])
        video = destination / "shot.mp4"
        video.write_bytes(result.media.content)
        evidence_path = destination / "evidence.json"
        evidence_path.write_text(json.dumps({"request_sha256": admission.request_sha256, "shot_id": admission.request["scope"]["shot_id"], "visual_basis_sha256": admission.request["production_input"]["content_sha256"], "provider": "Google Vertex AI", "model": "veo-3.1-generate-001", "provider_request_id": result.provider_request_id, "response_sha256": result.response_sha256, "video_sha256": result.media.content_sha256, "byte_count": len(result.media.content), "estimated_cost_usd": result.estimated_cost_usd, "attempts": 1, "audio": False, "authority": AUTHORITY}, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        ledger.terminal("completed")
        return CapabilityResult.success({**common, "status": "recovered_quarantined", "provider_call_count": 1,
                                         "attempt_reserved": True, "artifact_root": str(destination),
                                         "video": str(video), "evidence": str(evidence_path)})
    # The Runtime boundary has completed closed readiness and is now entering
    # the one execution slot. Reservation is not provider consumption.
    ledger.reserve_execution()
    accepted = False
    try:
        # Output allocation is post-reservation: a local collision is a
        # terminal failure of this one authorized execution, never a reason
        # to retry or create another attempt.
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir(exist_ok=False)
        # The provider handle's single generate call is the submission boundary.
        # Polling remains inside that call and cannot increment the ledger.
        result = context.providers.get_image_to_video_generator().generate(ImageToVideoRequest(
            prompt=admission.request["prompt"], image=admission.image,
            request_sha256=admission.request_sha256,
            provider_request_sha256=admission.request_sha256,
            duration_seconds=IMAGE_TO_VIDEO_DURATION_SECONDS, resolution="720p", generate_audio=False,
            image_mime_type=IMAGE_MIME_TYPE,
            operation_evidence_path=destination / "operation.json",
        ))
        # A returned result proves the provider accepted the operation. Consume
        # the authorization before any local media/evidence admission work.
        ledger.mark_submitted()
        accepted = True
        try:
            operation_value = json.loads((destination / "operation.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            operation_value = {"operation_name": result.provider_request_id,
                               "request_sha256": admission.request_sha256,
                               "submission_accepted": True}
        operation_value["execution_namespace"] = execution_namespace
        (destination / "operation.json").write_text(json.dumps(operation_value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    except Exception as exc:
        accepted = accepted or _provider_acceptance_evidenced(exc, destination / "operation.json")
        if accepted:
            if json.loads(ledger.path.read_text(encoding="utf-8"))["status"] == "reserved":
                ledger.mark_submitted()
            try:
                operation_value = json.loads((destination / "operation.json").read_text(encoding="utf-8"))
                operation_value["execution_namespace"] = execution_namespace
                (destination / "operation.json").write_text(json.dumps(operation_value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
            ledger.terminal("failed")
        else:
            ledger.release_execution()
            try:
                destination.rmdir()
            except OSError:
                pass
        raise
    try:
        video = destination / "shot.mp4"; video.write_bytes(result.media.content)
        evidence = destination / "evidence.json"
        evidence.write_text(json.dumps({"request_sha256": admission.request_sha256, "shot_id": admission.request["scope"]["shot_id"], "visual_basis_sha256": admission.request["production_input"]["content_sha256"], "provider": "Google Vertex AI", "model": "veo-3.1-generate-001", "provider_request_id": result.provider_request_id, "response_sha256": result.response_sha256, "video_sha256": hashlib.sha256(result.media.content).hexdigest(), "byte_count": len(result.media.content), "estimated_cost_usd": result.estimated_cost_usd, "attempts": 1, "audio": False, "authority": AUTHORITY}, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        ledger.terminal("completed")
    except Exception:
        # Acceptance was already sealed above; local failures cannot reopen it.
        ledger.terminal("failed")
        raise
    return CapabilityResult.success({**common, "status": "generated_quarantined", "provider_call_count": 1, "attempt_reserved": True, "artifact_root": str(destination), "video": str(video), "evidence": str(evidence)})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.moving-shot"
execute.command_identity = "movie.moving-shot-generate"
