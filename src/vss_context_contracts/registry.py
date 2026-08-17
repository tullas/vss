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
from threading import Lock

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json

from .errors import ContextRegistryError
from .models import ContextRegistration, ContextSchemaRecord

_BUILT_IN: dict[tuple[type, str, tuple[Any, ...]], ContextContractRegistry] = {}
_BUILT_IN_LOCK = Lock()

_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_ROOT = Path(__file__).resolve().parents[2] / "schemas"
_FILES = MappingProxyType({
    "vss.context_assembly_request/1": "context-assembly-request-v1.schema.json",
    "vss.context_object/1": "context-object-v1.schema.json",
    "vss.generate_options_context/1": "generate-options-context-v1.schema.json",
    "vss.scene_breakdown_context/1": "scene-breakdown-context-v1.schema.json",
    "vss.scene_production_options_context/1": "scene-production-options-context-v1.schema.json",
    "vss.scene_production_options_context/2": "scene-production-options-context-v2.schema.json",
    "vss.character_continuity_context/1": "character-continuity-context-v1.schema.json",
    "vss.character_continuity_context/2": "character-continuity-context-v2.schema.json",
    "vss.shot_cinematography_context/1": "shot-cinematography-context-v1.schema.json",
    "vss.context_assembly_report/1": "context-assembly-report-v1.schema.json",
})


def _schema_metadata_fingerprint() -> tuple[Any, ...]:
    fingerprint = []
    for filename in _FILES.values():
        path = _ROOT / filename
        try:
            item = os.lstat(path)
            fingerprint.append((filename, item.st_mode, item.st_ino, item.st_size, item.st_mtime_ns))
        except OSError:
            fingerprint.append((filename, None))
    return tuple(fingerprint)


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
    _validators: Mapping[str, Draft202012Validator] = field(init=False, repr=False)
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        expected = (
            ContextRegistration("context_assembly_request", "1", "vss.context_assembly_request/1"),
            ContextRegistration("context_object", "1", "vss.context_object/1"),
            ContextRegistration("generate_options_context", "1", "vss.generate_options_context/1"),
            ContextRegistration("scene_breakdown_context", "1", "vss.scene_breakdown_context/1"),
            ContextRegistration("scene_production_options_context", "1", "vss.scene_production_options_context/1"),
            ContextRegistration("scene_production_options_context", "2", "vss.scene_production_options_context/2"),
            ContextRegistration("character_continuity_context", "1", "vss.character_continuity_context/1"),
            ContextRegistration("character_continuity_context", "2", "vss.character_continuity_context/2"),
            ContextRegistration("shot_cinematography_context", "1", "vss.shot_cinematography_context/1"),
            ContextRegistration("context_assembly_report", "1", "vss.context_assembly_report/1"),
        )
        registrations = self.registrations or expected
        if registrations != expected:
            raise ContextRegistryError("context registration is not repository admitted")
        schemas = {identity: _load(identity, filename) for identity, filename in _FILES.items()}
        object.__setattr__(self, "registrations", tuple(registrations))
        object.__setattr__(self, "_schemas", MappingProxyType(schemas))
        object.__setattr__(self, "_validators", MappingProxyType({
            identity: Draft202012Validator(thaw_json(record.schema))
            for identity, record in schemas.items()
        }))
        object.__setattr__(self, "digest", canonical_digest({
            "registrations": [r.__dict__ if hasattr(r, "__dict__") else {name: getattr(r, name) for name in r.__dataclass_fields__} for r in registrations],
            "schemas": {key: schemas[key].sha256 for key in sorted(schemas)},
            "compatibility": dict(self.compatibility()),
        }))

    @classmethod
    def built_in(cls) -> "ContextContractRegistry":
        key = (cls, str(_ROOT), _schema_metadata_fingerprint())
        registry = _BUILT_IN.get(key)
        if registry is None:
            with _BUILT_IN_LOCK:
                registry = _BUILT_IN.get(key)
                if registry is None:
                    registry = cls()
                    _BUILT_IN[key] = registry
        return registry

    def schema(self, identity: str) -> ContextSchemaRecord:
        try:
            return self._schemas[identity]
        except KeyError as exc:
            raise ContextRegistryError("unknown context schema") from exc

    def iter_errors(self, identity: str, value: Any):
        try:
            return self._validators[identity].iter_errors(value)
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
            "production_input_result": "scene_breakdown/1",
            "production_context": "scene_production_options_context/1",
            "production_task": "generate_scene_production_options/1",
            "production_result": "scene_production_option_set/1",
            "production_context_v2": "scene_production_options_context/2",
            "production_task_v2": "generate_scene_production_options/2",
            "production_result_v2": "scene_production_option_set/2",
            "production_purpose": "scene_production_options_local_validation",
            "production_environment": "development",
            "production_policy": "scene_production_options_context_local/1",
            "production_catalogue": "vss.scene-production-profiles.deterministic/1.0.0",
            "production_strategy": "vss.generate-scene-production-options.deterministic/1.0.0",
            "production_provider": "vss.reasoning.deterministic-scene-production-options/1.0.0",
            "production_provider_api": "1",
            "continuity_context": "character_continuity_context/1",
            "continuity_task": "analyze_character_continuity/2",
            "continuity_result": "character_continuity_observation_set/1",
            "continuity_purpose": "character_continuity_local_validation",
            "continuity_environment": "development",
            "continuity_policy": "character_continuity_context_local/1",
            "continuity_catalogue": "vss.character-continuity.rules.deterministic/1.0.0",
            "continuity_strategy": "vss.analyze-character-continuity.deterministic/1.0.0",
            "continuity_provider": "vss.reasoning.character-continuity.deterministic/1.0.0",
            "continuity_provider_api": "1",
            "continuity_analysis_context": "character_continuity_context/2",
            "continuity_analysis_task": "analyze_character_continuity/3",
            "continuity_transition_evidence": "character_continuity_transition_evidence/1",
            "continuity_analysis_catalogue": "vss.character-continuity.rules.deterministic/1.1.0",
            "continuity_analysis_strategy": "vss.analyze-character-continuity.deterministic/1.1.0",
            "continuity_analysis_provider": "vss.reasoning.character-continuity.deterministic/1.1.0",
            "shot_cinematography_context": "shot_cinematography_context/1",
            "shot_cinematography_observation_set": "shot_cinematography_observation_set/1",
            "shot_cinematography_purpose": "shot_cinematography_local_analysis",
            "shot_cinematography_policy": "shot_cinematography_context_local/1",
        })
