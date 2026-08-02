from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from vss_knowledge_contracts import KnowledgeContractRegistry, KnowledgeRevocationRegistry, validate_package
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import validate_json_value

from .errors import ContextContractError, ContextIntegrityFailure, InvalidContextInput
from .limits import MAX_CONTEXT_BYTES, MAX_REPORT_BYTES, MAX_REQUEST_BYTES
from .models import ValidatedAssemblyReport, ValidatedContext
from .registry import ContextContractRegistry


def _schema(value: Any, schema: Any, message: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
    if errors:
        raise InvalidContextInput(message)


def parse_utc(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise InvalidContextInput("context timestamp is invalid") from exc


def validate_request(value: Any, registry: ContextContractRegistry) -> dict[str, Any]:
    try:
        validate_json_value(value, maximum_bytes=MAX_REQUEST_BYTES)
    except Exception as exc:
        raise InvalidContextInput("context request is unsafe") from exc
    if not isinstance(value, dict):
        raise InvalidContextInput("context request must be an object")
    _schema(value, registry.schema("vss.context_assembly_request/1").schema, "context request is invalid")
    if value["semantic_task"] != "generate_options" or value["semantic_task_version"] != "1" or value["context_family"] != "generate_options_context" or value["context_family_version"] != "1":
        raise InvalidContextInput("context task and family are incompatible")
    if value["policy_identity"] != "generate_options_context_local" or value["policy_version"] != "1" or value["purpose"] != "generate_options_local_validation" or value["environment"] != "development" or value["classification_ceiling"] not in {"public", "internal"} or value["minimum_trust"] != "approved_fixture":
        raise InvalidContextInput("context policy is not admitted")
    package_ids = [item["package_id"] for item in value["package_requirements"]]
    if len(package_ids) != len(set(package_ids)):
        raise InvalidContextInput("context package requirements are duplicated")
    item_ids = [item["item_id"] for item in value["item_requirements"]]
    if len(item_ids) != len(set(item_ids)):
        raise InvalidContextInput("context item requirements are duplicated")
    parse_utc(value["validation_time"])
    if value["lifecycle"] != "requested":
        raise InvalidContextInput("context request lifecycle is invalid")
    return value


def validate_context(value: Any, registry: ContextContractRegistry) -> ValidatedContext:
    try:
        validate_json_value(value, maximum_bytes=MAX_CONTEXT_BYTES)
    except Exception as exc:
        raise InvalidContextInput("context is unsafe") from exc
    if not isinstance(value, dict):
        raise InvalidContextInput("context must be an object")
    _schema(value, registry.schema("vss.context_object/1").schema, "context is invalid")
    _schema(value["payload"], registry.schema("vss.generate_options_context/1").schema, "context payload is invalid")
    if value["context_family"] != "generate_options_context" or value["context_family_version"] != "1" or value["purpose"] != "generate_options_local_validation" or value["semantic_task"] != "generate_options" or value["semantic_task_version"] != "1" or value["lifecycle"] != "validated":
        raise InvalidContextInput("context compatibility is invalid")
    if value["classification"] not in {"public", "internal"}:
        raise InvalidContextInput("context classification is invalid")
    if canonical_digest(value["payload"]) != value["context_content_digest"]:
        raise ContextIntegrityFailure("context content digest mismatch")
    if parse_utc(value["constructed_at"]) >= parse_utc(value["expires_at"]):
        raise InvalidContextInput("context expiry is invalid")
    material = dict(value)
    integrity = dict(material["integrity"])
    expected = integrity.pop("complete_context_sha256")
    material["integrity"] = integrity
    if expected != canonical_digest(material):
        raise ContextIntegrityFailure("context integrity mismatch")
    return ValidatedContext.create(value)


def validate_report(value: Any, registry: ContextContractRegistry) -> ValidatedAssemblyReport:
    if not isinstance(value, dict):
        raise InvalidContextInput("assembly report must be an object")
    # The report envelope has more governance counters than the shared semantic
    # object-field limit; its schema bounds every collection and its canonical
    # byte limit remains enforced here.
    from vss_reasoning_contracts import canonical_bytes
    try:
        if len(canonical_bytes(value)) > MAX_REPORT_BYTES:
            raise ValueError
    except Exception as exc:
        raise InvalidContextInput("assembly report is unsafe") from exc
    _schema(value, registry.schema("vss.context_assembly_report/1").schema, "assembly report is invalid")
    material = dict(value)
    integrity = dict(material["integrity"])
    expected = integrity.pop("complete_report_sha256")
    material["integrity"] = integrity
    if expected != canonical_digest(material):
        raise ContextIntegrityFailure("assembly report integrity mismatch")
    return ValidatedAssemblyReport.create(value)


def revalidate_package(value: dict[str, Any], validation_time: str) -> dict[str, Any]:
    package = validate_package(value, KnowledgeContractRegistry.built_in(), validation_time=validation_time, revocations=KnowledgeRevocationRegistry.built_in())
    return package.to_json_value()
