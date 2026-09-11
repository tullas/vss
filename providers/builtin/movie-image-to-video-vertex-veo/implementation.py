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
from vss_providers import GeneratedMedia, ImageToVideoRequest, ImageToVideoResult, ProviderExecutionFailure

POLL_INTERVAL_SECONDS = 5.0
_BEARER_PREFIX = re.compile(r"(?i)^Bearer(?:\s|$)")


def _https_json(url: str, body: bytes, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(128 * 1024 * 1024 + 1)


def _default_transport(url: str, body: bytes, headers: dict[str, str], timeout: float, maximum: int) -> bytes:
    return _https_json(url, body, headers, timeout)


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

    __slots__ = ("http_response_received", "classification", "http_status", "error_code", "message", "stage", "operation_name", "poll_count", "submission_accepted")

    def __init__(self, http_response_received: bool, classification: str,
                 http_status: int | None = None, error_code: str | None = None,
                 message: str | None = None, *, stage: str = "submission",
                 operation_name: str | None = None, poll_count: int = 0,
                 submission_accepted: bool = False) -> None:
        self.http_response_received = http_response_received
        self.classification = classification
        self.http_status = http_status
        self.error_code = error_code
        self.message = message
        self.stage = stage
        self.operation_name = operation_name
        self.poll_count = poll_count
        self.submission_accepted = submission_accepted

    def as_dict(self) -> dict[str, object]:
        return {
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


class VertexVeoProviderFailure(ProviderExecutionFailure):
    """Terminal failure from the one already-reserved provider attempt."""

    def __init__(self, message: str, diagnostic: VertexVeoProviderDiagnostic) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


def _persist_operation(request: ImageToVideoRequest, operation: str, endpoint: str) -> None:
    path = getattr(request, "operation_evidence_path", None)
    if path is None:
        return
    if not isinstance(path, Path):
        raise VertexVeoProviderFailure(
            "image-to-video operation evidence destination is invalid",
            VertexVeoProviderDiagnostic(
                True, "operation_persistence_failed", stage="submission",
                operation_name=operation, submission_accepted=True,
            ),
        )
    try:
        path.write_text(json.dumps({
            "operation_name": operation,
            "endpoint": endpoint,
            "method": "POST",
            "request_sha256": request.request_sha256,
            "submission_accepted": True,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise VertexVeoProviderFailure(
            "image-to-video operation evidence persistence failed",
            VertexVeoProviderDiagnostic(
                True, "operation_persistence_failed", stage="submission",
                operation_name=operation, submission_accepted=True,
            ),
        ) from exc


def _safe_message(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    # Provider messages are useful evidence, but must never retain credentials,
    # URLs with query material, or unbounded response content.
    value = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[redacted]", value)
    value = re.sub(r"https?://[^\s]+", "[url redacted]", value)
    value = " ".join(value.split())
    return value[:1024] or None


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
            raw = sender(endpoint, body, headers, 900.0, 128 * 1024 * 1024)
        except urllib.error.HTTPError as exc:
            raise _http_failure(exc, stage="submission") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise _transport_failure(exc, stage="submission") from exc
        value = _parse_json(raw, "submission", submission_accepted=False)
        operation = value.get("name") if isinstance(value, dict) else None
        expected_prefix = f"projects/{project}/locations/{LOCATION}/publishers/google/models/{MODEL_SNAPSHOT}/operations/"
        if not isinstance(operation, str) or not operation.startswith(expected_prefix) or len(operation) > 512:
            raise VertexVeoProviderFailure("image-to-video provider returned an invalid operation", VertexVeoProviderDiagnostic(True, "operation_invalid", stage="submission"))
        _persist_operation(request, operation, endpoint)
        poll_endpoint = endpoint.rsplit(":", 1)[0] + ":fetchPredictOperation"
        terminal_raw = None
        terminal = None
        poll_count = 0
        for _ in range(360):
            poll_count += 1
            try:
                terminal_raw = sender(poll_endpoint, json.dumps({"operationName": operation}, separators=(",", ":")).encode(), headers, 30.0, 128 * 1024 * 1024)
            except urllib.error.HTTPError as exc:
                raise _http_failure(exc, stage="polling", operation_name=operation,
                                    poll_count=poll_count, submission_accepted=True) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise _transport_failure(exc, stage="polling", operation_name=operation,
                                         poll_count=poll_count, submission_accepted=True) from exc
            terminal = _parse_json(terminal_raw, "operation", operation_name=operation,
                                   poll_count=poll_count, submission_accepted=True)
            if terminal.get("done") is True:
                break
            time.sleep(POLL_INTERVAL_SECONDS)
        if not isinstance(terminal, dict) or terminal.get("done") is not True:
            raise VertexVeoProviderFailure("image-to-video provider operation timed out", VertexVeoProviderDiagnostic(True, "operation_timeout", stage="polling", operation_name=operation, poll_count=poll_count, submission_accepted=True))
        if isinstance(terminal.get("error"), dict):
            error = terminal["error"]
            raise VertexVeoProviderFailure("image-to-video provider operation failed", VertexVeoProviderDiagnostic(True, "operation_failed", error_code=_safe_message(str(error.get("status", error.get("code", "unknown")))), message=_safe_message(error.get("message")), stage="polling", operation_name=operation, poll_count=poll_count, submission_accepted=True))
        response = terminal.get("response") if isinstance(terminal.get("response"), dict) else terminal
        videos = response.get("videos") if isinstance(response, dict) else None
        prediction = videos[0] if isinstance(videos, list) and len(videos) == 1 and isinstance(videos[0], dict) else {}
        encoded = prediction.get("bytesBase64Encoded")
        if not isinstance(encoded, str):
            raise VertexVeoProviderFailure("image-to-video provider returned no inline video", VertexVeoProviderDiagnostic(True, "output_missing", stage="result_retrieval", operation_name=operation, poll_count=poll_count, submission_accepted=True))
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                VertexVeoProviderDiagnostic(
                    True, "output_invalid", stage="result_retrieval",
                    operation_name=operation, poll_count=poll_count,
                    submission_accepted=True,
                ),
            ) from exc
        if not content or len(content) > 256 * 1024 * 1024 or content[:8] != b"\x00\x00\x00\x18ftyp":
            raise VertexVeoProviderFailure(
                "image-to-video provider returned invalid inline video",
                VertexVeoProviderDiagnostic(
                    True, "output_invalid", stage="result_retrieval",
                    operation_name=operation, poll_count=poll_count,
                    submission_accepted=True,
                ),
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
