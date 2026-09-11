from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from vss_movie_moving_shot import AttemptLedger, AttemptLedgerError, LOCATION, MODEL_SNAPSHOT, QUOTA_METRIC, admit_moving_shot, classify_legacy_record, record_existing_authorization, validate_fixed_quota_evidence, validate_moving_shot_admission, validate_vertex_readiness_evidence
from vss_providers import GeneratedMedia, ImageToVideoResult, ProviderAccess
from vss_runtime import RuntimeController
from vss_runtime.external_preflight import ExternalExecutionPreflight


MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"

HANDLER_PATH = Path(__file__).resolve().parents[2] / "capabilities/movie-moving-shot/handler.py"
HANDLER_SPEC = importlib.util.spec_from_file_location("m11_moving_shot_handler", HANDLER_PATH)
assert HANDLER_SPEC and HANDLER_SPEC.loader
HANDLER_MODULE = importlib.util.module_from_spec(HANDLER_SPEC)
HANDLER_SPEC.loader.exec_module(HANDLER_MODULE)


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
    def test_attempt_five_controller_namespace_does_not_reuse_attempts_one_to_four(self):
        source = (Path(__file__).resolve().parents[2] / "src/vss_runtime/controller.py").read_text(encoding="utf-8")
        self.assertIn('"attempt-5" / "output"', source)
        self.assertNotIn('"attempt-4" / "output"', source)

    def test_output_collision_after_reservation_consumes_without_provider_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "attempt-3"
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
            output = root / "output" / admission.request_sha256
            output.mkdir(parents=True)
            record_existing_authorization(root / "authorization.json", admission.request_sha256)
            provider = FakeVideoProvider()
            context = type("Context", (), {
                "environment": "development",
                "admitted_request": admission,
                "safe_configuration": {"artifact_root": str(output)},
                "providers": ProviderAccess(video=provider, video_secret_reader=lambda _: "token"),
            })()

            with self.assertRaises(FileExistsError):
                HANDLER_MODULE.execute(
                    context, {"admission_id": admission.request_sha256, "mode": "generate"}, False
                )

            ledger = json.loads((root / f"{admission.request_sha256}.attempt.json").read_text())
            self.assertEqual(ledger["status"], "failed")
            self.assertEqual(ledger["attempts"], 1)
            self.assertEqual(provider.calls, 0)

    def test_handler_uses_authorization_sibling_of_output_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "attempt-3"
            output = root / "output" / ("1" * 64)
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
            # Use the admission digest for the real ledger path while keeping
            # the output destination isolated from the repository.
            output = root / "output" / admission.request_sha256
            record_existing_authorization(root / "authorization.json", admission.request_sha256)
            context = type("Context", (), {
                "environment": "development",
                "admitted_request": admission,
                "safe_configuration": {"artifact_root": str(output)},
                "providers": ProviderAccess(video=FakeVideoProvider(), video_secret_reader=lambda _: "token"),
            })()
            result = HANDLER_MODULE.execute(
                context, {"admission_id": admission.request_sha256, "mode": "generate"}, False
            )
            ledger_path = root / f"{admission.request_sha256}.attempt.json"
            self.assertEqual(result.output["status"], "generated_quarantined")
            self.assertEqual(json.loads(ledger_path.read_text())["status"], "completed")
            self.assertFalse((output / "authorization.json").exists())

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

    def test_legacy_reserved_attempt_is_classified_as_consumed_without_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt.json"
            historical = {"attempts": 1, "maximum_cost_usd": "5.000000", "request_sha256": "e" * 64, "status": "reserved"}
            path.write_text(json.dumps(historical), encoding="utf-8")
            self.assertEqual(classify_legacy_record(path, "e" * 64)["status"], "consumed")
            self.assertEqual(json.loads(path.read_text()), historical)

    def test_existing_authorization_is_idempotently_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authorization.json"
            record_existing_authorization(path, "f" * 64)
            before = path.read_bytes()
            record_existing_authorization(path, "f" * 64)
            self.assertEqual(path.read_bytes(), before)

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
                "iam_policy": {
                    "principal": "service-1008607911742@gcp-sa-aiplatform.iam.gserviceaccount.com",
                    "role": "roles/aiplatform.serviceAgent",
                },
                "audit_provisioning": {
                    "log": "cloudaudit.googleapis.com/activity",
                    "service": "cloudresourcemanager.googleapis.com",
                    "method": "SetIamPolicy",
                    "actor": "service-agent-manager@system.gserviceaccount.com",
                    "delta": "ADD",
                    "principal": "service-1008607911742@gcp-sa-aiplatform.iam.gserviceaccount.com",
                    "role": "roles/aiplatform.serviceAgent",
                    "timestamp": "2026-09-10T21:12:37.762713Z",
                },
            }), encoding="utf-8")
            self.assertEqual(len(validate_vertex_readiness_evidence(
                path, project_id="vss-film-poc", project_number="1008607911742")), 64)
            value = json.loads(path.read_text())
            value["audit_provisioning"]["principal"] = "service-other@gcp-sa-aiplatform.iam.gserviceaccount.com"
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
