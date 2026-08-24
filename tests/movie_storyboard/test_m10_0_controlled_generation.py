from __future__ import annotations

import base64
import copy
import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from vss_commands import CommandRunner, ExitCode
from vss_movie_controlled_generation import (
    APPROVER_SECRET_NAME, SECRET_NAME, admit_controlled_generation, issue_approval,
)
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_creative_smoke.provider import SmokeHTTPResponse
from vss_runtime import RuntimeController, RuntimePolicy
from vss_runtime.external_preflight import ExternalExecutionPreflight
from vss_resource_contracts import ResourceContractError


ROOT = Path(__file__).resolve().parents[2]
APPROVER_SECRET = "test-only-approver-key-material-00000001"  # pragma: allowlist secret
PROVIDER_SECRET = "test-only-provider-key"  # pragma: allowlist secret


def _chunk(kind: bytes, content: bytes) -> bytes:
    return (struct.pack(">I", len(content)) + kind + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF))


def png(*, cabx: bytes | None = None) -> bytes:
    header = struct.pack(">IIBBBBB", 1280, 720, 8, 2, 0, 0, 0)
    pixels = (b"\0" + b"\0" * (1280 * 3)) * 720
    chunks = [_chunk(b"IHDR", header)]
    if cabx is not None:
        chunks.append(_chunk(b"caBX", cabx))
    chunks.extend((_chunk(b"IDAT", zlib.compress(pixels)), _chunk(b"IEND", b"")))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def response(content: bytes) -> SmokeHTTPResponse:
    value = {
        "created": 42,
        "data": [{"b64_json": base64.b64encode(content).decode("ascii"), "revised_prompt": None}],
        "usage": {"input_tokens": 325, "output_tokens": 1200, "total_tokens": 1525,
                  "input_tokens_details": {"text_tokens": 325, "image_tokens": 0}},
        "background": "opaque", "output_format": "png", "quality": "medium", "size": "1280x720",
    }
    return SmokeHTTPResponse(json.dumps(value).encode("utf-8"), 200, "req_m10_safe")


class M100ControlledGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        story = json.loads((ROOT / "tests/fixtures/movie/story-fragment-valid.json").read_text())
        prepared = prepare_demo(story, correlation_id="m10-real-path")
        option_id = prepared.review_packet["payload"]["review_entries"][0]["option_id"]
        finished = finish_demo(
            prepared, option_id=option_id, reviewer_id="reviewer-m10",
            rationale="Accepted for controlled external review candidate test.",
            correlation_id="m10-real-path", include_storyboard=True,
        )
        cls.base_payload = {
            "story": prepared.story, "decision": finished["review_decision"],
            "review_packet": finished["review_packet"], "option_set": finished["scene_production_option_set"],
            "scene_breakdown": finished["scene_breakdown"],
            "creative_decision": finished["creative_decision_revision"],
            "canon_snapshot": finished["canon_snapshot"], "canon_binding": finished["production_canon_binding"],
            "shot_plan": finished["scene_shot_plan_draft"],
            "storyboard": finished["scene_storyboard_specification"],
            "frame_id": finished["scene_storyboard_specification"]["payload"]["ordered_frames"][0]["frame_id"],
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        self.calls = []
        self.provider_secret_reads = []
        self.approver_secret_reads = []

    def tearDown(self):
        self.temporary.cleanup()

    def admit(self, payload=None, approval=None):
        value = payload or self.base_payload
        return admit_controlled_generation(
            value["story"], value["decision"], value["review_packet"], value["option_set"],
            value["scene_breakdown"], value["creative_decision"], value["canon_snapshot"],
            value["canon_binding"], value["shot_plan"], value["storyboard"],
            frame_id=value["frame_id"], environment="development", approval=approval,
        )

    def approval(self, admitted):
        return issue_approval(
            admitted.request_json(), recorded_by="reviewer-m10", secret=APPROVER_SECRET,
            issued_at="2030-01-02T03:00:00Z", expires_at="2030-01-02T03:15:00Z",
        )

    def transport(self, *args):
        self.calls.append(args)
        return response(png())

    def provider_secret_reader(self, name):
        self.provider_secret_reads.append(name)
        return PROVIDER_SECRET

    def approver_secret_reader(self, name):
        self.approver_secret_reads.append(name)
        return APPROVER_SECRET

    def controller(self, *, policy=None, transport=None):
        return RuntimeController(
            root=self.root, policy=policy,
            controlled_provider_transport=transport or self.transport,
            controlled_provider_secret_reader=self.provider_secret_reader,
            controlled_approver_secret_reader=self.approver_secret_reader,
            controlled_now=lambda: "2030-01-02T03:05:00Z",
            external_execution_preflight=ExternalExecutionPreflight(
                environment_contains=lambda name: name == SECRET_NAME,
                resolver=lambda hostname, port: [(hostname, port)],
            ),
        )

    def runtime(self, admitted, *, mode, controller=None):
        return (controller or self.controller()).run(
            command="movie.controlled-review-frame-generate", environment="development", configuration={},
            input_data={"admission_id": admitted.request["request_sha256"], "mode": mode},
            correlation_id="m10-test", started_at="2030-01-02T03:05:00.000Z", started_clock=0.0,
            dry_run=mode == "preflight", timeout_seconds=150, admitted_request=admitted,
        )

    def test_genuine_demo_path_is_deterministic_and_minimizes_provider_projection(self):
        first = self.admit()
        second = self.admit()
        self.assertEqual(first.request_json(), second.request_json())
        prompt = first.prompt.casefold()
        for expected in ("clean cinematic", "continuity constraints", "negative constraints"):
            self.assertIn(expected, prompt)
        for prohibited in ("tenant-local", "reviewer-m10", "canon_sha256", "request_sha256"):
            self.assertNotIn(prohibited, prompt)
        self.assertEqual(first.request["bounds"]["maximum_provider_attempts"], 1)
        self.assertEqual(first.request["bounds"]["maximum_cost_usd"], "0.100000")
        with self.assertRaises(TypeError):
            first.request["provider"]["model_snapshot"] = "moving-alias"

    def test_preflight_is_zero_call_zero_secret_zero_reservation(self):
        admitted = self.admit()
        result, code = self.runtime(admitted, mode="preflight")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["output"]["provider_call_count"], 0)
        self.assertFalse(result["output"]["attempt_reserved"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [])
        self.assertFalse((self.root / ".local/movie/m10-0-controlled-review-frame").exists())

    def test_one_approved_fake_call_admits_quarantined_candidate_and_empty_review(self):
        base = self.admit()
        admitted = self.admit(approval=self.approval(base))
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, 0, result)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.approver_secret_reads, [APPROVER_SECRET_NAME])
        self.assertEqual(self.provider_secret_reads, [SECRET_NAME])
        output = result["output"]
        candidate = json.loads((self.root / output["candidate"]).read_text())
        review = json.loads((self.root / output["review"]).read_text())
        self.assertEqual(candidate["status"], "development_review_quarantined")
        self.assertEqual(candidate["scope"]["project_id"], base.request["scope"]["project_id"])
        self.assertTrue(all(value is False for value in candidate["authority"].values()))
        self.assertEqual(candidate["preservation"]["policy"], "disposable_local")
        self.assertIsNone(review["disposition"])
        self.assertEqual((self.root / output["image"]).read_bytes(), png())

    def test_valid_story_substitution_is_rejected_before_any_secret_or_call(self):
        payload = copy.deepcopy(self.base_payload)
        payload["story"]["payload"]["fragment_text"] += " A validly shaped substitution."
        with self.assertRaises(Exception):
            self.admit(payload)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [])

    def test_tampered_approval_and_kill_switch_fail_before_attempt(self):
        base = self.admit()
        approval = self.approval(base)
        approval["recorded_by"] = "attacker"
        admitted = self.admit(approval=approval)
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, ExitCode.PERMISSION_DENIED, result)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        attempt_root = self.root / ".local/movie/m10-0-controlled-review-frame"
        self.assertFalse(attempt_root.exists())

        policy = RuntimePolicy(
            allowed_builtin_permissions=("provider_access",),
            allowed_provider_identities=("movie.storyboard-image.openai",),
            allowed_capability_permissions={"movie.controlled-review-frame":
                ("filesystem_write", "network", "provider_access", "secrets")},
            controlled_media_killed=True,
        )
        result, code = self.runtime(self.admit(approval=self.approval(base)), mode="generate",
                                    controller=self.controller(policy=policy))
        self.assertEqual(code, ExitCode.PERMISSION_DENIED, result)
        self.assertEqual(self.calls, [])

    def test_expired_or_overlong_approval_is_denied_before_attempt(self):
        base = self.admit()
        with self.assertRaises(ResourceContractError):
            issue_approval(
                base.request_json(), recorded_by="reviewer-m10", secret=APPROVER_SECRET,
                issued_at="2030-01-02T03:00:00Z", expires_at="2030-01-02T03:15:01Z",
            )
        expired = issue_approval(
            base.request_json(), recorded_by="reviewer-m10", secret=APPROVER_SECRET,
            issued_at="2030-01-02T02:45:00Z", expires_at="2030-01-02T03:00:00Z",
        )
        result, code = self.runtime(self.admit(approval=expired), mode="generate")
        self.assertEqual(code, ExitCode.PERMISSION_DENIED, result)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [APPROVER_SECRET_NAME])
        self.assertFalse((self.root / ".local/movie/m10-0-controlled-review-frame").exists())

    def test_closed_provider_response_and_cost_ceiling_are_terminal(self):
        base = self.admit()
        approval = self.approval(base)

        def unexpected_field(value):
            value["unexpected"] = "not admitted"

        def extra_image(value):
            value["data"].append(copy.deepcopy(value["data"][0]))

        def excessive_cost(value):
            value["usage"].update({"output_tokens": 4_000_000, "total_tokens": 4_000_325})

        for label, mutate in (("unexpected-field", unexpected_field),
                              ("extra-image", extra_image), ("excessive-cost", excessive_cost)):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                isolated_root = Path(directory)
                for name in ("capabilities", "providers", "schemas"):
                    shutil.copytree(ROOT / name, isolated_root / name)
                calls = []

                def malformed_transport(*args):
                    calls.append(args)
                    value = json.loads(response(png()).content)
                    mutate(value)
                    return SmokeHTTPResponse(
                        json.dumps(value).encode("utf-8"), 200, "req_m10_rejected")

                controller = RuntimeController(
                    root=isolated_root,
                    controlled_provider_transport=malformed_transport,
                    controlled_provider_secret_reader=self.provider_secret_reader,
                    controlled_approver_secret_reader=self.approver_secret_reader,
                    controlled_now=lambda: "2030-01-02T03:05:00Z",
                    external_execution_preflight=ExternalExecutionPreflight(
                        environment_contains=lambda name: name == SECRET_NAME,
                        resolver=lambda hostname, port: [(hostname, port)],
                    ),
                )
                admitted = self.admit(approval=approval)
                result, code = self.runtime(admitted, mode="generate", controller=controller)
                self.assertNotEqual(code, 0, result)
                self.assertEqual(len(calls), 1)
                artifact_root = (isolated_root / ".local/movie/m10-0-controlled-review-frame"
                                 / base.request["request_sha256"])
                self.assertTrue((artifact_root / "attempt.json").exists())
                self.assertFalse((artifact_root / "generated-review-candidate.json").exists())

    def test_replay_and_content_credentials_are_terminal_after_reservation(self):
        base = self.admit()
        approval = self.approval(base)
        admitted = self.admit(approval=approval)
        result, code = self.runtime(admitted, mode="generate",
                                    controller=self.controller(transport=lambda *args: response(png(cabx=b"foreign"))))
        self.assertNotEqual(code, 0, result)
        root = self.root / ".local/movie/m10-0-controlled-review-frame" / base.request["request_sha256"]
        self.assertTrue((root / "attempt.json").exists())
        self.assertFalse((root / "generated-review-candidate.json").exists())
        calls = len(self.calls)
        result, code = self.runtime(admitted, mode="generate")
        self.assertNotEqual(code, 0, result)
        self.assertEqual(len(self.calls), calls)

    def test_command_runner_preflight_approval_and_generate_use_real_stage_service(self):
        payload = {**self.base_payload, "mode": "preflight"}
        result, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.controlled-review-frame", "development", payload, "m10-runner")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["output"]["request"]["request_sha256"],
                         result["output"]["request_sha256"])
        self.assertEqual(self.calls, [])

        with patch.dict("os.environ", {APPROVER_SECRET_NAME: APPROVER_SECRET}):
            approval_result, approval_code = CommandRunner().run(
                "movie.controlled-review-frame", "development",
                {**self.base_payload, "mode": "approve", "recorded_by": "reviewer-m10"},
                "m10-runner-approve",
            )
        self.assertEqual(approval_code, 0, approval_result)
        self.assertEqual(approval_result["output"]["provider_call_count"], 0)
        approval = approval_result["output"]["approval"]

        controller = self.controller()
        controller.controlled_now = lambda: approval["issued_at"]
        generated, generated_code = CommandRunner(runtime_controller=controller).run(
            "movie.controlled-review-frame", "development",
            {**self.base_payload, "mode": "generate", "approval": approval},
            "m10-runner-generate",
        )
        self.assertEqual(generated_code, 0, generated)
        self.assertEqual(generated["output"]["provider_call_count"], 1)


if __name__ == "__main__":
    unittest.main()
