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
    provider_request_body,
)
from vss_movie_creative_smoke.png import inspect_openai_png, validate_openai_png
from vss_movie_creative_smoke.provider import SmokeHTTPResponse, _https_post
from vss_providers import ControlledFrameRequest, ControlledFrameResult, GeneratedMedia
from vss_providers.errors import ProviderAccessDenied, ProviderExecutionFailure
from vss_reasoning_contracts import canonical_digest


MAX_RESPONSE_BYTES = ((MAXIMUM_OUTPUT_BYTES + 2) // 3) * 4 + 65536
MAX_REQUEST_BYTES = 32768


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
            raise ProviderExecutionFailure("controlled frame provider returned invalid JSON") from exc
        allowed_top = {"created", "data", "usage", "background", "output_format", "quality", "size"}
        if not isinstance(value, dict) or set(value) - allowed_top or set(value) < {"data", "usage"}:
            raise ProviderExecutionFailure("controlled frame provider returned an invalid response")
        if "created" in value and (type(value["created"]) is not int or value["created"] < 0):
            raise ProviderExecutionFailure("controlled frame provider returned invalid provenance")
        for name, expected in (("background", "opaque"), ("output_format", "png"),
                               ("quality", "medium"), ("size", "1280x720")):
            if name in value and value[name] != expected:
                raise ProviderExecutionFailure("controlled frame provider response settings drifted")
        data = value["data"]
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise ProviderExecutionFailure("controlled frame provider must return exactly one image")
        image = data[0]
        if set(image) - {"b64_json", "revised_prompt"} or set(image) < {"b64_json"}:
            raise ProviderExecutionFailure("controlled frame provider image payload is invalid")
        if "revised_prompt" in image and not (image["revised_prompt"] is None
                or isinstance(image["revised_prompt"], str) and len(image["revised_prompt"]) <= 4096):
            raise ProviderExecutionFailure("controlled frame provider revised prompt is invalid")
        try:
            content = base64.b64decode(image["b64_json"], validate=True)
        except (KeyError, TypeError, binascii.Error, ValueError) as exc:
            raise ProviderExecutionFailure("controlled frame provider image encoding is invalid") from exc
        if not content or len(content) > MAXIMUM_OUTPUT_BYTES:
            raise ProviderExecutionFailure("controlled frame provider image exceeds its bound")
        summary = validate_openai_png(content)
        if summary.content_credentials_present or inspect_openai_png(content).content_credentials_present:
            raise ProviderExecutionFailure("controlled frame provider output cannot claim VSS Content Credentials")
        raw_usage = value["usage"]
        if not isinstance(raw_usage, dict) or set(raw_usage) - {
                "input_tokens", "output_tokens", "total_tokens", "input_tokens_details"}:
            raise ProviderExecutionFailure("controlled frame provider usage is invalid")
        usage = {}
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            item = raw_usage.get(name)
            if type(item) is not int or not 0 <= item <= 10_000_000:
                raise ProviderExecutionFailure("controlled frame provider usage is incomplete")
            usage[name] = item
        details = raw_usage.get("input_tokens_details")
        if details is not None:
            if (not isinstance(details, dict) or set(details) - {"text_tokens", "image_tokens"}
                    or any(type(item) is not int or not 0 <= item <= 10_000_000 for item in details.values())):
                raise ProviderExecutionFailure("controlled frame provider usage details are invalid")
        estimated = (Decimal(usage["input_tokens"]) * Decimal("5")
                     + Decimal(usage["output_tokens"]) * Decimal("30")) / Decimal(1_000_000)
        estimated_cost = format(estimated.quantize(Decimal("0.000001")), "f")
        if estimated > Decimal(MAXIMUM_COST_USD):
            raise ProviderExecutionFailure("controlled frame provider reported cost above authorization")
        digest = hashlib.sha256(content).hexdigest()
        return ControlledFrameResult(
            media=GeneratedMedia("image/png", content, 1280, 720, digest),
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            usage=MappingProxyType(usage), estimated_cost_usd=estimated_cost,
            response_sha256=hashlib.sha256(response.content).hexdigest(),
            provider_created=value.get("created"), request_id=response.request_id,
            content_credentials_present=False,
        )


def create_provider() -> OpenAIControlledFrameProvider:
    return OpenAIControlledFrameProvider()
