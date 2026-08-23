from __future__ import annotations

import json
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .errors import ExperimentalProviderDiagnostic, ProviderExecutionFailure, ProviderUnavailable
from .experimental_png import MAX_BYTES as MAX_DECODED_MEDIA_BYTES

ENDPOINT = "https://api.openai.com/v1/images/generations"
SECRET_NAME = "VSS_EXPERIMENT_OPENAI_API_KEY"  # pragma: allowlist secret
BASE64_RESPONSE_BYTES = ((MAX_DECODED_MEDIA_BYTES + 2) // 3) * 4
RESPONSE_ENVELOPE_OVERHEAD_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = BASE64_RESPONSE_BYTES + RESPONSE_ENVELOPE_OVERHEAD_BYTES
MAX_ERROR_RESPONSE_BYTES = 8192
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
KNOWN_ERROR_TYPES = frozenset({"invalid_request_error", "authentication_error", "permission_error",
                               "rate_limit_error", "server_error", "api_error"})
KNOWN_ERROR_CODES = frozenset({"invalid_api_key", "insufficient_quota", "rate_limit_exceeded",
                               "model_not_found", "invalid_model", "billing_hard_limit_reached",
                               "organization_verification_required", "project_not_found"})


@dataclass(frozen=True, slots=True)
class ExperimentalHTTPResponse:
    content: bytes
    status: int
    request_id: str | None


Transport = Callable[[str, bytes, dict[str, str], float, int], bytes | ExperimentalHTTPResponse]


def _safe_known(value: object, known: frozenset[str], fallback: str) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and SAFE_IDENTIFIER.fullmatch(value) and value in known else fallback


def _http_classification(status: int) -> str:
    if 300 <= status <= 399:
        return "http_redirect"
    return {400: "http_bad_request", 401: "http_authentication", 403: "http_access",
            429: "http_rate_limit"}.get(status, "http_server" if 500 <= status <= 599 else "http_other")


def _http_diagnostic(exc: urllib.error.HTTPError) -> ExperimentalProviderDiagnostic:
    status = int(exc.code) if isinstance(exc.code, int) and 100 <= exc.code <= 599 else None
    request_id = None
    if exc.headers is not None:
        candidate = exc.headers.get("x-request-id")
        if isinstance(candidate, str) and SAFE_REQUEST_ID.fullmatch(candidate):
            request_id = candidate
    classification = _http_classification(status) if status is not None else "http_other"
    error_type = error_code = None
    if classification == "http_redirect":
        return ExperimentalProviderDiagnostic(True, classification, status,
            message="provider returned a sanitized error classification", request_id=request_id)
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
    return ExperimentalProviderDiagnostic(True, classification, status, error_type, error_code,
        "provider returned a sanitized error classification", request_id)


def _transport_diagnostic(exc: BaseException) -> ExperimentalProviderDiagnostic:
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
    return ExperimentalProviderDiagnostic(False, classification,
        message="provider transport failed with a sanitized classification")


class _DenyRedirects(urllib.request.HTTPRedirectHandler):
    """Fail closed before urllib can construct a request for another destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001 - stdlib override
        raise urllib.error.HTTPError(req.full_url, code, "redirect denied", headers, fp)


def _urlopen_no_redirect(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(_DenyRedirects()).open(request, timeout=timeout)


def _https_post(url: str, body: bytes, headers: dict[str, str], timeout: float, maximum: int) -> ExperimentalHTTPResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _urlopen_no_redirect(request, timeout) as response:  # exact origin; redirects denied above
            if response.status != 200:
                raise ProviderExecutionFailure("external image provider returned an unsuccessful status")
            content = response.read(maximum + 1)
            candidate = response.headers.get("x-request-id") if response.headers is not None else None
            request_id = candidate if isinstance(candidate, str) and SAFE_REQUEST_ID.fullmatch(candidate) else None
    except urllib.error.HTTPError as exc:
        raise ProviderExecutionFailure("external image provider returned an unsuccessful status",
            diagnostic=_http_diagnostic(exc)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderExecutionFailure("external image provider request failed",
            diagnostic=_transport_diagnostic(exc)) from exc
    if len(content) > maximum:
        raise ProviderExecutionFailure("external image provider response exceeded its bound", diagnostic=
            ExperimentalProviderDiagnostic(True, "response_too_large", 200,
                message="provider response failed bounded validation", request_id=request_id,
                encoded_response_bytes=len(content)))
    return ExperimentalHTTPResponse(content, 200, request_id)


@dataclass(frozen=True, slots=True)
class ExperimentalOpenAIExecutionAccess:
    transport: Transport = _https_post
    secret_reader: Callable[[str], str | None] = os.environ.get

    def post_images(self, body: dict[str, object], *, timeout_seconds: float = 90.0) -> ExperimentalHTTPResponse:
        if ENDPOINT != "https://api.openai.com/v1/images/generations":
            raise ProviderUnavailable("external provider egress destination is invalid")
        secret = self.secret_reader(SECRET_NAME)
        if not isinstance(secret, str) or not secret or len(secret) > 512:
            raise ProviderUnavailable("external image provider credential is unavailable")
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 32768:
            raise ProviderExecutionFailure("external image provider request exceeded its bound")
        headers = {"Authorization": "Bearer " + secret, "Content-Type": "application/json"}
        response = self.transport(ENDPOINT, encoded, headers, timeout_seconds, MAX_RESPONSE_BYTES)
        if isinstance(response, bytes):
            if len(response) > MAX_RESPONSE_BYTES:
                raise ProviderExecutionFailure("external image provider response exceeded its bound", diagnostic=
                    ExperimentalProviderDiagnostic(True, "response_too_large", 200,
                        message="provider response failed bounded validation",
                        encoded_response_bytes=len(response)))
            return ExperimentalHTTPResponse(response, 200, None)
        if type(response) is not ExperimentalHTTPResponse or response.status != 200:
            raise ProviderExecutionFailure("external image provider returned an invalid response envelope")
        return response
