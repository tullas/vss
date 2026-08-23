from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import socket
import ssl
import shutil
import struct
import tempfile
import unittest
import urllib.error
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.movie_storyboard.test_m8_0 import bundle, execute as execute_storyboard, reseal_storyboard
from vss_commands import CommandRunner, ExitCode
from vss_capabilities import SDKValidationError
from vss_commands.cli import main
from vss_movie_creative_smoke import (
    ENDPOINT,
    EXPERIMENT_FRAME_ID,
    MAX_RESPONSE_BYTES,
    MODEL_IDENTITY,
    OpenAIImageSmokeAccess,
    SECRET_NAME,
    SmokeHTTPResponse,
    SmokeProviderFailure,
    admit_creative_smoke,
)
from vss_movie_creative_smoke.png import MAX_CABX_BYTES, validate_openai_png
from vss_movie_creative_smoke.provider import _https_post
from vss_runtime import RuntimeController
from vss_runtime.audit import AuditLogger
from vss_runtime.errors import RuntimeInternalFailure
from vss_runtime.external_preflight import ExternalExecutionPreflight
from vss_runtime.policy import RuntimePolicy
from vss_reasoning_contracts.canonicalization import thaw_json
from vss_providers import ProviderAccessDenied

ROOT = Path(__file__).resolve().parents[2]
SECRET = "test-only-not-a-real-key"  # pragma: allowlist secret


def _chunk(kind: bytes, content: bytes) -> bytes:
    return (struct.pack(">I", len(content)) + kind + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF))


def _png(*, cabx: bytes | None = b"opaque-content-credentials") -> bytes:
    header = struct.pack(">IIBBBBB", 1280, 720, 8, 2, 0, 0, 0)
    pixels = (b"\0" + b"\0" * (1280 * 3)) * 720
    chunks = [_chunk(b"IHDR", header)]
    if cabx is not None:
        chunks.append(_chunk(b"caBX", cabx))
    chunks.extend((_chunk(b"IDAT", zlib.compress(pixels)), _chunk(b"IEND", b"")))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _response(content: bytes) -> SmokeHTTPResponse:
    value = {
        "created": 1,
        "data": [{"b64_json": base64.b64encode(content).decode("ascii"),
                  "revised_prompt": "documented but ignored", "url": None}],
        "usage": {"input_tokens": 325, "output_tokens": 1200, "total_tokens": 1525},
        "background": "opaque", "output_format": "png", "quality": "medium", "size": "1280x720",
    }
    return SmokeHTTPResponse(json.dumps(value).encode(), 200, "req_safe_1")


class PublicationOrderAudit(AuditLogger):
    def __init__(self, root: Path, repository: Path) -> None:
        super().__init__(root, trusted_root=repository)
        self.repository = repository
        self.checked = False

    def append(self, record):
        self.checked = True
        image_root = self.repository / ".local/movie/storyboard-images"
        self.assert_no_png = not image_root.exists() or not list(image_root.rglob("*.png"))
        super().append(record)


class FailingAudit(AuditLogger):
    def append(self, record):
        raise RuntimeInternalFailure("audit failed")


class M83RealProviderSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        self.values = bundle(knowledge=True)
        self.storyboard = execute_storyboard(self.values)["scene_storyboard_specification"]
        self.payload = dict(zip(
            ("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), self.values,
        ))
        self.payload["storyboard"] = self.storyboard
        self.calls: list[tuple] = []
        self.secret_reads: list[str] = []

    def tearDown(self):
        self.temporary.cleanup()

    def transport(self, url, body, headers, timeout, maximum):
        self.calls.append((url, body, dict(headers), timeout, maximum))
        return _response(_png())

    def secret_reader(self, name):
        self.secret_reads.append(name)
        return SECRET

    def controller(self, **kwargs):
        return RuntimeController(
            root=self.root,
            creative_smoke_transport=kwargs.pop("transport", self.transport),
            creative_smoke_secret_reader=kwargs.pop("secret_reader", self.secret_reader),
            external_execution_preflight=kwargs.pop(
                "external_execution_preflight",
                ExternalExecutionPreflight(
                    environment_contains=lambda name: name == SECRET_NAME,
                    resolver=lambda hostname, port: [(hostname, port)],
                ),
            ),
            **kwargs,
        )

    def generate(self, *, dry_run=False, controller=None, payload=None):
        return CommandRunner(runtime_controller=controller or self.controller()).run(
            "movie.m8-3-real-provider-smoke-2", "development", payload or self.payload,
            "m83-smoke-test", dry_run=dry_run,
        )

    def test_exact_m8_3_projection_and_fixed_provider_configuration(self):
        admitted = admit_creative_smoke(*self.values, self.storyboard, environment="development")
        self.assertEqual(admitted.frame_id, EXPERIMENT_FRAME_ID)
        self.assertEqual(admitted.depiction_projection_digest,
                         "3aa69cfccff612188bfd8d5820be1e691891d583074aff1e5205be986ed4c554")  # pragma: allowlist secret
        serialized = json.dumps(thaw_json(admitted.projection)).casefold()
        for value in ("mira", "courtyard", "dawn", "lantern", "locked gate"):
            self.assertIn(value, serialized)
        self.assertIn("significance of the lantern is not established", serialized)
        for control in ("review status", "human determination", "bounded_minimal_stage", "tbd"):
            self.assertNotIn(control, admitted.prompt.casefold())
        response, code = self.generate()
        self.assertEqual(code, 0, response)
        self.assertEqual(len(self.calls), 1)
        url, body, headers, _, maximum = self.calls[0]
        self.assertEqual(url, ENDPOINT)
        self.assertEqual(maximum, MAX_RESPONSE_BYTES)
        request = json.loads(body)
        self.assertEqual(request, {"model": MODEL_IDENTITY, "n": 1, "output_format": "png",
                                  "prompt": admitted.prompt, "quality": "medium", "size": "1280x720"})
        self.assertEqual(headers["Authorization"], "Bearer " + SECRET)

    def test_success_preserves_bytes_audits_before_publication_and_creates_review_gate(self):
        audit = PublicationOrderAudit(self.root / ".local/runtime/audit", self.root)
        response, code = self.generate(controller=self.controller(audit_logger=audit))
        self.assertEqual(code, 0, response)
        self.assertTrue(audit.checked and audit.assert_no_png)
        output = response["output"]
        image = self.root / output["artifact_path"]
        content = image.read_bytes()
        self.assertEqual(content, _png())
        self.assertEqual(output["content_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual((output["width"], output["height"]), (1280, 720))
        self.assertTrue(output["png"]["content_credentials_present"])
        self.assertEqual(output["png"]["content_credentials_chunk_bytes"], 26)
        reviewer = json.loads((self.root / output["review_path"]).read_text())
        self.assertIsNone(reviewer["disposition"])
        self.assertEqual(reviewer["allowed_dispositions"], ["USE", "REGENERATE", "REJECT"])
        self.assertFalse(reviewer["regenerate_authorizes_another_call"])
        self.assertTrue(all(value is False for value in output["authority_boundary"].values()))

    def test_dry_run_is_zero_call_zero_secret_and_zero_state(self):
        class ForbiddenPreflight:
            def run(self, spec):
                raise AssertionError("dry-run entered external preflight")

        response, code = self.generate(
            dry_run=True,
            controller=self.controller(external_execution_preflight=ForbiddenPreflight()),
        )
        self.assertEqual(code, 0, response)
        self.assertEqual(response["output"]["provider_call_count"], 0)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.secret_reads, [])
        self.assertFalse((self.root / ".local/movie/m8-3-real-provider-smoke-2").exists())

    def test_preflight_failures_use_no_secret_call_or_attempt(self):
        cases = {
            "credential_unavailable": ExternalExecutionPreflight(
                environment_contains=lambda _: False,
                resolver=lambda *_: self.fail("DNS must not run without a credential"),
            ),
            "proxy_environment_unsupported": ExternalExecutionPreflight(
                environment_contains=lambda name: name == "HTTPS_PROXY",
                resolver=lambda *_: self.fail("DNS must not run with an unsupported proxy"),
            ),
            "dns": ExternalExecutionPreflight(
                environment_contains=lambda name: name == SECRET_NAME,
                resolver=lambda *_: (_ for _ in ()).throw(socket.gaierror()),
            ),
        }
        state = self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json"
        for expected, preflight in cases.items():
            with self.subTest(expected=expected):
                response, code = self.generate(controller=self.controller(
                    external_execution_preflight=preflight,
                ))
                self.assertNotEqual(code, 0, response)
                self.assertFalse(state.exists())
                self.assertEqual(self.secret_reads, [])
                self.assertEqual(self.calls, [])
                audit = (self.root / ".local/runtime/audit/executions.jsonl").read_text()
                self.assertIn(f'"classification":"{expected}"', audit)

    def test_preflight_precedes_reservation_and_credentialed_transport(self):
        events = []
        state = self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json"
        from vss_movie_creative_smoke import SmokeExperimentArtifactPublisher
        reserve = SmokeExperimentArtifactPublisher.reserve

        def present(name):
            if name == SECRET_NAME:
                events.append("credential_presence")
                return True
            return False

        def resolve(hostname, port):
            self.assertFalse(state.exists())
            events.append("dns")
            return [(hostname, port)]

        def read_secret(name):
            self.assertEqual(name, SECRET_NAME)
            self.assertEqual(json.loads(state.read_text())["status"], "attempted")
            events.append("credential_read")
            return SECRET

        def transport(*args):
            self.assertTrue(state.exists())
            events.append("transport")
            return _response(_png())

        def record_reservation(publisher, admitted, attempt_id):
            self.assertFalse(state.exists())
            events.append("reserve")
            reserve(publisher, admitted, attempt_id)

        with patch.object(SmokeExperimentArtifactPublisher, "reserve", record_reservation):
            response, code = self.generate(controller=self.controller(
                secret_reader=read_secret,
                transport=transport,
                external_execution_preflight=ExternalExecutionPreflight(
                    environment_contains=present,
                    resolver=resolve,
                ),
            ))
        self.assertEqual(code, 0, response)
        self.assertEqual(events, ["credential_presence", "dns", "reserve", "credential_read", "transport"])

    def test_sdk_input_validation_failure_does_not_reserve_attempt(self):
        state = self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json"
        with patch("vss_runtime.controller.validate_input",
                   side_effect=SDKValidationError("fixed SDK validation failure")):
            response, code = self.generate()
        self.assertNotEqual(code, 0, response)
        self.assertFalse(state.exists())
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])

    def test_handler_load_failure_does_not_reserve_attempt(self):
        state = self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json"
        controller = self.controller()
        with patch.object(controller.loader, "load",
                          side_effect=RuntimeInternalFailure("fixed handler load failure")):
            response, code = self.generate(controller=controller)
        self.assertNotEqual(code, 0, response)
        self.assertFalse(state.exists())
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])

    def test_credential_failure_consumes_attempt_without_transport(self):
        state = self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json"
        response, code = self.generate(controller=self.controller(secret_reader=lambda _: None))
        self.assertNotEqual(code, 0, response)
        self.assertEqual(json.loads(state.read_text())["status"], "failed")
        self.assertEqual(self.calls, [])

    def test_nonempty_state_root_fails_before_reservation(self):
        state_root = self.root / ".local/movie/m8-3-real-provider-smoke-2"
        state_root.mkdir(parents=True)
        (state_root / "stale-evidence.json").write_text("{}", encoding="utf-8")
        response, code = self.generate()
        self.assertNotEqual(code, 0, response)
        self.assertFalse((state_root / "attempt.json").exists())
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])

    def test_attempt_is_create_once_after_success_and_failure(self):
        first, code = self.generate()
        self.assertEqual(code, 0, first)
        second, second_code = self.generate()
        self.assertNotEqual(second_code, 0, second)
        self.assertEqual(len(self.calls), 1)
        state = json.loads((self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json").read_text())
        self.assertEqual(state["status"], "succeeded")

        with tempfile.TemporaryDirectory() as directory:
            failed_root = Path(directory)
            for name in ("capabilities", "providers", "schemas"):
                shutil.copytree(ROOT / name, failed_root / name)
            failures = []
            def fail(*args):
                failures.append(args)
                raise SmokeProviderFailure("fixed safe failure")
            failed = RuntimeController(root=failed_root, creative_smoke_transport=fail,
                                       creative_smoke_secret_reader=lambda _: SECRET,
                                       external_execution_preflight=ExternalExecutionPreflight(
                                           environment_contains=lambda name: name == SECRET_NAME,
                                           resolver=lambda hostname, port: [(hostname, port)],
                                       ))
            response, code = CommandRunner(runtime_controller=failed).run(
                "movie.m8-3-real-provider-smoke-2", "development", self.payload, "failure")
            self.assertNotEqual(code, 0, response)
            again, again_code = CommandRunner(runtime_controller=failed).run(
                "movie.m8-3-real-provider-smoke-2", "development", self.payload, "again")
            self.assertNotEqual(again_code, 0, again)
            self.assertEqual(len(failures), 1)
            state = json.loads((failed_root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json").read_text())
            self.assertEqual(state["status"], "failed")

    def test_redirects_are_denied_without_second_origin_or_location_persistence(self):
        for status in (301, 302, 303, 307, 308):
            seen = []
            def reject(request, timeout):
                seen.append((request.full_url, request.get_header("Authorization")))
                headers = {"Location": "https://attacker.invalid/credential-target", "x-request-id": "req_safe"}
                raise urllib.error.HTTPError(request.full_url, status, "redirect", headers, io.BytesIO(b""))
            with self.subTest(status=status), patch(
                    "vss_movie_creative_smoke.provider._urlopen_no_redirect", side_effect=reject):
                with self.assertRaises(SmokeProviderFailure) as raised:
                    _https_post(ENDPOINT, b"{}", {"Authorization": "Bearer " + SECRET}, 1, 100)
            self.assertEqual(seen, [(ENDPOINT, "Bearer " + SECRET)])
            diagnostic = raised.exception.diagnostic.as_dict()
            self.assertEqual(diagnostic["classification"], "http_redirect")
            self.assertNotIn("attacker", json.dumps(diagnostic))
            self.assertNotIn(SECRET, json.dumps(diagnostic))

    def test_post_http_failures_are_closed_bounded_and_content_free(self):
        admitted = admit_creative_smoke(*self.values, self.storyboard, environment="development")
        request = __import__("vss_movie_creative_smoke", fromlist=["SmokeProviderRequest"]).SmokeProviderRequest(
            admitted.prompt, admitted.provider_request_digest, admitted.depiction_projection_digest)
        cases = {
            "response_json_invalid": SmokeHTTPResponse(b"not-json", 200, None),
            "image_payload_missing": SmokeHTTPResponse(json.dumps({"data": [{}]}).encode(), 200, None),
            "base64_invalid": SmokeHTTPResponse(json.dumps({"data": [{"b64_json": "!prompt-secret!"}]}).encode(), 200, None),
        }
        for expected, response in cases.items():
            access = OpenAIImageSmokeAccess(transport=lambda *args, value=response: value,
                                            secret_reader=lambda _: SECRET)
            access.prepare(request)
            with self.subTest(expected=expected), self.assertRaises(SmokeProviderFailure) as raised:
                access.generate(request)
            diagnostic = raised.exception.diagnostic.as_dict()
            self.assertEqual(diagnostic["classification"], expected)
            evidence = json.dumps(diagnostic)
            self.assertNotIn("prompt-secret", evidence)
            self.assertLess(len(evidence), 1500)

    def test_http_and_transport_failures_have_closed_sanitized_diagnostics(self):
        http_cases = {
            400: "http_bad_request", 401: "http_authentication", 403: "http_access",
            429: "http_rate_limit", 500: "http_server",
        }
        for status, expected in http_cases.items():
            body = json.dumps({"error": {"message": SECRET, "type": "authentication_error",
                                         "param": None, "code": "invalid_api_key"}}).encode()
            def reject(request, timeout, *, code=status, content=body):
                raise urllib.error.HTTPError(request.full_url, code, "unsafe", {"x-request-id": "req_safe"},
                                             io.BytesIO(content))
            with self.subTest(status=status), patch(
                    "vss_movie_creative_smoke.provider._urlopen_no_redirect", side_effect=reject):
                with self.assertRaises(SmokeProviderFailure) as raised:
                    _https_post(ENDPOINT, b"{}", {"Authorization": "Bearer " + SECRET}, 1, 100)
            diagnostic = raised.exception.diagnostic.as_dict()
            self.assertEqual(diagnostic["classification"], expected)
            self.assertEqual(diagnostic["http_status"], status)
            self.assertNotIn(SECRET, json.dumps(diagnostic))

        transport_cases = (
            (urllib.error.URLError(socket.gaierror()), "dns"),
            (urllib.error.URLError(ConnectionRefusedError()), "connect"),
            (urllib.error.URLError(ssl.SSLError()), "tls"),
            (urllib.error.URLError(TimeoutError()), "timeout"),
        )
        for failure, expected in transport_cases:
            with self.subTest(expected=expected), patch(
                    "vss_movie_creative_smoke.provider._urlopen_no_redirect", side_effect=failure):
                with self.assertRaises(SmokeProviderFailure) as raised:
                    _https_post(ENDPOINT, b"{}", {"Authorization": "Bearer " + SECRET}, 1, 100)
            self.assertEqual(raised.exception.diagnostic.classification, expected)

    def test_response_bound_is_derived_and_fails_one_byte_over(self):
        from vss_movie_creative_smoke.provider import (
            BASE64_RESPONSE_BYTES, MAX_DECODED_MEDIA_BYTES, RESPONSE_ENVELOPE_OVERHEAD_BYTES,
        )
        self.assertEqual(BASE64_RESPONSE_BYTES, ((MAX_DECODED_MEDIA_BYTES + 2) // 3) * 4)
        self.assertEqual(MAX_RESPONSE_BYTES, BASE64_RESPONSE_BYTES + RESPONSE_ENVELOPE_OVERHEAD_BYTES)

        class BoundedResponse:
            status = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, amount): return b"x" * amount

        with patch("vss_movie_creative_smoke.provider._urlopen_no_redirect", return_value=BoundedResponse()):
            with self.assertRaises(SmokeProviderFailure) as raised:
                _https_post(ENDPOINT, b"{}", {}, 1, 100)
        diagnostic = raised.exception.diagnostic.as_dict()
        self.assertEqual(diagnostic["classification"], "response_too_large")
        self.assertEqual(diagnostic["encoded_response_bytes"], 101)

    def test_png_profile_is_experiment_local_strict_and_cabx_opaque(self):
        content = _png(cabx=b"CREDENTIAL-PAYLOAD-MUST-NOT-SURFACE")
        summary = validate_openai_png(content)
        self.assertTrue(summary.content_credentials_present)
        self.assertNotIn("PAYLOAD", json.dumps(summary.as_dict()))
        for bad in (
            _png(cabx=b""),
            _png(cabx=b"x" * (MAX_CABX_BYTES + 1)),
            _png(cabx=None)[:-12] + _chunk(b"tEXt", b"hidden") + _chunk(b"IEND", b""),
        ):
            with self.assertRaises(Exception):
                validate_openai_png(bad)

    def test_caller_cannot_change_frame_provider_model_or_reseal_substitution(self):
        for key, value in (("frame_id", EXPERIMENT_FRAME_ID), ("model", "other"),
                           ("provider", "other"), ("retry", True)):
            response, code = self.generate(payload={**self.payload, key: value})
            self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)
        forged = copy.deepcopy(self.storyboard)
        forged["payload"]["ordered_frames"][2]["action"] = "Invent an unrelated event."
        reseal_storyboard(forged)
        response, code = self.generate(payload={**self.payload, "storyboard": forged})
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)

        admitted = admit_creative_smoke(*self.values, self.storyboard, environment="development")
        request_type = __import__("vss_movie_creative_smoke", fromlist=["SmokeProviderRequest"]).SmokeProviderRequest
        access = OpenAIImageSmokeAccess(secret_reader=lambda name: self.secret_reads.append(name))
        with self.assertRaises(ProviderAccessDenied):
            access.prepare(request_type(
                admitted.prompt,
                admitted.provider_request_digest,
                "0" * 64,
            ))
        self.assertEqual(self.secret_reads, [])

    def test_credential_and_provider_content_never_enter_persisted_evidence(self):
        response, code = self.generate()
        self.assertEqual(code, 0, response)
        all_text = json.dumps(response)
        for path in (self.root / ".local").rglob("*"):
            if path.is_file() and path.suffix != ".png":
                all_text += path.read_text(errors="replace")
        self.assertNotIn(SECRET, all_text)
        self.assertNotIn("Authorization", all_text)
        self.assertNotIn("documented but ignored", all_text)
        self.assertNotIn("b64_json", all_text)
        self.assertNotIn("Create one clean cinematic image", all_text)

    def test_failure_diagnostic_is_audited_and_audit_failure_never_publishes(self):
        unsafe = SECRET.encode() + b" unrestricted response"
        response, code = self.generate(controller=self.controller(
            transport=lambda *args: SmokeHTTPResponse(unsafe, 200, "req_safe")))
        self.assertNotEqual(code, 0, response)
        audit = (self.root / ".local/runtime/audit/executions.jsonl").read_text()
        self.assertIn('"classification":"response_json_invalid"', audit)
        self.assertNotIn(SECRET, audit)
        self.assertNotIn("unrestricted response", audit)
        self.assertEqual(json.loads(
            (self.root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json").read_text())["status"],
            "failed",
        )

        with tempfile.TemporaryDirectory() as directory:
            failed_root = Path(directory)
            for name in ("capabilities", "providers", "schemas"):
                shutil.copytree(ROOT / name, failed_root / name)
            failing_audit = FailingAudit(failed_root / ".local/runtime/audit", trusted_root=failed_root)
            controller = RuntimeController(
                root=failed_root, audit_logger=failing_audit,
                creative_smoke_transport=lambda *args: _response(_png()),
                creative_smoke_secret_reader=lambda _: SECRET,
                external_execution_preflight=ExternalExecutionPreflight(
                    environment_contains=lambda name: name == SECRET_NAME,
                    resolver=lambda hostname, port: [(hostname, port)],
                ),
            )
            result, result_code = CommandRunner(runtime_controller=controller).run(
                "movie.m8-3-real-provider-smoke-2", "development", self.payload, "audit-failure")
            self.assertEqual(result_code, int(ExitCode.INTERNAL_ERROR), result)
            image_root = failed_root / ".local/movie/storyboard-images"
            self.assertFalse(image_root.exists() and list(image_root.rglob("*.png")))
            state = json.loads((failed_root / ".local/movie/m8-3-real-provider-smoke-2/attempt.json").read_text())
            self.assertEqual(state["status"], "failed")

    def test_runtime_denial_reads_no_secret_and_makes_no_call(self):
        class ForbiddenPreflight:
            def run(self, spec):
                raise AssertionError("denied execution entered external preflight")

        policy = RuntimePolicy(allowed_capability_permissions={
            "movie.m8-3-real-provider-smoke-2": ("filesystem_write", "network"),
        })
        response, code = self.generate(controller=self.controller(
            policy=policy,
            external_execution_preflight=ForbiddenPreflight(),
        ))
        self.assertEqual(code, int(ExitCode.PERMISSION_DENIED), response)
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".local/movie/m8-3-real-provider-smoke-2").exists())

    def test_manifest_cannot_underdeclare_external_execution_permissions(self):
        manifest = self.root / "capabilities/movie-m8-3-real-provider-smoke-2/manifest.yaml"
        content = manifest.read_text(encoding="utf-8")
        self.assertIn("  - network\n", content)
        manifest.write_text(content.replace("  - network\n", "", 1), encoding="utf-8")

        class ForbiddenPreflight:
            def run(self, spec):
                raise AssertionError("underdeclared permissions entered external preflight")

        response, code = self.generate(controller=self.controller(
            external_execution_preflight=ForbiddenPreflight(),
        ))
        self.assertEqual(code, int(ExitCode.PERMISSION_DENIED), response)
        self.assertEqual(self.secret_reads, [])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".local/movie/m8-3-real-provider-smoke-2").exists())

    def test_explicit_cli_has_no_frame_provider_model_or_retry_controls(self):
        paths = {}
        for name, value in self.payload.items():
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = path
        arguments = ["movie", "m8-3-real-provider-smoke-2"]
        for name, path in paths.items():
            arguments.extend((f"--{name.replace('_', '-')}", str(path)))
        arguments.extend(("--environment", "development", "--correlation-id", "smoke-cli", "--dry-run"))
        output = io.StringIO()
        with patch("vss_runtime.RuntimeController", return_value=self.controller()), \
                patch("socket.socket.connect") as connect, redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(main(arguments), 0)
        connect.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["output"]["provider_call_count"], 0)
        parser_output = io.StringIO()
        with redirect_stdout(parser_output), redirect_stderr(io.StringIO()):
            self.assertNotEqual(main([*arguments, "--model", "attacker"]), 0)
            self.assertNotEqual(main([*arguments, "--timeout", "1"]), 0)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
