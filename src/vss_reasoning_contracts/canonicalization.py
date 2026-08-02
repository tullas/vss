from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from .constants import (
    MAX_INTEGER_ABS,
    MAX_LIST_ITEMS,
    MAX_NESTING_DEPTH,
    MAX_OBJECT_PROPERTIES,
    MAX_STRING_LENGTH,
    MAX_TOTAL_NODES,
)
from .errors import UnsafeSemanticContent


def validate_json_value(value: Any, *, maximum_bytes: int) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_TOTAL_NODES:
            raise UnsafeSemanticContent("semantic value contains too many items")
        if depth > MAX_NESTING_DEPTH:
            raise UnsafeSemanticContent("semantic value exceeds the nesting limit")
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, int):
            if abs(item) > MAX_INTEGER_ABS:
                raise UnsafeSemanticContent("semantic value contains an oversized integer")
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise UnsafeSemanticContent("semantic value contains a non-finite number")
            return
        if isinstance(item, str):
            if len(item) > MAX_STRING_LENGTH:
                raise UnsafeSemanticContent("semantic value contains an oversized string")
            return
        if isinstance(item, list):
            if len(item) > MAX_LIST_ITEMS:
                raise UnsafeSemanticContent("semantic value contains too many list items")
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, dict):
            if len(item) > MAX_OBJECT_PROPERTIES:
                raise UnsafeSemanticContent("semantic value contains too many object fields")
            for key, child in item.items():
                if not isinstance(key, str):
                    raise UnsafeSemanticContent("semantic object keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
            return
        raise UnsafeSemanticContent("semantic value contains a non-JSON type")

    visit(value, 0)
    encoded = canonical_bytes(value)
    if len(encoded) > maximum_bytes:
        raise UnsafeSemanticContent("semantic value exceeds the serialized size limit")


def canonical_bytes(value: Any) -> bytes:
    plain = thaw_json(value)
    try:
        return json.dumps(
            plain, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise UnsafeSemanticContent("semantic value is not canonical JSON") from exc


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_json(item) for item in value)
    return value


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw_json(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise UnsafeSemanticContent("semantic value contains an unsupported immutable type")
