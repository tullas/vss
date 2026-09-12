from __future__ import annotations

import binascii
import hashlib
import json
import os
import struct
import tempfile
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from vss_movie_moving_shot import MovingShotAdmission, admit_moving_shot, record_existing_authorization, validate_moving_shot_admission
from vss_provider_reliability import reconstruct_durable_moving_shot_request
from vss_runtime import RuntimeController


REPO = Path(__file__).resolve().parents[2]
SHOT3_PACKAGE = REPO / "docs/experiments/m11-3-film1-shot3-durable-planning-package.json"
SHOT3_INPUT = REPO / ".local/movie/m11-3-film1-shot3/shot-471187bad6ae782a5ef83800/inputs/shot-2-final-frame-191.png"
SHOT3_DIGEST = "6f482e960dc12faa5f9bfc51599a423cb6364374ebc8bb58d919ca6212095d86"
SHOT3_NAMESPACE = "vikramaditya-local/shot-471187bad6ae782a5ef83800"
SHOT3_INPUT_SHA256 = "96aa4941105438137a82dbb9acd71869354900d9320946c9bc548f76960b5459"
OPERATION = "projects/vss-film-poc/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/offline-rehearsal"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF))


def deterministic_png() -> bytes:
    """Return a valid, deterministic one-pixel PNG without local media files."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x00\x00\x00\xff", level=9)
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
            + _png_chunk(b"IDAT", pixels) + _png_chunk(b"IEND", b""))


def synthetic_admission() -> MovingShotAdmission:
    image = deterministic_png()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "test-input.png"
        path.write_bytes(image)
        admission = admit_moving_shot(
            shot_id="shot-111111111111111111111111",
            scene_id="scene-222222222222222222222222",
            visual_basis_path=path,
            visual_basis_sha256=hashlib.sha256(image).hexdigest(),
            prompt="A bounded camera move continues the established action.",
            source_lineage={"shot_plan": "a" * 64},
            production_id="vikramaditya-local",
        )
    validate_moving_shot_admission(admission)
    return admission


def shot3_admission() -> MovingShotAdmission:
    package = json.loads(SHOT3_PACKAGE.read_text(encoding="utf-8"))
    if (package.get("package_identity") != "film-1-shot-3-durable-planning-package"
            or package.get("certification", {}).get("status") != "TECHNICAL_EXECUTION_CONFORMS"):
        raise AssertionError("authoritative Shot 3 package identity or certification changed")
    request, digest, namespace = reconstruct_durable_moving_shot_request(package["runtime_package"])
    image = SHOT3_INPUT.read_bytes()
    if (digest != SHOT3_DIGEST or namespace != SHOT3_NAMESPACE
            or hashlib.sha256(image).hexdigest() != SHOT3_INPUT_SHA256):
        raise AssertionError("authoritative Shot 3 package or input changed")
    admission = MovingShotAdmission(request, image)
    validate_moving_shot_admission(admission)
    return admission


class NoNetworkPreflight:
    def __init__(self):
        self.calls = 0

    def run(self, _spec):
        self.calls += 1
        return None


class MovingShotRecoveryHarness:
    def make_runtime_root(self, root: Path) -> None:
        for name in ("capabilities", "providers", "schemas"):
            link = root / name
            if not link.exists():
                link.symlink_to(REPO / name, target_is_directory=True)

    def controller(self, root: Path, transport, preflight=None) -> RuntimeController:
        self.make_runtime_root(root)
        return RuntimeController(
            root=root,
            external_execution_preflight=preflight or NoNetworkPreflight(),
            moving_shot_provider_transport=transport,
            moving_shot_secret_reader=lambda _name: "offline-test-token",
        )

    def run_runtime(self, controller, admission, mode):
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return controller.run(
            "movie.moving-shot-generate", "development", {},
            {"admission_id": admission.request_sha256, "mode": mode},
            "offline-acceptance-recovery-test", now, 0.0, dry_run=False,
            timeout_seconds=30, admitted_request=admission,
        )

    @contextmanager
    def runtime_environment(self):
        quota_evidence = {
            "metric": "aiplatform.googleapis.com/long_running_online_prediction_requests_per_base_model",
            "dimensions": {"base_model": "veo-3.1-generate-001", "region": "us-central1"},
            "quota": {"defaultLimit": 30, "effectiveLimit": 50},
            "unit": "1/min/{project}/{region}/{base_model}",
            "project_id": "vss-film-poc",
        }
        with tempfile.TemporaryDirectory() as directory:
            quota_path = Path(directory) / "quota-evidence.json"
            quota_path.write_text(json.dumps(quota_evidence, sort_keys=True), encoding="utf-8")
            with patch.dict(os.environ, {
                "VSS_VERTEX_AI_PROJECT_ID": "vss-film-poc",
                "VSS_VERTEX_AI_LOCATION": "us-central1",
                "VSS_VERTEX_AI_ACCESS_TOKEN": "offline-test-token",
                "VSS_VERTEX_AI_READINESS_EVIDENCE_FILE": str(REPO / "docs/reviews/m11-0-vertex-readiness-evidence.json"),
                "VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE": str(quota_path),
            }, clear=False):
                yield

    def authorize(self, root: Path, admission: MovingShotAdmission) -> Path:
        state = root / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"]
        record_existing_authorization(state / "authorization.json", admission.request_sha256)
        return state
