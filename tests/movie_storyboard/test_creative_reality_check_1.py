from __future__ import annotations

import base64
import copy
import json
import shutil
import struct
import tempfile
import time
import unittest
import zlib
from pathlib import Path

from tests.movie_storyboard.test_m8_0 import bundle, execute as execute_storyboard
from vss_commands import CommandRunner, ExitCode
from vss_movie_creative_experiment import (EXPERIMENT_FRAME_ID, AdmittedCreativeExperiment,
    CreativeExperimentPlanStore, admit_creative_experiment)
from vss_providers.experimental import ENDPOINT, SECRET_NAME, ExperimentalOpenAIExecutionAccess
from vss_providers.experimental_png import MAX_BYTES, validate_experimental_openai_png
from vss_providers import (CreativeExperimentRequest, ExperimentalProviderDiagnostic,
                           ProviderAccessDenied, ProviderExecutionFailure)
from vss_reasoning_contracts import canonical_digest
from vss_runtime import RuntimeController
from vss_runtime.audit import AuditLogger
from vss_runtime.errors import RuntimeInternalFailure
from vss_runtime.policy import RuntimePolicy

ROOT = Path(__file__).resolve().parents[2]


def chunk(kind: bytes, value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)


def png() -> bytes:
    width, height = 1536, 1024
    raw = (b"\x00" + b"\x80\x70\x60" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def png_with_content_credentials(payload: bytes = b"opaque-c2pa-test-payload") -> bytes:
    content = png()
    return content[:33] + chunk(b"caBX", payload) + content[33:]


class FailedAudit(AuditLogger):
    def append(self, record):
        raise RuntimeInternalFailure("audit failed")


class CreativeRealityCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        self.values = bundle(knowledge=True)
        self.storyboard = execute_storyboard(self.values)["scene_storyboard_specification"]
        self.assertIn(EXPERIMENT_FRAME_ID, [f["frame_id"] for f in self.storyboard["payload"]["ordered_frames"]])
        self.base = dict(zip(("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), self.values))
        self.base.update(storyboard=self.storyboard, frame_id=EXPERIMENT_FRAME_ID)
        self.calls = []

    def tearDown(self): self.temporary.cleanup()

    def transport(self, url, body, headers, timeout, maximum):
        self.calls.append((url, json.loads(body), dict(headers), timeout, maximum))
        return json.dumps({"data": [{"b64_json": base64.b64encode(png()).decode("ascii")}]}).encode()

    def controller(self, **kwargs):
        return RuntimeController(root=self.root, experiment_transport=kwargs.pop("transport", self.transport),
            experiment_secret_reader=kwargs.pop("secret_reader", lambda name: "test-credential"), **kwargs)

    def direct_provider_generate(self, response: bytes):
        controller = self.controller()
        registration = controller.provider_registry.resolve("movie.storyboard-image.openai-crc1")
        provider = controller.provider_registry.initialize(registration,
            ExperimentalOpenAIExecutionAccess(lambda *args: response, lambda _: "test-credential"))
        handle = __import__("vss_providers", fromlist=["ProviderAccess"]).ProviderAccess(experiment=provider).get_creative_experiment_generator()
        admitted = admit_creative_experiment(*self.values, self.storyboard, frame_id=EXPERIMENT_FRAME_ID,
            condition="A", environment="development")
        request = CreativeExperimentRequest(admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest,
            admitted.frame_id, admitted.frame_specification_digest, admitted.condition, admitted.prompt,
            admitted.prompt_digest, admitted.semantic_request_digest)
        return handle.generate(request)

    def generate(self, **kwargs):
        return CommandRunner(runtime_controller=kwargs.pop("controller", self.controller())).run(
            "movie.creative-reality-check-1", kwargs.pop("environment", "development"),
            self.base, "crc1-test", **kwargs)

    def test_fake_end_to_end_follows_plan_and_is_blind_bound(self):
        outputs = []
        for _ in range(6):
            response, code = self.generate(); self.assertEqual(code, 0, response)
            output = response["output"]; outputs.append(output)
            self.assertEqual(validate_experimental_openai_png((self.root / output["artifact_path"]).read_bytes()), (1536, 1024))
            review = json.loads((self.root / output["review_path"]).read_text())
            self.assertNotIn("condition", review); self.assertNotIn("condition", output)
            self.assertNotIn("prompt_digest", output); self.assertNotIn("condition_mapping_path", output)
            self.assertTrue(all(value is False for value in output["authority_boundary"].values()))
        self.assertEqual([output["plan_ordinal"] for output in outputs], list(range(1, 7)))
        self.assertEqual(len({output["candidate_label"] for output in outputs}), 6)
        reviewer_plan = json.loads((self.root / ".local/movie/creative-reality-check-1/reviewer-plan.json").read_text())
        self.assertEqual([item["image_path"] for item in reviewer_plan["candidates"]],
                         [output["artifact_path"] for output in outputs])
        self.assertNotIn("condition", json.dumps(reviewer_plan)); self.assertNotIn("prompt", json.dumps(reviewer_plan))
        self.assertEqual([call[0] for call in self.calls], [ENDPOINT] * 6)
        self.assertEqual(sum("Dramatic purpose" in call[1]["prompt"] for call in self.calls), 3)
        settings = [{k: v for k, v in call[1].items() if k != "prompt"} for call in self.calls]
        self.assertTrue(all(value == settings[0] for value in settings))
        self.assertNotIn("test-credential", json.dumps(outputs))

    def test_content_credentials_are_preserved_as_opaque_non_authoritative_evidence(self):
        payload = b"opaque-c2pa-secret-payload"
        encoded = json.dumps({"data": [{"b64_json": base64.b64encode(png_with_content_credentials(payload)).decode()}]}).encode()
        response, code = self.generate(controller=self.controller(transport=lambda *args: encoded))
        self.assertEqual(code, 0, response)
        output = response["output"]
        media = (self.root / output["artifact_path"]).read_bytes()
        self.assertEqual(media, png_with_content_credentials(payload))
        self.assertTrue(output["content_credentials_present"])
        self.assertEqual(output["content_credentials_chunk_bytes"], len(payload))
        mapping = next((self.root / ".local/movie/creative-reality-check-1/condition-mapping").glob("*.json"))
        evidence = json.loads(mapping.read_text())
        self.assertEqual(evidence["content_credentials"], {"present": True, "chunk_type": "caBX",
            "chunk_bytes": len(payload), "cryptographically_verified": False, "grants_authority": False})
        persisted = "".join(path.read_text(errors="replace") for path in (self.root / ".local").rglob("*")
                            if path.is_file() and path.suffix != ".png")
        self.assertNotIn(payload.decode(), persisted)
        self.assertTrue(all(value is False for value in output["authority_boundary"].values()))

    def test_plan_is_balanced_preassigned_separate_stable_and_network_free(self):
        tokens = iter(f"{value:016x}" for value in range(1, 7))
        store = CreativeExperimentPlanStore(self.root, token_hex=lambda _: next(tokens), shuffle=lambda values: values.reverse())
        expected = {condition: admit_creative_experiment(*self.values, self.storyboard,
            frame_id=EXPERIMENT_FRAME_ID, condition=condition, environment="development").prompt_digest
            for condition in ("A", "B")}
        internal, reviewer = store.initialize(expected)
        self.assertEqual(self.calls, [])
        self.assertEqual([slot["condition"] for slot in internal["slots"]].count("A"), 3)
        self.assertEqual([slot["condition"] for slot in internal["slots"]].count("B"), 3)
        labels = [slot["candidate_label"] for slot in internal["slots"]]
        self.assertEqual(len(set(labels)), 6); self.assertTrue(all(len(label) == 26 for label in labels))
        self.assertEqual(labels, [candidate["candidate_label"] for candidate in reviewer["candidates"]])
        self.assertNotIn("condition", json.dumps(reviewer)); self.assertNotIn("prompt", json.dumps(reviewer))
        self.assertEqual((internal, reviewer), store.initialize(expected))

    def test_malformed_or_conflicting_plan_fails_closed(self):
        expected = {condition: admit_creative_experiment(*self.values, self.storyboard,
            frame_id=EXPERIMENT_FRAME_ID, condition=condition, environment="development").prompt_digest
            for condition in ("A", "B")}
        store = CreativeExperimentPlanStore(self.root); store.initialize(expected)
        path = self.root / ".local/movie/creative-reality-check-1/internal-condition-plan.json"
        value = json.loads(path.read_text()); value["slots"][0]["expected_prompt_digest"] = "0" * 64
        path.write_text(json.dumps(value))
        with self.assertRaises(Exception): store.initialize(expected)
        self.assertEqual(self.calls, [])

    def test_caller_cannot_select_condition_and_failed_slot_is_not_replaced(self):
        response, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.creative-reality-check-1", "development", {**self.base, "condition": "A"}, "caller-choice")
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response); self.assertEqual(self.calls, [])
        failed = self.controller(transport=lambda *args: b"{}")
        _, code = self.generate(controller=failed); self.assertNotEqual(code, 0)
        response, code = self.generate(); self.assertEqual(code, 0, response)
        self.assertEqual(response["output"]["plan_ordinal"], 2)
        attempts = sorted((self.root / ".local/movie/creative-reality-check-1/attempts").glob("*.json"))
        statuses = [json.loads(path.read_text())["status"] for path in attempts]
        self.assertEqual(sorted(statuses), ["failed", "succeeded"])

    def test_admission_is_exact_immutable_and_not_publicly_forgeable(self):
        admitted = admit_creative_experiment(*self.values, self.storyboard, frame_id=EXPERIMENT_FRAME_ID, condition="A", environment="development")
        again = admit_creative_experiment(*self.values, self.storyboard, frame_id=EXPERIMENT_FRAME_ID, condition="A", environment="development")
        self.assertEqual(admitted.semantic_request_digest, again.semantic_request_digest)
        self.assertEqual(admitted.prompt_digest, "be177a187032bbf227b485ee0ec667ba0aec313df75d1bdb209e6cab01fb4c67")  # pragma: allowlist secret
        admitted_b = admit_creative_experiment(*self.values, self.storyboard, frame_id=EXPERIMENT_FRAME_ID, condition="B", environment="development")
        self.assertEqual(admitted_b.prompt_digest, "a482c5ddfaa950f9478ae768b23a87a2f46d900ee501561dd835b73e9b980c38")  # pragma: allowlist secret
        with self.assertRaises(TypeError): AdmittedCreativeExperiment(object())
        response, code = self.controller().run("movie.creative-reality-check-1-generate", "development", {},
            {"admission_id": admitted.admission_id}, "bypass", "2026-01-01T00:00:00.000Z", 0.0)
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)
        for frame, condition in (("frame-" + "0" * 24, "A"), (EXPERIMENT_FRAME_ID, "C")):
            with self.assertRaises(Exception): admit_creative_experiment(*self.values, self.storyboard, frame_id=frame, condition=condition, environment="development")

    def test_dry_run_production_secret_and_permission_denials_make_no_call(self):
        response, code = self.generate(dry_run=True); self.assertEqual(code, 0, response); self.assertEqual(self.calls, [])
        self.assertTrue((self.root / ".local/movie/creative-reality-check-1/reviewer-plan.json").exists())
        _, code = self.generate(environment="production"); self.assertEqual(code, int(ExitCode.INVALID_INPUT))
        _, code = self.generate(controller=self.controller(secret_reader=lambda name: None)); self.assertNotEqual(code, 0)
        for permissions in (("provider_access", "filesystem_write", "secrets"), ("provider_access", "filesystem_write", "network")):
            policy = RuntimePolicy(allowed_provider_identities=("movie.storyboard-image.openai-crc1",),
                allowed_capability_permissions={"movie.creative-reality-check-1": permissions})
            _, code = self.generate(controller=self.controller(policy=policy)); self.assertNotEqual(code, 0)
        self.assertEqual(self.calls, [])

    def test_provider_response_and_audit_fail_closed_without_leakage(self):
        for response in (b"{}", b"x" * (12 * 1024 * 1024 + 1),
                         json.dumps({"data": [{"b64_json": base64.b64encode(b"not png").decode()}]}).encode()):
            _, code = self.generate(controller=self.controller(transport=lambda *args, value=response: value))
            self.assertNotEqual(code, 0)
        _, code = self.generate(controller=self.controller(audit_logger=FailedAudit(self.root / "audit", trusted_root=self.root)))
        self.assertNotEqual(code, 0)
        self.assertFalse(any((self.root / ".local/movie/storyboard-images").rglob("*.png")))

    def test_sanitized_provider_diagnostic_is_preserved_only_in_failure_audit(self):
        diagnostic = ExperimentalProviderDiagnostic(True, "http_authentication", 401,
            "authentication_error", "invalid_api_key", "provider returned a sanitized error classification", "req_safe123")
        def failed_transport(*args):
            raise ProviderExecutionFailure("external image provider returned an unsuccessful status", diagnostic=diagnostic)
        response, code = self.generate(controller=self.controller(transport=failed_transport))
        self.assertNotEqual(code, 0); self.assertNotIn("invalid_api_key", json.dumps(response))
        audit = [json.loads(line) for line in (self.root / ".local/runtime/audit/executions.jsonl").read_text().splitlines()][-1]
        self.assertEqual(audit["provider_diagnostic"], diagnostic.as_dict())
        persisted = "".join(path.read_text(errors="replace") for path in (self.root / ".local").rglob("*") if path.is_file())
        self.assertNotIn("test-credential", persisted); self.assertNotIn("Authorization", persisted)
        self.assertNotIn("Dramatic purpose", persisted)

    def test_post_http_success_extras_and_closed_failure_stages(self):
        valid = {"created": 1, "data": [{"b64_json": base64.b64encode(png()).decode(),
            "revised_prompt": "documented optional", "url": None}], "output_format": "png",
            "size": "1536x1024", "quality": "medium", "usage": {"total_tokens": 3,
            "input_tokens": 1, "output_tokens": 2, "input_tokens_details": {"text_tokens": 1}}}
        result = self.direct_provider_generate(json.dumps(valid).encode())
        self.assertEqual((result.media.width, result.media.height), (1536, 1024))
        base_png = png(); ancillary_png = base_png[:33] + chunk(b"sRGB", b"\x00") + base_png[33:]
        cases = (
            (b"not-json", "response_json_invalid"),
            (json.dumps({"unexpected": 1}).encode(), "response_schema_invalid"),
            (json.dumps({"data": [{}]}).encode(), "image_payload_missing"),
            (json.dumps({"data": [{"b64_json": 4}]}).encode(), "image_payload_invalid"),
            (json.dumps({"data": [{"b64_json": "%%%"}]}).encode(), "base64_invalid"),
            (json.dumps({"data": [{"b64_json": base64.b64encode(b"x" * (MAX_BYTES + 1)).decode()}]}).encode(), "decoded_media_too_large"),
            (json.dumps({"data": [{"b64_json": base64.b64encode(ancillary_png).decode()}]}).encode(), "png_conformance_failed"),
        )
        for response, classification in cases:
            with self.subTest(classification=classification), self.assertRaises(ProviderExecutionFailure) as caught:
                self.direct_provider_generate(response)
            diagnostic = caught.exception.diagnostic
            self.assertEqual(diagnostic.classification, classification)
            self.assertEqual(diagnostic.http_status, 200)
            self.assertEqual(diagnostic.encoded_response_bytes, len(response))
            encoded = json.dumps(diagnostic.as_dict())
            self.assertNotIn("test-credential", encoded); self.assertNotIn("Dramatic purpose", encoded)
            self.assertNotIn("b64_json", encoded); self.assertLess(len(encoded), 1200)
        oversized = cases[-2][0]
        diagnostic = None
        try: self.direct_provider_generate(oversized)
        except ProviderExecutionFailure as exc: diagnostic = exc.diagnostic
        self.assertEqual(diagnostic.decoded_media_bytes, MAX_BYTES + 1)
        self.assertEqual(diagnostic.media_sha256, __import__("hashlib").sha256(b"x" * (MAX_BYTES + 1)).hexdigest())
        png_failure = cases[-1][0]
        try: self.direct_provider_generate(png_failure)
        except ProviderExecutionFailure as exc: diagnostic = exc.diagnostic
        self.assertEqual(diagnostic.png.rejection_reason, "disallowed_chunk")
        self.assertIn("sRGB", diagnostic.png.chunk_types)

    def test_exact_provider_model_egress_and_one_call_ceiling(self):
        controller = self.controller()
        registration = controller.provider_registry.resolve("movie.storyboard-image.openai-crc1")
        from vss_providers.experimental import ExperimentalOpenAIExecutionAccess
        provider = controller.provider_registry.initialize(registration, ExperimentalOpenAIExecutionAccess(self.transport, lambda name: "test-credential"))
        handle = __import__("vss_providers", fromlist=["ProviderAccess"]).ProviderAccess(experiment=provider).get_creative_experiment_generator()
        admitted = admit_creative_experiment(*self.values, self.storyboard, frame_id=EXPERIMENT_FRAME_ID, condition="A", environment="development")
        request = CreativeExperimentRequest(admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest,
            admitted.frame_id, admitted.frame_specification_digest, admitted.condition, admitted.prompt,
            admitted.prompt_digest, admitted.semantic_request_digest)
        handle.generate(request)
        with self.assertRaises(ProviderAccessDenied): handle.generate(request)
        manifest = self.root / "providers/builtin/movie-storyboard-image-openai-crc1/provider.yaml"
        manifest.write_text(manifest.read_text().replace("vss.experimental-openai-creative-reality-check-1", "substituted-implementation"))
        _, code = self.generate(controller=self.controller()); self.assertNotEqual(code, 0)
        import vss_providers.experimental as boundary
        original = boundary.ENDPOINT
        try:
            boundary.ENDPOINT = "https://attacker.invalid/v1/images/generations"
            with self.assertRaises(Exception): ExperimentalOpenAIExecutionAccess(self.transport, lambda name: "test-credential").post_images({})
        finally:
            boundary.ENDPOINT = original

    def test_timeout_aborts_late_publication_and_no_retry(self):
        count = [0]
        def slow(*args):
            count[0] += 1; time.sleep(.15); return self.transport(*args)
        _, code = self.generate(controller=self.controller(transport=slow), timeout_seconds=.01)
        self.assertNotEqual(code, 0); time.sleep(.2); self.assertEqual(count[0], 1)
        self.assertFalse(any((self.root / ".local/movie/storyboard-images").rglob("*.png")))

    def test_resealed_storyboard_substitution_fails_before_provider(self):
        forged = copy.deepcopy(self.storyboard)
        frame = next(f for f in forged["payload"]["ordered_frames"] if f["frame_id"] == EXPERIMENT_FRAME_ID)
        frame["action"] = "Unsupported supernatural event"
        material = dict(frame); material.pop("frame_specification_digest")
        frame["frame_specification_digest"] = canonical_digest(material)
        forged["payload"]["storyboard_specification_digest"] = canonical_digest({**forged["payload"], "storyboard_specification_digest": None})
        forged["integrity"]["payload_sha256"] = canonical_digest(forged["payload"])
        forged["integrity"]["complete_result_sha256"] = canonical_digest({**forged, "integrity": {"payload_sha256": forged["integrity"]["payload_sha256"]}})
        response, code = CommandRunner(runtime_controller=self.controller()).run("movie.creative-reality-check-1", "development",
            {**self.base, "storyboard": forged}, "forged")
        self.assertNotEqual(code, 0, response); self.assertEqual(self.calls, [])


if __name__ == "__main__": unittest.main()
