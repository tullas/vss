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


def _admit_terminal_media(result, admission, destination, ledger):
    """Persist one accepted result through the common candidate provenance path."""
    import hashlib
    video = destination / "shot.mp4"
    video.write_bytes(result.media.content)
    evidence_path = destination / "evidence.json"
    evidence_path.write_text(json.dumps({
        "request_sha256": admission.request_sha256,
        "shot_id": admission.request["scope"]["shot_id"],
        "visual_basis_sha256": admission.request["production_input"]["content_sha256"],
        "provider": "Google Vertex AI", "model": "veo-3.1-generate-001",
        "provider_request_id": result.provider_request_id,
        "response_sha256": result.response_sha256,
        "video_sha256": hashlib.sha256(result.media.content).hexdigest(),
        "byte_count": len(result.media.content),
        "estimated_cost_usd": result.estimated_cost_usd,
        "attempts": 1, "audio": False, "authority": AUTHORITY,
    }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    ledger.terminal("completed")
    return video, evidence_path


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
    from pathlib import Path
    from vss_provider_reliability import provider_acceptance_evidenced, retry_permitted, same_operation_recovery_required
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
            evidence = json.loads((destination / "operation.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("accepted operation evidence is unavailable") from exc
        operation_name = evidence.get("operation_name") if isinstance(evidence, dict) else None
        if not same_operation_recovery_required(accepted=provider_acceptance_evidenced(evidence=evidence)):
            raise ValueError("accepted operation evidence is unavailable")
        record = ledger.assert_operation(operation_name, execution_namespace)
        if (evidence.get("request_sha256") != admission.request_sha256
                or evidence.get("execution_namespace") != execution_namespace
                or record.get("request_sha256") != admission.request_sha256):
            raise ValueError("accepted operation evidence does not match recovery")
        if record["status"] == "completed" and (destination / "shot.mp4").is_file() and (destination / "evidence.json").is_file():
            return CapabilityResult.success({**common, "status": "recovered_quarantined", "provider_call_count": 0,
                                             "attempt_reserved": True, "artifact_root": str(destination),
                                             "video": str(destination / "shot.mp4"), "evidence": str(destination / "evidence.json")})
        result = context.providers.get_image_to_video_generator().recover(ImageToVideoRequest(
            prompt=admission.request["prompt"], image=admission.image,
            request_sha256=admission.request_sha256, provider_request_sha256=admission.request_sha256,
            duration_seconds=IMAGE_TO_VIDEO_DURATION_SECONDS, resolution="720p", generate_audio=False,
            image_mime_type=IMAGE_MIME_TYPE, operation_evidence_path=destination / "operation.json",
            execution_namespace=execution_namespace), operation_name)
        video, evidence_path = _admit_terminal_media(result, admission, destination, ledger)
        return CapabilityResult.success({**common, "status": "recovered_quarantined", "provider_call_count": 0,
                                         "attempt_reserved": True, "artifact_root": str(destination),
                                         "video": str(video), "evidence": str(evidence_path)})
    # The Runtime boundary has completed closed readiness and is now entering
    # the one execution slot. Reservation is not provider consumption.
    ledger.reserve_execution()
    accepted = False

    def record_acceptance(operation_name):
        nonlocal accepted
        try:
            evidence_value = json.loads((destination / "operation.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("accepted provider operation evidence is unavailable") from exc
        if (not isinstance(evidence_value, dict)
                or evidence_value.get("operation_name") != operation_name
                or evidence_value.get("request_sha256") != admission.request_sha256
                or evidence_value.get("execution_namespace") != execution_namespace
                or not provider_acceptance_evidenced(evidence=evidence_value)):
            raise ValueError("accepted provider operation identity does not match this execution")
        ledger.accept_operation(operation_name, execution_namespace)
        accepted = True

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
            execution_namespace=execution_namespace,
            on_accepted=record_acceptance,
        ))
        if not accepted:
            # Keep compatibility with provider test doubles while failing
            # closed unless they supplied the same durable acceptance record.
            record_acceptance(result.provider_request_id)
        ledger.assert_operation(result.provider_request_id, execution_namespace)
    except Exception as exc:
        try:
            evidence_value = json.loads((destination / "operation.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            evidence_value = None
        accepted = accepted or _provider_acceptance_evidenced(exc, destination / "operation.json")
        if not retry_permitted(accepted=accepted):
            diagnostic = getattr(exc, "diagnostic", None)
            operation_name = (evidence_value.get("operation_name") if isinstance(evidence_value, dict)
                              else getattr(diagnostic, "operation_name", None))
            if not isinstance(evidence_value, dict):
                evidence_value = {
                    "operation_name": operation_name,
                    "endpoint": None,
                    "method": "POST",
                    "request_sha256": admission.request_sha256,
                    "execution_namespace": execution_namespace,
                    "submission_accepted": True,
                    "polls": [],
                }
                (destination / "operation.json").write_text(
                    json.dumps(evidence_value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            if (evidence_value.get("operation_name") != operation_name
                    or evidence_value.get("request_sha256") != admission.request_sha256
                    or evidence_value.get("execution_namespace") != execution_namespace
                    or not provider_acceptance_evidenced(evidence=evidence_value)):
                raise ValueError("accepted operation could not be bound to this execution") from exc
            ledger.accept_operation(operation_name, execution_namespace)
            ledger.terminal("failed")
        else:
            ledger.release_execution()
            try:
                destination.rmdir()
            except OSError:
                pass
        raise
    try:
        video, evidence = _admit_terminal_media(result, admission, destination, ledger)
    except Exception:
        # Acceptance was already sealed above; local failures cannot reopen it.
        ledger.terminal("failed")
        raise
    return CapabilityResult.success({**common, "status": "generated_quarantined", "provider_call_count": 1, "attempt_reserved": True, "artifact_root": str(destination), "video": str(video), "evidence": str(evidence)})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "movie.moving-shot"
execute.command_identity = "movie.moving-shot-generate"
