from __future__ import annotations

import struct
import zlib

from .errors import ExperimentalPNGDiagnostic, ProviderExecutionFailure

SIGNATURE = b"\x89PNG\r\n\x1a\n"
WIDTH, HEIGHT = 1536, 1024
MAX_BYTES = 10 * 1024 * 1024
MAX_CABX_BYTES = 4 * 1024 * 1024


def _safe_chunk_type(kind: bytes) -> str:
    if (len(kind) == 4 and all(65 <= value <= 90 or 97 <= value <= 122 for value in kind)
            and 65 <= kind[2] <= 90):
        return kind.decode("ascii")
    return "malformed"


def inspect_experimental_png(content: bytes) -> ExperimentalPNGDiagnostic:
    """Return a payload-free bounded summary without changing admission semantics."""
    width = height = depth = color = interlace = None
    chunks: list[str] = []
    if not isinstance(content, bytes) or content[:8] != SIGNATURE:
        return ExperimentalPNGDiagnostic(width, height, depth, color, interlace, (), "invalid_signature")
    offset, malformed, invalid_crc = 8, False, False
    cabx_lengths: list[int] = []
    while offset < len(content) and len(chunks) < 32:
        if offset + 12 > len(content): malformed = True; break
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        chunks.append(_safe_chunk_type(kind))
        if length > MAX_BYTES or end > len(content): malformed = True; break
        data = content[offset + 8:offset + 8 + length]
        if content[offset + 8 + length:end] != struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff):
            invalid_crc = True; break
        if kind == b"caBX": cabx_lengths.append(length)
        if kind == b"IHDR" and length == 13 and offset == 8:
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", content[offset + 8:offset + 21])
        offset = end
    if invalid_crc: reason = "invalid_crc"
    elif malformed or offset != len(content): reason = "malformed_structure"
    elif len(cabx_lengths) > 1: reason = "duplicate_content_credentials"
    elif cabx_lengths and (cabx_lengths[0] == 0 or cabx_lengths[0] > MAX_CABX_BYTES): reason = "content_credentials_too_large"
    elif "caBX" in chunks and (len(chunks) < 3 or chunks[1] != "caBX" or "IDAT" not in chunks[2:]): reason = "invalid_order"
    elif any(kind not in {"IHDR", "caBX", "IDAT", "IEND"} for kind in chunks): reason = "disallowed_chunk"
    elif (width, height, depth, interlace) != (WIDTH, HEIGHT, 8, 0) or color not in {2, 6}: reason = "unsupported_profile"
    else: reason = "conformance_failed"
    return ExperimentalPNGDiagnostic(width, height, depth, color, interlace, tuple(chunks), reason,
        bool(cabx_lengths), cabx_lengths[0] if len(cabx_lengths) == 1 else None)


def validate_experimental_openai_png(content: bytes) -> tuple[int, int]:
    """Accept the strict experimental RGB/RGBA profile and one opaque pre-IDAT caBX."""
    if not isinstance(content, bytes) or len(content) > MAX_BYTES or content[:8] != SIGNATURE:
        raise ProviderExecutionFailure("experimental provider returned invalid PNG")
    offset, kinds, compressed = 8, [], bytearray()
    while offset < len(content):
        if offset + 12 > len(content):
            raise ProviderExecutionFailure("experimental provider returned malformed PNG")
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        if length > MAX_BYTES or end > len(content):
            raise ProviderExecutionFailure("experimental provider returned malformed PNG")
        data = content[offset + 8:offset + 8 + length]
        if content[offset + 8 + length:end] != struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff):
            raise ProviderExecutionFailure("experimental provider returned PNG with invalid CRC")
        if kind not in {b"IHDR", b"caBX", b"IDAT", b"IEND"}:
            raise ProviderExecutionFailure("experimental provider returned PNG with disallowed metadata")
        if kind == b"IHDR":
            if kinds or length != 13:
                raise ProviderExecutionFailure("experimental provider returned malformed PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if (width, height, depth, compression, filtering, interlace) != (WIDTH, HEIGHT, 8, 0, 0, 0) or color not in {2, 6}:
                raise ProviderExecutionFailure("experimental provider returned unsupported PNG profile")
            channels = 3 if color == 2 else 4
        elif kind == b"caBX":
            if kinds != [b"IHDR"] or length == 0 or length > MAX_CABX_BYTES:
                raise ProviderExecutionFailure("experimental provider returned invalid Content Credentials chunk")
        elif kind == b"IDAT":
            if not kinds or kinds[0] != b"IHDR" or (b"IEND" in kinds) or (b"IDAT" in kinds and kinds[-1] != b"IDAT"):
                raise ProviderExecutionFailure("experimental provider returned invalid PNG order")
            compressed.extend(data)
        else:
            if b"IDAT" not in kinds or length or end != len(content):
                raise ProviderExecutionFailure("experimental provider returned invalid PNG ending")
        kinds.append(kind); offset = end
    if kinds.count(b"IHDR") != 1 or kinds.count(b"IEND") != 1 or kinds[-1] != b"IEND":
        raise ProviderExecutionFailure("experimental provider returned incomplete PNG")
    expected = HEIGHT * (1 + WIDTH * channels)
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(compressed), expected + 1)
        raw += decoder.flush(max(1, expected + 1 - len(raw)))
    except zlib.error as exc:
        raise ProviderExecutionFailure("experimental provider returned invalid PNG compression") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ProviderExecutionFailure("experimental provider returned unsafe PNG decompression")
    stride = 1 + WIDTH * channels
    if any(raw[row * stride] not in range(5) for row in range(HEIGHT)):
        raise ProviderExecutionFailure("experimental provider returned unsupported PNG filter")
    return WIDTH, HEIGHT
