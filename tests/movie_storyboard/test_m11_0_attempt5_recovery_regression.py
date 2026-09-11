"""Regression coverage for the recovered M11.0 Attempt 5 terminal response."""

import base64
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "providers/builtin/movie-image-to-video-vertex-veo/implementation.py"
FIXTURE = ROOT / "tests/fixtures/movie/m11-attempt5-google-terminal-response.json"
RECOVERY = ROOT / "docs/reviews/m11-0-attempt-5-recovery.json"
SPEC = importlib.util.spec_from_file_location("m11_attempt5_vertex_veo_provider", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _request():
    return type("Request", (), {
        "prompt": "prompt",
        "image": b"png",
        "request_sha256": "a" * 64,
        "provider_request_sha256": "a" * 64,
        "duration_seconds": 8,
        "resolution": "720p",
        "generate_audio": False,
        "image_mime_type": "image/png",
    })()


def test_attempt5_google_inline_shape_is_admitted_without_resubmission():
    terminal = json.loads(FIXTURE.read_text())
    operation = terminal["name"]
    calls = []

    def transport(url, _body, _headers, _timeout, _maximum):
        calls.append(url)
        if url.endswith(":predictLongRunning"):
            return json.dumps({"name": operation}).encode()
        assert url.endswith(":fetchPredictOperation")
        return json.dumps(terminal).encode()

    with patch.dict("os.environ", {
        "VSS_VERTEX_AI_PROJECT_ID": "vss-film-poc",
        "VSS_VERTEX_AI_LOCATION": "us-central1",
    }, clear=False):
        result = MODULE.VertexVeoImageToVideoProvider().generate(
            _request(), credential="token", transport=transport,
        )

    expected = base64.b64decode(
        terminal["response"]["videos"][0]["bytesBase64Encoded"], validate=True,
    )
    assert result.provider_request_id == operation
    assert result.media.content == expected
    assert len(calls) == 2
    assert calls[0].endswith(":predictLongRunning")
    assert calls[1].endswith(":fetchPredictOperation")


def test_attempt5_recovery_evidence_preserves_verified_artifact_identity():
    recovery = json.loads(RECOVERY.read_text())
    assert recovery["attempt"] == 5
    assert recovery["historical_status"] == "consumed"
    assert recovery["corrected_outcome"] == "provider_success_admission_failure_recovered_artifact"
    assert recovery["provider_execution"]["new_provider_call"] is False
    assert recovery["provider_execution"]["new_paid_attempt"] is False
    assert recovery["provider_execution"]["video_count"] == 1
    assert recovery["provider_execution"]["rai_media_filtered_count"] == 0
    assert recovery["recovered_media"]["sha256"] == "1008b512047b98451cf6b3760eb7b18d1909ed319474a24c103b4db2e6e0bda3"
    assert recovery["recovered_media"]["size_bytes"] == 6330737
    assert recovery["recovered_media"]["width"] == 1280
    assert recovery["recovered_media"]["height"] == 720
    assert recovery["recovered_media"]["frame_rate"] == "24/1"
    assert recovery["recovered_media"]["duration_seconds"] == "8.000000"
    assert recovery["recovered_media"]["audio_stream_present"] is False
    assert recovery["root_cause"]["provider_generation_failed"] is False
