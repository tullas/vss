from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Callable, Mapping

from vss_providers import GeneratedMedia, ProviderAccessDenied, ProviderExecutionFailure, ProviderUnavailable
from vss_reasoning_contracts import canonical_digest

from .png import MAX_DECODED_MEDIA_BYTES, PNGSummary, inspect_openai_png, validate_openai_png
from .service import (
    ENDPOINT, EXPECTED_DEPICTION_PROJECTION_DIGEST, MAXIMUM_ESTIMATED_COST_USD,
    MODEL_IDENTITY, OUTPUT_FORMAT, OUTPUT_HEIGHT, OUTPUT_QUALITY, OUTPUT_WIDTH,
)

SECRET_NAME = "VSS_EXPERIMENT_M8_3_SMOKE_OPENAI_API_KEY"  # pragma: allowlist secret
BASE64_RESPONSE_BYTES = ((MAX_DECODED_MEDIA_BYTES + 2) // 3) * 4
RESPONSE_ENVELOPE_OVERHEAD_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = BASE64_RESPONSE_BYTES + RESPONSE_ENVELOPE_OVERHEAD_BYTES
MAX_ERROR_RESPONSE_BYTES = 8192
MAX_REQUEST_BYTES = 32768
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
KNOWN_ERROR_TYPES = frozenset({
    "invalid_request_error", "authentication_error", "permission_error",
    "rate_limit_error", "server_error", "api_error",
})
KNOWN_ERROR_CODES = frozenset({
    "invalid_api_key", "insufficient_quota", "rate_limit_exceeded", "model_not_found",
    "invalid_model", "billing_hard_limit_reached", "organization_verification_required",
    "project_not_found",
})
CLASSIFICATIONS = frozenset({
    "http_redirect", "http_bad_request", "http_authentication", "http_access",
    "http_rate_limit", "http_server", "http_other", "malformed_error_response",
    "oversized_error_response", "dns", "connect", "tls", "timeout", "other_transport",
    "response_too_large", "response_json_invalid", "response_schema_invalid",
    "image_payload_missing", "image_payload_invalid", "base64_invalid",
    "decoded_media_too_large", "png_conformance_failed", "provider_result_invalid",
})


@dataclass(frozen=True, slots=True)
class SmokeProviderDiagnostic:
    http_response_received: bool
    classification: str
    http_status: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    request_id: str | None = None
    encoded_response_bytes: int | None = None
    decoded_media_bytes: int | None = None
    media_sha256: str | None = None
    png: PNGSummary | None = None

    def __post_init__(self) -> None:
        error_types = {None, *KNOWN_ERROR_TYPES, "other_provider_error"}
        error_codes = {None, *KNOWN_ERROR_CODES, "other_provider_code"}
        if (type(self.http_response_received) is not bool or self.classification not in CLASSIFICATIONS
                or self.error_type not in error_types or self.error_code not in error_codes
                or not (self.http_status is None or type(self.http_status) is int and 100 <= self.http_status <= 599)
                or not (self.request_id is None or isinstance(self.request_id, str)
                        and SAFE_REQUEST_ID.fullmatch(self.request_id))
                or not all(value is None or type(value) is int and 0 <= value <= 16 * 1024 * 1024
                           for value in (self.encoded_response_bytes, self.decoded_media_bytes))
                or not (self.media_sha256 is None or isinstance(self.media_sha256, str)
                        and re.fullmatch(r"[0-9a-f]{64}", self.media_sha256))
                or not (self.png is None or type(self.png) is PNGSummary)
                or not self.http_response_received and self.http_status is not None):
            raise ValueError("creative smoke provider diagnostic is unsafe")

    def as_dict(self) -> dict[str, object]:
        return {
            "http_response_received": self.http_response_received,
            "classification": self.classification,
            "http_status": self.http_status,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "message": "external image provider failed with a bounded classification",
            "request_id": self.request_id,
            "encoded_response_bytes": self.encoded_response_bytes,
            "decoded_media_bytes": self.decoded_media_bytes,
            "media_sha256": self.media_sha256,
            "png": self.png.as_dict() if self.png is not None else None,
        }


class SmokeProviderFailure(ProviderExecutionFailure):
    def __init__(self, message: str, diagnostic: SmokeProviderDiagnostic | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


@dataclass(frozen=True, slots=True)
class SmokeHTTPResponse:
    content: bytes
    status: int
    request_id: str | None


@dataclass(frozen=True, slots=True)
class SmokeProviderRequest:
    prompt: str
    provider_request_digest: str
    depiction_projection_digest: str


@dataclass(frozen=True, slots=True)
class SmokeProviderResult:
    media: GeneratedMedia
    latency_ms: int
    provider_call_count: int
    usage: Mapping[str, int]
    estimated_cost_usd: str | None
    png: PNGSummary


Transport = Callable[[str, bytes, dict[str, str], float, int], bytes | SmokeHTTPResponse]


def _safe_known(value: object, known: frozenset[str], fallback: str) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and SAFE_IDENTIFIER.fullmatch(value) and value in known else fallback


def _http_classification(status: int) -> str:
    if 300 <= status <= 399:
        return "http_redirect"
    return {400: "http_bad_request", 401: "http_authentication", 403: "http_access",
            429: "http_rate_limit"}.get(status, "http_server" if 500 <= status <= 599 else "http_other")


def _http_diagnostic(exc: urllib.error.HTTPError) -> SmokeProviderDiagnostic:
    status = int(exc.code) if isinstance(exc.code, int) and 100 <= exc.code <= 599 else None
    request_id = None
    if exc.headers is not None:
        candidate = exc.headers.get("x-request-id")
        if isinstance(candidate, str) and SAFE_REQUEST_ID.fullmatch(candidate):
            request_id = candidate
    classification = _http_classification(status) if status is not None else "http_other"
    if classification == "http_redirect":
        return SmokeProviderDiagnostic(True, classification, status, request_id=request_id)
    error_type = error_code = None
    try:
        content = exc.read(MAX_ERROR_RESPONSE_BYTES + 1)
    except Exception:
        content = b""
    if len(content) > MAX_ERROR_RESPONSE_BYTES:
        classification = "oversized_error_response"
    elif content:
        try:
            value = json.loads(content)
            error = value.get("error") if isinstance(value, dict) and set(value) == {"error"} else None
            if not isinstance(error, dict) or set(error) - {"message", "type", "param", "code"}:
                raise ValueError
            error_type = _safe_known(error.get("type"), KNOWN_ERROR_TYPES, "other_provider_error")
            error_code = _safe_known(error.get("code"), KNOWN_ERROR_CODES, "other_provider_code")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            classification = "malformed_error_response"
    return SmokeProviderDiagnostic(True, classification, status, error_type, error_code, request_id)


def _transport_diagnostic(exc: BaseException) -> SmokeProviderDiagnostic:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, (TimeoutError, socket.timeout)):
        classification = "timeout"
    elif isinstance(reason, socket.gaierror):
        classification = "dns"
    elif isinstance(reason, ssl.SSLError):
        classification = "tls"
    elif isinstance(reason, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        classification = "connect"
    else:
        classification = "other_transport"
    return SmokeProviderDiagnostic(False, classification)


class _DenyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect denied", headers, fp)


def _urlopen_no_redirect(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(_DenyRedirects()).open(request, timeout=timeout)


def _https_post(url: str, body: bytes, headers: dict[str, str], timeout: float, maximum: int) -> SmokeHTTPResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _urlopen_no_redirect(request, timeout) as response:
            content = response.read(maximum + 1)
            candidate = response.headers.get("x-request-id") if response.headers is not None else None
            request_id = candidate if isinstance(candidate, str) and SAFE_REQUEST_ID.fullmatch(candidate) else None
            status = int(response.status)
            if status != 200:
                raise SmokeProviderFailure("external image provider returned an unsuccessful status",
                                           SmokeProviderDiagnostic(True, _http_classification(status), status,
                                                                   request_id=request_id))
    except urllib.error.HTTPError as exc:
        raise SmokeProviderFailure("external image provider returned an unsuccessful status", _http_diagnostic(exc)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SmokeProviderFailure("external image provider request failed", _transport_diagnostic(exc)) from exc
    if len(content) > maximum:
        raise SmokeProviderFailure("external image provider response exceeded its bound",
            SmokeProviderDiagnostic(True, "response_too_large", 200, request_id=request_id,
                                    encoded_response_bytes=len(content)))
    return SmokeHTTPResponse(content, 200, request_id)


def _post_failure(stage: str, response: SmokeHTTPResponse, *, decoded: bytes | None = None,
                  png: PNGSummary | None = None) -> SmokeProviderFailure:
    return SmokeProviderFailure(
        "external image provider returned an invalid bounded response",
        SmokeProviderDiagnostic(
            True, stage, response.status, request_id=response.request_id,
            encoded_response_bytes=len(response.content),
            decoded_media_bytes=len(decoded) if decoded is not None else None,
            media_sha256=hashlib.sha256(decoded).hexdigest() if decoded is not None else None,
            png=png,
        ),
    )


def _estimated_cost(usage: Mapping[str, int]) -> str | None:
    if "input_tokens" not in usage or "output_tokens" not in usage:
        return None
    value = Decimal(usage["input_tokens"]) * Decimal("5") / Decimal(1_000_000)
    value += Decimal(usage["output_tokens"]) * Decimal("30") / Decimal(1_000_000)
    return format(value.quantize(Decimal("0.000001")), "f")


@dataclass(slots=True)
class OpenAIImageSmokeAccess:
    transport: Transport = _https_post
    secret_reader: Callable[[str], str | None] = os.environ.get
    _calls: int = 0
    _prepared_request: SmokeProviderRequest | None = None
    _prepared_body: bytes | None = None

    def prepare(self, request: SmokeProviderRequest) -> str:
        if type(request) is not SmokeProviderRequest:
            raise SmokeProviderFailure("exact creative smoke request is required")
        if request.depiction_projection_digest != EXPECTED_DEPICTION_PROJECTION_DIGEST:
            raise ProviderAccessDenied("creative smoke depiction binding is invalid")
        if self._calls or self._prepared_request is not None:
            raise ProviderAccessDenied("creative smoke provider call ceiling exceeded")
        body = {
            "model": MODEL_IDENTITY,
            "prompt": request.prompt,
            "n": 1,
            "size": f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}",
            "quality": OUTPUT_QUALITY,
            "output_format": OUTPUT_FORMAT,
        }
        authoritative_digest = canonical_digest(body)
        if authoritative_digest != request.provider_request_digest:
            raise ProviderAccessDenied("creative smoke provider request binding is invalid")
        encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_REQUEST_BYTES:
            raise SmokeProviderFailure("external image provider request exceeded its bound")
        if ENDPOINT != "https://api.openai.com/v1/images/generations":
            raise SmokeProviderFailure("external image provider egress destination is invalid")
        self._prepared_request = request
        self._prepared_body = encoded
        return authoritative_digest

    def generate(self, request: SmokeProviderRequest, *, timeout_seconds: float = 120.0) -> SmokeProviderResult:
        if (type(request) is not SmokeProviderRequest or request != self._prepared_request
                or self._prepared_body is None):
            raise ProviderAccessDenied("creative smoke request was not preflighted")
        if self._calls:
            raise ProviderAccessDenied("creative smoke provider call ceiling exceeded")
        self._calls += 1
        secret = self.secret_reader(SECRET_NAME)
        if not isinstance(secret, str) or not secret or len(secret) > 512:
            raise ProviderUnavailable("external image provider credential is unavailable")
        started = time.monotonic()
        response = self.transport(
            ENDPOINT, self._prepared_body,
            {"Authorization": "Bearer " + secret, "Content-Type": "application/json"},
            timeout_seconds, MAX_RESPONSE_BYTES,
        )
        if isinstance(response, bytes):
            if len(response) > MAX_RESPONSE_BYTES:
                raise SmokeProviderFailure("external image provider response exceeded its bound",
                    SmokeProviderDiagnostic(True, "response_too_large", 200,
                                            encoded_response_bytes=len(response)))
            response = SmokeHTTPResponse(response, 200, None)
        if type(response) is not SmokeHTTPResponse or response.status != 200:
            raise SmokeProviderFailure("external image provider returned an invalid response envelope")
        try:
            value = json.loads(response.content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _post_failure("response_json_invalid", response) from exc
        allowed_top = {"created", "data", "usage", "background", "output_format", "quality", "size"}
        if not isinstance(value, dict) or set(value) - allowed_top or "data" not in value:
            raise _post_failure("response_schema_invalid", response)
        data = value["data"]
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise _post_failure("image_payload_invalid", response)
        image = data[0]
        if set(image) - {"b64_json", "revised_prompt", "url"}:
            raise _post_failure("image_payload_invalid", response)
        if any(name in image and not (image[name] is None or isinstance(image[name], str) and len(image[name]) <= 4096)
               for name in ("revised_prompt", "url")):
            raise _post_failure("image_payload_invalid", response)
        if "b64_json" not in image:
            raise _post_failure("image_payload_missing", response)
        if not isinstance(image["b64_json"], str):
            raise _post_failure("image_payload_invalid", response)
        try:
            content = base64.b64decode(image["b64_json"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise _post_failure("base64_invalid", response) from exc
        if len(content) > MAX_DECODED_MEDIA_BYTES:
            raise _post_failure("decoded_media_too_large", response, decoded=content)
        raw_usage = value.get("usage", {})
        if not isinstance(raw_usage, dict):
            raise _post_failure("response_schema_invalid", response, decoded=content)
        usage = {
            key: raw_usage[key]
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if key in raw_usage and type(raw_usage[key]) is int and 0 <= raw_usage[key] <= 10_000_000
        }
        try:
            png = validate_openai_png(content)
        except ProviderExecutionFailure as exc:
            raise _post_failure("png_conformance_failed", response, decoded=content,
                                png=inspect_openai_png(content)) from exc
        digest = hashlib.sha256(content).hexdigest()
        media = GeneratedMedia("image/png", content, OUTPUT_WIDTH, OUTPUT_HEIGHT, digest)
        result = SmokeProviderResult(
            media=media,
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            provider_call_count=1,
            usage=MappingProxyType(usage),
            estimated_cost_usd=_estimated_cost(usage),
            png=png,
        )
        if result.estimated_cost_usd is not None and Decimal(result.estimated_cost_usd) > Decimal(MAXIMUM_ESTIMATED_COST_USD):
            raise _post_failure("provider_result_invalid", response, decoded=content, png=png)
        return result
