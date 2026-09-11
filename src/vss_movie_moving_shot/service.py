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
QUOTA_EVIDENCE_ENV = "VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE"
READINESS_EVIDENCE_ENV = "VSS_VERTEX_AI_READINESS_EVIDENCE_FILE"
QUOTA_METRIC = "aiplatform.googleapis.com/long_running_online_prediction_requests_per_base_model"
VERTEX_SERVICE_AGENT_ROLE = "roles/aiplatform.serviceAgent"
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


def validate_fixed_quota_evidence(path: Path, *, project_id: str) -> str:
    """Validate a bounded, local copy of authoritative quota CLI evidence."""
    if not isinstance(project_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{5,29}", project_id):
        raise ValueError("quota evidence project is invalid")
    try:
        raw = path.read_bytes()
        if len(raw) > 16 * 1024:
            raise ValueError("quota evidence exceeds its bound")
        evidence = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("quota evidence is unavailable or invalid") from exc
    if not isinstance(evidence, dict) or set(evidence) != {"metric", "dimensions", "quota", "unit", "project_id"}:
        raise ValueError("quota evidence shape is invalid")
    if (evidence["metric"] != QUOTA_METRIC
            or evidence["project_id"] != project_id
            or evidence["unit"] != "1/min/{project}/{region}/{base_model}"
            or evidence["dimensions"] != {"base_model": MODEL_SNAPSHOT, "region": LOCATION}):
        raise ValueError("quota evidence binding is invalid")
    quota = evidence["quota"]
    if (not isinstance(quota, dict) or set(quota) != {"defaultLimit", "effectiveLimit"}
            or type(quota["defaultLimit"]) is not int or type(quota["effectiveLimit"]) is not int
            or quota["defaultLimit"] <= 0 or quota["effectiveLimit"] <= 0
            or quota["effectiveLimit"] < quota["defaultLimit"]):
        raise ValueError("quota evidence limits are invalid")
    return hashlib.sha256(raw).hexdigest()


def validate_vertex_readiness_evidence(path: Path, *, project_id: str,
                                       project_number: str) -> str:
    """Validate bounded, read-only evidence for Vertex first-use readiness."""
    if (not isinstance(project_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{5,29}", project_id)
            or not isinstance(project_number, str) or not re.fullmatch(r"[0-9]{5,20}", project_number)):
        raise ValueError("Vertex readiness project identity is invalid")
    try:
        raw = path.read_bytes()
        if len(raw) > 16 * 1024:
            raise ValueError("Vertex readiness evidence exceeds its bound")
        evidence = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Vertex readiness evidence is unavailable or invalid") from exc
    if (not isinstance(evidence, dict)
            or set(evidence) != {"api_enabled", "project_id", "project_number", "iam_policy", "audit_provisioning"}
            or evidence["api_enabled"] is not True
            or evidence["project_id"] != project_id
            or evidence["project_number"] != project_number):
        raise ValueError("Vertex readiness evidence binding is invalid")
    policy = evidence["iam_policy"]
    expected_email = f"service-{project_number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
    if (not isinstance(policy, dict) or set(policy) != {"principal", "role"}
            or policy["principal"] != expected_email
            or policy["role"] != VERTEX_SERVICE_AGENT_ROLE):
        raise ValueError("Vertex service-agent readiness is unconfirmed")
    audit = evidence["audit_provisioning"]
    if (not isinstance(audit, dict)
            or set(audit) != {"log", "service", "method", "actor", "delta", "principal", "role", "timestamp"}
            or audit["log"] != "cloudaudit.googleapis.com/activity"
            or audit["service"] != "cloudresourcemanager.googleapis.com"
            or audit["method"] != "SetIamPolicy"
            or audit["actor"] != "service-agent-manager@system.gserviceaccount.com"
            or audit["delta"] != "ADD"
            or audit["principal"] != expected_email
            or audit["role"] != VERTEX_SERVICE_AGENT_ROLE
            or not re.fullmatch(r"2026-09-10T21:12:37\.762713Z", audit["timestamp"])):
        raise ValueError("Vertex service-agent provisioning evidence is unconfirmed")
    return hashlib.sha256(raw).hexdigest()
