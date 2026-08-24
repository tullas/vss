import hashlib
import json
import os
import stat
from pathlib import Path
from threading import Lock
from types import MappingProxyType

from jsonschema import Draft202012Validator

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json

from .errors import ResourceContractError, ResourceRegistryError
from .models import ResourceRegistration


ROOT = Path(__file__).resolve().parents[2] / "schemas"
FILES = MappingProxyType({
    "production_resource_artifact/1": "production-resource-artifact-v1.schema.json",
    "reusable_asset_admission/1": "reusable-asset-admission-v1.schema.json",
    "reusable_asset/1": "reusable-asset-v1.schema.json",
    "resource_resolution_request/1": "resource-resolution-request-v1.schema.json",
    "resource_resolution_result/1": "resource-resolution-result-v1.schema.json",
})
BUILT_IN_REGISTRY_SHA256 = "9e88806d679c218c3ffaffd3055b4d3ebd9650458777245b2934e89e5b875a60"  # pragma: allowlist secret
_BUILT_IN = {}
_LOCK = Lock()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResourceRegistryError("resource schema has duplicate keys")
        result[key] = value
    return result


def _fingerprint():
    result = []
    for filename in FILES.values():
        try:
            item = os.lstat(ROOT / filename)
            result.append((filename, item.st_mode, item.st_ino, item.st_size, item.st_mtime_ns))
        except OSError:
            result.append((filename, None))
    return tuple(result)


def _load(identity, filename):
    path = ROOT / filename
    if path.is_symlink():
        raise ResourceRegistryError("resource schema symlink rejected")
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(ROOT):
            raise ResourceRegistryError("resource schema escapes root")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ResourceRegistryError("resource schema is not regular")
            raw = os.read(descriptor, 262145)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ResourceRegistryError("resource schema unavailable") from exc
    if len(raw) > 262144:
        raise ResourceRegistryError("resource schema too large")
    try:
        schema = json.loads(raw, object_pairs_hook=_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception as exc:
        raise ResourceRegistryError("resource schema invalid") from exc
    if schema.get("$id") != f"vss.resource.{identity}":
        raise ResourceRegistryError("resource schema identity mismatch")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ResourceRegistryError("resource schema dialect invalid")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ResourceRegistryError("resource schema malformed") from exc
    return {"identity": identity, "sha256": hashlib.sha256(raw).hexdigest(),
            "schema": freeze_json(schema)}


class ResourceContractRegistry:
    __slots__ = ("registrations", "schemas", "digest", "_validators")

    def __init__(self):
        registrations = tuple(ResourceRegistration(
            identity, identity.rsplit("/", 1)[1], f"vss.resource.{identity}"
        ) for identity in FILES)
        schemas = {identity: _load(identity, filename) for identity, filename in FILES.items()}
        self.registrations = registrations
        self.schemas = freeze_json(schemas)
        self._validators = MappingProxyType({
            identity: Draft202012Validator(thaw_json(record["schema"]))
            for identity, record in schemas.items()
        })
        self.digest = canonical_digest({
            "registry": "resource_contract_registry/1",
            "registrations": [
                {"identity": item.identity, "version": item.version,
                 "schema_identity": item.schema_identity, "lifecycle": item.lifecycle,
                 "owner": item.owner}
                for item in registrations
            ],
            "schemas": {key: value["sha256"] for key, value in sorted(schemas.items())},
        })
        if self.digest != BUILT_IN_REGISTRY_SHA256:
            raise ResourceRegistryError("resource registry digest does not match reviewed pin")

    @classmethod
    def built_in(cls):
        key = (cls, str(ROOT), _fingerprint())
        registry = _BUILT_IN.get(key)
        if registry is None:
            with _LOCK:
                registry = _BUILT_IN.get(key)
                if registry is None:
                    registry = cls()
                    _BUILT_IN[key] = registry
        return registry

    def resolve(self, identity, version=None):
        if not isinstance(identity, str) or not identity or "*" in identity or identity.endswith("latest"):
            raise ResourceContractError("unknown resource contract")
        qualified = identity if version is None else f"{identity}/{version}"
        for registration in self.registrations:
            if registration.identity == qualified:
                return registration
        raise ResourceContractError("unknown resource contract")

    def iter_errors(self, identity, value):
        self.resolve(identity)
        return self._validators[identity].iter_errors(value)
