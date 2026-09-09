#!/usr/bin/env python3
"""Run only the fixed M11 Candidate 1 zero-call preflight on the host."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from vss_movie_controlled_generation import load_sealed_grounded_admission
from vss_runtime import RuntimeController


ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / "docs/reviews/m11-0-candidate-1-sealed-admission.json"
REQUEST_SHA = "3ebdeced6133e558f26f4c6174580174ed7a070b31cd5749f5dd7800692691e6"
PROVIDER_SHA = "dd30b2dd121ed50d58fc7fa057cf8f0fc6ab75ae310e6c76e8030f4ff85d0f84"
PROFILE_SHA = "51e785c899f7331e51c7583edc4558f779864236dfa1501e826ace994a71b903"
VARIATION_IDENTITY = "comparison-candidate-1"
VARIATION_ORDINAL = 1
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
    response, code = RuntimeController(root=ROOT).run(
        command="movie.controlled-review-frame-generate", environment="development",
        configuration={}, input_data={"admission_id": REQUEST_SHA, "mode": "preflight"},
        correlation_id="vikramaditya-m11-candidate-1-preflight",
        started_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        started_clock=time.monotonic(), dry_run=True, admitted_request=admitted,
    )
    print(json.dumps({"code": code, "response": response}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
