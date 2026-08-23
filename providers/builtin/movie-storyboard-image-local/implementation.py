from __future__ import annotations

import hashlib
import struct
import zlib
from collections.abc import Mapping

from vss_movie_pictorial.service import CREATIVE_DEGREES_OF_FREEDOM
from vss_providers.contracts import GeneratedMedia, PictorialFrameRequest

WIDTH, HEIGHT = 640, 360

PROJECTION_FIELDS = {
    "depictable_facts", "required_narrative_emphasis", "narrative_context",
    "deliberate_ambiguities", "creative_degrees_of_freedom", "shot",
    "prohibited_contradictions", "depiction_instructions", "output",
}


def _text_tuple(value: object, *, maximum_items: int) -> bool:
    return (type(value) is tuple and len(value) <= maximum_items
            and all(type(item) is str and 0 < len(item) <= 4096 for item in value))


def _valid_projection(projection: object) -> bool:
    if not isinstance(projection, Mapping):
        return False
    if set(projection) != PROJECTION_FIELDS:
        return False
    context = projection["narrative_context"]
    shot = projection["shot"]
    output = projection["output"]
    if (not isinstance(context, Mapping)
            or set(context) != {"characters", "locations", "time_indicators"}
            or not isinstance(shot, Mapping) or set(shot) != {"purpose", "scale_constraint"}
            or not isinstance(output, Mapping)
            or set(output) != {"media_type", "width", "height", "purpose"}):
        return False
    if not all(_text_tuple(context[key], maximum_items=64)
               for key in ("characters", "locations", "time_indicators")):
        return False
    if (not _text_tuple(projection["depictable_facts"], maximum_items=128)
            or not projection["depictable_facts"]
            or not _text_tuple(projection["required_narrative_emphasis"], maximum_items=128)
            or not projection["required_narrative_emphasis"]
            or not _text_tuple(projection["deliberate_ambiguities"], maximum_items=128)
            or not _text_tuple(projection["prohibited_contradictions"], maximum_items=16)
            or not _text_tuple(projection["depiction_instructions"], maximum_items=16)
            or projection["creative_degrees_of_freedom"] != CREATIVE_DEGREES_OF_FREEDOM):
        return False
    shot_pairs = {
        ("scene_orientation", "wide"),
        ("primary_action", "medium"),
        ("detail_or_transition", "close_detail"),
    }
    if (type(shot["purpose"]) is not str or type(shot["scale_constraint"]) is not str
            or (shot["purpose"], shot["scale_constraint"]) not in shot_pairs):
        return False
    return (type(output["media_type"]) is str and output["media_type"] == "image/png"
            and type(output["width"]) is int and output["width"] == WIDTH
            and type(output["height"]) is int and output["height"] == HEIGHT
            and type(output["purpose"]) is str
            and output["purpose"] == "cinematic_image_candidate")


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _rect(pixels: bytearray, x0: int, y0: int, x1: int, y1: int, shade: int) -> None:
    for y in range(max(0, y0), min(HEIGHT, y1)):
        start = (y * WIDTH + max(0, x0)) * 3
        end = (y * WIDTH + min(WIDTH, x1)) * 3
        pixels[start:end] = bytes((shade, shade, shade)) * ((end - start) // 3)


def _circle(pixels: bytearray, cx: int, cy: int, radius: int, shade: int) -> None:
    squared = radius * radius
    for y in range(max(0, cy - radius), min(HEIGHT, cy + radius + 1)):
        width = int(max(0, squared - (y - cy) ** 2) ** 0.5)
        _rect(pixels, cx - width, y, cx + width + 1, y + 1, shade)


class LocalDeterministicPictorialPngProvider:
    def generate(self, request: PictorialFrameRequest) -> GeneratedMedia:
        if type(request) is not PictorialFrameRequest:
            raise ValueError("exact admitted pictorial request required")
        if not _valid_projection(request.projection):
            raise ValueError("pictorial projection is incompatible")
        pixels = bytearray((238, 238, 238) * (WIDTH * HEIGHT))
        # Neutral tonal planes and silhouettes intentionally avoid unsupported appearance facts.
        _rect(pixels, 0, 225, WIDTH, HEIGHT, 190)
        _rect(pixels, 28, 92, 150, 225, 211)
        _rect(pixels, 490, 70, 612, 225, 211)
        _rect(pixels, 150, 205, 490, 225, 172)
        framing = request.projection["shot"]["scale_constraint"]
        if framing not in {"wide", "medium", "close_detail"}:
            raise ValueError("pictorial shot scale is incompatible")
        scale = {"wide": 0, "medium": 1, "close_detail": 2}[framing]
        radius, half_body, head_y = ((22, 20, 164), (35, 30, 139), (58, 48, 112))[scale]
        body_top, body_bottom = head_y + radius, 300
        _circle(pixels, 320, head_y, radius, 65)
        _rect(pixels, 320 - half_body, body_top, 320 + half_body, body_bottom, 65)
        arm = 14 + scale * 8
        _rect(pixels, 320 - half_body - arm, body_top + 20, 320 - half_body, body_bottom - 25, 90)
        _rect(pixels, 320 + half_body, body_top + 20, 320 + half_body + arm, body_bottom - 25, 90)
        _rect(pixels, 300, body_bottom, 318, 342, 82)
        _rect(pixels, 332, body_bottom, 350, 342, 82)
        # A bounded gesture line signifies action without assigning a concrete prop or pose detail.
        for step in range(75):
            _rect(pixels, 320 + half_body + arm + step, body_top + 35 - step // 3,
                  322 + half_body + arm + step, body_top + 38 - step // 3, 105)
        raw = bytearray()
        stride = WIDTH * 3
        for y in range(HEIGHT):
            raw.append(0); raw.extend(pixels[y * stride:(y + 1) * stride])
        content = (b"\x89PNG\r\n\x1a\n"
                   + _chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
                   + _chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
                   + _chunk(b"IEND", b""))
        return GeneratedMedia("image/png", content, WIDTH, HEIGHT, hashlib.sha256(content).hexdigest())


def create_provider() -> LocalDeterministicPictorialPngProvider:
    return LocalDeterministicPictorialPngProvider()
