from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.request
from typing import Any

from vss_movie_moving_shot import MODEL_SNAPSHOT, MAXIMUM_COST_USD
from vss_providers import GeneratedMedia, ImageToVideoRequest, ImageToVideoResult


def _https_json(url: str, body: bytes, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(128 * 1024 * 1024 + 1)


def _default_transport(url: str, body: bytes, headers: dict[str, str], timeout: float, maximum: int) -> bytes:
    return _https_json(url, body, headers, timeout)


class VertexVeoImageToVideoProvider:
    def generate(self, request: ImageToVideoRequest, *, credential: str, transport=None) -> ImageToVideoResult:
        if (request.model_snapshot if hasattr(request, "model_snapshot") else MODEL_SNAPSHOT) != MODEL_SNAPSHOT:
            raise ValueError("unsupported Veo model")
        project = os.environ.get("VSS_VERTEX_AI_PROJECT_ID", "")
        location = os.environ.get("VSS_VERTEX_AI_LOCATION", "us-central1")
        if not project or not credential:
            raise ValueError("Vertex project or credential is unavailable")
        endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{MODEL_SNAPSHOT}:predictLongRunning"
        body_value = {"instances": [{"prompt": request.prompt, "image": {"bytesBase64Encoded": base64.b64encode(request.image).decode("ascii")}}], "parameters": {"aspectRatio": "16:9", "resolution": request.resolution, "durationSeconds": request.duration_seconds, "generateAudio": request.generate_audio}}
        body = json.dumps(body_value, sort_keys=True, separators=(",", ":")).encode()
        if len(body) > 32 * 1024 * 1024:
            raise ValueError("Vertex request exceeds its bound")
        started = time.monotonic()
        sender = transport or _default_transport
        raw = sender(endpoint, body, {"Authorization": "Bearer " + credential, "Content-Type": "application/json"}, 900.0, 128 * 1024 * 1024)
        value = json.loads(raw)
        # The transport owns the provider's long-running operation polling. It may
        # return only the terminal prediction, never a second generation request.
        prediction = value.get("predictions", [{}])[0] if isinstance(value, dict) else {}
        encoded = prediction.get("bytesBase64Encoded") or prediction.get("video", {}).get("bytesBase64Encoded")
        if not isinstance(encoded, str):
            raise ValueError("Vertex response did not contain inline video bytes")
        content = base64.b64decode(encoded, validate=True)
        if not content or len(content) > 256 * 1024 * 1024 or content[:8] != b"\x00\x00\x00\x18ftyp":
            raise ValueError("Vertex response is not a bounded MP4")
        digest = hashlib.sha256(content).hexdigest()
        return ImageToVideoResult(GeneratedMedia("video/mp4", content, 1280, 720, digest), max(0, int((time.monotonic() - started) * 1000)), hashlib.sha256(raw).hexdigest(), str(value.get("name", "vertex-operation")), "0.000000")


def create_provider() -> VertexVeoImageToVideoProvider:
    return VertexVeoImageToVideoProvider()
