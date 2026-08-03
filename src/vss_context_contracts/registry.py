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

from vss_reasoning_contracts import canonical_digest

from .errors import ContextRegistryError
from .models import ContextRegistration, ContextSchemaRecord

_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_ROOT = Path(__file__).resolve().parents[2] / "schemas"
_FILES = MappingProxyType({
    "vss.context_assembly_request/1": "context-assembly-request-v1.schema.json",
    "vss.context_object/1": "context-object-v1.schema.json",
    "vss.generate_options_context/1": "generate-options-context-v1.schema.json",
    "vss.scene_breakdown_context/1": "scene-breakdown-context-v1.schema.json",
    "vss.context_assembly_report/1": "context-assembly-report-v1.schema.json",
})


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContextRegistryError("context schema contains duplicate keys")
        out[key] = value
    return out


def _refs(value: Any, root: bool = True) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$dynamicRef", "$recursiveRef", "$anchor", "$dynamicAnchor"}:
                raise ContextRegistryError("dynamic context schema references are prohibited")
            if key == "$id" and not root:
                raise ContextRegistryError("nested context schema identities are prohibited")
            if key == "$ref" and isinstance(child, str):
                parsed = urlparse(child)
                if parsed.scheme or parsed.netloc or not child.startswith("#/"):
                    raise ContextRegistryError("external context schema references are prohibited")
            _refs(child, False)
    elif isinstance(value, list):
        for child in value:
            _refs(child, False)


def _load(identity: str, filename: str) -> ContextSchemaRecord:
    root = _ROOT.resolve(strict=True)
    candidate = root / filename
    if candidate.is_symlink():
        raise ContextRegistryError("context schema symlinks are prohibited")
    descriptor = -1
    raw = b""
    try:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ContextRegistryError("context schema escapes trusted root")
        expected = resolved.stat()
        descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino) or not stat.S_ISREG(opened.st_mode):
            raise ContextRegistryError("context schema changed or is not regular")
        raw = os.read(descriptor, 262145)
    except OSError as exc:
        raise ContextRegistryError("context schema is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(raw) > 262144:
        raise ContextRegistryError("context schema exceeds its bound")
    try:
        schema = json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(schema, dict) or schema.get("$id") != identity or schema.get("$schema") != _DIALECT:
            raise ValueError
        _refs(schema)
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ContextRegistryError("context schema is invalid") from exc
    return ContextSchemaRecord(identity, hashlib.sha256(raw).hexdigest(), schema)


@dataclass(frozen=True, slots=True)
class ContextContractRegistry:
    registrations: tuple[ContextRegistration, ...] = field(default_factory=tuple)
    _schemas: Mapping[str, ContextSchemaRecord] = field(init=False, repr=False)
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        expected = (
            ContextRegistration("context_assembly_request", "1", "vss.context_assembly_request/1"),
            ContextRegistration("context_object", "1", "vss.context_object/1"),
            ContextRegistration("generate_options_context", "1", "vss.generate_options_context/1"),
            ContextRegistration("scene_breakdown_context", "1", "vss.scene_breakdown_context/1"),
            ContextRegistration("context_assembly_report", "1", "vss.context_assembly_report/1"),
        )
        registrations = self.registrations or expected
        if registrations != expected:
            raise ContextRegistryError("context registration is not repository admitted")
        schemas = {identity: _load(identity, filename) for identity, filename in _FILES.items()}
        object.__setattr__(self, "registrations", tuple(registrations))
        object.__setattr__(self, "_schemas", MappingProxyType(schemas))
        object.__setattr__(self, "digest", canonical_digest({
            "registrations": [r.__dict__ if hasattr(r, "__dict__") else {name: getattr(r, name) for name in r.__dataclass_fields__} for r in registrations],
            "schemas": {key: schemas[key].sha256 for key in sorted(schemas)},
            "compatibility": {"generate_options/1": {"context": "generate_options_context/1", "knowledge": "knowledge_package/1", "item": "reference_note/1", "purpose": "local_validation_context"}},
        }))

    @classmethod
    def built_in(cls) -> "ContextContractRegistry":
        return cls()

    def schema(self, identity: str) -> ContextSchemaRecord:
        try:
            return self._schemas[identity]
        except KeyError as exc:
            raise ContextRegistryError("unknown context schema") from exc

    def resolve(self, identity: str, version: str) -> ContextRegistration:
        for registration in self.registrations:
            if registration.identity == identity and registration.version == version:
                return registration
        raise ContextRegistryError("unknown context contract")

    def compatibility(self) -> Mapping[str, str]:
        return MappingProxyType({
            "semantic_task": "generate_options/1",
            "result_family": "option_set/1",
            "context_family": "generate_options_context/1",
            "knowledge_package": "knowledge_package/1",
            "knowledge_item": "reference_note/1",
            "package_purpose": "local_validation_context",
            "context_purpose": "generate_options_local_validation",
            "policy": "generate_options_context_local/1",
            "scene_breakdown": "scene_breakdown_context/1",
            "scene_breakdown_policy": "scene_breakdown_context_local/1",
            "scene_breakdown_strategy": "vss.break-down-scenes.deterministic/1.0.0",
            "scene_breakdown_provider": "vss.reasoning.deterministic-scene-breakdown/1.0.0",
        })
