from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json


@dataclass(frozen=True, slots=True)
class ContextSchemaRecord:
    identity: str
    sha256: str
    schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema", freeze_json(dict(self.schema)))


@dataclass(frozen=True, slots=True)
class ContextRegistration:
    identity: str
    version: str
    schema_identity: str
    lifecycle: str = "active"
    owner: str = "vss-context-architecture"


@dataclass(frozen=True, slots=True, init=False)
class ValidatedContext:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def create(cls, value: dict[str, Any]) -> "ValidatedContext":
        instance = object.__new__(cls)
        frozen = freeze_json(value)
        object.__setattr__(instance, "value", frozen)
        object.__setattr__(instance, "digest", canonical_digest(frozen))
        return instance

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


@dataclass(frozen=True, slots=True, init=False)
class ValidatedAssemblyReport:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def create(cls, value: dict[str, Any]) -> "ValidatedAssemblyReport":
        instance = object.__new__(cls)
        frozen = freeze_json(value)
        object.__setattr__(instance, "value", frozen)
        object.__setattr__(instance, "digest", canonical_digest(frozen))
        return instance

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


@dataclass(frozen=True, slots=True)
class AssemblyOutcome:
    context: ValidatedContext | None
    report: ValidatedAssemblyReport | None
    summary: Mapping[str, Any]
    readiness: Mapping[str, Any] | None = None


def immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))
