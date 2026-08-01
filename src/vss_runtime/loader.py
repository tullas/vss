from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from vss_capabilities import SDK_API_VERSION

from .errors import InvalidManifest, RuntimeInternalFailure
from .models import CapabilityHandler, RegisteredCapability


class CapabilityLoader:
    def __init__(self, builtins_root: Path) -> None:
        self.builtins_root = builtins_root.resolve()

    def load(self, capability: RegisteredCapability) -> CapabilityHandler:
        try:
            current_digest = hashlib.sha256(capability.manifest_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise InvalidManifest("capability manifest changed before loading") from exc
        if current_digest != capability.manifest_sha256:
            raise InvalidManifest("capability manifest changed before loading")
        filename, function_name = capability.manifest.entry_point.split(":", 1)
        handler_path = (capability.capability_root / filename).resolve()
        if not handler_path.is_relative_to(capability.capability_root) or not handler_path.is_relative_to(self.builtins_root):
            raise InvalidManifest("capability code escapes trusted root")
        if not handler_path.is_file():
            raise InvalidManifest("capability entry point does not exist")
        module_name = f"_vss_builtin_{capability.manifest.namespace}_{capability.manifest.name}_{capability.manifest_sha256[:12]}"
        spec = importlib.util.spec_from_file_location(module_name, handler_path)
        if spec is None or spec.loader is None:
            raise InvalidManifest("capability entry point cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise RuntimeInternalFailure("capability module could not be loaded") from exc
        handler = getattr(module, function_name, None)
        if not callable(handler):
            raise InvalidManifest("capability handler is unavailable")
        handler_sdk_version = getattr(handler, "sdk_api_version", None)
        if capability.manifest.sdk_api_version is not None:
            if handler_sdk_version != capability.manifest.sdk_api_version:
                raise InvalidManifest("capability manifest and handler SDK versions do not match")
            if handler_sdk_version != SDK_API_VERSION:
                raise InvalidManifest("capability handler uses an unsupported SDK API version")
            if getattr(handler, "capability_identity", None) != capability.manifest.identity:
                raise InvalidManifest("capability manifest and handler identities do not match")
            commands = {command["name"] for command in capability.manifest.commands}
            if getattr(handler, "command_identity", None) not in commands:
                raise InvalidManifest("capability manifest and handler commands do not match")
        elif handler_sdk_version is not None:
            raise InvalidManifest("SDK handler requires an sdk_api_version manifest declaration")
        return handler
