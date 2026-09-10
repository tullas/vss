"""Offline tests for bounded Vertex Veo failure evidence."""

import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from unittest.mock import patch
from pathlib import Path

from vss_providers import ProviderAccess


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "providers/builtin/movie-image-to-video-vertex-veo/implementation.py"
SPEC = importlib.util.spec_from_file_location("m11_vertex_veo_provider", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class VertexDiagnosticTests(unittest.TestCase):
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
        request = type("Request", (), {
            "prompt": "prompt", "image": b"png", "request_sha256": "a" * 64,
            "provider_request_sha256": "a" * 64, "duration_seconds": 8,
            "resolution": "720p", "generate_audio": False, "image_mime_type": "image/png",
        })()
        with patch.dict("os.environ", {"VSS_VERTEX_AI_PROJECT_ID": "p", "VSS_VERTEX_AI_LOCATION": "us-central1"}, clear=False):
            result = provider.generate(request, credential="token", transport=transport)
        self.assertEqual(result.provider_request_id, operation)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].endswith(":predictLongRunning"))
        self.assertTrue(calls[1][0].endswith(":fetchPredictOperation"))
        self.assertEqual(calls[1][1], {"operationName": operation})
        self.assertEqual(calls[0][1]["instances"][0]["image"]["mimeType"], "image/png")
        self.assertEqual(calls[0][1]["parameters"]["durationSeconds"], 8)

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


if __name__ == "__main__":
    unittest.main()
