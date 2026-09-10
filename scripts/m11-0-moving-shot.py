#!/usr/bin/env python3
"""Fixed M11.0 host handoff for one Vertex Veo image-to-video attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from vss_movie_moving_shot import admit_moving_shot
from vss_runtime import RuntimeController

ROOT = Path(__file__).resolve().parents[1]
ADMISSION = ROOT / "docs/reviews/m11-0-candidate-2-sealed-admission.json"
BASIS = ROOT / ".local/movie/m10-0-controlled-review-frame/a471323eec0b3d3c69897447a5bb6d1922023cf09825a4910eed687514108d54/image.png"


def admission():
    material = json.loads(ADMISSION.read_text(encoding="utf-8"))
    request = material["request"]
    return admit_moving_shot(
        shot_id=material["binding"]["shot_id"], scene_id=material["binding"]["scene_id"],
        visual_basis_path=BASIS, visual_basis_sha256=hashlib.sha256(BASIS.read_bytes()).hexdigest(),
        prompt=("Create one restrained cinematic 4-second image-to-video development review shot. "
                "Preserve the exact source action, characters, spatial relationship, and deliberate unknowns; "
                "use a subtle forward camera movement beneath the banyan at dawn. No text, logos, watermarks, "
                "fantasy spectacle, added characters, or audio."),
        source_lineage=request["lineage"], production_id=request["scope"]["production_id"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if not ADMISSION.is_file() or not BASIS.is_file():
        raise SystemExit("M11 authoritative sealed admission or visual basis is unavailable")
    admitted = admission()
    controller = RuntimeController(root=ROOT)
    response, code = controller.run(
        "movie.moving-shot-generate", "development", {},
        {"admission_id": admitted.request_sha256, "mode": "preflight" if args.preflight else "generate"},
        "vikramaditya-m11-moving-shot", __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), time.monotonic(),
        dry_run=args.preflight, admitted_request=admitted,
    )
    print(json.dumps(response, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
