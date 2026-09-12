from __future__ import annotations

import base64
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vss_movie_moving_shot import AttemptLedger, AttemptLedgerError
from vss_providers import ProviderAccess

from m11_0_moving_shot_recovery_support import (
    MP4, OPERATION, MovingShotRecoveryHarness, NoNetworkPreflight, synthetic_admission,
)


REPO = Path(__file__).resolve().parents[2]
HANDLER_SPEC = importlib.util.spec_from_file_location(
    "acceptance_recovery_handler", REPO / "capabilities/movie-moving-shot/handler.py")
assert HANDLER_SPEC and HANDLER_SPEC.loader
HANDLER = importlib.util.module_from_spec(HANDLER_SPEC)
HANDLER_SPEC.loader.exec_module(HANDLER)


class SimulatedProcessDeath(BaseException):
    """Terminate between durable provider evidence and the ledger callback."""


class MovingShotRecoveryTests(MovingShotRecoveryHarness, unittest.TestCase):
    def make_handler_context(self, admission, destination, provider, transport=None):
        return SimpleNamespace(
            environment="development",
            admitted_request=admission,
            safe_configuration={"artifact_root": str(destination)},
            providers=ProviderAccess(video=provider, video_secret_reader=lambda _name: "offline-test-token",
                                     video_transport=transport),
        )

    def operation_record(self, admission, operation=OPERATION):
        return {
            "operation_name": operation,
            "endpoint": "https://us-central1-aiplatform.googleapis.com/v1/projects/vss-film-poc/locations/us-central1/publishers/google/models/veo-3.1-generate-001:predictLongRunning",
            "method": "POST",
            "request_sha256": admission.request_sha256,
            "execution_namespace": (f"{admission.request['scope']['production_id']}/"
                                     f"{admission.request['scope']['shot_id']}"),
            "submission_accepted": True,
            "polls": [],
        }

    def test_operation_persisted_then_process_death_reconciles_and_recovers_same_operation(self):
        admission = synthetic_admission()
        namespace = f"{admission.request['scope']['production_id']}/{admission.request['scope']['shot_id']}"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.authorize(root, admission)
            destination = root / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"] / "output" / admission.request_sha256
            generation_submissions = []
            recovery_polls = []

            def offline_transport(url, body, _headers, _timeout, _maximum):
                if url.endswith(":predictLongRunning"):
                    generation_submissions.append(url)
                    return 200, json.dumps({"name": OPERATION}).encode()
                self.assertTrue(url.endswith(":fetchPredictOperation"))
                self.assertEqual(json.loads(body)["operationName"], OPERATION)
                record = json.loads((state / f"{admission.request_sha256}.attempt.json").read_text())
                self.assertEqual(record["status"], "submitted")
                self.assertEqual(record["attempts"], 1)
                self.assertEqual(record["operation_name"], OPERATION)
                self.assertEqual(record["execution_namespace"], namespace)
                self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "consumed")
                recovery_polls.append(url)
                terminal = {"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": base64.b64encode(MP4).decode(), "mimeType": "video/mp4",
                }]}}
                return 200, json.dumps(terminal).encode()

            provider_path = REPO / "providers/builtin/movie-image-to-video-vertex-veo/implementation.py"
            provider_spec = importlib.util.spec_from_file_location("crash_window_vertex_provider", provider_path)
            self.assertIsNotNone(provider_spec)
            provider_module = importlib.util.module_from_spec(provider_spec)
            sys.modules[provider_spec.name] = provider_module
            provider_spec.loader.exec_module(provider_module)
            provider = provider_module.create_provider()
            context = self.make_handler_context(admission, destination, provider, offline_transport)
            original_persist = provider_module._persist_operation

            def persist_then_die(*args, **kwargs):
                original_persist(*args, **kwargs)
                raise SimulatedProcessDeath()

            ledger_path = state / f"{admission.request_sha256}.attempt.json"
            with self.runtime_environment(), patch.object(provider_module, "_persist_operation", persist_then_die):
                with self.assertRaises(SimulatedProcessDeath):
                    HANDLER.execute(context, {"admission_id": admission.request_sha256, "mode": "generate"}, False)

            reserved = json.loads(ledger_path.read_text())
            persisted_operation = json.loads((destination / "operation.json").read_text())
            self.assertEqual(reserved["status"], "reserved")
            self.assertEqual(reserved["attempts"], 0)
            self.assertEqual(reserved["execution_namespace"], namespace)
            self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "authorized")
            self.assertEqual(persisted_operation["operation_name"], OPERATION)
            self.assertEqual(persisted_operation["request_sha256"], admission.request_sha256)
            self.assertEqual(persisted_operation["execution_namespace"], namespace)
            self.assertEqual(len(generation_submissions), 1)

            # A fresh provider instance simulates process restart. Recovery can
            # only invoke fetchPredictOperation for the persisted identity.
            context.providers = ProviderAccess(
                video=provider_module.create_provider(),
                video_secret_reader=lambda _name: "offline-test-token",
                video_transport=offline_transport,
            )
            with self.runtime_environment():
                recovered = HANDLER.execute(
                    context, {"admission_id": admission.request_sha256, "mode": "recover"}, False)
            self.assertEqual(recovered.output["status"], "recovered_quarantined")
            self.assertEqual(recovered.output["provider_call_count"], 0)
            self.assertTrue(Path(recovered.output["video"]).is_file())
            self.assertTrue(Path(recovered.output["evidence"]).is_file())
            consumed = json.loads(ledger_path.read_text())
            self.assertEqual(consumed["status"], "completed")
            self.assertEqual(consumed["attempts"], 1)
            self.assertEqual(consumed["operation_name"], OPERATION)
            self.assertEqual(consumed["execution_namespace"], namespace)
            self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "consumed")
            self.assertEqual(len(generation_submissions), 1)
            self.assertEqual(len(recovery_polls), 1)

            # Reconciliation and recovery are idempotent after restart.
            with self.runtime_environment():
                repeated = HANDLER.execute(
                    context, {"admission_id": admission.request_sha256, "mode": "recover"}, False)
            self.assertEqual(repeated.output["status"], "recovered_quarantined")
            self.assertEqual(json.loads(ledger_path.read_text())["attempts"], 1)
            self.assertEqual(len(generation_submissions), 1)
            self.assertEqual(len(recovery_polls), 1)

            with self.assertRaises(AttemptLedgerError):
                HANDLER.execute(context, {"admission_id": admission.request_sha256, "mode": "generate"}, False)
            self.assertEqual(len(generation_submissions), 1)

    def test_normal_acceptance_consumes_before_polling_and_recovery_never_submits(self):
        admission = synthetic_admission()
        namespace = f"{admission.request['scope']['production_id']}/{admission.request['scope']['shot_id']}"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.authorize(root, admission)
            submissions = []
            polls = []

            def interrupted_transport(url, _body, _headers, _timeout, _maximum):
                if url.endswith(":predictLongRunning"):
                    submissions.append(url)
                    return 200, json.dumps({"name": OPERATION}).encode()
                self.assertTrue(url.endswith(":fetchPredictOperation"))
                record = json.loads((state / f"{admission.request_sha256}.attempt.json").read_text())
                self.assertEqual((record["status"], record["attempts"]), ("submitted", 1))
                self.assertEqual(record["execution_namespace"], namespace)
                self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "consumed")
                polls.append(url)
                raise urllib.error.URLError("simulated polling interruption")

            with self.runtime_environment():
                _, failed_code = self.run_runtime(self.controller(root, interrupted_transport), admission, "generate")
            self.assertNotEqual(failed_code, 0)
            ledger_path = state / f"{admission.request_sha256}.attempt.json"
            failed = json.loads(ledger_path.read_text())
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["attempts"], 1)
            self.assertEqual(failed["operation_name"], OPERATION)

            def recovery_transport(url, body, _headers, _timeout, _maximum):
                if url.endswith(":predictLongRunning"):
                    submissions.append(url)
                    return 200, json.dumps({"name": OPERATION}).encode()
                self.assertTrue(url.endswith(":fetchPredictOperation"))
                self.assertEqual(json.loads(body)["operationName"], OPERATION)
                polls.append(url)
                return 200, json.dumps({"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": base64.b64encode(MP4).decode(), "mimeType": "video/mp4",
                }]}}).encode()

            with self.runtime_environment():
                _, duplicate_code = self.run_runtime(self.controller(root, recovery_transport), admission, "generate")
            self.assertNotEqual(duplicate_code, 0)
            self.assertEqual(len(submissions), 1)
            self.assertEqual(polls, [polls[0]])
            preflight = NoNetworkPreflight()
            with self.runtime_environment():
                os.environ.pop("VSS_VERTEX_AI_QUOTA_EVIDENCE_FILE", None)
                recovered, recovery_code = self.run_runtime(
                    self.controller(root, recovery_transport, preflight), admission, "recover")
            self.assertEqual(recovery_code, 0, recovered)
            self.assertEqual(preflight.calls, 0)
            self.assertEqual(len(submissions), 1)
            self.assertEqual(recovered["output"]["provider_call_count"], 0)
            self.assertEqual(json.loads(ledger_path.read_text())["attempts"], 1)

    def test_recovery_rejects_missing_malformed_mismatched_or_conflicting_evidence(self):
        admission = synthetic_admission()
        namespace = f"{admission.request['scope']['production_id']}/{admission.request['scope']['shot_id']}"
        invalid_cases = ("missing", "malformed", "digest", "namespace", "operation", "reservation", "conflict", "bound_operation")
        for case in invalid_cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = self.authorize(root, admission)
                destination = root / ".local/movie/m11-0-moving-shot" / admission.request["scope"]["shot_id"] / "output" / admission.request_sha256
                destination.mkdir(parents=True)
                ledger_path = state / f"{admission.request_sha256}.attempt.json"
                ledger = AttemptLedger(ledger_path, admission.request_sha256)
                reservation_namespace = "wrong/identity" if case == "reservation" else namespace
                ledger.reserve_execution(reservation_namespace)
                evidence = self.operation_record(admission)
                if case == "digest":
                    evidence["request_sha256"] = "0" * 64
                elif case == "namespace":
                    evidence["execution_namespace"] = "wrong/identity"
                elif case == "operation":
                    evidence["operation_name"] = "not-a-vertex-operation"
                elif case == "bound_operation":
                    ledger.accept_operation(OPERATION + "-different", namespace)
                    ledger.terminal("failed")
                if case == "malformed":
                    (destination / "operation.json").write_text("{", encoding="utf-8")
                elif case != "missing":
                    (destination / "operation.json").write_text(json.dumps(evidence), encoding="utf-8")
                if case == "conflict":
                    (destination / "operation-conflict.json").write_text(json.dumps(evidence), encoding="utf-8")
                provider_calls = {"generate": 0, "recover": 0}

                class NeverProvider:
                    def generate(self, *_args, **_kwargs):
                        provider_calls["generate"] += 1
                        raise AssertionError("mismatched recovery must not generate")

                    def recover(self, *_args, **_kwargs):
                        provider_calls["recover"] += 1
                        raise AssertionError("invalid recovery must not poll")

                context = self.make_handler_context(admission, destination, NeverProvider())
                with self.assertRaises((ValueError, AttemptLedgerError)):
                    HANDLER.execute(context, {"admission_id": admission.request_sha256, "mode": "recover"}, False)
                self.assertEqual(provider_calls, {"generate": 0, "recover": 0})
                current = json.loads(ledger_path.read_text())
                if case != "bound_operation":
                    self.assertEqual(current["attempts"], 0)
                    self.assertEqual(current["status"], "reserved")
                    self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "authorized")

    def test_malformed_terminal_and_media_admission_failures_never_resubmit(self):
        admission = synthetic_admission()
        for failure_kind in ("malformed_terminal", "invalid_media"):
            with self.subTest(failure_kind=failure_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = self.authorize(root, admission)
                submissions = []
                polls = []

                def transport(url, body, _headers, _timeout, _maximum):
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
                        }]}}
                    else:
                        terminal = {"done": True, "response": {"videos": [{
                            "bytesBase64Encoded": base64.b64encode(MP4).decode(),
                        }]}}
                    return 200, json.dumps(terminal).encode()

                with self.runtime_environment():
                    _, initial_code = self.run_runtime(self.controller(root, transport), admission, "generate")
                self.assertNotEqual(initial_code, 0)
                ledger_path = state / f"{admission.request_sha256}.attempt.json"
                failed = json.loads(ledger_path.read_text())
                self.assertEqual(failed["attempts"], 1)
                self.assertEqual(failed["operation_name"], OPERATION)
                self.assertEqual(json.loads((state / "authorization.json").read_text())["status"], "consumed")
                with self.runtime_environment():
                    recovered, recovery_code = self.run_runtime(self.controller(root, transport), admission, "recover")
                self.assertEqual(recovery_code, 0, recovered)
                self.assertEqual(len(submissions), 1)
                self.assertEqual(len(polls), 2)
                self.assertEqual(json.loads(ledger_path.read_text())["attempts"], 1)
                self.assertEqual(json.loads(ledger_path.read_text())["status"], "completed")


if __name__ == "__main__":
    unittest.main()
