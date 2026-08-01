from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    provider_type: str
    name: str
    version: str
    identity: str
    provider_api_version: str
    implementation_identity: str
    lifecycle_status: str
    source: str


@dataclass(frozen=True, slots=True)
class RegisteredProvider:
    metadata: ProviderIdentity
    manifest_path: Path
    implementation_path: Path
    manifest_sha256: str
    implementation_sha256: str
    factory_name: str
