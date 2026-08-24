from functools import lru_cache
import json
from pathlib import Path
import struct
import zlib

from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_pictorial import admit_pictorial_frame


ROOT = Path(__file__).resolve().parents[1]


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


@lru_cache(maxsize=1)
def pictorial_png() -> bytes:
    header = struct.pack(">IIBBBBB", 640, 360, 8, 2, 0, 0, 0)
    rows = (b"\0" + b"\x20\x40\x60" * 640) * 360
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(
        b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b"")


@lru_cache(maxsize=1)
def admitted_pictorial_frame():
    story = json.loads((ROOT / "tests/fixtures/movie/story-fragment-valid.json").read_text())
    correlation_id = "m91-resource-upstream"
    prepared = prepare_demo(story, correlation_id=correlation_id)
    finished = finish_demo(
        prepared,
        option_id=prepared.review_packet["payload"]["review_entries"][0]["option_id"],
        reviewer_id="m91.resource.reviewer",
        rationale="Accepted for exact inert pictorial resource admission testing.",
        correlation_id=correlation_id,
        include_storyboard=True,
    )
    storyboard = finished["scene_storyboard_specification"]
    frame_id = storyboard["payload"]["ordered_frames"][0]["frame_id"]
    return admit_pictorial_frame(
        finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"],
        finished["scene_shot_plan_draft"], storyboard,
        frame_id=frame_id, environment="development",
    )
