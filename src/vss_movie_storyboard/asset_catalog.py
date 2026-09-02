"""Small local metadata catalog for authoritative M10.4 admissions."""
from __future__ import annotations
import hashlib, json, os, stat, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import ResourceContractError
from .asset_admission import GroundedStoryboardAssetAdmission, _sealed_promotion_value

_KEY = object()
_AUTHORITY = {"catalog_registration": False, "asset_use": False, "production_use": False,
              "publication": False, "export": False, "workflow_activation": False,
              "provider_execution": False, "runtime_execution": False, "generation": False,
              "regeneration": False, "canon_decision": False, "rights_decision": False,
              "lifecycle_management": False}
_LIMITATIONS = ["metadata_only", "exact_m10_4_admission_only", "not_media_storage",
                "not_asset_use_authority", "not_rights_or_canon_authority",
                "not_runtime_or_provider_authority"]

@dataclass(frozen=True, slots=True, init=False)
class GroundedStoryboardAssetCatalogEntry:
    _value: Any
    def __init__(self, key: object, value: dict[str, Any]):
        if key is not _KEY: raise TypeError("catalog entry requires authoritative registration")
        object.__setattr__(self, "_value", freeze_json(value))
    def to_json_value(self): return thaw_json(self._value)
    @property
    def asset_id(self): return self._value["asset_id"]

def _record(admission: GroundedStoryboardAssetAdmission) -> dict[str, Any]:
    if type(admission) is not GroundedStoryboardAssetAdmission:
        raise ResourceContractError("catalog registration requires authoritative M10.4 admission")
    value = admission.to_json_value()
    if value.get("admission_sha256") != admission._authoritative_admission_sha256:
        raise ResourceContractError("asset admission authoritative seal mismatch")
    if value.get("admission_sha256") != canonical_digest({**value, "admission_sha256": "0" * 64}):
        raise ResourceContractError("asset admission seal mismatch")
    asset_id = "asset-" + canonical_digest({"kind": "grounded_storyboard_asset", "admission_sha256": value["admission_sha256"]})[:32]
    out = {"schema_version":"1", "contract_identity":"grounded_storyboard_asset_catalog_entry",
           "contract_version":"1", "asset_id":asset_id, "asset_revision":1,
           "registration_status":"registered_metadata_only", "admission":value,
           "authority":dict(_AUTHORITY), "limitations":list(_LIMITATIONS), "asset_sha256":"0"*64}
    out["asset_sha256"] = canonical_digest(out)
    return out

def _root(repository_root: Path, create: bool) -> Path:
    root = repository_root.resolve(strict=True) / ".local/movie/grounded-storyboard-asset-catalog/v1"
    if create: root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not root.is_dir(): raise ResourceContractError("asset catalog root is unsafe")
    return root

def _read(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise OSError
        raw = path.read_bytes()
        if len(raw) > 131072: raise OSError
        value = json.loads(raw)
        if not isinstance(value, dict): raise OSError
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResourceContractError("asset catalog record is invalid") from exc

def _checked(value: dict[str, Any], asset_id: str) -> GroundedStoryboardAssetCatalogEntry:
    if value.get("asset_id") != asset_id or value.get("asset_revision") != 1 or value.get("registration_status") != "registered_metadata_only":
        raise ResourceContractError("asset catalog identity mismatch")
    if value.get("authority") != _AUTHORITY or value.get("limitations") != _LIMITATIONS:
        raise ResourceContractError("asset catalog authority mismatch")
    admission = value.get("admission")
    if not isinstance(admission, dict) or admission.get("admission_sha256") != canonical_digest({**admission, "admission_sha256":"0"*64}):
        raise ResourceContractError("asset catalog admission integrity mismatch")
    expected = "asset-" + canonical_digest({"kind":"grounded_storyboard_asset", "admission_sha256": admission["admission_sha256"]})[:32]
    if asset_id != expected or value.get("asset_sha256") != canonical_digest({**value, "asset_sha256":"0"*64}):
        raise ResourceContractError("asset catalog integrity mismatch")
    return GroundedStoryboardAssetCatalogEntry(_KEY, value)

def register_grounded_storyboard_asset(repository_root: Path, admission: GroundedStoryboardAssetAdmission):
    value = _record(admission); root = _root(Path(repository_root), True); destination = root / (value["asset_id"] + ".json")
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"
    if destination.exists() or destination.is_symlink():
        existing = _checked(_read(destination), value["asset_id"])
        if existing.to_json_value() != value: raise ResourceContractError("asset catalog registration conflict")
        return existing
    fd, name = tempfile.mkstemp(prefix=".entry-", dir=root)
    temporary = Path(name)
    try:
        os.fchmod(fd, 0o600); os.write(fd, data); os.fsync(fd); os.close(fd); fd = -1
        try: os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            existing = _checked(_read(destination), value["asset_id"])
            if existing.to_json_value() != value: raise ResourceContractError("asset catalog registration conflict")
            return existing
        return _checked(value, value["asset_id"])
    finally:
        if fd >= 0: os.close(fd)
        temporary.unlink(missing_ok=True)

def lookup_grounded_storyboard_asset(repository_root: Path, asset_id: str):
    if not isinstance(asset_id, str) or not asset_id.startswith("asset-") or len(asset_id) != 38:
        raise ResourceContractError("asset catalog identity is invalid")
    return _checked(_read(_root(Path(repository_root), False) / (asset_id + ".json")), asset_id)
