from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_REFERENCE = re.compile(r"^(?P<algorithm>[a-z0-9-]+):(?P<value>[0-9a-f]+)$")


@dataclass(frozen=True)
class DigestReference:
    """Algorithm-aware digest identity; legacy bare SHA-256 remains accepted."""

    algorithm: str
    value: str
    canonicalization: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", self.algorithm) or not re.fullmatch(r"[0-9a-f]{8,128}", self.value):
            raise ValueError("invalid digest reference")

    def as_string(self) -> str:
        return f"{self.algorithm}:{self.value}"

    @classmethod
    def parse(cls, value: str, *, legacy_sha256: bool = True) -> "DigestReference":
        if legacy_sha256 and re.fullmatch(r"[0-9a-f]{64}", value):
            return cls("sha256", value)
        match = _REFERENCE.fullmatch(value)
        if match is None:
            raise ValueError("digest reference must include an algorithm")
        return cls(match["algorithm"], match["value"])


def sha256_reference(value: bytes, *, canonicalization: str | None = None, version: str | None = None) -> DigestReference:
    return DigestReference("sha256", hashlib.sha256(value).hexdigest(), canonicalization, version)
