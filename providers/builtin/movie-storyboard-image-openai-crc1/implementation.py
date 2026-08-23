from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time

from vss_providers.contracts import CreativeExperimentRequest, CreativeExperimentResult, GeneratedMedia
from vss_providers.errors import ExperimentalProviderDiagnostic, ProviderExecutionFailure
from vss_providers.experimental_png import MAX_BYTES, inspect_experimental_png, validate_experimental_openai_png

MODEL = "gpt-image-2-2026-04-21"


class OpenAICreativeRealityCheckProvider:
    def __init__(self, access) -> None:
        self._access = access

    def generate(self, request: CreativeExperimentRequest) -> CreativeExperimentResult:
        if type(request) is not CreativeExperimentRequest:
            raise ProviderExecutionFailure("exact experimental request is required")
        started = time.monotonic()
        response = self._access.post_images({
            "model": MODEL, "prompt": request.prompt, "n": 1, "size": "1536x1024",
            "quality": "medium", "output_format": "png",
        })
        def failure(stage: str, *, decoded: bytes | None = None, png=None) -> ProviderExecutionFailure:
            return ProviderExecutionFailure("external image provider returned an invalid bounded response", diagnostic=
                ExperimentalProviderDiagnostic(True, stage, response.status,
                    message="provider response failed bounded validation", request_id=response.request_id,
                    encoded_response_bytes=len(response.content),
                    decoded_media_bytes=len(decoded) if decoded is not None else None,
                    media_sha256=hashlib.sha256(decoded).hexdigest() if decoded is not None else None, png=png))
        try:
            value = json.loads(response.content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise failure("response_json_invalid") from exc
        allowed_top = {"created", "data", "usage", "background", "output_format", "quality", "size"}
        if not isinstance(value, dict) or set(value) - allowed_top or "data" not in value:
            raise failure("response_schema_invalid")
        data = value["data"]
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise failure("image_payload_invalid")
        image = data[0]
        if set(image) - {"b64_json", "revised_prompt", "url"}:
            raise failure("image_payload_invalid")
        if any(name in image and not (image[name] is None or isinstance(image[name], str) and len(image[name]) <= 4096)
               for name in ("revised_prompt", "url")):
            raise failure("image_payload_invalid")
        if "b64_json" not in image:
            raise failure("image_payload_missing")
        if not isinstance(image["b64_json"], str):
            raise failure("image_payload_invalid")
        try:
            content = base64.b64decode(image["b64_json"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise failure("base64_invalid") from exc
        if len(content) > MAX_BYTES:
            raise failure("decoded_media_too_large", decoded=content)
        raw_usage = value.get("usage", {})
        if not isinstance(raw_usage, dict):
            raise failure("response_schema_invalid", decoded=content)
        usage = {key: raw_usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                 if key in raw_usage and isinstance(raw_usage[key], int) and 0 <= raw_usage[key] <= 10000000}
        try:
            width, height = validate_experimental_openai_png(content)
        except ProviderExecutionFailure as exc:
            raise failure("png_conformance_failed", decoded=content, png=inspect_experimental_png(content)) from exc
        media = GeneratedMedia("image/png", content, width, height, hashlib.sha256(content).hexdigest())
        png_evidence = inspect_experimental_png(content)
        return CreativeExperimentResult(media, max(0, int((time.monotonic() - started) * 1000)), 1, usage,
            png_evidence.content_credentials_present, png_evidence.content_credentials_chunk_bytes)


def create_provider(access=None) -> OpenAICreativeRealityCheckProvider:
    if access is None:
        raise ProviderExecutionFailure("experimental network and secret access is unavailable")
    return OpenAICreativeRealityCheckProvider(access)
