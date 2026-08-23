from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .constants import CLOCK_PROVIDER_TYPE, PICTORIAL_FRAME_PROVIDER_TYPE, PROVIDER_API_VERSION, PROVIDER_MANIFEST_SCHEMA_VERSION, STORYBOARD_RENDER_PROVIDER_TYPE
from .errors import ProviderIncompatible
from .models import ProviderIdentity, RegisteredProvider

IDENTITY = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*){2,}$")
IMPLEMENTATION = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.py:[A-Za-z][A-Za-z0-9_]*$")


def _schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderIncompatible("provider manifest schema is unavailable") from exc
    if not isinstance(value, dict):
        raise ProviderIncompatible("provider manifest schema is invalid")
    return value


def load_provider_manifest(path: Path, schema_path: Path, trusted_root: Path) -> RegisteredProvider:
    try:
        content = path.read_bytes()
        value = yaml.safe_load(content)
    except (OSError, yaml.YAMLError) as exc:
        raise ProviderIncompatible("provider manifest is malformed") from exc
    if not isinstance(value, dict):
        raise ProviderIncompatible("provider manifest must be an object")
    errors = sorted(Draft202012Validator(_schema(schema_path)).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ProviderIncompatible(f"provider manifest is invalid: {errors[0].message}")
    if value["schema_version"] != PROVIDER_MANIFEST_SCHEMA_VERSION:
        raise ProviderIncompatible("unsupported provider manifest schema version")
    if value["provider_api_version"] != PROVIDER_API_VERSION:
        raise ProviderIncompatible("unsupported provider API version")
    if value["provider_type"] not in {CLOCK_PROVIDER_TYPE, STORYBOARD_RENDER_PROVIDER_TYPE, PICTORIAL_FRAME_PROVIDER_TYPE}:
        raise ProviderIncompatible("unknown provider type")
    if not IDENTITY.fullmatch(value["identity"]):
        raise ProviderIncompatible("provider identity is unsafe")
    if not IMPLEMENTATION.fullmatch(value["implementation"]):
        raise ProviderIncompatible("provider implementation path is unsafe")
    filename, factory_name = value["implementation"].split(":", 1)
    implementation_path = (path.parent / filename).resolve()
    if not implementation_path.is_relative_to(path.parent.resolve()) or not implementation_path.is_relative_to(trusted_root):
        raise ProviderIncompatible("provider implementation escapes trusted root")
    if not implementation_path.is_file():
        raise ProviderIncompatible("provider implementation is unavailable")
    try:
        implementation_content = implementation_path.read_bytes()
    except OSError as exc:
        raise ProviderIncompatible("provider implementation is unavailable") from exc
    metadata = ProviderIdentity(
        provider_type=value["provider_type"],
        name=value["name"],
        version=value["version"],
        identity=value["identity"],
        provider_api_version=value["provider_api_version"],
        implementation_identity=value["implementation_identity"],
        lifecycle_status=value["lifecycle_status"],
        source=value["source"],
    )
    return RegisteredProvider(
        metadata=metadata,
        manifest_path=path,
        implementation_path=implementation_path,
        manifest_sha256=hashlib.sha256(content).hexdigest(),
        implementation_sha256=hashlib.sha256(implementation_content).hexdigest(),
        factory_name=factory_name,
    )
