from dataclasses import dataclass
from typing import Any, Mapping
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json

@dataclass(frozen=True, slots=True)
class MovieRegistration:
    identity: str
    version: str
    schema_identity: str
    lifecycle: str = "active"
    owner: str = "vss-movie-domain"

@dataclass(frozen=True, slots=True, init=False)
class ValidatedMovieArtifact:
    value: Mapping[str, Any]
    digest: str
    def __init__(self, value: dict[str, Any]):
        frozen = freeze_json(value)
        object.__setattr__(self, "value", frozen)
        object.__setattr__(self, "digest", canonical_digest(frozen))
    def to_json_value(self):
        return thaw_json(self.value)
