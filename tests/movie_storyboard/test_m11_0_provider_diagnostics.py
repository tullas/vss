"""Offline tests for bounded Vertex Veo failure evidence."""

import importlib.util
import io
import json
import os
import tempfile
import sys
import unittest
import urllib.error
from unittest.mock import patch
from pathlib import Path

from vss_providers import ProviderAccess, ProviderExecutionFailure


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "providers/builtin/movie-image-to-video-vertex-veo/implementation.py"
SPEC = importlib.util.spec_from_file_location("m11_vertex_veo_provider", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class VertexDiagnosticTests(unittest.TestCase):
    @staticmethod
    def _request():
        return type("Request", (), {
            "prompt": "prompt", "image": b"png", "request_sha256": "a" * 64,
            "provider_request_sha256": "a" * 64, "duration_seconds": 8,
            "resolution": "720p", "generate_audio": False, "image_mime_type": "image/png",
        })()

    def test_environment_token_is_sent_as_one_exact_bearer_header_without_persistence(self):
        token = "ya29.raw.token-with_opaque/chars"
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
        seen_headers = []

        def transport(_url, _body, headers, _timeout, _maximum):
            seen_headers.append(dict(headers))
            if len(seen_headers) == 1:
                return json.dumps({"name": operation}).encode()
            return json.dumps({"done": True, "response": {"videos": [{
                "bytesBase64Encoded": __import__("base64").b64encode(mp4).decode(),
            }]}}).encode()

        provider = MODULE.VertexVeoImageToVideoProvider()
        access = ProviderAccess(
            video=provider, video_secret_reader=os.environ.get,
            video_transport=transport,
        )
        with patch.dict("os.environ", {
            "VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1",
            "VSS_VERTEX_AI_ACCESS_TOKEN": token,
        }, clear=False):
            result = access.get_image_to_video_generator().generate(self._request())
        self.assertEqual(result.provider_request_id, operation)
        self.assertEqual([headers["Authorization"] for headers in seen_headers], [
            "Bearer " + token, "Bearer " + token,
        ])
        self.assertNotIn(token, repr(result))

    def test_wrapped_or_whitespace_token_is_rejected_before_transport(self):
        for token in ('"raw-token"', "'raw-token'", " raw-token", "raw-token ", "raw\ntoken", "Bearer raw-token"):
            transport_calls = []
            provider = MODULE.VertexVeoImageToVideoProvider()

            def transport(*_args):
                transport_calls.append(True)
                self.fail("fake transport must not receive a malformed token")

            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}, clear=False):
                with self.assertRaises(ProviderExecutionFailure):
                    ProviderAccess(
                        video=provider, video_secret_reader=lambda name, value=token: value,
                        video_transport=transport,
                    ).get_image_to_video_generator().generate(self._request())
            self.assertEqual(transport_calls, [])

    def test_submission_is_once_then_fetches_same_operation_without_resubmission(self):
        mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        calls = []

        def transport(url, body, _headers, _timeout, _maximum):
            calls.append((url, json.loads(body)))
            if len(calls) == 1:
                return json.dumps({"name": operation}).encode()
            return json.dumps({"done": True, "response": {"videos": [{
                "bytesBase64Encoded": __import__("base64").b64encode(mp4).decode(),
            }]} }).encode()

        provider = MODULE.VertexVeoImageToVideoProvider()
        request = self._request()
        with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}, clear=False):
            result = provider.generate(request, credential="token", transport=transport)
        self.assertEqual(result.provider_request_id, operation)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].endswith(":predictLongRunning"))
        self.assertTrue(calls[1][0].endswith(":fetchPredictOperation"))
        self.assertEqual(calls[1][1], {"operationName": operation})
        self.assertEqual(calls[0][1]["instances"][0]["image"]["mimeType"], "image/png")
        self.assertEqual(calls[0][1]["parameters"]["durationSeconds"], 8)

    def test_recovery_fetches_persisted_operation_without_submission(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-recover"
        mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = Path(directory) / "operation.json"
            evidence_path.write_text(json.dumps({"operation_name": operation, "request_sha256": "a" * 64,
                                                  "submission_accepted": True}), encoding="utf-8")

            def transport(url, body, _headers, _timeout, _maximum):
                calls.append((url, json.loads(body)))
                return json.dumps({"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": __import__("base64").b64encode(mp4).decode(),
                }]}}).encode()

            request = self._request()
            request.operation_evidence_path = evidence_path
            provider = MODULE.VertexVeoImageToVideoProvider()
            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}, clear=False):
                result = provider.recover(request, operation, credential="token", transport=transport)
            self.assertEqual(result.provider_request_id, operation)
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0][0].endswith(":fetchPredictOperation"))
            self.assertEqual(calls[0][1], {"operationName": operation})
    def test_http_error_preserves_bounded_google_status_code_and_message(self):
        response = io.BytesIO(json.dumps({
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota exceeded for project; Bearer secret-must-not-leak",
            }
        }).encode())
        error = urllib.error.HTTPError(
            "https://us-central1-aiplatform.googleapis.com/endpoint",
            429, "too many requests", {}, response,
        )
        failure = MODULE._http_failure(error)
        self.assertEqual(failure.diagnostic.as_dict(), {
            "http_response_received": True,
            "classification": "http_rate_limit",
            "http_status": 429,
            "error_code": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded for project; Bearer [redacted]",
            "stage": "submission",
            "operation_name": None,
            "poll_count": 0,
            "submission_accepted": False,
        })

    def test_provider_failure_diagnostic_survives_runtime_provider_handle(self):
        def transport(*_args):
            body = io.BytesIO(json.dumps({"error": {
                "code": 400, "status": "INVALID_ARGUMENT",
                "message": "invalid request",
            }}).encode())
            raise urllib.error.HTTPError("https://example.test", 400, "bad request", {}, body)

        provider = MODULE.VertexVeoImageToVideoProvider()
        access = ProviderAccess(video=provider, video_secret_reader=lambda _: "token", video_transport=transport)
        request = type("Request", (), {
            "prompt": "prompt", "image": b"png", "request_sha256": "a" * 64,
            "provider_request_sha256": "a" * 64, "duration_seconds": 8,
            "resolution": "720p", "generate_audio": False, "image_mime_type": "image/png",
        })()
        with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
            access.get_image_to_video_generator().generate(request)
        self.assertEqual(raised.exception.diagnostic.http_status, 400)
        self.assertEqual(raised.exception.diagnostic.error_code, "INVALID_ARGUMENT")

    def test_polling_failure_preserves_operation_and_stage(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        def transport(url, _body, _headers, _timeout, _maximum):
            if url.endswith(":predictLongRunning"):
                return json.dumps({"name": operation}).encode()
            response = io.BytesIO(json.dumps({"error": {"code": 503, "status": "UNAVAILABLE", "message": "poll unavailable"}}).encode())
            raise urllib.error.HTTPError(url, 503, "unavailable", {}, response)
        provider = MODULE.VertexVeoImageToVideoProvider()
        request = type("Request", (), {
            "prompt": "prompt", "image": b"png", "request_sha256": "a" * 64,
            "provider_request_sha256": "a" * 64, "duration_seconds": 8,
            "resolution": "720p", "generate_audio": False, "image_mime_type": "image/png",
        })()
        with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}, clear=False):
            with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                provider.generate(request, credential="token", transport=transport)
        self.assertEqual(raised.exception.diagnostic.as_dict(), {
            "http_response_received": True, "classification": "http_server", "http_status": 503,
            "error_code": "UNAVAILABLE", "message": "poll unavailable", "stage": "polling",
            "operation_name": operation, "poll_count": 1, "submission_accepted": True,
        })

    def test_invalid_terminal_inline_video_preserves_accepted_lro_diagnostics(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"

        def transport(url, _body, _headers, _timeout, _maximum):
            if url.endswith(":predictLongRunning"):
                return json.dumps({"name": operation}).encode()
            return json.dumps({"done": True, "response": {"videos": [
                {"bytesBase64Encoded": "not-base64"},
            ]}}).encode()

        provider = MODULE.VertexVeoImageToVideoProvider()
        request = self._request()
        with patch.dict("os.environ", {
            "VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1",
        }, clear=False):
            with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                provider.generate(request, credential="token", transport=transport)
        self.assertEqual(raised.exception.diagnostic.as_dict(), {
            "http_response_received": True, "classification": "output_invalid",
            "http_status": None, "error_code": None, "message": None,
            "stage": "result_retrieval", "operation_name": operation,
            "poll_count": 1, "submission_accepted": True,
            "validation_check": "base64_decode",
            "underlying_exception": {"type": "Error", "message": "Only base64 data is allowed"},
        })

    def test_mp4_accepts_variable_ftyp_size_and_leading_box(self):
        self.assertEqual(MODULE._mp4_check(b"\x00\x00\x00\x08free" + b"\x00\x00\x00\x10ftypisom\x00\x00\x00\x00"),
                         (True, "valid_iso_bmff_ftyp"))

    def test_mp4_accepts_compatible_brands(self):
        self.assertEqual(MODULE._mp4_check(b"\x00\x00\x00\x18ftypxxxx\x00\x00\x00\x00av01iso6"),
                         (True, "valid_iso_bmff_ftyp"))

    def test_result_metadata_is_bounded_and_records_successful_inline_media(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        media = b"\x00\x00\x00\x10ftypisom\x00\x00\x00\x00"
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "operation.json"
            def transport(url, *_args):
                if url.endswith(":predictLongRunning"):
                    return (200, json.dumps({"name": operation, "ignored": "bounded"}).encode())
                return (200, json.dumps({"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": __import__("base64").b64encode(media).decode(), "mimeType": "video/mp4",
                }]}}).encode())
            request = self._request(); request.operation_evidence_path = evidence
            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}):
                result = MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
            saved = json.loads(evidence.read_text())
            self.assertEqual(result.media.content, media)
            self.assertEqual(saved["submission_http_status"], 200)
            self.assertEqual([poll["http_status"] for poll in saved["polls"]], [200])
            representation = saved["terminal_response"]["video_representation"]
            self.assertEqual(representation["field_path"], "response.videos[0].bytesBase64Encoded")
            self.assertEqual(representation["kind"], "inline_base64")
            self.assertEqual(representation["decoded_length"], len(media))
            self.assertEqual(representation["magic_hex"], media.hex())

    def test_empty_payload_is_rejected_and_recorded(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "operation.json"
            def transport(url, *_args):
                if url.endswith(":predictLongRunning"):
                    return (200, json.dumps({"name": operation}).encode())
                return (200, json.dumps({"done": True, "response": {"videos": [{"bytesBase64Encoded": ""}]}}).encode())
            request = self._request(); request.operation_evidence_path = evidence
            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}):
                with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                    MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
            self.assertEqual(raised.exception.diagnostic.validation_check, "empty_payload")
            self.assertEqual(json.loads(evidence.read_text())["result_admission"]["validation_check"], "empty_payload")

    def test_oversized_payload_is_rejected_before_decode(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        class OversizedText(str):
            def __len__(self):
                return ((256 * 1024 * 1024 + 2) // 3) * 4 + 1
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "operation.json"
            def transport(url, *_args):
                if url.endswith(":predictLongRunning"):
                    return (200, json.dumps({"name": operation}).encode())
                return (200, b"{}")
            request = self._request(); request.operation_evidence_path = evidence
            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}):
                terminal = {"done": True, "response": {"videos": [{"bytesBase64Encoded": OversizedText("x")} ]}}
                with patch.object(MODULE, "_parse_json", side_effect=[{"name": operation}, terminal]):
                    with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                        MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
            self.assertEqual(raised.exception.diagnostic.validation_check, "encoded_payload_size")

    def test_unexpected_terminal_shape_is_recorded_before_admission_failure(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "operation.json"
            def transport(url, *_args):
                if url.endswith(":predictLongRunning"):
                    return (200, json.dumps({"name": operation}).encode())
                return (200, json.dumps({"done": True, "response": {"unexpected": []}}).encode())
            request = self._request(); request.operation_evidence_path = evidence
            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}):
                with self.assertRaises(MODULE.VertexVeoProviderFailure):
                    MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
            saved = json.loads(evidence.read_text())
            self.assertEqual(saved["terminal_response"]["video_representation"]["kind"], "other")
            self.assertEqual(saved["result_admission"]["validation_check"], "inline_base64_field_missing")

    def test_uri_representation_is_diagnosed_without_retrieval(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "operation.json"
            def transport(url, *_args):
                if url.endswith(":predictLongRunning"):
                    return (201, json.dumps({"name": operation}).encode())
                return (200, json.dumps({"done": True, "response": {"videos": [{"gcsUri": "gs://bucket/path/video.mp4", "mimeType": "video/mp4"}]}}).encode())
            request = self._request(); request.operation_evidence_path = evidence
            with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}):
                with self.assertRaises(MODULE.VertexVeoProviderFailure):
                    MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
            saved = json.loads(evidence.read_text())
            self.assertEqual(saved["terminal_response"]["video_representation"]["kind"], "uri")
            self.assertEqual(saved["result_admission"]["validation_check"], "uri_representation_not_admitted")

    def test_persistence_failure_is_fail_closed(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        request = self._request(); request.operation_evidence_path = Path("/proc/1/operation.json")
        def transport(url, *_args):
            if url.endswith(":predictLongRunning"):
                return (200, json.dumps({"name": operation}).encode())
            self.fail("polling must not begin after persistence failure")
        with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}):
            with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
        self.assertEqual(raised.exception.diagnostic.classification, "operation_persistence_failed")

    def test_terminal_provider_error_preserves_accepted_lro_diagnostics(self):
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"

        def transport(url, _body, _headers, _timeout, _maximum):
            if url.endswith(":predictLongRunning"):
                return json.dumps({"name": operation}).encode()
            return json.dumps({"done": True, "error": {
                "code": 400, "status": "INVALID_ARGUMENT", "message": "provider rejected request",
            }}).encode()

        provider = MODULE.VertexVeoImageToVideoProvider()
        with patch.dict("os.environ", {
            "VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1",
        }, clear=False):
            with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                provider.generate(self._request(), credential="token", transport=transport)
        self.assertEqual(raised.exception.diagnostic.as_dict(), {
            "http_response_received": True, "classification": "operation_failed",
            "http_status": None, "error_code": "INVALID_ARGUMENT",
            "message": "provider rejected request", "stage": "polling",
            "operation_name": operation, "poll_count": 1, "submission_accepted": True,
        })

    def test_accepted_operation_is_persisted_before_polling(self):
        from pathlib import Path
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "operation.json"
            calls = []

            def transport(url, _body, _headers, _timeout, _maximum):
                calls.append((url, evidence.exists()))
                if url.endswith(":predictLongRunning"):
                    return json.dumps({"name": operation}).encode()
                return json.dumps({"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": __import__("base64").b64encode(
                        b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2").decode(),
                }]}}).encode()

            request = self._request()
            request.operation_evidence_path = evidence
            with patch.dict("os.environ", {
                "VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1",
            }, clear=False):
                MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
            self.assertEqual(calls, [(calls[0][0], False), (calls[1][0], True)])
            self.assertEqual(json.loads(evidence.read_text())["operation_name"], operation)

    def test_operation_persistence_failure_preserves_accepted_lro_diagnostics(self):
        from pathlib import Path
        operation = "projects/p/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/op-1"

        def transport(url, _body, _headers, _timeout, _maximum):
            if url.endswith(":predictLongRunning"):
                return json.dumps({"name": operation}).encode()
            self.fail("polling must not begin when operation evidence persistence fails")

        request = self._request()
        request.operation_evidence_path = Path("/proc/1/m11-operation.json")
        with patch.dict("os.environ", {
            "VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1",
        }, clear=False):
            with self.assertRaises(MODULE.VertexVeoProviderFailure) as raised:
                MODULE.VertexVeoImageToVideoProvider().generate(request, credential="token", transport=transport)
        self.assertEqual(raised.exception.diagnostic.as_dict(), {
            "http_response_received": True, "classification": "operation_persistence_failed",
            "http_status": None, "error_code": None, "message": None,
            "stage": "submission", "operation_name": operation,
            "poll_count": 0, "submission_accepted": True,
        })


if __name__ == "__main__":
    unittest.main()
