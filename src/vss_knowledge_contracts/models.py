from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json


@dataclass(frozen=True, slots=True)
class KnowledgeSchemaRecord:
    identity: str
    path: Path
    sha256: str
    schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", self.path.resolve())
        object.__setattr__(self, "schema", freeze_json(dict(self.schema)))


@dataclass(frozen=True, slots=True)
class KnowledgeRegistration:
    item_envelope_identity: str = "knowledge_item"
    item_envelope_version: str = "1"
    item_family: str = "reference_note"
    item_family_version: str = "1"
    package_identity: str = "knowledge_package"
    package_version: str = "1"
    lifecycle_status: str = "active"
    owner: str = "vss-knowledge-architecture"
    maximum_item_bytes: int = 16_384
    maximum_package_bytes: int = 65_536
    deprecated_after: str | None = None


@dataclass(frozen=True, slots=True, init=False)
class ValidatedKnowledgeItem:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def _create(cls, value: dict[str, Any]) -> "ValidatedKnowledgeItem":
        instance = object.__new__(cls)
        frozen = freeze_json(value)
        object.__setattr__(instance, "value", frozen)
        object.__setattr__(instance, "digest", canonical_digest(frozen))
        return instance

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


@dataclass(frozen=True, slots=True, init=False)
class ValidatedKnowledgePackage:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def _create(cls, value: dict[str, Any]) -> "ValidatedKnowledgePackage":
        instance = object.__new__(cls)
        frozen = freeze_json(value)
        object.__setattr__(instance, "value", frozen)
        object.__setattr__(instance, "digest", canonical_digest(frozen))
        return instance

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


def immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))
