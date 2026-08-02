from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from vss_reasoning_contracts import canonical_digest

from .errors import KnowledgeRegistryFailure, UnknownKnowledgeContract
from .models import KnowledgeRegistration, KnowledgeSchemaRecord

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_ROOT = Path(__file__).resolve().parents[2] / "schemas"
_MAX_SCHEMA_BYTES = 262_144
_FILES = MappingProxyType({
    "vss.knowledge_item/1": "knowledge-item-envelope-v1.schema.json",
    "vss.reference_note/1": "reference-note-v1.schema.json",
    "vss.knowledge_package/1": "knowledge-package-v1.schema.json",
})


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise KnowledgeRegistryFailure("knowledge schema contains duplicate keys")
        result[key] = value
    return result


def _references(value: Any, *, root: bool = True) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$dynamicRef", "$recursiveRef", "$anchor", "$dynamicAnchor"}:
                raise KnowledgeRegistryFailure("dynamic knowledge schema references are prohibited")
            if key == "$id" and not root:
                raise KnowledgeRegistryFailure("nested knowledge schema identities are prohibited")
            if key == "$ref" and isinstance(child, str):
                parsed = urlparse(child)
                if parsed.scheme or parsed.netloc or not child.startswith("#/"):
                    raise KnowledgeRegistryFailure("external knowledge schema references are prohibited")
            _references(child, root=False)
    elif isinstance(value, list):
        for child in value:
            _references(child, root=False)


def _resolve_pointer(schema: dict[str, Any], reference: str) -> Any:
    current: Any = schema
    for part in reference[2:].split("/"):
        token = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise KnowledgeRegistryFailure("knowledge schema reference is invalid")
        current = current[token]
    return current


def _reject_reference_cycles(schema: dict[str, Any]) -> None:
    def visit(value: Any, stack: frozenset[str]) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str):
                if reference in stack:
                    raise KnowledgeRegistryFailure("cyclic knowledge schema references are prohibited")
                visit(_resolve_pointer(schema, reference), stack | {reference})
            for key, child in value.items():
                if key != "$ref": visit(child, stack)
        elif isinstance(value, list):
            for child in value: visit(child, stack)
    visit(schema, frozenset())


def _load(root: Path, identity: str, filename: str) -> KnowledgeSchemaRecord:
    candidate = root / filename
    if candidate.is_symlink():
        raise KnowledgeRegistryFailure("knowledge schema symlinks are prohibited")
    descriptor = -1
    try:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise KnowledgeRegistryFailure("knowledge schema escapes trusted root")
        descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        mode = os.fstat(descriptor).st_mode
        raw = os.read(descriptor, _MAX_SCHEMA_BYTES + 1)
    except OSError as exc:
        raise KnowledgeRegistryFailure("knowledge schema is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not stat.S_ISREG(mode) or len(raw) > _MAX_SCHEMA_BYTES:
        raise KnowledgeRegistryFailure("knowledge schema is unsafe")
    try:
        schema = json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, json.JSONDecodeError) as exc:
        raise KnowledgeRegistryFailure("knowledge schema is invalid") from exc
    if not isinstance(schema, dict) or schema.get("$id") != identity or schema.get("$schema") != SCHEMA_DIALECT:
        raise KnowledgeRegistryFailure("knowledge schema identity or dialect mismatch")
    _references(schema)
    _reject_reference_cycles(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise KnowledgeRegistryFailure("knowledge schema is malformed") from exc
    return KnowledgeSchemaRecord(identity, resolved, hashlib.sha256(raw).hexdigest(), schema)


@dataclass(frozen=True, slots=True)
class KnowledgeContractRegistry:
    registrations: tuple[KnowledgeRegistration, ...] = field(default_factory=tuple)
    _schemas: Mapping[str, KnowledgeSchemaRecord] = field(init=False, repr=False)
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        root = _ROOT.resolve(strict=True)
        registrations = self.registrations or (KnowledgeRegistration(),)
        if registrations != (KnowledgeRegistration(),):
            raise KnowledgeRegistryFailure("knowledge registration is not repository admitted")
        schemas = {identity: _load(root, identity, filename) for identity, filename in _FILES.items()}
        object.__setattr__(self, "registrations", tuple(registrations))
        object.__setattr__(self, "_schemas", MappingProxyType(schemas))
        snapshot = {
            "registration": {name: getattr(registrations[0], name) for name in registrations[0].__dataclass_fields__},
            "schemas": {key: schemas[key].sha256 for key in sorted(schemas)},
        }
        object.__setattr__(self, "digest", canonical_digest(snapshot))

    @classmethod
    def built_in(cls) -> "KnowledgeContractRegistry":
        return cls()

    @property
    def schemas(self) -> Mapping[str, KnowledgeSchemaRecord]:
        return self._schemas

    def schema(self, identity: str) -> KnowledgeSchemaRecord:
        try:
            return self._schemas[identity]
        except KeyError as exc:
            raise UnknownKnowledgeContract("unknown knowledge schema") from exc

    def resolve_item(self, family: str, version: str) -> KnowledgeRegistration:
        registration = self.registrations[0]
        if (family, version) != (registration.item_family, registration.item_family_version):
            raise UnknownKnowledgeContract("unknown knowledge item contract")
        return registration

    def resolve_package(self, identity: str, version: str) -> KnowledgeRegistration:
        registration = self.registrations[0]
        if (identity, version) != (registration.package_identity, registration.package_version):
            raise UnknownKnowledgeContract("unknown knowledge package contract")
        return registration
