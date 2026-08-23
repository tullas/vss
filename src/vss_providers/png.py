from __future__ import annotations

import struct
import zlib

from .errors import ProviderExecutionFailure

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
WIDTH, HEIGHT = 640, 360
MAX_PNG_BYTES = 2 * 1024 * 1024


def validate_pictorial_png(content: bytes) -> tuple[int, int]:
    if not isinstance(content, bytes) or not (PNG_SIGNATURE == content[:8]) or len(content) > MAX_PNG_BYTES:
        raise ProviderExecutionFailure("pictorial provider returned invalid PNG")
    offset, chunks, compressed = 8, [], bytearray()
    seen_idat = False
    while offset < len(content):
        if offset + 12 > len(content):
            raise ProviderExecutionFailure("pictorial provider returned malformed PNG")
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        if length > MAX_PNG_BYTES or end > len(content):
            raise ProviderExecutionFailure("pictorial provider returned malformed PNG")
        data, supplied_crc = content[offset + 8:offset + 8 + length], content[offset + 8 + length:end]
        expected_crc = struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        if supplied_crc != expected_crc:
            raise ProviderExecutionFailure("pictorial provider returned PNG with invalid CRC")
        if kind not in {b"IHDR", b"IDAT", b"IEND"}:
            raise ProviderExecutionFailure("pictorial provider returned PNG with disallowed metadata")
        if kind == b"IHDR":
            if chunks or length != 13:
                raise ProviderExecutionFailure("pictorial provider returned malformed PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if (width, height, depth, color, compression, filtering, interlace) != (WIDTH, HEIGHT, 8, 2, 0, 0, 0):
                raise ProviderExecutionFailure("pictorial provider returned unsupported PNG format")
        elif kind == b"IDAT":
            if not chunks or chunks[0] != b"IHDR" or (seen_idat and chunks[-1] != b"IDAT"):
                raise ProviderExecutionFailure("pictorial provider returned invalid PNG chunk order")
            seen_idat = True
            compressed.extend(data)
        else:
            if not seen_idat or length != 0 or end != len(content):
                raise ProviderExecutionFailure("pictorial provider returned invalid PNG ending")
        chunks.append(kind); offset = end
    if not chunks or chunks[-1] != b"IEND" or chunks.count(b"IHDR") != 1 or chunks.count(b"IEND") != 1:
        raise ProviderExecutionFailure("pictorial provider returned incomplete PNG")
    expected_size = HEIGHT * (1 + WIDTH * 3)
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(compressed), expected_size + 1)
        raw += decoder.flush(max(1, expected_size + 1 - len(raw)))
    except zlib.error as exc:
        raise ProviderExecutionFailure("pictorial provider returned invalid PNG compression") from exc
    if len(raw) != expected_size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ProviderExecutionFailure("pictorial provider returned unsafe PNG decompression")
    stride = 1 + WIDTH * 3
    if any(raw[row * stride] != 0 for row in range(HEIGHT)):
        raise ProviderExecutionFailure("pictorial provider returned unsupported PNG filtering")
    return WIDTH, HEIGHT
