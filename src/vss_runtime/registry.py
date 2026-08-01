from __future__ import annotations

from pathlib import Path

from .errors import CapabilityNotFound, InvalidManifest
from .manifest import load_manifest
from .models import RegisteredCapability


class CapabilityRegistry:
    def __init__(self, builtins_root: Path, schema_path: Path) -> None:
        self.builtins_root = builtins_root.resolve()
        self.schema_path = schema_path.resolve()
        self._capabilities: dict[str, RegisteredCapability] | None = None

    def discover(self) -> dict[str, RegisteredCapability]:
        capabilities: dict[str, RegisteredCapability] = {}
        try:
            entries = sorted(self.builtins_root.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            raise InvalidManifest("trusted capability root is unavailable") from exc
        for directory in entries:
            if not directory.is_dir():
                continue
            resolved_directory = directory.resolve()
            if not resolved_directory.is_relative_to(self.builtins_root):
                raise InvalidManifest("capability directory escapes trusted root")
            manifest_path = directory / "manifest.yaml"
            if not manifest_path.is_file():
                continue
            resolved_manifest = manifest_path.resolve()
            if not resolved_manifest.is_relative_to(resolved_directory):
                raise InvalidManifest("capability manifest escapes trusted root")
            manifest, digest = load_manifest(resolved_manifest, self.schema_path)
            if manifest.identity in capabilities:
                raise InvalidManifest(f"duplicate capability identity: {manifest.identity}")
            capabilities[manifest.identity] = RegisteredCapability(
                manifest=manifest,
                manifest_path=resolved_manifest,
                capability_root=resolved_directory,
                manifest_sha256=digest,
            )
        self._capabilities = capabilities
        return dict(capabilities)

    def resolve_command(self, command: str) -> RegisteredCapability:
        capabilities = self.discover()
        matches = [capability for capability in capabilities.values() if capability.manifest.command(command)]
        if not matches:
            raise CapabilityNotFound(f"capability not found: {command}")
        if len(matches) != 1:
            raise InvalidManifest(f"duplicate capability command: {command}")
        return matches[0]
