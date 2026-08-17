from __future__ import annotations

import hashlib
import json
import os
import stat
from threading import Lock
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .canonicalization import canonical_digest, thaw_json
from .constants import (
    ACTIVE_LIFECYCLE,
    CONTRACT_VERSION,
    GENERATE_OPTIONS_TASK,
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    OPTION_SET_FAMILY,
    REQUEST_ENVELOPE_ID,
    RESULT_ENVELOPE_ID,
    SCHEMA_DIALECT,
)
from .errors import (
    ContractDisabled,
    IncompatibleContract,
    InvalidContractSchema,
    RegistryIntegrityError,
    UnknownContractIdentity,
    UnsupportedContractVersion,
)
from .models import ContractRegistration, SchemaRecord

_SCHEMA_FILES = MappingProxyType(
    {
        "vss.semantic_request/1": "semantic-request-v1.schema.json",
        "vss.semantic_result/1": "semantic-result-v1.schema.json",
        "vss.generate_options/1": "generate-options-v1.schema.json",
        "vss.option_set/1": "option-set-v1.schema.json",
    }
)
_TRUSTED_SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas"
_MAX_SCHEMA_BYTES = 262_144
_BUILT_IN = {}
_BUILT_IN_LOCK = Lock()


def _schema_metadata_fingerprint(root: Path) -> tuple[Any, ...]:
    """Cheaply detect repository-schema replacement before reusing a cache entry."""
    fingerprint = []
    for filename in _SCHEMA_FILES.values():
        path = root / filename
        try:
            item = os.lstat(path)
            fingerprint.append((filename, item.st_mode, item.st_ino, item.st_size, item.st_mtime_ns))
        except OSError:
            fingerprint.append((filename, None))
    return tuple(fingerprint)


def _reject_external_references(value: Any, *, root: bool = True) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$dynamicRef", "$recursiveRef"}:
                raise InvalidContractSchema("dynamic semantic schema references are prohibited")
            if key in {"$anchor", "$dynamicAnchor"} or (key == "$id" and not root):
                raise InvalidContractSchema("semantic schema reference anchors are prohibited")
            if key == "$ref" and isinstance(child, str):
                parsed = urlparse(child)
                if parsed.scheme or parsed.netloc or not child.startswith("#/"):
                    raise InvalidContractSchema(
                        "external schema references are prohibited"
                    )
            _reject_external_references(child, root=False)
    elif isinstance(value, list):
        for child in value:
            _reject_external_references(child, root=False)


def _resolve_pointer(schema: dict[str, Any], reference: str) -> Any:
    current: Any = schema
    for part in reference[2:].split("/"):
        token = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise InvalidContractSchema("semantic schema reference is invalid")
        current = current[token]
    return current


def _reject_reference_cycles(schema: dict[str, Any]) -> None:
    def visit(value: Any, reference_stack: frozenset[str]) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str):
                if reference in reference_stack:
                    raise InvalidContractSchema(
                        "cyclic semantic schema references are prohibited"
                    )
                visit(
                    _resolve_pointer(schema, reference), reference_stack | {reference}
                )
            for key, child in value.items():
                if key != "$ref":
                    visit(child, reference_stack)
        elif isinstance(value, list):
            for child in value:
                visit(child, reference_stack)

    visit(schema, frozenset())


def _load_schema(root: Path, identity: str, filename: str) -> SchemaRecord:
    candidate = root / filename
    if candidate.is_symlink():
        raise InvalidContractSchema("semantic schema symlinks are prohibited")
    try:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise InvalidContractSchema("semantic schema escapes the trusted root")
        descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            mode = os.fstat(descriptor).st_mode
            raw = handle.read(_MAX_SCHEMA_BYTES + 1)
    except OSError as exc:
        raise InvalidContractSchema("semantic schema is unavailable") from exc
    if not stat.S_ISREG(mode):
        raise InvalidContractSchema("semantic schema escapes the trusted root")
    if len(raw) > _MAX_SCHEMA_BYTES:
        raise InvalidContractSchema("semantic schema exceeds the size limit")
    try:
        schema = json.loads(raw, object_pairs_hook=_reject_schema_duplicate_keys)
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidContractSchema("semantic schema is invalid") from exc
    if not isinstance(schema, dict) or schema.get("$id") != identity:
        raise InvalidContractSchema("semantic schema identity mismatch")
    if schema.get("$schema") != SCHEMA_DIALECT:
        raise InvalidContractSchema("unsupported semantic schema dialect")
    _reject_external_references(schema)
    _reject_reference_cycles(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise InvalidContractSchema("semantic schema is malformed") from exc
    name, version = identity.rsplit("/", 1)
    return SchemaRecord(
        name, version, identity, resolved, hashlib.sha256(raw).hexdigest(), schema
    )


def _reject_schema_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InvalidContractSchema(
                "semantic schema contains duplicate object keys"
            )
        value[key] = item
    return value


@dataclass(frozen=True, slots=True)
class SemanticContractRegistry:
    registrations: tuple[ContractRegistration, ...] = field(default_factory=tuple)
    schema_root: Path = field(default=_TRUSTED_SCHEMA_ROOT, init=False)
    _schemas: Mapping[str, SchemaRecord] = field(init=False, repr=False)
    _contracts: Mapping[tuple[str, str], ContractRegistration] = field(
        init=False, repr=False
    )
    _validators: Mapping[str, Draft202012Validator] = field(init=False, repr=False)
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        try:
            root = _TRUSTED_SCHEMA_ROOT.resolve(strict=True)
        except OSError as exc:
            raise InvalidContractSchema("semantic schema root is unavailable") from exc
        if not root.is_dir():
            raise InvalidContractSchema("semantic schema root is not a directory")
        object.__setattr__(self, "schema_root", root)
        registrations = self.registrations or (_default_registration(),)
        object.__setattr__(self, "registrations", tuple(registrations))

        schemas: dict[str, SchemaRecord] = {}
        schema_paths: set[Path] = set()
        for identity, filename in _SCHEMA_FILES.items():
            record = _load_schema(root, identity, filename)
            if identity in schemas or record.path in schema_paths:
                raise RegistryIntegrityError("duplicate semantic schema identity")
            schemas[identity] = record
            schema_paths.add(record.path)

        contracts: dict[tuple[str, str], ContractRegistration] = {}
        families: set[tuple[str, str]] = set()
        admitted = _default_registration()
        for registration in registrations:
            key = (registration.task_identity, registration.task_version)
            family_key = (registration.result_family, registration.result_version)
            if key in contracts:
                raise RegistryIntegrityError(
                    "duplicate semantic task identity and version"
                )
            if family_key in families:
                raise RegistryIntegrityError(
                    "duplicate semantic family identity and version"
                )
            if registration.lifecycle_status not in {
                "active",
                "deprecated",
                "disabled",
            }:
                raise RegistryIntegrityError("unknown semantic contract lifecycle")
            if replace_lifecycle(registration, admitted.lifecycle_status) != admitted:
                raise RegistryIntegrityError(
                    "semantic registration is not repository admitted"
                )
            for schema_identity in (
                registration.request_schema_identity,
                registration.result_schema_identity,
                f"vss.{REQUEST_ENVELOPE_ID}/{registration.request_envelope_version}",
                f"vss.{RESULT_ENVELOPE_ID}/{registration.result_envelope_version}",
            ):
                if schema_identity not in schemas:
                    raise RegistryIntegrityError(
                        "semantic registration references an unknown schema"
                    )
            contracts[key] = registration
            families.add(family_key)

        object.__setattr__(self, "_schemas", MappingProxyType(schemas))
        object.__setattr__(self, "_contracts", MappingProxyType(contracts))
        object.__setattr__(self, "_validators", MappingProxyType({
            identity: Draft202012Validator(thaw_json(record.schema))
            for identity, record in schemas.items()
        }))
        snapshot = {
            "registrations": [registration_to_json(item) for item in registrations],
            "schemas": {key: schemas[key].sha256 for key in sorted(schemas)},
        }
        object.__setattr__(self, "digest", canonical_digest(snapshot))

    @classmethod
    def built_in(cls) -> "SemanticContractRegistry":
        root = _TRUSTED_SCHEMA_ROOT
        key = (cls, str(root), _schema_metadata_fingerprint(root))
        registry = _BUILT_IN.get(key)
        if registry is None:
            with _BUILT_IN_LOCK:
                registry = _BUILT_IN.get(key)
                if registry is None:
                    registry = cls()
                    _BUILT_IN[key] = registry
        return registry

    @property
    def schemas(self) -> Mapping[str, SchemaRecord]:
        return self._schemas

    def resolve(
        self,
        task_identity: str,
        task_version: str,
        result_family: str,
        result_version: str,
        *,
        allow_deprecated: bool = False,
    ) -> ContractRegistration:
        registration = self._contracts.get((task_identity, task_version))
        if registration is None:
            known_identity = any(
                identity == task_identity for identity, _ in self._contracts
            )
            if known_identity:
                raise UnsupportedContractVersion("unsupported semantic task version")
            raise UnknownContractIdentity("unknown semantic task identity")
        if (registration.result_family, registration.result_version) != (
            result_family,
            result_version,
        ):
            known_family = any(
                item.result_family == result_family for item in self._contracts.values()
            )
            if known_family and registration.result_family == result_family:
                raise UnsupportedContractVersion(
                    "unsupported semantic result-family version"
                )
            raise IncompatibleContract(
                "semantic task and result family are incompatible"
            )
        if registration.lifecycle_status == "disabled":
            raise ContractDisabled("semantic contract is disabled")
        if registration.lifecycle_status == "deprecated" and not allow_deprecated:
            raise ContractDisabled("deprecated semantic contract is not admitted")
        return registration

    def schema(self, identity: str) -> SchemaRecord:
        try:
            return self._schemas[identity]
        except KeyError as exc:
            raise UnknownContractIdentity("unknown semantic schema identity") from exc

    def iter_errors(self, identity: str, value: Any):
        try:
            return self._validators[identity].iter_errors(value)
        except KeyError as exc:
            raise UnknownContractIdentity("unknown semantic schema identity") from exc


def _default_registration() -> ContractRegistration:
    return ContractRegistration(
        task_identity=GENERATE_OPTIONS_TASK,
        task_version=CONTRACT_VERSION,
        result_family=OPTION_SET_FAMILY,
        result_version=CONTRACT_VERSION,
        request_envelope_version=CONTRACT_VERSION,
        result_envelope_version=CONTRACT_VERSION,
        lifecycle_status=ACTIVE_LIFECYCLE,
        request_schema_identity="vss.generate_options/1",
        result_schema_identity="vss.option_set/1",
        owner="vss-runtime-architecture",
        maximum_request_bytes=MAX_REQUEST_BYTES,
        maximum_result_bytes=MAX_RESULT_BYTES,
    )


def replace_lifecycle(
    value: ContractRegistration, lifecycle_status: str
) -> ContractRegistration:
    """Normalize the only registry field varied by lifecycle-policy tests."""
    return ContractRegistration(
        task_identity=value.task_identity,
        task_version=value.task_version,
        result_family=value.result_family,
        result_version=value.result_version,
        request_envelope_version=value.request_envelope_version,
        result_envelope_version=value.result_envelope_version,
        lifecycle_status=lifecycle_status,
        request_schema_identity=value.request_schema_identity,
        result_schema_identity=value.result_schema_identity,
        owner=value.owner,
        maximum_request_bytes=value.maximum_request_bytes,
        maximum_result_bytes=value.maximum_result_bytes,
        deprecated_after=value.deprecated_after,
    )


def registration_to_json(value: ContractRegistration) -> dict[str, Any]:
    return {
        "task_identity": value.task_identity,
        "task_version": value.task_version,
        "result_family": value.result_family,
        "result_version": value.result_version,
        "request_envelope_version": value.request_envelope_version,
        "result_envelope_version": value.result_envelope_version,
        "lifecycle_status": value.lifecycle_status,
        "request_schema_identity": value.request_schema_identity,
        "result_schema_identity": value.result_schema_identity,
        "owner": value.owner,
        "maximum_request_bytes": value.maximum_request_bytes,
        "maximum_result_bytes": value.maximum_result_bytes,
        "deprecated_after": value.deprecated_after,
    }
