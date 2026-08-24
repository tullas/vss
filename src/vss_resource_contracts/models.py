from dataclasses import dataclass
from typing import Any, Mapping

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json


@dataclass(frozen=True, slots=True)
class ResourceRegistration:
    identity: str
    version: str
    schema_identity: str
    lifecycle: str = "active"
    owner: str = "vss-resource-contracts"


@dataclass(frozen=True, slots=True, init=False)
class ValidatedResourceArtifact:
    value: Mapping[str, Any]
    digest: str

    def __init__(self, value: dict[str, Any]):
        raise TypeError("validated resource artifacts must be created by validators")

    @classmethod
    def _create(cls, value: dict[str, Any]):
        obj = object.__new__(cls)
        frozen = freeze_json(value)
        object.__setattr__(obj, "value", frozen)
        object.__setattr__(obj, "digest", canonical_digest(frozen))
        return obj

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)
