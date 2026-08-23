from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from vss_providers.errors import ProviderExecutionFailure

from .service import OUTPUT_HEIGHT, OUTPUT_WIDTH

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DECODED_MEDIA_BYTES = 10 * 1024 * 1024
MAX_CABX_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PNGSummary:
    width: int | None
    height: int | None
    bit_depth: int | None
    color_type: int | None
    interlace: int | None
    chunk_types: tuple[str, ...]
    rejection_reason: str | None
    content_credentials_present: bool
    content_credentials_chunk_bytes: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "width": self.width, "height": self.height, "bit_depth": self.bit_depth,
            "color_type": self.color_type, "interlace": self.interlace,
            "chunk_types": list(self.chunk_types), "rejection_reason": self.rejection_reason,
            "content_credentials_present": self.content_credentials_present,
            "content_credentials_chunk_bytes": self.content_credentials_chunk_bytes,
        }


def _safe_chunk_type(kind: bytes) -> str:
    if (len(kind) == 4 and all(65 <= value <= 90 or 97 <= value <= 122 for value in kind)
            and 65 <= kind[2] <= 90):
        return kind.decode("ascii")
    return "malformed"


def inspect_openai_png(content: bytes) -> PNGSummary:
    width = height = depth = color = interlace = None
    chunks: list[str] = []
    if not isinstance(content, bytes) or content[:8] != SIGNATURE:
        return PNGSummary(width, height, depth, color, interlace, (), "invalid_signature", False, None)
    offset, malformed, invalid_crc = 8, False, False
    cabx_lengths: list[int] = []
    while offset < len(content) and len(chunks) < 32:
        if offset + 12 > len(content):
            malformed = True
            break
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        chunks.append(_safe_chunk_type(kind))
        if length > MAX_DECODED_MEDIA_BYTES or end > len(content):
            malformed = True
            break
        data = content[offset + 8:offset + 8 + length]
        expected_crc = struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        if content[offset + 8 + length:end] != expected_crc:
            invalid_crc = True
            break
        if kind == b"caBX":
            cabx_lengths.append(length)
        if kind == b"IHDR" and length == 13 and offset == 8:
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", data)
        offset = end
    if invalid_crc:
        reason = "invalid_crc"
    elif malformed or offset != len(content) or len(chunks) >= 32 and offset < len(content):
        reason = "malformed_structure"
    elif len(cabx_lengths) > 1:
        reason = "duplicate_content_credentials"
    elif cabx_lengths and (cabx_lengths[0] == 0 or cabx_lengths[0] > MAX_CABX_BYTES):
        reason = "content_credentials_too_large"
    elif "caBX" in chunks and (len(chunks) < 3 or chunks[1] != "caBX" or "IDAT" not in chunks[2:]):
        reason = "invalid_order"
    elif any(kind not in {"IHDR", "caBX", "IDAT", "IEND"} for kind in chunks):
        reason = "disallowed_chunk"
    elif (width, height, depth, interlace) != (OUTPUT_WIDTH, OUTPUT_HEIGHT, 8, 0) or color not in {2, 6}:
        reason = "unsupported_profile"
    elif not chunks or chunks[0] != "IHDR" or chunks[-1] != "IEND" or "IDAT" not in chunks:
        reason = "invalid_order"
    else:
        reason = None
    return PNGSummary(
        width, height, depth, color, interlace, tuple(chunks), reason,
        bool(cabx_lengths), cabx_lengths[0] if len(cabx_lengths) == 1 else None,
    )


def validate_openai_png(content: bytes) -> PNGSummary:
    if not isinstance(content, bytes) or len(content) > MAX_DECODED_MEDIA_BYTES or content[:8] != SIGNATURE:
        raise ProviderExecutionFailure("experimental image provider returned invalid PNG")
    offset, kinds, compressed = 8, [], bytearray()
    channels = 0
    while offset < len(content):
        if len(kinds) >= 32:
            raise ProviderExecutionFailure("experimental image provider returned too many PNG chunks")
        if offset + 12 > len(content):
            raise ProviderExecutionFailure("experimental image provider returned malformed PNG")
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        if length > MAX_DECODED_MEDIA_BYTES or end > len(content):
            raise ProviderExecutionFailure("experimental image provider returned malformed PNG")
        data = content[offset + 8:offset + 8 + length]
        if content[offset + 8 + length:end] != struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF):
            raise ProviderExecutionFailure("experimental image provider returned PNG with invalid CRC")
        if kind not in {b"IHDR", b"caBX", b"IDAT", b"IEND"}:
            raise ProviderExecutionFailure("experimental image provider returned PNG with disallowed metadata")
        if kind == b"IHDR":
            if kinds or length != 13:
                raise ProviderExecutionFailure("experimental image provider returned malformed PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if ((width, height, depth, compression, filtering, interlace)
                    != (OUTPUT_WIDTH, OUTPUT_HEIGHT, 8, 0, 0, 0) or color not in {2, 6}):
                raise ProviderExecutionFailure("experimental image provider returned unsupported PNG profile")
            channels = 3 if color == 2 else 4
        elif kind == b"caBX":
            if kinds != [b"IHDR"] or length == 0 or length > MAX_CABX_BYTES:
                raise ProviderExecutionFailure("experimental image provider returned invalid Content Credentials chunk")
        elif kind == b"IDAT":
            if not kinds or kinds[0] != b"IHDR" or b"IEND" in kinds or b"IDAT" in kinds and kinds[-1] != b"IDAT":
                raise ProviderExecutionFailure("experimental image provider returned invalid PNG order")
            compressed.extend(data)
        else:
            if b"IDAT" not in kinds or length or end != len(content):
                raise ProviderExecutionFailure("experimental image provider returned invalid PNG ending")
        kinds.append(kind)
        offset = end
    if kinds.count(b"IHDR") != 1 or kinds.count(b"IEND") != 1 or kinds[-1] != b"IEND":
        raise ProviderExecutionFailure("experimental image provider returned incomplete PNG")
    expected = OUTPUT_HEIGHT * (1 + OUTPUT_WIDTH * channels)
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(compressed), expected + 1)
        raw += decoder.flush(max(1, expected + 1 - len(raw)))
    except zlib.error as exc:
        raise ProviderExecutionFailure("experimental image provider returned invalid PNG compression") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ProviderExecutionFailure("experimental image provider returned unsafe PNG decompression")
    stride = 1 + OUTPUT_WIDTH * channels
    if any(raw[row * stride] not in range(5) for row in range(OUTPUT_HEIGHT)):
        raise ProviderExecutionFailure("experimental image provider returned unsupported PNG filter")
    summary = inspect_openai_png(content)
    if summary.rejection_reason is not None:
        raise ProviderExecutionFailure("experimental image provider returned nonconformant PNG")
    return summary
