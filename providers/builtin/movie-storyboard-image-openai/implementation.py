from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from decimal import Decimal
from types import MappingProxyType

from vss_movie_controlled_generation.service import (
    ENDPOINT, MAXIMUM_COST_USD, MAXIMUM_OUTPUT_BYTES, MODEL_SNAPSHOT, SETTINGS,
    content_credentials_summary, provider_request_body,
)
from vss_movie_creative_smoke.provider import SmokeHTTPResponse, _https_post
from vss_providers import ControlledFrameRequest, ControlledFrameResult, GeneratedMedia
from vss_providers.errors import ControlledFrameProviderFailure, ProviderAccessDenied, ProviderExecutionFailure
from vss_reasoning_contracts import canonical_digest


MAX_RESPONSE_BYTES = ((MAXIMUM_OUTPUT_BYTES + 2) // 3) * 4 + 65536
MAX_REQUEST_BYTES = 32768


def _evidence(response: SmokeHTTPResponse, value: dict, started: float, *, usage=None,
              estimated_cost=None, content=None, credentials=None) -> dict:
    return {
        "response": {
            "availability": "available", "response_sha256": hashlib.sha256(response.content).hexdigest(),
            "provider_created": value.get("created"), "request_id": response.request_id,
            "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
        },
        "usage_and_cost": {
            "availability": "available" if usage is not None and estimated_cost is not None else "unavailable",
            "input_tokens": usage["input_tokens"] if usage is not None else None,
            "output_tokens": usage["output_tokens"] if usage is not None else None,
            "total_tokens": usage["total_tokens"] if usage is not None else None,
            "estimated_cost_usd": estimated_cost,
        },
        "media": {
            "availability": "available" if content is not None else "unavailable",
            "content_sha256": hashlib.sha256(content).hexdigest() if content is not None else None,
            "byte_count": len(content) if content is not None else None,
            "content_credentials": credentials,
        },
    }


class OpenAIControlledFrameProvider:
    def generate(self, request: ControlledFrameRequest, *, credential: str, transport=None) -> ControlledFrameResult:
        if type(request) is not ControlledFrameRequest:
            raise ProviderAccessDenied("exact controlled frame request is required")
        body = provider_request_body(request.prompt)
        if (request.provider_request_sha256 != canonical_digest(body)
                or not isinstance(request.request_sha256, str)
                or len(request.request_sha256) != 64):
            raise ProviderAccessDenied("controlled frame provider request binding is invalid")
        encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_REQUEST_BYTES or ENDPOINT != "https://api.openai.com/v1/images/generations":
            raise ProviderExecutionFailure("controlled frame provider request is unsafe")
        started = time.monotonic()
        sender = transport or _https_post
        response = sender(
            ENDPOINT, encoded, {"Authorization": "Bearer " + credential, "Content-Type": "application/json"},
            150.0, MAX_RESPONSE_BYTES,
        )
        if isinstance(response, bytes):
            response = SmokeHTTPResponse(response, 200, None)
        if type(response) is not SmokeHTTPResponse or response.status != 200 or len(response.content) > MAX_RESPONSE_BYTES:
            raise ProviderExecutionFailure("controlled frame provider returned an invalid response envelope")
        try:
            value = json.loads(response.content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlledFrameProviderFailure(
                "controlled frame provider returned invalid JSON", classification="response_invalid",
                evidence=_evidence(response, {}, started),
            ) from exc
        allowed_top = {"created", "data", "usage", "background", "output_format", "quality", "size"}
        if not isinstance(value, dict) or set(value) - allowed_top or set(value) < {"data", "usage"}:
            raise ControlledFrameProviderFailure(
                "controlled frame provider returned an invalid response", classification="response_invalid",
                evidence=_evidence(response, value if isinstance(value, dict) else {}, started),
            )
        if "created" in value and (type(value["created"]) is not int or value["created"] < 0):
            raise ControlledFrameProviderFailure(
                "controlled frame provider returned invalid provenance", classification="response_invalid",
                evidence=_evidence(response, {}, started),
            )
        for name, expected in (("background", "opaque"), ("output_format", "png"),
                               ("quality", "medium"), ("size", "1280x720")):
            if name in value and value[name] != expected:
                raise ControlledFrameProviderFailure(
                    "controlled frame provider response settings drifted", classification="response_invalid",
                    evidence=_evidence(response, value, started),
                )
        raw_usage = value["usage"]
        if not isinstance(raw_usage, dict) or set(raw_usage) - {
                "input_tokens", "output_tokens", "total_tokens", "input_tokens_details"}:
            raise ControlledFrameProviderFailure(
                "controlled frame provider usage is invalid", classification="response_invalid",
                evidence=_evidence(response, value, started),
            )
        usage = {}
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            item = raw_usage.get(name)
            if type(item) is not int or not 0 <= item <= 10_000_000:
                raise ControlledFrameProviderFailure(
                    "controlled frame provider usage is incomplete", classification="response_invalid",
                    evidence=_evidence(response, value, started),
                )
            usage[name] = item
        details = raw_usage.get("input_tokens_details")
        if details is not None:
            if (not isinstance(details, dict) or set(details) - {"text_tokens", "image_tokens"}
                    or any(type(item) is not int or not 0 <= item <= 10_000_000 for item in details.values())):
                raise ControlledFrameProviderFailure(
                    "controlled frame provider usage details are invalid", classification="response_invalid",
                    evidence=_evidence(response, value, started),
                )
        estimated = (Decimal(usage["input_tokens"]) * Decimal("5")
                     + Decimal(usage["output_tokens"]) * Decimal("30")) / Decimal(1_000_000)
        estimated_cost = format(estimated.quantize(Decimal("0.000001")), "f")
        if estimated > Decimal(MAXIMUM_COST_USD):
            raise ControlledFrameProviderFailure(
                "controlled frame provider reported cost above authorization",
                classification="cost_exceeded",
                evidence=_evidence(response, value, started, usage=usage, estimated_cost=estimated_cost),
            )
        data = value["data"]
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise ControlledFrameProviderFailure(
                "controlled frame provider must return exactly one image", classification="response_invalid",
                evidence=_evidence(response, value, started, usage=usage, estimated_cost=estimated_cost),
            )
        image = data[0]
        if set(image) - {"b64_json", "revised_prompt"} or set(image) < {"b64_json"}:
            raise ControlledFrameProviderFailure(
                "controlled frame provider image payload is invalid", classification="response_invalid",
                evidence=_evidence(response, value, started, usage=usage, estimated_cost=estimated_cost),
            )
        if "revised_prompt" in image and not (image["revised_prompt"] is None
                or isinstance(image["revised_prompt"], str) and len(image["revised_prompt"]) <= 4096):
            raise ControlledFrameProviderFailure(
                "controlled frame provider revised prompt is invalid", classification="response_invalid",
                evidence=_evidence(response, value, started, usage=usage, estimated_cost=estimated_cost),
            )
        try:
            content = base64.b64decode(image["b64_json"], validate=True)
        except (KeyError, TypeError, binascii.Error, ValueError) as exc:
            raise ControlledFrameProviderFailure(
                "controlled frame provider image encoding is invalid", classification="output_invalid",
                evidence=_evidence(response, value, started, usage=usage, estimated_cost=estimated_cost),
            ) from exc
        if not content or len(content) > MAXIMUM_OUTPUT_BYTES:
            raise ControlledFrameProviderFailure(
                "controlled frame provider image exceeds its bound", classification="output_invalid",
                evidence=_evidence(response, value, started, usage=usage, estimated_cost=estimated_cost),
            )
        try:
            credentials = content_credentials_summary(content)
        except ProviderExecutionFailure as exc:
            raise ControlledFrameProviderFailure(
                "controlled frame provider returned invalid PNG", classification="output_invalid",
                evidence=_evidence(response, value, started, usage=usage,
                                   estimated_cost=estimated_cost, content=content),
            ) from exc
        digest = hashlib.sha256(content).hexdigest()
        return ControlledFrameResult(
            media=GeneratedMedia("image/png", content, 1280, 720, digest),
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            usage=MappingProxyType(usage), estimated_cost_usd=estimated_cost,
            response_sha256=hashlib.sha256(response.content).hexdigest(),
            provider_created=value.get("created"), request_id=response.request_id,
            content_credentials=MappingProxyType(credentials),
        )


def create_provider() -> OpenAIControlledFrameProvider:
    return OpenAIControlledFrameProvider()
