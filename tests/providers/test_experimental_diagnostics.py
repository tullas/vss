from __future__ import annotations

import io
import base64
import json
import socket
import ssl
import struct
import unittest
import urllib.error
import zlib
from email.message import Message
from unittest.mock import patch

from vss_providers import ExperimentalProviderDiagnostic, ProviderExecutionFailure
from vss_providers.experimental import (BASE64_RESPONSE_BYTES, MAX_ERROR_RESPONSE_BYTES, MAX_RESPONSE_BYTES,
    RESPONSE_ENVELOPE_OVERHEAD_BYTES, ExperimentalOpenAIExecutionAccess, _DenyRedirects, _https_post)
from vss_providers.experimental_png import (MAX_BYTES, MAX_CABX_BYTES, inspect_experimental_png,
    validate_experimental_openai_png)
from vss_providers.png import validate_pictorial_png


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)


def diagnostic_png(kind: bytes, payload: bytes) -> bytes:
    header = struct.pack(">IIBBBBB", 1536, 1024, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(kind, payload) + png_chunk(b"IDAT", b"") + png_chunk(b"IEND", b"")


def provider_png(*middle: tuple[bytes, bytes]) -> bytes:
    header = struct.pack(">IIBBBBB", 1536, 1024, 8, 2, 0, 0, 0)
    raw = (b"\x00" + b"\x80\x70\x60" * 1536) * 1024
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
            + b"".join(png_chunk(kind, payload) for kind, payload in middle)
            + png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b""))


class ExperimentalProviderDiagnosticTests(unittest.TestCase):
    def test_diagnostic_type_rejects_arbitrary_provider_material(self):
        with self.assertRaises(ValueError):
            ExperimentalProviderDiagnostic(True, "https://attacker.invalid", 400,
                "credential-value", "prompt-text", "unrestricted provider response", "bad request id")

    def invoke_http(self, status: int, body: bytes, request_id: str = "req_safe123"):
        headers = Message(); headers["x-request-id"] = request_id
        error = urllib.error.HTTPError("https://api.openai.com/v1/images/generations", status,
                                      "provider text must not persist", headers, io.BytesIO(body))
        with patch("vss_providers.experimental._urlopen_no_redirect", side_effect=error), self.assertRaises(ProviderExecutionFailure) as caught:
            _https_post("https://api.openai.com/v1/images/generations", b"{}",
                        {"Authorization": "Bearer test-secret"}, 1.0, 100)
        return caught.exception.diagnostic

    def test_http_statuses_have_closed_classification(self):
        body = json.dumps({"error": {"message": "arbitrary", "type": "invalid_request_error",
                                     "param": None, "code": "model_not_found"}}).encode()
        expected = {400: "http_bad_request", 401: "http_authentication", 403: "http_access",
                    429: "http_rate_limit", 500: "http_server", 503: "http_server"}
        for status, classification in expected.items():
            with self.subTest(status=status):
                diagnostic = self.invoke_http(status, body)
                self.assertTrue(diagnostic.http_response_received)
                self.assertEqual(diagnostic.http_status, status)
                self.assertEqual(diagnostic.classification, classification)

    def test_redirects_are_never_followed_or_persisted(self):
        target = "https://redirected.invalid/credential-capture?secret=location-value"
        original = urllib.request.Request("https://api.openai.com/v1/images/generations", b"prompt",
            {"Authorization": "Bearer credential-value"}, method="POST")
        handler = _DenyRedirects()
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status), patch("urllib.request.Request") as redirected_request:
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    handler.redirect_request(original, None, status, "redirect-provider-text", Message(), target)
                self.assertEqual((denied.exception.code, denied.exception.filename), (status, original.full_url))
                self.assertNotIn(target, str(denied.exception))
                redirected_request.assert_not_called()
            headers = Message(); headers["Location"] = target; headers["x-request-id"] = "req_redirect123"
            error = urllib.error.HTTPError(original.full_url, status, "redirect-provider-text", headers, io.BytesIO(b"redirect-body-secret"))
            with patch("vss_providers.experimental._urlopen_no_redirect", side_effect=error), self.assertRaises(ProviderExecutionFailure) as caught:
                _https_post(original.full_url, b"prompt", {"Authorization": "Bearer credential-value"}, 1.0, 100)
            diagnostic = caught.exception.diagnostic
            self.assertEqual((diagnostic.http_response_received, diagnostic.http_status,
                              diagnostic.classification), (True, status, "http_redirect"))
            persisted = json.dumps(diagnostic.as_dict()) + str(caught.exception)
            for forbidden in (target, "redirected.invalid", "location-value", "credential-value",
                              "Authorization", "redirect-body-secret", "redirect-provider-text"):
                self.assertNotIn(forbidden, persisted)

    def test_documented_error_fields_and_request_id_are_bounded(self):
        diagnostic = self.invoke_http(400, json.dumps({"error": {"message": "unsafe detail",
            "type": "invalid_request_error", "code": "model_not_found"}}).encode())
        self.assertEqual(diagnostic.error_type, "invalid_request_error")
        self.assertEqual(diagnostic.error_code, "model_not_found")
        self.assertEqual(diagnostic.request_id, "req_safe123")
        self.assertNotIn("unsafe detail", json.dumps(diagnostic.as_dict()))
        unknown = self.invoke_http(400, json.dumps({"error": {"message": "x", "type": "secret-value",
            "code": "another-secret"}}).encode(), request_id="bad request id")
        self.assertEqual(unknown.error_type, "other_provider_error")
        self.assertEqual(unknown.error_code, "other_provider_code")
        self.assertIsNone(unknown.request_id)

    def test_malformed_and_oversized_error_bodies_are_not_retained(self):
        malformed = self.invoke_http(400, b"not-json unrestricted provider body")
        oversized = self.invoke_http(500, b"x" * (MAX_ERROR_RESPONSE_BYTES + 1))
        self.assertEqual(malformed.classification, "malformed_error_response")
        self.assertEqual(oversized.classification, "oversized_error_response")
        combined = json.dumps([malformed.as_dict(), oversized.as_dict()])
        self.assertNotIn("not-json", combined); self.assertNotIn("x" * 100, combined)

    def test_transport_failures_have_closed_classification(self):
        failures = ((urllib.error.URLError(socket.gaierror(-2, "secret host")), "dns"),
                    (urllib.error.URLError(ConnectionRefusedError("secret endpoint")), "connect"),
                    (urllib.error.URLError(ssl.SSLError("secret certificate")), "tls"),
                    (TimeoutError("secret timeout detail"), "timeout"),
                    (urllib.error.URLError(OSError("secret transport detail")), "other_transport"))
        for failure, classification in failures:
            with self.subTest(classification=classification), patch("vss_providers.experimental._urlopen_no_redirect", side_effect=failure), self.assertRaises(ProviderExecutionFailure) as caught:
                _https_post("https://api.openai.com/v1/images/generations", b"prompt text",
                            {"Authorization": "Bearer credential-value"}, 1.0, 100)
            diagnostic = caught.exception.diagnostic
            self.assertFalse(diagnostic.http_response_received)
            self.assertEqual(diagnostic.classification, classification)
            encoded = json.dumps(diagnostic.as_dict())
            for forbidden in ("secret", "prompt text", "credential-value", "Authorization", "api.openai.com"):
                self.assertNotIn(forbidden, encoded)

    def test_encoded_response_ceiling_is_derived_and_enforced(self):
        self.assertEqual(BASE64_RESPONSE_BYTES, ((MAX_BYTES + 2) // 3) * 4)
        self.assertEqual(MAX_RESPONSE_BYTES, BASE64_RESPONSE_BYTES + RESPONSE_ENVELOPE_OVERHEAD_BYTES)
        envelope = json.dumps({"data": [{"b64_json": base64.b64encode(b"x" * MAX_BYTES).decode()}]}).encode()
        self.assertLessEqual(len(envelope), MAX_RESPONSE_BYTES)
        intended = ExperimentalOpenAIExecutionAccess(lambda *args: envelope, lambda _: "credential")
        self.assertEqual(len(intended.post_images({}).content), len(envelope))
        access = ExperimentalOpenAIExecutionAccess(lambda *args: b"x" * MAX_RESPONSE_BYTES, lambda _: "credential")
        self.assertEqual(len(access.post_images({}).content), MAX_RESPONSE_BYTES)
        access = ExperimentalOpenAIExecutionAccess(lambda *args: b"x" * (MAX_RESPONSE_BYTES + 1), lambda _: "credential")
        with self.assertRaises(ProviderExecutionFailure) as caught:
            access.post_images({})
        diagnostic = caught.exception.diagnostic
        self.assertEqual(diagnostic.classification, "response_too_large")
        self.assertEqual(diagnostic.encoded_response_bytes, MAX_RESPONSE_BYTES + 1)

    def test_exact_safe_disallowed_chunk_names_never_expose_payloads(self):
        cases = ((b"vpAg", b"ancillary-secret-payload", "vpAg"),
                 (b"VpAg", b"critical-secret-payload", "VpAg"),
                 (b"tEXt", b"Comment\x00textual-secret", "tEXt"),
                 (b"iCCP", b"profile-name\x00icc-secret", "iCCP"),
                 (b"\xffBAD", b"binary-secret", "malformed"),
                 (b"abcd", b"reserved-bit-secret", "malformed"))
        for kind, payload, expected in cases:
            with self.subTest(kind=kind):
                content = diagnostic_png(kind, payload)
                summary = inspect_experimental_png(content)
                self.assertEqual(summary.rejection_reason, "disallowed_chunk")
                self.assertEqual(summary.chunk_types, ("IHDR", expected, "IDAT", "IEND"))
                encoded = json.dumps(summary.as_dict())
                self.assertNotIn("secret", encoded); self.assertNotIn(payload.hex(), encoded)
                self.assertLess(len(encoded), 500)
                with self.assertRaises(ProviderExecutionFailure):
                    validate_experimental_openai_png(content)

    def test_one_bounded_pre_idat_cabx_is_accepted_opaque_and_digest_significant(self):
        payload = b"opaque-c2pa-manifest-secret"
        content = provider_png((b"caBX", payload))
        original = bytes(content)
        self.assertEqual(validate_experimental_openai_png(content), (1536, 1024))
        self.assertEqual(content, original)
        summary = inspect_experimental_png(content)
        self.assertTrue(summary.content_credentials_present)
        self.assertEqual(summary.content_credentials_chunk_bytes, len(payload))
        self.assertEqual(summary.chunk_types, ("IHDR", "caBX", "IDAT", "IEND"))
        self.assertNotIn(payload.decode(), json.dumps(summary.as_dict()))
        without = provider_png()
        self.assertNotEqual(__import__("hashlib").sha256(content).hexdigest(),
                            __import__("hashlib").sha256(without).hexdigest())
        with self.assertRaises(ProviderExecutionFailure):
            validate_pictorial_png(content)

    def test_cabx_structure_is_closed_and_other_ancillary_chunks_remain_rejected(self):
        cases = {
            "duplicate": provider_png((b"caBX", b"one"), (b"caBX", b"two")),
            "empty": provider_png((b"caBX", b"")),
            "oversized": provider_png((b"caBX", b"x" * (MAX_CABX_BYTES + 1))),
            "other_ancillary": provider_png((b"vpAg", b"opaque")),
        }
        after_idat = provider_png()
        after_idat = after_idat[:-12] + png_chunk(b"caBX", b"late") + after_idat[-12:]
        cases["wrong_position"] = after_idat
        bad_crc = bytearray(provider_png((b"caBX", b"opaque")))
        cabx = bad_crc.index(b"caBX"); bad_crc[cabx + 4] ^= 1
        cases["crc"] = bytes(bad_crc)
        malformed = bytearray(provider_png((b"caBX", b"opaque")))
        cabx = malformed.index(b"caBX"); malformed[cabx:cabx + 4] = b"caB1"
        cases["malformed_type"] = bytes(malformed)
        for name, content in cases.items():
            with self.subTest(name=name), self.assertRaises(ProviderExecutionFailure):
                validate_experimental_openai_png(content)


if __name__ == "__main__":
    unittest.main()
