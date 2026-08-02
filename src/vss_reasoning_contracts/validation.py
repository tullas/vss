from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from .canonicalization import validate_json_value
from .constants import ADMITTED_LIFECYCLE_MODE, REQUEST_ENVELOPE_ID, RESULT_ENVELOPE_ID
from .errors import (
    InvalidSemanticInput,
    UnsafeSemanticContent,
    UnsupportedContractVersion,
)
from .models import ValidatedSemanticRequest, ValidatedSemanticResult
from .registry import SemanticContractRegistry


def _schema_validate(value: Any, schema: Any, kind: str) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.path),
    )
    if errors:
        raise InvalidSemanticInput(f"{kind} does not match its admitted contract")


def _ensure_unique_identities(value: dict[str, Any]) -> None:
    payload = value["payload"]
    groups = [payload.get("options", [])]
    common = payload.get("common_sections", {})
    groups.extend(
        common.get(name, [])
        for name in ("facts", "assumptions", "unknowns", "constraints", "limitations")
    )
    for group in groups:
        identities = [item.get("id") for item in group]
        if len(identities) != len(set(identities)):
            raise InvalidSemanticInput("semantic result contains duplicate identities")


def _validate_constraint_references(value: dict[str, Any]) -> None:
    payload = value["payload"]
    known = {item["id"] for item in payload["common_sections"]["constraints"]}
    for option in payload["options"]:
        satisfied = set(option["constraints_satisfied"])
        not_satisfied = set(option["constraints_not_satisfied"])
        if satisfied & not_satisfied:
            raise InvalidSemanticInput(
                "semantic option has contradictory constraint references"
            )
        if not (satisfied | not_satisfied).issubset(known):
            raise InvalidSemanticInput(
                "semantic option references an unknown constraint"
            )


def validate_request(
    value: Any, registry: SemanticContractRegistry
) -> ValidatedSemanticRequest:
    try:
        validate_json_value(
            value,
            maximum_bytes=max(
                item.maximum_request_bytes for item in registry.registrations
            ),
        )
    except UnsafeSemanticContent:
        raise
    if not isinstance(value, dict):
        raise InvalidSemanticInput("semantic request must be an object")
    if isinstance(value.get("schema_version"), str) and value["schema_version"] != "1":
        raise UnsupportedContractVersion(
            "unsupported semantic request-envelope version"
        )
    if all(
        isinstance(value.get(name), str)
        for name in (
            "task_identity",
            "task_version",
            "required_result_family",
            "required_result_version",
        )
    ):
        registry.resolve(
            value["task_identity"],
            value["task_version"],
            value["required_result_family"],
            value["required_result_version"],
        )
    envelope = registry.schema(
        f"vss.{REQUEST_ENVELOPE_ID}/{value.get('schema_version', '')}"
    )
    _schema_validate(value, envelope.schema, "semantic request envelope")
    if value["lifecycle_mode"] != ADMITTED_LIFECYCLE_MODE:
        raise InvalidSemanticInput("semantic lifecycle mode is not admitted")
    registration = registry.resolve(
        value["task_identity"],
        value["task_version"],
        value["required_result_family"],
        value["required_result_version"],
    )
    _schema_validate(
        value["payload"],
        registry.schema(registration.request_schema_identity).schema,
        "semantic task payload",
    )
    constraint_ids = [item["id"] for item in value["payload"]["constraints"]]
    if len(constraint_ids) != len(set(constraint_ids)):
        raise InvalidSemanticInput(
            "semantic request contains duplicate constraint identities"
        )
    return ValidatedSemanticRequest._from_validated_value(value)


def validate_result(
    value: Any, registry: SemanticContractRegistry
) -> ValidatedSemanticResult:
    try:
        validate_json_value(
            value,
            maximum_bytes=max(
                item.maximum_result_bytes for item in registry.registrations
            ),
        )
    except UnsafeSemanticContent:
        raise
    if not isinstance(value, dict):
        raise InvalidSemanticInput("semantic result must be an object")
    if isinstance(value.get("schema_version"), str) and value["schema_version"] != "1":
        raise UnsupportedContractVersion("unsupported semantic result-envelope version")
    if all(
        isinstance(value.get(name), str)
        for name in (
            "task_identity",
            "task_version",
            "object_family",
            "object_family_version",
        )
    ):
        registry.resolve(
            value["task_identity"],
            value["task_version"],
            value["object_family"],
            value["object_family_version"],
        )
    envelope = registry.schema(
        f"vss.{RESULT_ENVELOPE_ID}/{value.get('schema_version', '')}"
    )
    _schema_validate(value, envelope.schema, "semantic result envelope")
    registration = registry.resolve(
        value["task_identity"],
        value["task_version"],
        value["object_family"],
        value["object_family_version"],
    )
    if value["contract_identity"] != registration.result_schema_identity:
        raise InvalidSemanticInput("semantic result contract identity mismatch")
    _schema_validate(
        value["payload"],
        registry.schema(registration.result_schema_identity).schema,
        "semantic family payload",
    )
    _ensure_unique_identities(value)
    _validate_constraint_references(value)
    return ValidatedSemanticResult._from_validated_value(value)
