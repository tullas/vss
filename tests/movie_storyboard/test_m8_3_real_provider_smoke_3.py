from __future__ import annotations

import json
import io
import copy
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from tests.movie_storyboard import test_m8_3_real_provider_smoke as smoke_support
from tests.movie_storyboard.test_m8_0 import bundle, execute as execute_storyboard, reseal_storyboard
from vss_commands import CommandRunner, ExitCode
from vss_commands.cli import main
from vss_movie_creative_smoke import (
    EXPERIMENT_IDENTITY, SECRET_NAME, SMOKE_3_EXPERIMENT_IDENTITY, SmokeProviderFailure,
    admit_creative_smoke,
)
from vss_runtime import RuntimeController
from vss_runtime.external_preflight import ExternalExecutionPreflight


ROOT = Path(__file__).resolve().parents[2]


class M83RealProviderSmoke3Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        values = bundle(knowledge=True)
        self.values = values
        self.payload = dict(zip(
            ("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), values,
        ))
        self.payload["storyboard"] = execute_storyboard(values)["scene_storyboard_specification"]
        self.presence_checks: list[str] = []
        self.resolutions: list[tuple[str, int]] = []
        self.secret_reads: list[str] = []
        self.calls: list[tuple] = []

    def tearDown(self):
        self.temporary.cleanup()

    def preflight(self):
        def present(name):
            self.presence_checks.append(name)
            return name == SECRET_NAME

        def resolve(hostname, port):
            self.resolutions.append((hostname, port))
            return [(hostname, port)]

        return ExternalExecutionPreflight(environment_contains=present, resolver=resolve)

    def controller(self, *, transport=None, secret_reader=None):
        return RuntimeController(
            root=self.root,
            external_execution_preflight=self.preflight(),
            creative_smoke_transport=transport or (lambda *args: self.calls.append(args)),
            creative_smoke_secret_reader=secret_reader or (lambda name: self.secret_reads.append(name)),
        )

    def execute_smoke(self, *, dry_run, controller=None):
        payload = {**self.payload, "mode": "preflight" if dry_run else "generate"}
        return CommandRunner(runtime_controller=controller or self.controller()).run(
            "movie.m8-3-real-provider-smoke-3", "development", payload,
            "m83-smoke-3-test", dry_run=dry_run,
        )

    def test_prepaid_checkpoint_runs_authoritative_preflight_without_secret_call_or_state(self):
        response, code = self.execute_smoke(dry_run=True)
        self.assertEqual(code, 0, response)
        output = response["output"]
        self.assertEqual(output["experiment_status"], "ready_for_paid_authorization")
        self.assertEqual(output["provider_call_count"], 0)
        self.assertFalse(output["readiness"]["attempt_reserved"])
        self.assertTrue(output["readiness"]["credential_available"] and output["readiness"]["dns_ready"])
        self.assertIn(SECRET_NAME, self.presence_checks)
        self.assertEqual(self.resolutions, [("api.openai.com", 443)])
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY).exists())

    def test_generation_reruns_preflight_then_reserves_immediately_before_secret_read(self):
        checkpoint, code = self.execute_smoke(dry_run=True)
        self.assertEqual(code, 0, checkpoint)
        state = self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY / "attempt.json"

        def read_secret(name):
            self.assertEqual(name, SECRET_NAME)
            self.assertEqual(json.loads(state.read_text())["status"], "attempted")
            self.secret_reads.append(name)
            return smoke_support.SECRET

        def transport(*args):
            self.assertTrue(state.exists())
            self.calls.append(args)
            return smoke_support._response(smoke_support._png())

        response, code = self.execute_smoke(
            dry_run=False, controller=self.controller(transport=transport, secret_reader=read_secret),
        )
        self.assertEqual(code, 0, response)
        self.assertEqual(self.resolutions, [("api.openai.com", 443), ("api.openai.com", 443)])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.secret_reads, [SECRET_NAME])
        self.assertEqual(json.loads(state.read_text())["experiment"], SMOKE_3_EXPERIMENT_IDENTITY)
        self.assertFalse((self.root / ".local/movie/m8-3-real-provider-smoke-2").exists())
        reviewer = json.loads((self.root / response["output"]["review_path"]).read_text())
        self.assertEqual(reviewer["allowed_dispositions"], ["USE", "REGENERATE", "REJECT"])
        self.assertFalse(reviewer["regenerate_authorizes_another_call"])

    def test_failed_checkpoint_is_closed_and_does_not_reserve_or_read_secret(self):
        controller = RuntimeController(
            root=self.root,
            external_execution_preflight=ExternalExecutionPreflight(
                environment_contains=lambda name: name == SECRET_NAME,
                resolver=lambda *_: (),
            ),
            creative_smoke_transport=lambda *_: self.fail("transport called"),
            creative_smoke_secret_reader=lambda *_: self.fail("credential value read"),
        )
        response, code = self.execute_smoke(dry_run=True, controller=controller)
        self.assertNotEqual(code, 0, response)
        audit = json.loads((self.root / ".local/runtime/audit/executions.jsonl").read_text().splitlines()[-1])
        self.assertEqual(audit["external_execution_preflight"], {
            "classification": "dns", "provider_call_count": 0, "attempt_reserved": False,
        })
        self.assertFalse((self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY).exists())

    def test_successful_checkpoint_cannot_substitute_for_paid_path_preflight(self):
        checkpoint, code = self.execute_smoke(dry_run=True)
        self.assertEqual(code, 0, checkpoint)
        paid = RuntimeController(
            root=self.root,
            external_execution_preflight=ExternalExecutionPreflight(
                environment_contains=lambda name: name == SECRET_NAME,
                resolver=lambda *_: (),
            ),
            creative_smoke_transport=lambda *_: self.fail("transport called"),
            creative_smoke_secret_reader=lambda *_: self.fail("credential value read"),
        )
        response, code = self.execute_smoke(dry_run=False, controller=paid)
        self.assertNotEqual(code, 0, response)
        self.assertFalse((self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY).exists())

    def test_post_reservation_credential_failure_consumes_attempt_and_blocks_second_call(self):
        controller = self.controller(secret_reader=lambda name: self.secret_reads.append(name))
        response, code = self.execute_smoke(dry_run=False, controller=controller)
        self.assertNotEqual(code, 0, response)
        state_path = self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY / "attempt.json"
        self.assertEqual(json.loads(state_path.read_text())["status"], "failed")
        again, again_code = self.execute_smoke(dry_run=False, controller=controller)
        self.assertNotEqual(again_code, 0, again)
        self.assertEqual(self.secret_reads, [SECRET_NAME])
        self.assertEqual(self.calls, [])

    def test_post_reservation_transport_failure_consumes_attempt_and_is_sanitized(self):
        unsafe = "provider-secret-response-and-prompt"

        def fail(*args):
            self.calls.append(args)
            raise SmokeProviderFailure("fixed safe failure")

        controller = self.controller(transport=fail, secret_reader=lambda _: smoke_support.SECRET)
        response, code = self.execute_smoke(dry_run=False, controller=controller)
        self.assertNotEqual(code, 0, response)
        state_path = self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY / "attempt.json"
        self.assertEqual(json.loads(state_path.read_text())["status"], "failed")
        again, again_code = self.execute_smoke(dry_run=False, controller=controller)
        self.assertNotEqual(again_code, 0, again)
        self.assertEqual(len(self.calls), 1)
        persisted = response["errors"] + [
            path.read_text(errors="replace") for path in (self.root / ".local").rglob("*")
            if path.is_file() and path.suffix != ".png"
        ]
        self.assertNotIn(unsafe, json.dumps(persisted))
        self.assertNotIn("Create one clean cinematic image", json.dumps(persisted))

    def test_mode_and_authoritative_input_substitution_fail_before_provider_access(self):
        runner = CommandRunner(runtime_controller=self.controller())
        for payload, dry_run in (
            (self.payload, False),
            ({**self.payload, "mode": "preflight"}, False),
            ({**self.payload, "mode": "generate"}, True),
            ({**self.payload, "mode": "other"}, False),
            ({**self.payload, "mode": "preflight", "retry": True}, True),
        ):
            with self.subTest(payload_keys=tuple(payload), dry_run=dry_run):
                response, code = runner.run(
                    "movie.m8-3-real-provider-smoke-3", "development", payload,
                    "invalid-mode", dry_run=dry_run,
                )
                self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)
        forged = copy.deepcopy(self.payload["storyboard"])
        forged["payload"]["ordered_frames"][2]["action"] = "Invent an unrelated event."
        reseal_storyboard(forged)
        response, code = runner.run(
            "movie.m8-3-real-provider-smoke-3", "development",
            {**self.payload, "storyboard": forged, "mode": "preflight"},
            "forged-upstream", dry_run=True,
        )
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY).exists())

    def test_direct_runtime_rejects_mode_and_experiment_identity_confusion_before_state(self):
        smoke_3 = admit_creative_smoke(
            *self.values, self.payload["storyboard"], environment="development",
            experiment_identity=SMOKE_3_EXPERIMENT_IDENTITY,
        )
        smoke_2 = admit_creative_smoke(
            *self.values, self.payload["storyboard"], environment="development",
            experiment_identity=EXPERIMENT_IDENTITY,
        )
        controller = self.controller()
        cases = (
            (smoke_3, {"admission_id": smoke_3.admission_id, "mode": "preflight"}, False),
            (smoke_3, {"admission_id": smoke_3.admission_id, "mode": "generate"}, True),
            (smoke_2, {"admission_id": smoke_2.admission_id, "mode": "generate"}, False),
        )
        for admitted, input_data, dry_run in cases:
            with self.subTest(experiment=admitted.experiment_identity, input_data=input_data, dry_run=dry_run):
                response, code = controller.run(
                    command="movie.m8-3-real-provider-smoke-3-generate",
                    environment="development", configuration={}, input_data=input_data,
                    correlation_id="direct-runtime-boundary", started_at="2026-08-23T00:00:00Z",
                    started_clock=time.monotonic(), dry_run=dry_run, admitted_request=admitted,
                )
                self.assertNotEqual(code, 0, response)
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".local/movie" / EXPERIMENT_IDENTITY).exists())
        self.assertFalse((self.root / ".local/movie" / SMOKE_3_EXPERIMENT_IDENTITY).exists())

    def test_cli_requires_explicit_preflight_or_generate_mode(self):
        arguments = ["movie", "m8-3-real-provider-smoke-3"]
        for name, value in self.payload.items():
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            arguments.extend((f"--{name.replace('_', '-')}", str(path)))
        arguments.extend(("--environment", "development", "--correlation-id", "smoke-3-cli"))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertNotEqual(main(arguments), 0)
            self.assertNotEqual(main([*arguments, "--preflight", "--generate"]), 0)
        output = io.StringIO()
        with patch("vss_runtime.RuntimeController", return_value=self.controller()), \
                redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(main([*arguments, "--preflight"]), 0)
        value = json.loads(output.getvalue())["output"]
        self.assertEqual(value["provider_call_count"], 0)
        self.assertFalse(value["readiness"]["attempt_reserved"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.secret_reads, [])


if __name__ == "__main__":
    unittest.main()
