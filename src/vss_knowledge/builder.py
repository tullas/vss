from __future__ import annotations

import hashlib
import os
import stat
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from vss_knowledge_contracts import (
    KnowledgeContractRegistry,
    canonical_digest,
    complete_package_material,
    item_content_material,
    load_json_document,
    package_content_material,
    validate_item,
    validate_package,
)

from .audit import DevelopmentKnowledgeAudit, KnowledgeAuditSink
from .errors import KnowledgeFixtureFailure, KnowledgePolicyDenied, UnknownKnowledgeSource

SOURCE_ID = "vss.local.reference-fixtures"
SOURCE_VERSION = "1"
FIXTURE_ID = "reference-note-local-validation"
PURPOSE = "local_validation_context"
VALIDATION_TIME = "2026-08-02T00:00:00Z"
MAX_FIXTURE_BYTES = 16_384
_TRANSFORMATIONS = ["strict_json_decode/1", "typed_normalization/1", "classification_validation/1", "canonicalization/1"]


@dataclass(frozen=True, slots=True)
class SourceRegistration:
    fixture_id: str
    source_id: str
    source_version: str
    relative_path: str
    lifecycle: str
    trust: str
    classification_ceiling: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class KnowledgePolicy:
    identity: str = "vss.local-knowledge-policy"
    version: str = "1"
    environment: str = "development"
    purpose: str = PURPOSE
    classifications: tuple[str, ...] = ("public", "internal")
    trust: str = "approved_fixture"

    @property
    def digest(self) -> str:
        return canonical_digest({name: getattr(self, name) for name in self.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class KnowledgeBuildOutcome:
    package: Any
    summary: Mapping[str, Any]


class KnowledgePackageBuilder:
    __slots__ = ("_root", "_registry", "_policy", "_sources", "_audit")

    def __init__(self, repository_root: Path | None = None, registry: KnowledgeContractRegistry | None = None, audit: KnowledgeAuditSink | None = None) -> None:
        root = (repository_root or Path(__file__).resolve().parents[2]).resolve()
        self._root = root
        self._registry = registry or KnowledgeContractRegistry.built_in()
        self._policy = KnowledgePolicy()
        registration = SourceRegistration(FIXTURE_ID, SOURCE_ID, SOURCE_VERSION, "tests/fixtures/knowledge/reference-note-local-validation.json", "active", "approved_fixture", "internal", "0af2a6811de3601986f5b64e5bacdfd6e2166726dca7de823d0c1cc5e42ec4c7")
        self._sources = MappingProxyType({FIXTURE_ID: registration})
        self._audit = audit or DevelopmentKnowledgeAudit(root)

    @property
    def registry(self) -> KnowledgeContractRegistry:
        return self._registry

    def _load(self, source: SourceRegistration) -> tuple[bytes, dict[str, Any]]:
        path = self._root / source.relative_path
        descriptor = -1
        try:
            resolved = path.resolve(strict=True)
            fixture_root = (self._root / "tests/fixtures/knowledge").resolve(strict=True)
            if not resolved.is_relative_to(fixture_root) or path.is_symlink():
                raise KnowledgeFixtureFailure("knowledge fixture path is unsafe")
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise KnowledgeFixtureFailure("knowledge fixture is not a regular file")
            raw = os.read(descriptor, MAX_FIXTURE_BYTES + 1)
        except OSError as exc:
            raise KnowledgeFixtureFailure("knowledge fixture is unavailable") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if len(raw) > MAX_FIXTURE_BYTES:
            raise KnowledgeFixtureFailure("knowledge fixture exceeds its bound")
        try:
            value = load_json_document(raw)
        except Exception as exc:
            raise KnowledgeFixtureFailure("knowledge fixture is invalid") from exc
        if not isinstance(value, dict):
            raise KnowledgeFixtureFailure("knowledge fixture is invalid")
        expected = {"fixture_schema_version", "source_item_id", "source_version", "classification", "trust", "lifecycle_status", "observed_at", "effective_from", "effective_until", "retrieved_at", "stale_after", "retention_until", "owning_authority", "payload"}
        if set(value) != expected:
            raise KnowledgeFixtureFailure("knowledge fixture has unknown fields")
        return raw, value

    def _audit_record(self, *, operation: str = "build", correlation_id: str, operation_id: str, status: str, duration_ms: int, source_digest: str | None = None, item_digest: str | None = None, package_content_digest: str | None = None, package_digest: str | None = None) -> None:
        self._audit.append({
            "event_type": f"knowledge_package_{operation}_completed" if status == "success" else f"knowledge_package_{operation}_failed",
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "knowledge_operation_id": operation_id, "correlation_id": correlation_id,
            "source_identity": SOURCE_ID, "source_version": SOURCE_VERSION,
            "item_family": "reference_note", "item_version": "1",
            "package_identity": "knowledge_package", "package_version": "1",
            "purpose": PURPOSE, "classification": "internal", "trust": "approved_fixture",
            "item_count": 1 if status == "success" else 0, "source_count": 1,
            "source_sha256": source_digest, "item_sha256": item_digest,
            "package_content_sha256": package_content_digest, "package_sha256": package_digest,
            "registry_sha256": self._registry.digest, "policy_sha256": self._policy.digest,
            "freshness_status": "all_current" if status == "success" else "unknown",
            "conflict_count": 0, "revocation_status": "none" if status == "success" else "unknown",
            "lifecycle": "validated" if status == "success" else "failed",
            "validation_outcome": status, "duration_ms": duration_ms, "status": status,
        })

    def build(self, source_identity: str, purpose: str, environment: str, correlation_id: str, *, validation_time: str | None = None) -> KnowledgeBuildOutcome:
        started = time.monotonic()
        operation_id = uuid.uuid4().hex
        source_digest = item_digest = content_digest = package_digest = None
        try:
            if environment != self._policy.environment or purpose != self._policy.purpose:
                raise KnowledgePolicyDenied("knowledge operation is not permitted")
            source = self._sources.get(source_identity)
            if source is None or source.lifecycle != "active":
                raise UnknownKnowledgeSource("knowledge source is unknown or inactive")
            raw, fixture = self._load(source)
            if fixture["trust"] != self._policy.trust or fixture["classification"] not in self._policy.classifications or fixture["source_version"] != source.source_version:
                raise KnowledgePolicyDenied("knowledge source metadata is not admitted")
            source_digest = hashlib.sha256(raw).hexdigest()
            if source_digest != source.source_sha256:
                raise KnowledgeFixtureFailure("knowledge fixture integrity mismatch")
            decoded_digest = canonical_digest(fixture)
            payload_digest = canonical_digest(fixture["payload"])
            item = {
                "schema_version":"1", "item_id":fixture["source_item_id"], "item_family":"reference_note", "item_family_version":"1",
                "source_id":source.source_id, "source_item_id":fixture["source_item_id"], "source_version":fixture["source_version"],
                "classification":fixture["classification"], "trust":fixture["trust"], "permitted_purposes":[PURPOSE], "lifecycle_status":fixture["lifecycle_status"],
                "observed_at":fixture["observed_at"], "effective_from":fixture["effective_from"], "effective_until":fixture["effective_until"], "retrieved_at":fixture["retrieved_at"], "stale_after":fixture["stale_after"], "retention_until":fixture["retention_until"],
                "provenance":{"retrieval_mechanism":"repository_fixture_loader","retrieval_version":"1","normalization_contract":"reference_note_normalizer","normalization_version":"1","owning_authority":fixture["owning_authority"]},
                "transformations":list(_TRANSFORMATIONS), "integrity":{"source_sha256":source_digest,"decoded_sha256":decoded_digest,"payload_sha256":payload_digest,"item_content_sha256":"0"*64}, "payload":fixture["payload"],
            }
            item["integrity"]["item_content_sha256"] = canonical_digest(item_content_material(item))
            now_text = validation_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            validated_item = validate_item(item, self._registry, validation_time=now_text)
            item = validated_item.to_json_value(); item_digest = item["integrity"]["item_content_sha256"]
            constructed = datetime.strptime(now_text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            package = {
                "schema_version":"1", "package_id":"package-"+hashlib.sha256((correlation_id+item_digest).encode()).hexdigest()[:32], "package_contract_identity":"knowledge_package", "package_contract_version":"1", "correlation_id":correlation_id,
                "permitted_purpose":PURPOSE, "task_family":"local_validation", "classification":item["classification"], "lifecycle_status":"validated",
                "constructed_at":constructed.strftime("%Y-%m-%dT%H:%M:%SZ"), "expires_at":item["effective_until"], "retention_until":item["retention_until"],
                "source_references":[SOURCE_ID], "item_references":[item["item_id"]], "items":[item],
                "provenance_summary":{"source_count":1,"transformation_count":4}, "freshness_summary":"all_current", "classification_summary":{"maximum":item["classification"],"item_count":1},
                "redaction_summary":{"policy_identity":"vss.no-redaction-required","policy_version":"1","status":"not_required","removed_field_count":0},
                "conflict_summary":{"status":"none_detected","conflicts":[]}, "uncertainty_summary":["Truth and real-world applicability were not independently verified."], "revocation_summary":{"status":"none","revoked_item_ids":[]},
                "lineage":[], "integrity":{"package_content_sha256":"0"*64,"complete_package_sha256":"0"*64,"registry_sha256":self._registry.digest},
            }
            content_digest = canonical_digest(package_content_material(package)); package["integrity"]["package_content_sha256"] = content_digest
            package["lineage"] = [
                {"step_id":"lineage-source","kind":"source","input_sha256":source_digest,"output_sha256":decoded_digest,"item_id":item["item_id"]},
                {"step_id":"lineage-payload","kind":"normalized_payload","input_sha256":decoded_digest,"output_sha256":payload_digest,"item_id":item["item_id"]},
                {"step_id":"lineage-item","kind":"validated_item","input_sha256":payload_digest,"output_sha256":item["integrity"]["item_content_sha256"],"item_id":item["item_id"]},
                {"step_id":"lineage-content","kind":"package_content","input_sha256":item["integrity"]["item_content_sha256"],"output_sha256":content_digest,"item_id":None},
                {"step_id":"lineage-package","kind":"complete_package","input_sha256":content_digest,"output_sha256":"0"*64,"item_id":None},
            ]
            package_digest = canonical_digest(complete_package_material(package)); package["integrity"]["complete_package_sha256"] = package_digest; package["lineage"][-1]["output_sha256"] = package_digest
            validated = validate_package(package, self._registry, validation_time=now_text)
            self._audit_record(correlation_id=correlation_id, operation_id=operation_id, status="success", duration_ms=int((time.monotonic()-started)*1000), source_digest=source_digest, item_digest=item_digest, package_content_digest=content_digest, package_digest=package_digest)
            summary = MappingProxyType({"registry_sha256":self._registry.digest,"source_sha256":source_digest,"item_sha256":item_digest,"package_content_sha256":content_digest,"package_sha256":package_digest,"classification":item["classification"],"purpose":PURPOSE,"freshness":"all_current","item_count":1})
            return KnowledgeBuildOutcome(validated, summary)
        except Exception:
            self._audit_record(correlation_id=correlation_id, operation_id=operation_id, status="failed", duration_ms=int((time.monotonic()-started)*1000), source_digest=source_digest, item_digest=item_digest, package_content_digest=content_digest, package_digest=package_digest)
            raise

    def validate(self, value: dict[str, Any], environment: str, correlation_id: str, *, validation_time: str | None = None) -> KnowledgeBuildOutcome:
        started = time.monotonic(); operation_id = uuid.uuid4().hex
        source_digest = item_digest = content_digest = package_digest = None
        try:
            if environment != self._policy.environment:
                raise KnowledgePolicyDenied("knowledge operation is not permitted")
            now_text = validation_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            validated = validate_package(value, self._registry, validation_time=now_text)
            plain = validated.to_json_value(); item = plain["items"][0]
            source_digest = item["integrity"]["source_sha256"]
            item_digest = item["integrity"]["item_content_sha256"]
            content_digest = plain["integrity"]["package_content_sha256"]
            package_digest = plain["integrity"]["complete_package_sha256"]
            self._audit_record(operation="validate", correlation_id=correlation_id, operation_id=operation_id, status="success", duration_ms=int((time.monotonic()-started)*1000), source_digest=source_digest, item_digest=item_digest, package_content_digest=content_digest, package_digest=package_digest)
            summary = MappingProxyType({"registry_sha256":self._registry.digest,"source_sha256":source_digest,"item_sha256":item_digest,"package_content_sha256":content_digest,"package_sha256":package_digest,"classification":plain["classification"],"purpose":plain["permitted_purpose"],"freshness":plain["freshness_summary"],"item_count":len(plain["items"])})
            return KnowledgeBuildOutcome(validated, summary)
        except Exception:
            self._audit_record(operation="validate", correlation_id=correlation_id, operation_id=operation_id, status="failed", duration_ms=int((time.monotonic()-started)*1000), source_digest=source_digest, item_digest=item_digest, package_content_digest=content_digest, package_digest=package_digest)
            raise
