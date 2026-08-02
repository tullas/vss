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
from .errors import InvalidSemanticInput, UnsafeSemanticContent


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InvalidSemanticInput("JSON document contains duplicate object keys")
        value[key] = item
    return value


def load_json_document(document: str | bytes) -> Any:
    """Decode JSON without silently accepting duplicate keys or non-finite values."""
    if type(document) not in (str, bytes):
        raise InvalidSemanticInput("JSON document must be text or bytes")
    try:
        return json.loads(
            document,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                UnsafeSemanticContent("JSON document contains a non-finite number")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidSemanticInput("JSON document is invalid") from exc


def validate_json_value(value: Any, *, maximum_bytes: int) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_TOTAL_NODES:
            raise UnsafeSemanticContent("semantic value contains too many items")
        if depth > MAX_NESTING_DEPTH:
            raise UnsafeSemanticContent("semantic value exceeds the nesting limit")
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            if abs(item) > MAX_INTEGER_ABS:
                raise UnsafeSemanticContent(
                    "semantic value contains an oversized integer"
                )
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise UnsafeSemanticContent(
                    "semantic value contains a non-finite number"
                )
            return
        if type(item) is str:
            if len(item) > MAX_STRING_LENGTH:
                raise UnsafeSemanticContent(
                    "semantic value contains an oversized string"
                )
            return
        if type(item) is list:
            if len(item) > MAX_LIST_ITEMS:
                raise UnsafeSemanticContent(
                    "semantic value contains too many list items"
                )
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            if len(item) > MAX_OBJECT_PROPERTIES:
                raise UnsafeSemanticContent(
                    "semantic value contains too many object fields"
                )
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
            plain,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise UnsafeSemanticContent("semantic value is not canonical JSON") from exc


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def freeze_json(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: freeze_json(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(freeze_json(item) for item in value)
    return value


def thaw_json(value: Any) -> Any:
    if type(value) is dict or isinstance(value, MappingProxyType):
        return {key: thaw_json(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [thaw_json(item) for item in value]
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise UnsafeSemanticContent("semantic value contains an unsupported immutable type")
