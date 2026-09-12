from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from vss_movie_moving_shot import AttemptLedger, AttemptLedgerError, MovingShotAdmission, record_existing_authorization, validate_moving_shot_admission
from vss_provider_reliability import reconstruct_durable_moving_shot_request
from vss_providers import ProviderAccess
from vss_runtime import RuntimeController


REPO = Path(__file__).resolve().parents[2]
EXPECTED_DIGEST = "6f482e960dc12faa5f9bfc51599a423cb6364374ebc8bb58d919ca6212095d86"
EXPECTED_NAMESPACE = "vikramaditya-local/shot-471187bad6ae782a5ef83800"
EXPECTED_PNG = "96aa4941105438137a82dbb9acd71869354900d9320946c9bc548f76960b5459"
OPERATION = "projects/vss-film-poc/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/offline-rehearsal"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"


def shot3_admission() -> MovingShotAdmission:
    package = json.loads((REPO / "docs/experiments/m11-3-film1-shot3-durable-planning-package.json").read_text())
    request, digest, namespace = reconstruct_durable_moving_shot_request(package["runtime_package"])
    input_path = REPO / ".local/movie/m11-3-film1-shot3/shot-471187bad6ae782a5ef83800/inputs/shot-2-final-frame-191.png"
    image = input_path.read_bytes()
    if digest != EXPECTED_DIGEST or namespace != EXPECTED_NAMESPACE or hashlib.sha256(image).hexdigest() != EXPECTED_PNG:
        raise AssertionError("authoritative Shot 3 package or input changed")
    admission = MovingShotAdmission(request, image)
    validate_moving_shot_admission(admission)
    return admission


class NoNetworkPreflight:
    def __init__(self):
        self.calls = 0

    def run(self, spec):
        self.calls += 1
        return None


class MovingShotRecoveryRuntimeTests(unittest.TestCase):
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

    def runtime_environment(self):
        return patch.dict(os.environ, {
            "VSS_VERTEX_AI_PROJECT_ID": "vss-film-poc",
            "VSS_VERTEX_AI_LOCATION": "us-central1",
            "VSS_VERTEX_AI_ACCESS_TOKEN": "offline-test-token",
            "VSS_VERTEX_AI_READINESS_EVIDENCE_FILE": str(REPO / "docs/reviews/m11-0-vertex-readiness-evidence.json"),
            "VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE": str(REPO / ".local/config/m11-0-veo-quota-evidence.json"),
        }, clear=False)

    def authorize(self, root: Path, admission: MovingShotAdmission) -> Path:
        state = root / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"]
        record_existing_authorization(state / "authorization.json", admission.request_sha256)
        return state

    def test_shot3_restart_recovery_reuses_accepted_operation_and_admits_terminal_media(self):
        admission = shot3_admission()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.authorize(root, admission)
            submissions = []
            polls = []

            def interrupted_transport(url, body, headers, timeout, maximum):
                if url.endswith(":predictLongRunning"):
                    submissions.append(url)
                    return 200, json.dumps({"name": OPERATION}).encode()
                observed = json.loads((state / f"{EXPECTED_DIGEST}.attempt.json").read_text())
                self.assertEqual(observed["status"], "submitted")
                self.assertEqual(observed["attempts"], 1)
                self.assertEqual(observed["operation_name"], OPERATION)
                self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "consumed")
                raise urllib.error.URLError("simulated process interruption while polling")

            with self.runtime_environment():
                _, failed_code = self.run_runtime(self.controller(root, interrupted_transport), admission, "generate")
            self.assertNotEqual(failed_code, 0)
            ledger_path = state / f"{EXPECTED_DIGEST}.attempt.json"
            ledger = json.loads(ledger_path.read_text())
            authorization = json.loads((state / "authorization.json").read_text())
            operation_evidence = json.loads((root / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"] / "output" / EXPECTED_DIGEST / "operation.json").read_text())
            self.assertEqual(len(submissions), 1)
            self.assertEqual(ledger["attempts"], 1)
            self.assertEqual(ledger["status"], "failed")
            self.assertEqual(ledger["operation_name"], OPERATION)
            self.assertEqual(ledger["execution_namespace"], EXPECTED_NAMESPACE)
            self.assertEqual(authorization["status"], "consumed")
            self.assertEqual(operation_evidence["request_sha256"], EXPECTED_DIGEST)
            self.assertEqual(operation_evidence["execution_namespace"], EXPECTED_NAMESPACE)

            def recovery_transport(url, body, headers, timeout, maximum):
                if url.endswith(":predictLongRunning"):
                    submissions.append(url)
                    return 200, json.dumps({"name": OPERATION}).encode()
                self.assertTrue(url.endswith(":fetchPredictOperation"))
                self.assertEqual(json.loads(body)["operationName"], OPERATION)
                polls.append(url)
                return 200, json.dumps({"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": base64.b64encode(MP4).decode(), "mimeType": "video/mp4",
                }]}}).encode()

            # A second normal execution must fail before entering the provider transport.
            with self.runtime_environment():
                _, duplicate_code = self.run_runtime(self.controller(root, recovery_transport), admission, "generate")
            self.assertNotEqual(duplicate_code, 0)
            self.assertEqual(polls, [])
            self.assertEqual(len(submissions), 1)
            recovery_preflight = NoNetworkPreflight()
            with self.runtime_environment():
                os.environ.pop("VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE", None)
                recovered, recovery_code = self.run_runtime(
                    self.controller(root, recovery_transport, recovery_preflight), admission, "recover")
            self.assertEqual(recovery_code, 0, recovered)
            self.assertEqual(recovery_preflight.calls, 0)
            self.assertEqual(len(submissions), 1)
            self.assertEqual(len(polls), 1)
            self.assertEqual(recovered["output"]["status"], "recovered_quarantined")
            self.assertEqual(recovered["output"]["provider_call_count"], 0)
            self.assertTrue(Path(recovered["output"]["video"]).is_file())
            final_ledger = json.loads(ledger_path.read_text())
            self.assertEqual(final_ledger["attempts"], 1)
            self.assertEqual(final_ledger["operation_name"], OPERATION)
            # A lost local artifact can be rebuilt from the same completed
            # operation without reopening or incrementing the submission.
            Path(recovered["output"]["video"]).unlink()
            with self.runtime_environment():
                os.environ.pop("VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE", None)
                repeated, repeated_code = self.run_runtime(
                    self.controller(root, recovery_transport), admission, "recover")
            self.assertEqual(repeated_code, 0, repeated)
            self.assertEqual(len(submissions), 1)
            self.assertEqual(len(polls), 2)
            self.assertTrue(Path(repeated["output"]["video"]).is_file())
            self.assertEqual(json.loads(ledger_path.read_text())["attempts"], 1)

    def test_recovery_mode_rejects_missing_operation_and_identity_mismatches(self):
        admission = shot3_admission()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.authorize(root, admission)
            output = root / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"] / "output" / EXPECTED_DIGEST
            ledger = AttemptLedger(state / f"{EXPECTED_DIGEST}.attempt.json", EXPECTED_DIGEST)
            ledger.reserve_execution()
            calls = []
            context = type("Context", (), {
                "environment": "development", "admitted_request": admission,
                "safe_configuration": {"artifact_root": str(output)},
                "providers": ProviderAccess(video=type("Provider", (), {
                    "recover": lambda self, *args, **kwargs: calls.append("recover"),
                    "generate": lambda self, *args, **kwargs: calls.append("generate"),
                })(), video_secret_reader=lambda _name: "token"),
            })()
            import importlib.util
            spec = importlib.util.spec_from_file_location("acceptance_recovery_handler", REPO / "capabilities/movie-moving-shot/handler.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.assertRaises(ValueError):
                module.execute(context, {"admission_id": EXPECTED_DIGEST, "mode": "recover"}, False)
            output.mkdir(parents=True)

            for evidence, ledger_operation, ledger_namespace in (
                ({"operation_name": OPERATION, "request_sha256": "0" * 64, "execution_namespace": EXPECTED_NAMESPACE, "submission_accepted": True}, OPERATION, EXPECTED_NAMESPACE),
                ({"operation_name": OPERATION, "request_sha256": EXPECTED_DIGEST, "execution_namespace": "wrong/namespace", "submission_accepted": True}, OPERATION, "wrong/namespace"),
                ({"operation_name": OPERATION + "-other", "request_sha256": EXPECTED_DIGEST, "execution_namespace": EXPECTED_NAMESPACE, "submission_accepted": True}, OPERATION, EXPECTED_NAMESPACE),
            ):
                # Each malformed binding gets its own fresh ledger directory.
                attempt_dir = Path(tempfile.mkdtemp(dir=directory))
                state2 = attempt_dir / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"]
                record_existing_authorization(state2 / "authorization.json", EXPECTED_DIGEST)
                ledger2 = AttemptLedger(state2 / f"{EXPECTED_DIGEST}.attempt.json", EXPECTED_DIGEST)
                ledger2.reserve_execution()
                ledger2.accept_operation(ledger_operation, ledger_namespace)
                ledger2.terminal("failed")
                output2 = attempt_dir / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"] / "output" / EXPECTED_DIGEST
                output2.mkdir(parents=True)
                (output2 / "operation.json").write_text(json.dumps(evidence))
                context.safe_configuration = {"artifact_root": str(output2)}
                with self.assertRaises(ValueError):
                    module.execute(context, {"admission_id": EXPECTED_DIGEST, "mode": "recover"}, False)
            self.assertEqual(calls, [])

    def test_malformed_terminal_and_media_admission_failures_recover_same_operation(self):
        admission = shot3_admission()
        for failure_kind in ("malformed_terminal", "invalid_media"):
            with self.subTest(failure_kind=failure_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = self.authorize(root, admission)
                submissions = []
                polls = []

                def transport(url, body, headers, timeout, maximum):
                    if url.endswith(":predictLongRunning"):
                        submissions.append(url)
                        return 200, json.dumps({"name": OPERATION}).encode()
                    self.assertTrue(url.endswith(":fetchPredictOperation"))
                    self.assertEqual(json.loads(body)["operationName"], OPERATION)
                    polls.append(url)
                    if len(polls) == 1 and failure_kind == "malformed_terminal":
                        terminal = {"done": True, "response": {"videos": []}}
                    elif len(polls) == 1:
                        terminal = {"done": True, "response": {"videos": [{
                            "bytesBase64Encoded": base64.b64encode(b"invalid media").decode(),
                            "mimeType": "video/mp4",
                        }]}}
                    else:
                        terminal = {"done": True, "response": {"videos": [{
                            "bytesBase64Encoded": base64.b64encode(MP4).decode(),
                            "mimeType": "video/mp4",
                        }]}}
                    return 200, json.dumps(terminal).encode()

                with self.runtime_environment():
                    _, initial_code = self.run_runtime(self.controller(root, transport), admission, "generate")
                self.assertNotEqual(initial_code, 0)
                ledger_path = state / f"{EXPECTED_DIGEST}.attempt.json"
                failed_ledger = json.loads(ledger_path.read_text())
                self.assertEqual(failed_ledger["attempts"], 1)
                self.assertEqual(failed_ledger["operation_name"], OPERATION)
                self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "consumed")

                with self.runtime_environment():
                    recovered, recovery_code = self.run_runtime(self.controller(root, transport), admission, "recover")
                self.assertEqual(recovery_code, 0, recovered)
                self.assertEqual(len(submissions), 1)
                self.assertEqual(len(polls), 2)
                self.assertEqual(recovered["output"]["provider_call_count"], 0)
                self.assertEqual(json.loads(ledger_path.read_text())["attempts"], 1)
                self.assertEqual(json.loads(ledger_path.read_text())["status"], "completed")




if __name__ == "__main__":
    unittest.main()
