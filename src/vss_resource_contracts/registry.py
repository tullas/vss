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
    "creative_decision_revision/1": "creative-decision-revision-v1.schema.json",
    "creative_decision_revision/2": "creative-decision-revision-v2.schema.json",
    "canon_snapshot/1": "canon-snapshot-v1.schema.json",
    "canon_snapshot/2": "canon-snapshot-v2.schema.json",
    "production_canon_binding/1": "production-canon-binding-v1.schema.json",
    "production_canon_binding/2": "production-canon-binding-v2.schema.json",
    "production_visual_grounding_profile/1": "production-visual-grounding-profile-v1.schema.json",
    "production_visual_grounding_review/1": "production-visual-grounding-review-v1.schema.json",
    "dependency_impact_request/1": "dependency-impact-request-v1.schema.json",
    "dependency_impact_result/1": "dependency-impact-result-v1.schema.json",
    "media_provenance_request/1": "media-provenance-request-v1.schema.json",
    "media_provenance_view/1": "media-provenance-view-v1.schema.json",
    "rights_eligibility_reassessment_request/1": "rights-eligibility-reassessment-request-v1.schema.json",
    "rights_eligibility_reassessment_result/1": "rights-eligibility-reassessment-result-v1.schema.json",
    "controlled_storyboard_frame_generation_request/1": "controlled-storyboard-frame-generation-request-v1.schema.json",
    "controlled_storyboard_frame_generation_request/2": "controlled-storyboard-frame-generation-request-v2.schema.json",
    "controlled_storyboard_frame_generation_request/3": "controlled-storyboard-frame-generation-request-v3.schema.json",
    "controlled_media_generation_approval/1": "controlled-media-generation-approval-v1.schema.json",
    "controlled_media_generation_attempt/1": "controlled-media-generation-attempt-v1.schema.json",
    "controlled_media_generation_attempt_outcome/1": "controlled-media-generation-attempt-outcome-v1.schema.json",
    "generated_review_candidate/1": "generated-review-candidate-v1.schema.json",
    "generated_review_candidate/2": "generated-review-candidate-v2.schema.json",
    "generated_review_candidate_review/1": "generated-review-candidate-review-v1.schema.json",
})
BUILT_IN_REGISTRY_SHA256 = "4b6d43e240c92c2c4e7dfe04fa84eee22d03a13204561125b5b6ba95a4fb55ae"  # pragma: allowlist secret
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
