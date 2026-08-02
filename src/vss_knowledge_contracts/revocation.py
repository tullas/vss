from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping

from .errors import InvalidKnowledgeInput, KnowledgeRegistryFailure


def _utc(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise KnowledgeRegistryFailure("knowledge revocation timestamp is invalid") from exc


@dataclass(frozen=True, slots=True)
class RevocationRecord:
    target_identity: str
    target_type: str
    reason_category: str
    revoked_at: str
    policy_identity: str = "vss.local-revocation-policy"
    policy_version: str = "1"
    source_evidence_sha256: str = "0" * 64


@dataclass(frozen=True, slots=True)
class KnowledgeRevocationRegistry:
    records: tuple[RevocationRecord, ...] = field(default_factory=tuple)
    _by_target: Mapping[tuple[str, str], RevocationRecord] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        admitted_types = {"source", "item"}
        admitted_reasons = {"access_removed", "classification_changed", "legal_restriction", "source_compromised", "poisoning", "superseded", "owner_request", "incident_response"}
        values: dict[tuple[str, str], RevocationRecord] = {}
        for record in self.records:
            key = (record.target_type, record.target_identity)
            if record.target_type not in admitted_types or record.reason_category not in admitted_reasons:
                raise KnowledgeRegistryFailure("knowledge revocation record is not admitted")
            if record.policy_identity != "vss.local-revocation-policy" or record.policy_version != "1":
                raise KnowledgeRegistryFailure("knowledge revocation policy is not admitted")
            if len(record.source_evidence_sha256) != 64 or any(character not in "0123456789abcdef" for character in record.source_evidence_sha256):
                raise KnowledgeRegistryFailure("knowledge revocation evidence is invalid")
            if key in values:
                raise KnowledgeRegistryFailure("duplicate knowledge revocation target")
            _utc(record.revoked_at)
            values[key] = record
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "_by_target", MappingProxyType(values))

    @classmethod
    def built_in(cls) -> "KnowledgeRevocationRegistry":
        """Repository-owned known-empty M3.4 revocation snapshot."""
        return cls()

    def record(self, target_type: str, target_identity: str) -> RevocationRecord | None:
        return self._by_target.get((target_type, target_identity))

    def assert_not_revoked(self, target_type: str, target_identity: str, *, effective_from: str, validation_time: str) -> None:
        record = self.record(target_type, target_identity)
        if record is None:
            return
        revoked_at = _utc(record.revoked_at)
        if revoked_at < _utc(effective_from):
            raise InvalidKnowledgeInput("knowledge revocation temporal ordering is invalid")
        if revoked_at <= _utc(validation_time):
            raise InvalidKnowledgeInput("knowledge material is revoked")
