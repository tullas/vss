from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .canonicalization import canonical_digest, freeze_json, thaw_json


@dataclass(frozen=True, slots=True)
class SchemaRecord:
    identity: str
    version: str
    schema_id: str
    path: Path
    sha256: str
    schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", self.path.resolve())
        object.__setattr__(self, "schema", freeze_json(dict(self.schema)))


@dataclass(frozen=True, slots=True)
class ContractRegistration:
    task_identity: str
    task_version: str
    result_family: str
    result_version: str
    request_envelope_version: str
    result_envelope_version: str
    lifecycle_status: str
    request_schema_identity: str
    result_schema_identity: str
    owner: str
    maximum_request_bytes: int
    maximum_result_bytes: int
    deprecated_after: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedSemanticRequest:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def from_value(cls, value: dict[str, Any]) -> "ValidatedSemanticRequest":
        frozen = freeze_json(value)
        return cls(frozen, canonical_digest(frozen))

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


@dataclass(frozen=True, slots=True)
class ValidatedSemanticResult:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def from_value(cls, value: dict[str, Any]) -> "ValidatedSemanticResult":
        frozen = freeze_json(value)
        return cls(frozen, canonical_digest(frozen))

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


def immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))
