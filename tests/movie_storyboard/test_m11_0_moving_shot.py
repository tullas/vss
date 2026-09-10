from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from vss_movie_moving_shot import admit_moving_shot, validate_moving_shot_admission
from vss_providers import GeneratedMedia, ImageToVideoResult, ProviderAccess


MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"


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

    def test_runtime_handle_enforces_one_call_and_bounds_video(self):
        provider = FakeVideoProvider()
        access = ProviderAccess(video=provider, video_secret_reader=lambda _: "token")
        admission = self.admission()
        request = type("Request", (), {
            "prompt": admission.request["prompt"], "image": admission.image,
            "request_sha256": admission.request_sha256,
            "provider_request_sha256": admission.request_sha256,
            "duration_seconds": 4, "resolution": "720p", "generate_audio": False,
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
            "duration_seconds": 4, "resolution": "720p", "generate_audio": False,
        })()
        access.get_image_to_video_generator().generate(request)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(admission.request["provider"]["model_snapshot"], "veo-3.1-generate-001")
        self.assertFalse(admission.request["provider"]["generate_audio"])
        self.assertEqual(admission.request["bounds"]["maximum_provider_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
