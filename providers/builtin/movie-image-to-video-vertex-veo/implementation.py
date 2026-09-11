from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from vss_movie_moving_shot import IMAGE_MIME_TYPE, IMAGE_TO_VIDEO_DURATION_SECONDS, LOCATION, MODEL_SNAPSHOT, MAXIMUM_COST_USD
from vss_provider_reliability import FailureClass
from vss_providers import GeneratedMedia, ImageToVideoRequest, ImageToVideoResult, ProviderExecutionFailure

POLL_INTERVAL_SECONDS = 5.0
MAX_EVIDENCE_BYTES = 64 * 1024
MAX_MAGIC_BYTES = 32
MAX_URI_LENGTH = 2048
MAX_MP4_SCAN_BYTES = 1024 * 1024
_BEARER_PREFIX = re.compile(r"(?i)^Bearer(?:\s|$)")


class _TransportResponse:
    __slots__ = ("status", "body")

    def __init__(self, status: int | None, body: bytes) -> None:
        self.status = status
        self.body = body


def _https_json(url: str, body: bytes, headers: dict[str, str], timeout: float) -> _TransportResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return _TransportResponse(int(response.status), response.read(128 * 1024 * 1024 + 1))


def _default_transport(url: str, body: bytes, headers: dict[str, str], timeout: float, maximum: int) -> _TransportResponse:
    return _https_json(url, body, headers, timeout)


def _transport_response(value: object) -> _TransportResponse:
    """Normalize real and offline transports without retaining response bodies."""
    if isinstance(value, _TransportResponse):
        return value
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], bytes):
        return _TransportResponse(value[0], value[1])
    if isinstance(value, bytes):
        # Legacy fake transports predate status journaling.
        return _TransportResponse(None, value)
    raise TypeError("transport returned an invalid response")


def _authorization_header(raw_token: str) -> str:
    """Build one bearer header from an unwrapped environment token.

    The environment value is deliberately not stripped, decoded, encoded, or
    otherwise rewritten.  Rejecting shell/HTTP wrapper material prevents a
    malformed value from being sent while preserving valid token bytes.
    """
    if (not isinstance(raw_token, str) or not raw_token
            or any(char.isspace() or char in {'"', "'"} for char in raw_token)
            or _BEARER_PREFIX.match(raw_token)):
        raise ValueError("Vertex access token must be a raw, unwrapped token")
    return "Bearer " + raw_token


class VertexVeoProviderDiagnostic:
    """Bounded provider evidence safe to retain in the VSS audit record."""

    __slots__ = ("http_response_received", "classification", "http_status", "error_code", "message", "stage", "operation_name", "poll_count", "submission_accepted", "validation_check", "underlying_exception")

    def __init__(self, http_response_received: bool, classification: str,
                 http_status: int | None = None, error_code: str | None = None,
                 message: str | None = None, *, stage: str = "submission",
                 operation_name: str | None = None, poll_count: int = 0,
                 submission_accepted: bool = False, validation_check: str | None = None,
                 underlying_exception: dict[str, str | None] | None = None) -> None:
        self.http_response_received = http_response_received
        self.classification = classification
        self.http_status = http_status
        self.error_code = error_code
        self.message = message
        self.stage = stage
        self.operation_name = operation_name
        self.poll_count = poll_count
        self.submission_accepted = submission_accepted
        self.validation_check = validation_check
        self.underlying_exception = underlying_exception

    def as_dict(self) -> dict[str, object]:
        value = {
            "http_response_received": self.http_response_received,
            "classification": self.classification,
            "http_status": self.http_status,
            "error_code": self.error_code,
            "message": self.message,
            "stage": self.stage,
            "operation_name": self.operation_name,
            "poll_count": self.poll_count,
            "submission_accepted": self.submission_accepted,
        }
        if self.validation_check is not None:
            value["validation_check"] = self.validation_check
        if self.underlying_exception is not None:
            value["underlying_exception"] = self.underlying_exception
        return value


class VertexVeoProviderFailure(ProviderExecutionFailure):
    """Terminal failure from the one already-reserved provider attempt."""

    def __init__(self, message: str, diagnostic: VertexVeoProviderDiagnostic) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


def _write_evidence(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(encoded) > MAX_EVIDENCE_BYTES:
        raise ValueError("operation evidence exceeds its bound")
    path.write_bytes(encoded)


def _persist_operation(request: ImageToVideoRequest, operation: str, endpoint: str,
                       submission_status: int | None) -> dict[str, Any] | None:
    path = getattr(request, "operation_evidence_path", None)
    if path is None:
        return None
    if not isinstance(path, Path):
        raise VertexVeoProviderFailure(
            "image-to-video operation evidence destination is invalid",
            VertexVeoProviderDiagnostic(
                True, "operation_persistence_failed", stage="submission",
                operation_name=operation, submission_accepted=True,
            ),
        )
    try:
        evidence = {
            "operation_name": operation,
            "endpoint": endpoint,
            "method": "POST",
            "request_sha256": request.request_sha256,
            "submission_accepted": True,
            "submission_http_status": submission_status,
            "polls": [],
        }
        _write_evidence(path, evidence)
        return evidence
    except (OSError, TypeError, ValueError) as exc:
        raise VertexVeoProviderFailure(
            "image-to-video operation evidence persistence failed",
            VertexVeoProviderDiagnostic(
                True, "operation_persistence_failed", stage="submission",
                operation_name=operation, submission_accepted=True,
            ),
        ) from exc


def _persist_evidence(path: Path | None, evidence: dict[str, Any]) -> None:
    if path is None:
        return
    try:
        _write_evidence(path, evidence)
    except (OSError, TypeError, ValueError) as exc:
        operation = evidence.get("operation_name")
        raise VertexVeoProviderFailure(
            "image-to-video operation evidence persistence failed",
            VertexVeoProviderDiagnostic(
                True, "operation_persistence_failed", stage="result_retrieval",
                operation_name=operation if isinstance(operation, str) else None,
                poll_count=len(evidence.get("polls", [])), submission_accepted=True,
            ),
        ) from exc


def _record_transport_event(request: ImageToVideoRequest, *, stage: str,
                            status: int | None, ordinal: int | None = None,
                            done: bool | None = None) -> None:
    path = getattr(request, "operation_evidence_path", None)
    if not isinstance(path, Path) or not path.exists():
        return
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            return
        if stage == "submission":
            evidence["submission_http_status"] = status
            evidence["submission_transport_failure"] = True
        else:
            polls = evidence.setdefault("polls", [])
            if isinstance(polls, list):
                polls.append({"ordinal": ordinal, "http_status": status, "done": done})
        _persist_evidence(path, evidence)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        # The original transport failure remains the most useful diagnostic;
        # persistence failures are reported when an evidence write was required.
        return


def _safe_message(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    # Provider messages are useful evidence, but must never retain credentials,
    # URLs with query material, or unbounded response content.
    value = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[redacted]", value)
    value = re.sub(r"https?://[^\s]+", "[url redacted]", value)
    value = " ".join(value.split())
    return value[:1024] or None


def _safe_uri(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > MAX_URI_LENGTH:
        return None
    # Preserve useful object identity while excluding query credentials.
    value = value.split("?", 1)[0].split("#", 1)[0]
    return value[:MAX_URI_LENGTH]


def _safe_key(value: object) -> str:
    return str(value)[:128]


def _response_metadata(terminal: dict[str, Any]) -> dict[str, Any]:
    response = terminal.get("response") if isinstance(terminal.get("response"), dict) else None
    videos = response.get("videos") if isinstance(response, dict) else None
    metadata: dict[str, Any] = {
        "top_level_keys": sorted(_safe_key(key) for key in terminal.keys())[:64],
        "done": terminal.get("done") if isinstance(terminal.get("done"), bool) else None,
        "response_present": response is not None,
        "response_keys": sorted(_safe_key(key) for key in response.keys())[:64] if response is not None else [],
        "video_count": len(videos) if isinstance(videos, list) else None,
    }
    if isinstance(terminal.get("error"), dict):
        error = terminal["error"]
        metadata["error"] = {
            "keys": sorted(_safe_key(key) for key in error.keys())[:32],
            "code": error.get("code") if isinstance(error.get("code"), int) else None,
            "status": _safe_message(error.get("status")),
            "message": _safe_message(error.get("message")),
        }
    if isinstance(videos, list) and videos and isinstance(videos[0], dict):
        video = videos[0]
        representation: dict[str, Any] = {"field_path": "response.videos[0]", "keys": sorted(_safe_key(key) for key in video.keys())[:32]}
        if isinstance(video.get("bytesBase64Encoded"), str):
            representation.update({
                "field_path": "response.videos[0].bytesBase64Encoded",
                "kind": "inline_base64", "encoded_length": len(video["bytesBase64Encoded"]),
            })
        elif isinstance(video.get("gcsUri"), str):
            representation.update({"field_path": "response.videos[0].gcsUri", "kind": "uri", "uri": _safe_uri(video["gcsUri"])})
        else:
            representation["kind"] = "other"
        representation["declared_mime_type"] = _safe_message(video.get("mimeType"))
        metadata["video_representation"] = representation
    else:
        metadata["video_representation"] = {"field_path": None, "kind": "other"}
    return metadata


def _exception_metadata(exc: BaseException) -> dict[str, str | None]:
    return {"type": type(exc).__name__, "message": _safe_message(str(exc))}


def _record_result_failure(evidence: dict[str, Any] | None, path: Path | None,
                           classification: str, check: str, message: str,
                           cause: BaseException | None = None) -> None:
    if evidence is None:
        return
    result = evidence.setdefault("result_admission", {})
    taxonomy = FailureClass.MEDIA_DECODING.value if check == "base64_decode" else (
        FailureClass.MEDIA_CONTAINER_ADMISSION.value if check in {"empty_payload", "payload_size", "encoded_payload_size"} or check.startswith(("valid_", "invalid_", "unsupported_", "truncated_", "ftyp_")) else FailureClass.RESULT_REPRESENTATION.value)
    result.update({"status": "rejected", "classification": classification, "failure_taxonomy": taxonomy,
                   "validation_check": check, "message": _safe_message(message)})
    if cause is not None:
        result["underlying_exception"] = _exception_metadata(cause)
    _persist_evidence(path, evidence)


def _result_diagnostic(classification: str, operation: str, poll_count: int,
                       check: str, cause: BaseException | None = None) -> VertexVeoProviderDiagnostic:
    return VertexVeoProviderDiagnostic(
        True, classification, stage="result_retrieval", operation_name=operation,
        poll_count=poll_count, submission_accepted=True, validation_check=check,
        underlying_exception=_exception_metadata(cause) if cause is not None else None,
    )


def _mp4_check(content: bytes) -> tuple[bool, str]:
    """Bounded ISO-BMFF detection; ftyp need not be 24 bytes or byte zero."""
    limit = min(len(content), MAX_MP4_SCAN_BYTES)
    offset = 0
    while offset + 8 <= limit:
        size = int.from_bytes(content[offset:offset + 4], "big")
        box_type = content[offset + 4:offset + 8]
        header = 8
        if size == 1:
            if offset + 16 > limit:
                return False, "truncated_extended_box"
            size = int.from_bytes(content[offset + 8:offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(content) - offset
        if size < header or offset + size > len(content):
            return False, "invalid_box_size"
        if box_type == b"ftyp":
            if size < header + 8 or (size - header - 8) % 4:
                return False, "invalid_ftyp_box"
            major = content[offset + header:offset + header + 4]
            brands = [content[i:i + 4] for i in range(offset + header + 8, offset + size, 4)]
            known = {b"isom", b"iso2", b"iso3", b"iso4", b"iso5", b"iso6", b"iso7", b"iso8",
                     b"mp41", b"mp42", b"avc1", b"av01", b"hvc1", b"hev1", b"hev2", b"dash",
                     b"cmfc", b"cmff", b"mif1", b"msf1", b"avif", b"M4V ", b"qt  "}
            if major in known or any(brand in known for brand in brands):
                return True, "valid_iso_bmff_ftyp"
            return False, "unsupported_mp4_brand"
        offset += size
    return False, "ftyp_not_found"


def _http_classification(status: int) -> str:
    return {
        400: "http_bad_request", 401: "http_authentication",
        403: "http_access", 404: "http_not_found", 429: "http_rate_limit",
    }.get(status, "http_server" if 500 <= status <= 599 else "http_other")


def _http_failure(exc: urllib.error.HTTPError, *, stage: str = "submission",
                  operation_name: str | None = None, poll_count: int = 0,
                  submission_accepted: bool = False) -> VertexVeoProviderFailure:
    status = int(exc.code) if isinstance(exc.code, int) and 100 <= exc.code <= 599 else None
    code = message = None
    try:
        raw = exc.read(8193)
        if len(raw) <= 8192:
            value = json.loads(raw)
            error = value.get("error") if isinstance(value, dict) else None
            if isinstance(error, dict):
                provider_code = error.get("status", error.get("code"))
                code = _safe_message(str(provider_code)) if provider_code is not None else None
                message = _safe_message(error.get("message"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    diagnostic = VertexVeoProviderDiagnostic(
        True, _http_classification(status) if status is not None else "http_other",
        status, code, message, stage=stage, operation_name=operation_name,
        poll_count=poll_count, submission_accepted=submission_accepted,
    )
    return VertexVeoProviderFailure("image-to-video provider returned an HTTP error", diagnostic)


def _transport_failure(exc: BaseException, *, stage: str = "submission",
                       operation_name: str | None = None, poll_count: int = 0,
                       submission_accepted: bool = False) -> VertexVeoProviderFailure:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    classification = "timeout" if isinstance(reason, TimeoutError) else "transport"
    return VertexVeoProviderFailure(
        "image-to-video provider transport failed",
        VertexVeoProviderDiagnostic(False, classification, stage=stage,
                                    operation_name=operation_name,
                                    poll_count=poll_count,
                                    submission_accepted=submission_accepted),
    )


class VertexVeoImageToVideoProvider:
    def generate(self, request: ImageToVideoRequest, *, credential: str, transport=None) -> ImageToVideoResult:
        if (request.model_snapshot if hasattr(request, "model_snapshot") else MODEL_SNAPSHOT) != MODEL_SNAPSHOT:
            raise ValueError("unsupported Veo model")
        project = os.environ.get("VSS_VERTEX_AI_PROJECT_ID", "")
        location = os.environ.get("VSS_VERTEX_AI_LOCATION", LOCATION)
        if location != LOCATION or request.duration_seconds != IMAGE_TO_VIDEO_DURATION_SECONDS or request.image_mime_type != IMAGE_MIME_TYPE:
            raise ValueError("Vertex Veo image-to-video request contract is invalid")
        if not project or not credential:
            raise ValueError("Vertex project or credential is unavailable")
        endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{MODEL_SNAPSHOT}:predictLongRunning"
        body_value = {"instances": [{"prompt": request.prompt, "image": {"bytesBase64Encoded": base64.b64encode(request.image).decode("ascii"), "mimeType": request.image_mime_type}}], "parameters": {"aspectRatio": "16:9", "resolution": request.resolution, "durationSeconds": request.duration_seconds, "generateAudio": request.generate_audio, "sampleCount": 1}}
        body = json.dumps(body_value, sort_keys=True, separators=(",", ":")).encode()
        if len(body) > 32 * 1024 * 1024:
            raise ValueError("Vertex request exceeds its bound")
        started = time.monotonic()
        sender = transport or _default_transport
        try:
            authorization = _authorization_header(credential)
        except ValueError as exc:
            raise ValueError("Vertex project or credential is unavailable") from exc
        headers = {"Authorization": authorization, "Content-Type": "application/json"}
        try:
            submission = _transport_response(sender(endpoint, body, headers, 900.0, 128 * 1024 * 1024))
        except urllib.error.HTTPError as exc:
            _record_transport_event(request, stage="submission", status=int(exc.code) if isinstance(exc.code, int) else None)
            raise _http_failure(exc, stage="submission") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise _transport_failure(exc, stage="submission") from exc
        value = _parse_json(submission.body, "submission", submission_accepted=False)
        operation = value.get("name") if isinstance(value, dict) else None
        expected_prefix = f"projects/{project}/locations/{LOCATION}/publishers/google/models/{MODEL_SNAPSHOT}/operations/"
        if not isinstance(operation, str) or not operation.startswith(expected_prefix) or len(operation) > 512:
            raise VertexVeoProviderFailure("image-to-video provider returned an invalid operation", VertexVeoProviderDiagnostic(True, "operation_invalid", stage="submission"))
        evidence = _persist_operation(request, operation, endpoint, submission.status)
        if evidence is not None:
            evidence["submission_response"] = {
                "top_level_keys": sorted(_safe_key(key) for key in value.keys())[:64],
                "operation_name_present": isinstance(value.get("name"), str),
            }
            _persist_evidence(getattr(request, "operation_evidence_path", None), evidence)
        evidence_path = getattr(request, "operation_evidence_path", None)
        poll_endpoint = endpoint.rsplit(":", 1)[0] + ":fetchPredictOperation"
        terminal_raw = None
        terminal = None
        poll_count = 0
        for _ in range(360):
            poll_count += 1
            try:
                polled = _transport_response(sender(poll_endpoint, json.dumps({"operationName": operation}, separators=(",", ":")).encode(), headers, 30.0, 128 * 1024 * 1024))
                terminal_raw = polled.body
            except urllib.error.HTTPError as exc:
                _record_transport_event(request, stage="polling", status=int(exc.code) if isinstance(exc.code, int) else None, ordinal=poll_count)
                raise _http_failure(exc, stage="polling", operation_name=operation,
                                    poll_count=poll_count, submission_accepted=True) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise _transport_failure(exc, stage="polling", operation_name=operation,
                                         poll_count=poll_count, submission_accepted=True) from exc
            try:
                terminal = _parse_json(terminal_raw, "operation", operation_name=operation,
                                       poll_count=poll_count, submission_accepted=True)
            except VertexVeoProviderFailure:
                if evidence is not None:
                    evidence["polls"].append({"ordinal": poll_count, "http_status": polled.status, "done": None})
                    _persist_evidence(evidence_path, evidence)
                raise
            if evidence is not None:
                evidence["polls"].append({"ordinal": poll_count, "http_status": polled.status,
                                          "done": terminal.get("done") if isinstance(terminal.get("done"), bool) else None})
                _persist_evidence(evidence_path, evidence)
            if terminal.get("done") is True:
                break
            time.sleep(POLL_INTERVAL_SECONDS)
        if not isinstance(terminal, dict) or terminal.get("done") is not True:
            raise VertexVeoProviderFailure("image-to-video provider operation timed out", VertexVeoProviderDiagnostic(True, "operation_timeout", stage="polling", operation_name=operation, poll_count=poll_count, submission_accepted=True))
        if evidence is not None:
            evidence["terminal_response"] = _response_metadata(terminal)
            _persist_evidence(evidence_path, evidence)
        if isinstance(terminal.get("error"), dict):
            error = terminal["error"]
            if evidence is not None:
                evidence["result_admission"] = {"status": "rejected", "classification": "operation_failed",
                                                 "validation_check": "terminal_provider_error"}
                _persist_evidence(evidence_path, evidence)
            raise VertexVeoProviderFailure("image-to-video provider operation failed", VertexVeoProviderDiagnostic(True, "operation_failed", error_code=_safe_message(str(error.get("status", error.get("code", "unknown")))), message=_safe_message(error.get("message")), stage="polling", operation_name=operation, poll_count=poll_count, submission_accepted=True))
        response = terminal.get("response") if isinstance(terminal.get("response"), dict) else terminal
        videos = response.get("videos") if isinstance(response, dict) else None
        prediction = videos[0] if isinstance(videos, list) and len(videos) == 1 and isinstance(videos[0], dict) else {}
        encoded = prediction.get("bytesBase64Encoded")
        if not isinstance(encoded, str):
            check = "uri_representation_not_admitted" if isinstance(prediction.get("gcsUri"), str) else "inline_base64_field_missing"
            message = "provider returned a URI representation; local URI retrieval is not admitted" if check.startswith("uri") else "image-to-video provider returned no inline video"
            _record_result_failure(evidence, evidence_path, "output_missing", check, message)
            raise VertexVeoProviderFailure("image-to-video provider returned no inline video", _result_diagnostic("output_missing", operation, poll_count, check))
        # Reject by encoded length before allocating a potentially oversized
        # decoded buffer. Four base64 characters represent at most three bytes.
        if len(encoded) > ((256 * 1024 * 1024 + 2) // 3) * 4:
            _record_result_failure(evidence, evidence_path, "output_invalid", "encoded_payload_size", "encoded video payload exceeds 256 MiB")
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                _result_diagnostic("output_invalid", operation, poll_count, "encoded_payload_size"),
            )
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            _record_result_failure(evidence, evidence_path, "output_invalid", "base64_decode", str(exc), exc)
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                _result_diagnostic("output_invalid", operation, poll_count, "base64_decode", exc),
            ) from exc
        if not content:
            _record_result_failure(evidence, evidence_path, "output_invalid", "empty_payload", "decoded video payload is empty")
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                _result_diagnostic("output_invalid", operation, poll_count, "empty_payload"),
            )
        if len(content) > 256 * 1024 * 1024:
            _record_result_failure(evidence, evidence_path, "output_invalid", "payload_size", "decoded video payload exceeds 256 MiB")
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                _result_diagnostic("output_invalid", operation, poll_count, "payload_size"),
            )
        valid_mp4, check = _mp4_check(content)
        if evidence is not None:
            representation = evidence["terminal_response"]["video_representation"]
            representation.update({"decoded_length": len(content), "decoded_sha256": hashlib.sha256(content).hexdigest(),
                                   "magic_hex": content[:MAX_MAGIC_BYTES].hex(), "validation_check": check})
            _persist_evidence(evidence_path, evidence)
        if not valid_mp4:
            _record_result_failure(evidence, evidence_path, "output_invalid", check, "decoded video is not a bounded ISO-BMFF/MP4")
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                _result_diagnostic("output_invalid", operation, poll_count, check),
            )
        digest = hashlib.sha256(content).hexdigest()
        return ImageToVideoResult(GeneratedMedia("video/mp4", content, 1280, 720, digest), max(0, int((time.monotonic() - started) * 1000)), hashlib.sha256(terminal_raw).hexdigest(), operation, "0.000000")


def _parse_json(raw: bytes, stage: str, *, operation_name: str | None = None,
                poll_count: int = 0, submission_accepted: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VertexVeoProviderFailure("image-to-video provider returned invalid JSON", VertexVeoProviderDiagnostic(True, f"{stage}_json_invalid", stage=stage, operation_name=operation_name, poll_count=poll_count, submission_accepted=submission_accepted)) from exc
    if not isinstance(value, dict):
        raise VertexVeoProviderFailure("image-to-video provider returned an invalid object", VertexVeoProviderDiagnostic(True, f"{stage}_schema_invalid", stage=stage, operation_name=operation_name, poll_count=poll_count, submission_accepted=submission_accepted))
    return value


def create_provider() -> VertexVeoImageToVideoProvider:
    return VertexVeoImageToVideoProvider()
