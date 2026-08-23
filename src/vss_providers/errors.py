from __future__ import annotations

from dataclasses import dataclass
import re

from vss_commands.exit_codes import ExitCode


@dataclass(frozen=True, slots=True)
class ExperimentalPNGDiagnostic:
    width: int | None
    height: int | None
    bit_depth: int | None
    color_type: int | None
    interlace: int | None
    chunk_types: tuple[str, ...]
    rejection_reason: str
    content_credentials_present: bool = False
    content_credentials_chunk_bytes: int | None = None

    def __post_init__(self) -> None:
        if (not all(value is None or type(value) is int and 0 <= value <= 100000 for value in
                    (self.width, self.height, self.bit_depth, self.color_type, self.interlace))
                or len(self.chunk_types) > 32
                or any(value != "malformed" and not re.fullmatch(r"[A-Za-z]{2}[A-Z][A-Za-z]", value)
                       for value in self.chunk_types)
                or self.rejection_reason not in {"invalid_signature", "malformed_structure", "disallowed_chunk",
                                                 "unsupported_profile", "invalid_crc", "invalid_order",
                                                 "duplicate_content_credentials", "content_credentials_too_large",
                                                 "conformance_failed"}
                or type(self.content_credentials_present) is not bool
                or not (self.content_credentials_chunk_bytes is None
                        or type(self.content_credentials_chunk_bytes) is int
                        and 0 <= self.content_credentials_chunk_bytes <= 10 * 1024 * 1024)
                or (not self.content_credentials_present and self.content_credentials_chunk_bytes is not None)):
            raise ValueError("experimental PNG diagnostic is unsafe")

    def as_dict(self) -> dict[str, object]:
        return {"width": self.width, "height": self.height, "bit_depth": self.bit_depth,
                "color_type": self.color_type, "interlace": self.interlace,
                "chunk_types": list(self.chunk_types), "rejection_reason": self.rejection_reason,
                "content_credentials_present": self.content_credentials_present,
                "content_credentials_chunk_bytes": self.content_credentials_chunk_bytes}


@dataclass(frozen=True, slots=True)
class ExperimentalProviderDiagnostic:
    http_response_received: bool
    classification: str
    http_status: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    request_id: str | None = None
    encoded_response_bytes: int | None = None
    decoded_media_bytes: int | None = None
    media_sha256: str | None = None
    png: ExperimentalPNGDiagnostic | None = None

    def __post_init__(self) -> None:
        classifications = {"http_redirect", "http_bad_request", "http_authentication", "http_access", "http_rate_limit",
                           "http_server", "http_other", "malformed_error_response", "oversized_error_response",
                           "dns", "connect", "tls", "timeout", "other_transport", "response_too_large",
                           "response_json_invalid", "response_schema_invalid", "image_payload_missing",
                           "image_payload_invalid", "base64_invalid", "decoded_media_too_large",
                           "png_conformance_failed", "provider_result_invalid"}
        error_types = {None, "invalid_request_error", "authentication_error", "permission_error",
                       "rate_limit_error", "server_error", "api_error", "other_provider_error"}
        error_codes = {None, "invalid_api_key", "insufficient_quota", "rate_limit_exceeded", "model_not_found",
                       "invalid_model", "billing_hard_limit_reached", "organization_verification_required",
                       "project_not_found", "other_provider_code"}
        messages = {None, "provider returned a sanitized error classification",
                    "provider transport failed with a sanitized classification",
                    "provider response failed bounded validation"}
        if (type(self.http_response_received) is not bool or self.classification not in classifications
                or self.error_type not in error_types or self.error_code not in error_codes or self.message not in messages
                or not (self.http_status is None or type(self.http_status) is int and 100 <= self.http_status <= 599)
                or not (self.request_id is None or isinstance(self.request_id, str)
                        and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.request_id))
                or not all(value is None or type(value) is int and 0 <= value <= 16 * 1024 * 1024
                           for value in (self.encoded_response_bytes, self.decoded_media_bytes))
                or not (self.media_sha256 is None or isinstance(self.media_sha256, str)
                        and re.fullmatch(r"[0-9a-f]{64}", self.media_sha256))
                or not (self.png is None or type(self.png) is ExperimentalPNGDiagnostic)):
            raise ValueError("experimental provider diagnostic is unsafe")
        if not self.http_response_received and self.http_status is not None:
            raise ValueError("experimental provider diagnostic response classification is inconsistent")

    def as_dict(self) -> dict[str, object]:
        return {"http_response_received": self.http_response_received, "classification": self.classification,
                "http_status": self.http_status, "error_type": self.error_type, "error_code": self.error_code,
                "message": self.message, "request_id": self.request_id,
                "encoded_response_bytes": self.encoded_response_bytes,
                "decoded_media_bytes": self.decoded_media_bytes, "media_sha256": self.media_sha256,
                "png": self.png.as_dict() if self.png is not None else None}


class ProviderFailure(RuntimeError):
    exit_code = ExitCode.EXECUTION_FAILURE
    category = "provider_execution_failure"


class ProviderNotFound(ProviderFailure):
    exit_code = ExitCode.NOT_READY
    category = "provider_not_found"


class ProviderUnavailable(ProviderFailure):
    exit_code = ExitCode.NOT_READY
    category = "provider_unavailable"


class ProviderIncompatible(ProviderFailure):
    exit_code = ExitCode.INVALID_CONFIGURATION
    category = "provider_incompatible"


class ProviderAccessDenied(ProviderFailure):
    exit_code = ExitCode.PERMISSION_DENIED
    category = "provider_access_denied"


class ProviderExecutionFailure(ProviderFailure):
    def __init__(self, message: str, *, diagnostic: ExperimentalProviderDiagnostic | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic
