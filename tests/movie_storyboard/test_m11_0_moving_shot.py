from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from vss_movie_moving_shot import AttemptLedger, AttemptLedgerError, LOCATION, MODEL_SNAPSHOT, QUOTA_METRIC, admit_moving_shot, validate_fixed_quota_evidence, validate_moving_shot_admission, validate_vertex_readiness_evidence
from vss_providers import GeneratedMedia, ImageToVideoResult, ProviderAccess
from vss_runtime import RuntimeController
from vss_runtime.external_preflight import ExternalExecutionPreflight


MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"


class FakeVideoProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, request, *, credential, transport=None):
        self.calls += 1
        raw = transport(request) if transport else b"{}"
        return ImageToVideoResult(
            GeneratedMedia("video/mp4", MP4, 1280, 720, hashlib.sha256(MP4).hexdigest()),
            12, hashlib.sha256(raw).hexdigest(), "operations.test-1", "1.250000",
        )


class MovingShotTests(unittest.TestCase):
    def test_authorization_does_not_consume_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempt.json", "a" * 64)
            ledger.authorize()
            self.assertEqual(json.loads(ledger.path.read_text()), {"attempts": 0, "maximum_cost_usd": "5.000000", "request_sha256": "a" * 64, "status": "authorized"})
            ledger.reserve_execution()
            self.assertEqual(json.loads(ledger.path.read_text())["attempts"], 0)

    def test_approval_then_execution_consumes_once_and_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempt.json", "b" * 64)
            ledger.authorize(); ledger.reserve_execution(); ledger.mark_submitted(); ledger.terminal("completed")
            self.assertEqual(json.loads(ledger.path.read_text())["attempts"], 1)
            with self.assertRaises(AttemptLedgerError):
                ledger.reserve_execution()

    def test_failed_submission_consumes_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempt.json", "c" * 64)
            ledger.authorize(); ledger.reserve_execution(); ledger.mark_submitted(); ledger.terminal("failed")
            self.assertEqual(json.loads(ledger.path.read_text())["status"], "failed")
            with self.assertRaises(AttemptLedgerError):
                ledger.mark_submitted()

    def test_polling_does_not_count_as_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempt.json", "d" * 64)
            ledger.authorize(); ledger.reserve_execution(); ledger.mark_submitted()
            for _ in range(3):
                self.assertEqual(json.loads(ledger.path.read_text())["attempts"], 1)
            ledger.terminal("failed")

    def test_historical_attempt_is_not_migrated_or_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt.json"
            historical = {"attempts": 1, "maximum_cost_usd": "5.000000", "request_sha256": "e" * 64, "status": "reserved"}
            path.write_text(json.dumps(historical), encoding="utf-8")
            ledger = AttemptLedger(path, "e" * 64)
            with self.assertRaises(AttemptLedgerError):
                ledger.reserve_execution()
            self.assertEqual(json.loads(path.read_text()), historical)

    def admission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "basis.png"
            path.write_bytes(b"authoritative-basis")
            return admit_moving_shot(
                shot_id="shot-024b0d6352149eabb74df543",
                scene_id="scene-91f5c8634519d8264e2dd5f8",
                visual_basis_path=path,
                visual_basis_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                prompt="A bounded camera move preserves the source action.",
                source_lineage={"shot_plan": "a" * 64},
            )

    def test_admission_reconstructs_exact_visual_basis_and_rejects_substitution(self):
        admission = self.admission()
        validate_moving_shot_admission(admission)
        forged = type(admission)(admission.request, b"substituted")
        with self.assertRaises(ValueError):
            validate_moving_shot_admission(forged)

    def test_admission_rejects_non_current_veo_image_to_video_contract(self):
        admission = self.admission()
        for field, value in (("duration_seconds", 4), ("image_mime_type", ""), ("location", "global")):
            forged_request = dict(admission.request)
            forged_provider = dict(forged_request["provider"])
            forged_provider[field] = value
            forged_request["provider"] = forged_provider
            sealed = dict(forged_request)
            sealed["request_sha256"] = "0" * 64
            import json
            forged_request["request_sha256"] = __import__("hashlib").sha256(
                json.dumps(sealed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_moving_shot_admission(type(admission)(forged_request, admission.image))

    def test_fixed_quota_evidence_requires_exact_authoritative_dimensions(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quota.json"
            path.write_text(json.dumps({
                "metric": QUOTA_METRIC,
                "dimensions": {"base_model": MODEL_SNAPSHOT, "region": LOCATION},
                "quota": {"defaultLimit": 50, "effectiveLimit": 50},
                "unit": "1/min/{project}/{region}/{base_model}",
                "project_id": "vss-film-poc",
            }), encoding="utf-8")
            digest = validate_fixed_quota_evidence(path, project_id="vss-film-poc")
            self.assertEqual(len(digest), 64)
            value = json.loads(path.read_text())
            value["dimensions"]["region"] = "global"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_fixed_quota_evidence(path, project_id="vss-film-poc")

    def test_vertex_readiness_requires_api_project_service_agent_and_role(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "readiness.json"
            path.write_text(json.dumps({
                "api_enabled": True, "project_id": "vss-film-poc",
                "project_number": "1008607911742",
                "service_agent": {
                    "email": "service-1008607911742@gcp-sa-aiplatform.iam.gserviceaccount.com",
                    "exists": True, "project_number": "1008607911742",
                    "roles": ["roles/aiplatform.serviceAgent"],
                },
            }), encoding="utf-8")
            self.assertEqual(len(validate_vertex_readiness_evidence(
                path, project_id="vss-film-poc", project_number="1008607911742")), 64)
            value = json.loads(path.read_text())
            value["service_agent"]["roles"] = []
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_vertex_readiness_evidence(path, project_id="vss-film-poc", project_number="1008607911742")

    def test_missing_vertex_readiness_blocks_before_attempt_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            basis = Path(directory) / "basis.png"
            basis.write_bytes(b"authoritative-basis")
            admission = admit_moving_shot(
                shot_id="shot-024b0d6352149eabb74df543",
                scene_id="scene-91f5c8634519d8264e2dd5f8",
                visual_basis_path=basis,
                visual_basis_sha256=hashlib.sha256(basis.read_bytes()).hexdigest(),
                prompt="A bounded camera move preserves the source action.",
                source_lineage={"shot_plan": "a" * 64},
            )
            resolutions = []
            controller = RuntimeController(
                root=Path(__file__).resolve().parents[2],
                audit_logger=type("MemoryAudit", (), {"append": lambda self, record: None})(),
                external_execution_preflight=ExternalExecutionPreflight(
                    environment_contains=lambda name: name == "VSS_VERTEX_AI_ACCESS_TOKEN",
                    resolver=lambda *args: resolutions.append(args) or [("us-central1-aiplatform.googleapis.com", 443)],
                ),
            )
            with patch.dict("os.environ", {
                "VSS_VERTEX_AI_PROJECT_ID": "vss-film-poc",
                "VSS_VERTEX_AI_LOCATION": "us-central1",
                "VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE": str(Path(__file__).resolve().parents[2] / ".local/config/m11-0-veo-quota-evidence.json"),
                "VSS_VERTEX_AI_ACCESS_TOKEN": "token",
            }, clear=False):
                os.environ.pop("VSS_VERTEX_AI_READINESS_EVIDENCE_FILE", None)
                response, code = controller.run(
                    "movie.moving-shot-generate", "development", {},
                    {"admission_id": admission.request_sha256, "mode": "preflight"},
                    "readiness-test", datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), 0.0,
                    dry_run=True, admitted_request=admission,
                )
            self.assertEqual(code, 20, response)
            self.assertEqual(response["errors"], ["external execution preflight failed: vertex_readiness_unconfirmed"])
            self.assertEqual(resolutions, [])

    def test_runtime_handle_enforces_one_call_and_bounds_video(self):
        provider = FakeVideoProvider()
        access = ProviderAccess(video=provider, video_secret_reader=lambda _: "token")
        admission = self.admission()
        request = type("Request", (), {
            "prompt": admission.request["prompt"], "image": admission.image,
            "request_sha256": admission.request_sha256,
            "provider_request_sha256": admission.request_sha256,
            "duration_seconds": 8, "resolution": "720p", "generate_audio": False, "image_mime_type": "image/png",
        })()
        result = access.get_image_to_video_generator().generate(request)
        self.assertEqual(result.media.media_type, "video/mp4")
        self.assertEqual(provider.calls, 1)
        with self.assertRaises(Exception):
            access.get_image_to_video_generator().generate(request)

    def test_provider_projection_is_image_to_video_without_audio(self):
        provider = FakeVideoProvider()
        access = ProviderAccess(video=provider, video_secret_reader=lambda _: "token")
        admission = self.admission()
        captured = {}
        request = type("Request", (), {
            "prompt": admission.request["prompt"], "image": admission.image,
            "request_sha256": admission.request_sha256,
            "provider_request_sha256": admission.request_sha256,
            "duration_seconds": 8, "resolution": "720p", "generate_audio": False, "image_mime_type": "image/png",
        })()
        access.get_image_to_video_generator().generate(request)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(admission.request["provider"]["model_snapshot"], "veo-3.1-generate-001")
        self.assertFalse(admission.request["provider"]["generate_audio"])
        self.assertEqual(admission.request["bounds"]["maximum_provider_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
