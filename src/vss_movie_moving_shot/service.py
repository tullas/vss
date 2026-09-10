from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PROVIDER_IDENTITY = "movie.image-to-video.vertex-veo"
MODEL_SNAPSHOT = "veo-3.1-generate-001"
LOCATION = "us-central1"
IMAGE_MIME_TYPE = "image/png"
IMAGE_TO_VIDEO_DURATION_SECONDS = 8
SECRET_NAME = "VSS_VERTEX_AI_ACCESS_TOKEN"  # pragma: allowlist secret
MAXIMUM_COST_USD = "5.000000"
MAXIMUM_OUTPUT_BYTES = 256 * 1024 * 1024
REQUEST_LIMIT = 64 * 1024


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class MovingShotAdmission:
    request: Mapping[str, Any]
    image: bytes

    @property
    def request_sha256(self) -> str:
        return self.request["request_sha256"]


def admit_moving_shot(*, shot_id: str, scene_id: str, visual_basis_path: Path,
                     visual_basis_sha256: str, prompt: str, source_lineage: Mapping[str, str],
                     production_id: str = "vikramaditya-local") -> MovingShotAdmission:
    if not re.fullmatch(r"shot-[0-9a-f]{24}", shot_id) or not re.fullmatch(r"scene-[0-9a-f]{24}", scene_id):
        raise ValueError("authoritative shot identity is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", visual_basis_sha256) or not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4096:
        raise ValueError("moving-shot admission is invalid")
    image = visual_basis_path.read_bytes()
    actual = hashlib.sha256(image).hexdigest()
    if actual != visual_basis_sha256:
        raise ValueError("visual basis digest does not match authoritative bytes")
    if not isinstance(source_lineage, Mapping) or not source_lineage or any(
            not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
            for k, v in source_lineage.items()):
        raise ValueError("source lineage is invalid")
    request = {
        "schema_version": "1", "contract_identity": "moving_shot_generation_request", "contract_version": "1",
        "scope": {"production_id": production_id, "scene_id": scene_id, "shot_id": shot_id},
        "production_input": {"media_type": "image/png", "content_sha256": actual, "byte_count": len(image), "basis_path": str(visual_basis_path)},
        "source_lineage": dict(sorted(source_lineage.items())),
        "provider": {"identity": PROVIDER_IDENTITY, "model_snapshot": MODEL_SNAPSHOT, "location": LOCATION, "resolution": "720p", "duration_seconds": IMAGE_TO_VIDEO_DURATION_SECONDS, "generate_audio": False, "image_mime_type": IMAGE_MIME_TYPE},
        "bounds": {"maximum_provider_attempts": 1, "maximum_outputs": 1, "maximum_cost_usd": MAXIMUM_COST_USD},
        "prompt": prompt,
        "authority": {"production": False, "publication": False, "retry": False, "fallback": False, "workflow_activation": False},
        "request_sha256": "0" * 64,
    }
    raw = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > REQUEST_LIMIT:
        raise ValueError("moving-shot request exceeds its bound")
    request["request_sha256"] = _digest(request)
    return MovingShotAdmission(request=request, image=image)


def validate_moving_shot_admission(admission: MovingShotAdmission) -> MovingShotAdmission:
    if type(admission) is not MovingShotAdmission or not isinstance(admission.request, Mapping):
        raise ValueError("moving-shot admission is invalid")
    request = dict(admission.request)
    sealed = dict(request); sealed["request_sha256"] = "0" * 64
    if request.get("request_sha256") != _digest(sealed):
        raise ValueError("moving-shot request seal mismatch")
    if request.get("provider") != {"identity": PROVIDER_IDENTITY, "model_snapshot": MODEL_SNAPSHOT, "location": LOCATION, "resolution": "720p", "duration_seconds": IMAGE_TO_VIDEO_DURATION_SECONDS, "generate_audio": False, "image_mime_type": IMAGE_MIME_TYPE}:
        raise ValueError("moving-shot provider binding is invalid")
    if request.get("bounds") != {"maximum_provider_attempts": 1, "maximum_outputs": 1, "maximum_cost_usd": MAXIMUM_COST_USD}:
        raise ValueError("moving-shot bounds are invalid")
    if hashlib.sha256(admission.image).hexdigest() != request.get("production_input", {}).get("content_sha256"):
        raise ValueError("moving-shot input reconstruction failed")
    return admission
