from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .constants import (
    MAX_CONTAINER_ITEMS,
    MAX_INPUT_BYTES,
    MAX_NESTING_DEPTH,
    MAX_OUTPUT_BYTES,
    MAX_STRING_LENGTH,
    MAX_TOTAL_NODES,
)


class SDKValidationError(ValueError):
    pass


def validate_json_value(value: Any, *, maximum_bytes: int) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_TOTAL_NODES:
            raise SDKValidationError("value contains too many items")
        if depth > MAX_NESTING_DEPTH:
            raise SDKValidationError("value exceeds the nesting limit")
        if item is None or isinstance(item, (bool, int)):
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise SDKValidationError("value contains a non-JSON number")
            return
        if isinstance(item, str):
            if len(item) > MAX_STRING_LENGTH:
                raise SDKValidationError("value contains an oversized string")
            return
        if isinstance(item, list):
            if len(item) > MAX_CONTAINER_ITEMS:
                raise SDKValidationError("value contains too many list items")
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, dict):
            if len(item) > MAX_CONTAINER_ITEMS:
                raise SDKValidationError("value contains too many object fields")
            for key, child in item.items():
                if not isinstance(key, str):
                    raise SDKValidationError("object keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
            return
        raise SDKValidationError("value contains a non-JSON type")

    visit(value, 0)
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SDKValidationError("value is not JSON serializable") from exc
    if len(encoded) > maximum_bytes:
        raise SDKValidationError("value exceeds the serialized size limit")


def _validate_schema(value: Any, schema: dict[str, Any], kind: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise SDKValidationError(f"{kind} does not match its schema: {errors[0].message}")


def validate_input(value: Any, schema: dict[str, Any]) -> dict[str, Any]:
    validate_json_value(value, maximum_bytes=MAX_INPUT_BYTES)
    _validate_schema(value, schema, "input")
    if not isinstance(value, dict):
        raise SDKValidationError("capability input must be an object")
    return value


def validate_output(value: Any, schema: dict[str, Any]) -> dict[str, Any]:
    validate_json_value(value, maximum_bytes=MAX_OUTPUT_BYTES)
    _validate_schema(value, schema, "output")
    if not isinstance(value, dict):
        raise SDKValidationError("capability output must be an object")
    return value


def validate_manifest(manifest_path: Path, schema_path: Path):
    """Validate an authored manifest through the production runtime validator."""
    from vss_runtime.manifest import load_manifest

    return load_manifest(manifest_path, schema_path)[0]
