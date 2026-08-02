from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json, validate_json_value

from .errors import InvalidKnowledgeInput, KnowledgeIntegrityFailure
from .models import ValidatedKnowledgeItem, ValidatedKnowledgePackage
from .registry import KnowledgeContractRegistry

CLASSIFICATION_RANK = {"public": 0, "internal": 1}
MAX_ITEM_BYTES = 16_384
MAX_PACKAGE_BYTES = 65_536


def _schema(value: Any, schema: Any, label: str) -> None:
    try:
        errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    except Exception as exc:
        raise InvalidKnowledgeInput(f"{label} validation failed") from exc
    if errors:
        raise InvalidKnowledgeInput(f"{label} does not match its contract")


def _time(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise InvalidKnowledgeInput("knowledge timestamp is invalid") from exc
    return parsed


def item_content_material(value: dict[str, Any]) -> dict[str, Any]:
    material = thaw_json(value)
    material["integrity"]["item_content_sha256"] = "0" * 64
    return material


def package_content_material(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": value["schema_version"],
        "package_contract_identity": value["package_contract_identity"],
        "package_contract_version": value["package_contract_version"],
        "permitted_purpose": value["permitted_purpose"],
        "task_family": value["task_family"],
        "classification": value["classification"],
        "source_references": value["source_references"],
        "item_references": value["item_references"],
        "items": value["items"],
        "provenance_summary": value["provenance_summary"],
        "freshness_summary": value["freshness_summary"],
        "classification_summary": value["classification_summary"],
        "redaction_summary": value["redaction_summary"],
        "conflict_summary": value["conflict_summary"],
        "uncertainty_summary": value["uncertainty_summary"],
        "revocation_summary": value["revocation_summary"],
        "registry_sha256": value["integrity"]["registry_sha256"],
    }


def complete_package_material(value: dict[str, Any]) -> dict[str, Any]:
    material = thaw_json(value)
    material["integrity"]["complete_package_sha256"] = "0" * 64
    material["lineage"][-1]["output_sha256"] = "0" * 64
    return material


def validate_item(value: Any, registry: KnowledgeContractRegistry, *, validation_time: str) -> ValidatedKnowledgeItem:
    try:
        validate_json_value(value, maximum_bytes=MAX_ITEM_BYTES)
    except Exception as exc:
        raise InvalidKnowledgeInput("knowledge item is unsafe") from exc
    if not isinstance(value, dict):
        raise InvalidKnowledgeInput("knowledge item must be an object")
    registry.resolve_item(str(value.get("item_family", "")), str(value.get("item_family_version", "")))
    _schema(value, registry.schema("vss.knowledge_item/1").schema, "knowledge item")
    _schema(value["payload"], registry.schema("vss.reference_note/1").schema, "reference note")
    times = {name: _time(value[name]) for name in ("observed_at", "effective_from", "effective_until", "retrieved_at", "stale_after", "retention_until")}
    if not (times["effective_from"] <= times["observed_at"] <= times["retrieved_at"] < times["stale_after"] <= times["effective_until"] <= times["retention_until"]):
        raise InvalidKnowledgeInput("knowledge item temporal ordering is invalid")
    now = _time(validation_time)
    if value["lifecycle_status"] != "active" or now >= times["stale_after"]:
        raise InvalidKnowledgeInput("knowledge item is stale, revoked, or disabled")
    if value["trust"] != "approved_fixture" or value["permitted_purposes"] != ["local_validation_context"]:
        raise InvalidKnowledgeInput("knowledge item trust or purpose is not admitted")
    integrity = value["integrity"]
    if integrity["payload_sha256"] != canonical_digest(value["payload"]):
        raise KnowledgeIntegrityFailure("knowledge item payload integrity mismatch")
    if integrity["item_content_sha256"] != canonical_digest(item_content_material(value)):
        raise KnowledgeIntegrityFailure("knowledge item integrity mismatch")
    return ValidatedKnowledgeItem._create(value)


def validate_package(value: Any, registry: KnowledgeContractRegistry, *, validation_time: str) -> ValidatedKnowledgePackage:
    try:
        validate_json_value(value, maximum_bytes=MAX_PACKAGE_BYTES)
    except Exception as exc:
        raise InvalidKnowledgeInput("knowledge package is unsafe") from exc
    if not isinstance(value, dict):
        raise InvalidKnowledgeInput("knowledge package must be an object")
    registry.resolve_package(str(value.get("package_contract_identity", "")), str(value.get("package_contract_version", "")))
    _schema(value, registry.schema("vss.knowledge_package/1").schema, "knowledge package")
    constructed, expires, retention, now = map(_time, (value["constructed_at"], value["expires_at"], value["retention_until"], validation_time))
    if not constructed < expires <= retention or now >= expires or value["lifecycle_status"] != "validated":
        raise InvalidKnowledgeInput("knowledge package temporal or lifecycle state is invalid")
    items = [validate_item(item, registry, validation_time=validation_time) for item in value["items"]]
    item_values = [item.to_json_value() for item in items]
    item_ids = [item["item_id"] for item in item_values]
    if len(item_ids) != len(set(item_ids)) or value["item_references"] != item_ids:
        raise InvalidKnowledgeInput("knowledge package item references are invalid")
    maximum = max((item["classification"] for item in item_values), key=CLASSIFICATION_RANK.__getitem__)
    if value["classification"] != maximum or value["classification_summary"] != {"maximum": maximum, "item_count": len(items)}:
        raise InvalidKnowledgeInput("knowledge package classification is invalid")
    if any(value["permitted_purpose"] not in item["permitted_purposes"] for item in item_values):
        raise InvalidKnowledgeInput("knowledge package purpose is invalid")
    if value["revocation_summary"] != {"status": "none", "revoked_item_ids": []}:
        raise InvalidKnowledgeInput("knowledge package contains revoked lineage")
    conflicts = value["conflict_summary"]["conflicts"]
    if any(not set(conflict["item_ids"]).issubset(item_ids) for conflict in conflicts):
        raise InvalidKnowledgeInput("knowledge package conflict references are invalid")
    expected_conflict_status = "conflicts_present" if conflicts else "none_detected"
    if value["conflict_summary"]["status"] != expected_conflict_status:
        raise InvalidKnowledgeInput("knowledge package conflict summary is invalid")
    lineage = value["lineage"]
    step_ids = [step["step_id"] for step in lineage]
    expected_kinds = [kind for _ in item_values for kind in ("source", "normalized_payload", "validated_item")] + ["package_content", "complete_package"]
    if len(step_ids) != len(set(step_ids)) or [step["kind"] for step in lineage] != expected_kinds:
        raise InvalidKnowledgeInput("knowledge package lineage ordering is invalid")
    expected: list[tuple[str, str]] = []
    expected_step_items: list[str | None] = []
    for item in item_values:
        expected.extend([
            (item["integrity"]["source_sha256"], item["integrity"]["decoded_sha256"]),
            (item["integrity"]["decoded_sha256"], item["integrity"]["payload_sha256"]),
            (item["integrity"]["payload_sha256"], item["integrity"]["item_content_sha256"]),
        ])
        expected_step_items.extend([item["item_id"]] * 3)
    item_lineage_digest = item_values[0]["integrity"]["item_content_sha256"] if len(item_values) == 1 else canonical_digest([item["integrity"]["item_content_sha256"] for item in item_values])
    expected.extend([
        (item_lineage_digest, value["integrity"]["package_content_sha256"]),
        (value["integrity"]["package_content_sha256"], value["integrity"]["complete_package_sha256"]),
    ])
    expected_step_items.extend([None, None])
    if [(step["input_sha256"], step["output_sha256"]) for step in lineage] != expected:
        raise KnowledgeIntegrityFailure("knowledge package lineage mismatch")
    if [step["item_id"] for step in lineage] != expected_step_items:
        raise KnowledgeIntegrityFailure("knowledge package lineage item association mismatch")
    if value["integrity"]["registry_sha256"] != registry.digest:
        raise KnowledgeIntegrityFailure("knowledge registry integrity mismatch")
    if value["integrity"]["package_content_sha256"] != canonical_digest(package_content_material(value)):
        raise KnowledgeIntegrityFailure("knowledge package content integrity mismatch")
    if value["integrity"]["complete_package_sha256"] != canonical_digest(complete_package_material(value)):
        raise KnowledgeIntegrityFailure("knowledge package integrity mismatch")
    return ValidatedKnowledgePackage._create(value)
