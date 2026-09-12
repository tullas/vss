"""Bounded structural checks for media containers returned by providers."""
from __future__ import annotations


MAX_MP4_SCAN_BYTES = 1024 * 1024


def check_mp4_payload(content: bytes) -> tuple[bool, str]:
    """Check a bounded ISO-BMFF sequence for an MP4-profile ``ftyp`` box.

    Supported brands preserve VSS's existing MP4 profile. Container lengths
    come from the payload rather than a particular sample byte prefix.
    """
    if not isinstance(content, bytes):
        return False, "invalid_payload"

    limit = min(len(content), MAX_MP4_SCAN_BYTES)
    offset = 0
    while offset + 8 <= limit:
        size = int.from_bytes(content[offset:offset + 4], "big")
        box_type = content[offset + 4:offset + 8]
        header = 8
        if size == 1:
            if offset + 16 > limit:
                return False, "truncated_extended_box"
            size = int.from_bytes(content[offset + 8:offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(content) - offset

        if size < header or offset + size > len(content):
            return False, "invalid_box_size"
        if box_type == b"ftyp":
            # ftyp has a major brand, minor version, then zero or more
            # four-byte compatible brands after the box header.
            if size < header + 8 or (size - header - 8) % 4:
                return False, "invalid_ftyp_box"
            major = content[offset + header:offset + header + 4]
            brands = [content[index:index + 4]
                      for index in range(offset + header + 8, offset + size, 4)]
            supported = {
                b"isom", b"iso2", b"iso3", b"iso4", b"iso5", b"iso6", b"iso7", b"iso8",
                b"mp41", b"mp42", b"avc1", b"av01", b"hvc1", b"hev1", b"hev2", b"dash",
                b"cmfc", b"cmff", b"mif1", b"msf1", b"avif", b"M4V ", b"qt  ",
            }
            if major in supported or any(brand in supported for brand in brands):
                return True, "valid_iso_bmff_ftyp"
            return False, "unsupported_mp4_brand"
        offset += size

    return False, "ftyp_not_found"
