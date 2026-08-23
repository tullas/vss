from __future__ import annotations

import hashlib
import struct
import zlib

from vss_providers.contracts import GeneratedMedia, PictorialFrameRequest

WIDTH, HEIGHT = 640, 360


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
        required = {"subject_focus", "action", "environment", "time_and_lighting", "camera",
                    "visual_style", "assumptions", "explicit_unknowns", "generation_prompt",
                    "negative_constraints", "appearance_policy", "output"}
        if set(request.projection) != required:
            raise ValueError("pictorial projection is incompatible")
        pixels = bytearray((238, 238, 238) * (WIDTH * HEIGHT))
        # Neutral tonal planes and silhouettes intentionally avoid unsupported appearance facts.
        _rect(pixels, 0, 225, WIDTH, HEIGHT, 190)
        _rect(pixels, 28, 92, 150, 225, 211)
        _rect(pixels, 490, 70, 612, 225, 211)
        _rect(pixels, 150, 205, 490, 225, 172)
        framing = str(request.projection["camera"]["framing_and_shot_scale"]).lower()
        scale = 2 if "close" in framing else 1 if "medium" in framing else 0
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
