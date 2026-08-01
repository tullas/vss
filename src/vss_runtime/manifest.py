from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .errors import IncompatibleRuntimeAPI, InvalidManifest
from .models import CapabilityManifest
from vss_capabilities import MANIFEST_SCHEMA_VERSION, RUNTIME_API_VERSION, SDK_API_VERSION

SUPPORTED_SCHEMA_VERSION = MANIFEST_SCHEMA_VERSION
SUPPORTED_RUNTIME_API_VERSION = RUNTIME_API_VERSION
IDENTITY_SEGMENT = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ENTRY_POINT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.py:[A-Za-z][A-Za-z0-9_]*$")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidManifest("capability manifest schema is unavailable") from exc
    if not isinstance(value, dict):
        raise InvalidManifest("capability manifest schema is invalid")
    return value


def load_manifest(path: Path, schema_path: Path) -> tuple[CapabilityManifest, str]:
    try:
        content = path.read_bytes()
        value = yaml.safe_load(content)
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidManifest("capability manifest is malformed") from exc
    if not isinstance(value, dict):
        raise InvalidManifest("capability manifest must be an object")
    errors = sorted(Draft202012Validator(_load_json(schema_path)).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise InvalidManifest(f"capability manifest is invalid: {errors[0].message}")
    if value["schema_version"] != SUPPORTED_SCHEMA_VERSION:
        raise InvalidManifest("unsupported capability manifest schema version")
    if value["runtime_api_version"] != SUPPORTED_RUNTIME_API_VERSION:
        raise IncompatibleRuntimeAPI("unsupported runtime API version")
    sdk_api_version = value.get("sdk_api_version")
    if sdk_api_version is not None and sdk_api_version != SDK_API_VERSION:
        raise IncompatibleRuntimeAPI("unsupported capability SDK API version")
    if not IDENTITY_SEGMENT.fullmatch(value["namespace"]) or not IDENTITY_SEGMENT.fullmatch(value["name"]):
        raise InvalidManifest("capability identity is unsafe")
    if not ENTRY_POINT.fullmatch(value["entry_point"]):
        raise InvalidManifest("capability entry point is unsafe")
    command_names = [command["name"] for command in value["commands"]]
    if len(command_names) != len(set(command_names)):
        raise InvalidManifest("capability manifest contains duplicate commands")
    required_providers = value.get("required_providers", [])
    provider_identities = [requirement["identity"] for requirement in required_providers]
    provider_types = [requirement["type"] for requirement in required_providers]
    if len(provider_identities) != len(set(provider_identities)) or len(provider_types) != len(set(provider_types)):
        raise InvalidManifest("capability manifest contains duplicate provider requirements")
    requests_provider_access = "provider_access" in value["permissions"]
    if required_providers and not requests_provider_access:
        raise InvalidManifest("required providers need the provider_access permission")
    if requests_provider_access and not required_providers:
        raise InvalidManifest("provider_access permission requires a scoped provider requirement")
    manifest = CapabilityManifest(
        schema_version=value["schema_version"],
        namespace=value["namespace"],
        name=value["name"],
        version=value["version"],
        description=value["description"],
        runtime_api_version=value["runtime_api_version"],
        sdk_api_version=sdk_api_version,
        required_providers=tuple(required_providers),
        entry_point=value["entry_point"],
        commands=tuple(value["commands"]),
        permissions=tuple(value["permissions"]),
        compatibility=value["compatibility"],
        lifecycle_status=value["lifecycle_status"],
    )
    return manifest, hashlib.sha256(content).hexdigest()
