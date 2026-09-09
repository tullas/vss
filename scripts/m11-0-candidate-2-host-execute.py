#!/usr/bin/env python3
"""Execute the one fixed M11 Candidate 2 host handoff."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vss_movie_controlled_generation import (
    APPROVER_SECRET_NAME, issue_approval, load_sealed_grounded_admission,
)
from vss_runtime import RuntimeController


ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / "docs/reviews/m11-0-candidate-2-sealed-admission.json"
REQUEST_SHA = "a471323eec0b3d3c69897447a5bb6d1922023cf09825a4910eed687514108d54"
PROVIDER_SHA = "de2dfa6860117de59be5cb0202764b4e930f88187694d386415fc91dad7759a3"
PROFILE_SHA = "51e785c899f7331e51c7583edc4558f779864236dfa1501e826ace994a71b903"
VARIATION_IDENTITY = "comparison-candidate-2"
VARIATION_ORDINAL = 2
OPTION_ID = "option-b5d2461f4ec95dc0377938ba"
SCENE_ID = "scene-91f5c8634519d8264e2dd5f8"
SHOT_ID = "shot-024b0d6352149eabb74df543"
FRAME_ID = "frame-fb0d79ba59d7781b0bad3e7e"


def main() -> int:
    material = json.loads(MATERIAL.read_text(encoding="utf-8"))
    admitted = load_sealed_grounded_admission(
        material, expected_request_sha256=REQUEST_SHA,
        expected_provider_request_sha256=PROVIDER_SHA,
        expected_profile_sha256=PROFILE_SHA,
        expected_variation_identity=VARIATION_IDENTITY,
        expected_variation_ordinal=VARIATION_ORDINAL,
        expected_option_id=OPTION_ID, expected_scene_id=SCENE_ID,
        expected_shot_id=SHOT_ID, expected_frame_id=FRAME_ID,
    )
    secret = os.environ.get(APPROVER_SECRET_NAME)
    if not secret:
        raise SystemExit("fresh request-bound approver credential is required")
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    approval = issue_approval(
        admitted.request_json(), recorded_by="m11-human-approved-candidate-2",
        secret=secret, issued_at=issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(issued + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    admitted = load_sealed_grounded_admission(
        material, expected_request_sha256=REQUEST_SHA,
        expected_provider_request_sha256=PROVIDER_SHA,
        expected_profile_sha256=PROFILE_SHA,
        expected_variation_identity=VARIATION_IDENTITY,
        expected_variation_ordinal=VARIATION_ORDINAL,
        expected_option_id=OPTION_ID, expected_scene_id=SCENE_ID,
        expected_shot_id=SHOT_ID, expected_frame_id=FRAME_ID,
        approval=approval,
    )
    response, code = RuntimeController(root=ROOT).run(
        command="movie.controlled-review-frame-generate", environment="development",
        configuration={}, input_data={"admission_id": REQUEST_SHA, "mode": "generate"},
        correlation_id="vikramaditya-m11-candidate-2-host",
        started_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        started_clock=time.monotonic(), admitted_request=admitted,
    )
    print(json.dumps({"code": code, "response": response}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
