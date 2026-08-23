from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    CLOCK_PROVIDER_TYPE,
    LOCAL_CLOCK_IDENTITY,
    LOCAL_CLOCK_IMPLEMENTATION_IDENTITY,
    LOCAL_STORYBOARD_RENDER_IDENTITY,
    LOCAL_STORYBOARD_RENDER_IMPLEMENTATION_IDENTITY,
    LOCAL_PICTORIAL_FRAME_IDENTITY,
    LOCAL_PICTORIAL_FRAME_IMPLEMENTATION_IDENTITY,
    PICTORIAL_FRAME_PROVIDER_TYPE,
    PROVIDER_API_VERSION,
    STORYBOARD_RENDER_PROVIDER_TYPE,
)
from .contracts import ClockProvider, PictorialFrameProvider, StoryboardRenderProvider
from .errors import ProviderAccessDenied, ProviderIncompatible, ProviderNotFound, ProviderUnavailable
from .manifest import load_provider_manifest
from .models import RegisteredProvider


@dataclass(frozen=True, slots=True)
class ProviderRegistry:
    builtins_root: Path
    schema_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "builtins_root", self.builtins_root.resolve())
        object.__setattr__(self, "schema_path", self.schema_path.resolve())

    def discover(self) -> dict[str, RegisteredProvider]:
        providers: dict[str, RegisteredProvider] = {}
        try:
            entries = sorted(self.builtins_root.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            raise ProviderUnavailable("trusted provider root is unavailable") from exc
        for directory in entries:
            if not directory.is_dir():
                continue
            resolved = directory.resolve()
            if not resolved.is_relative_to(self.builtins_root):
                raise ProviderIncompatible("provider directory escapes trusted root")
            manifest_path = (directory / "provider.yaml").resolve()
            if not manifest_path.exists():
                continue
            if not manifest_path.is_relative_to(resolved):
                raise ProviderIncompatible("provider manifest escapes trusted root")
            provider = load_provider_manifest(manifest_path, self.schema_path, self.builtins_root)
            identity = provider.metadata.identity
            if identity in providers:
                raise ProviderIncompatible(f"duplicate provider identity: {identity}")
            providers[identity] = provider
        return providers

    def resolve(self, identity: str) -> RegisteredProvider:
        provider = self.discover().get(identity)
        if provider is None:
            raise ProviderNotFound(f"provider not found: {identity}")
        return provider

    @staticmethod
    def _verify_integrity(provider: RegisteredProvider) -> None:
        try:
            manifest_digest = hashlib.sha256(provider.manifest_path.read_bytes()).hexdigest()
            implementation_digest = hashlib.sha256(provider.implementation_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ProviderUnavailable("provider changed before initialization") from exc
        if manifest_digest != provider.manifest_sha256 or implementation_digest != provider.implementation_sha256:
            raise ProviderIncompatible("provider changed before initialization")

    def initialize(self, provider: RegisteredProvider) -> ClockProvider | StoryboardRenderProvider | PictorialFrameProvider:
        self._verify_integrity(provider)
        module_name = f"_vss_provider_{provider.metadata.identity.replace('.', '_')}_{provider.implementation_sha256[:12]}"
        spec = importlib.util.spec_from_file_location(module_name, provider.implementation_path)
        if spec is None or spec.loader is None:
            raise ProviderUnavailable("provider implementation cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            factory = getattr(module, provider.factory_name, None)
            if not callable(factory):
                raise ProviderUnavailable("provider factory is unavailable")
            implementation = factory()
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise ProviderUnavailable("provider initialization failed") from exc
        if provider.metadata.provider_type == CLOCK_PROVIDER_TYPE:
            if not callable(getattr(implementation, "now_utc", None)) or not callable(getattr(implementation, "monotonic_time", None)):
                raise ProviderIncompatible("provider does not implement the clock contract")
        elif provider.metadata.provider_type == STORYBOARD_RENDER_PROVIDER_TYPE and not callable(getattr(implementation, "render", None)):
            raise ProviderIncompatible("provider does not implement the storyboard render contract")
        elif provider.metadata.provider_type == PICTORIAL_FRAME_PROVIDER_TYPE and not callable(getattr(implementation, "generate", None)):
            raise ProviderIncompatible("provider does not implement the pictorial frame contract")
        return implementation


@dataclass(frozen=True, slots=True)
class ProviderSelector:
    """Static M2.4 selection; configuration and fallback are deliberately absent."""

    registry: ProviderRegistry

    def registration(self, requirement: dict) -> RegisteredProvider:
        if requirement["type"] not in {CLOCK_PROVIDER_TYPE, STORYBOARD_RENDER_PROVIDER_TYPE, PICTORIAL_FRAME_PROVIDER_TYPE}:
            raise ProviderIncompatible("unknown provider type")
        expected_identity = (LOCAL_CLOCK_IDENTITY if requirement["type"] == CLOCK_PROVIDER_TYPE else
                             LOCAL_STORYBOARD_RENDER_IDENTITY if requirement["type"] == STORYBOARD_RENDER_PROVIDER_TYPE else
                             LOCAL_PICTORIAL_FRAME_IDENTITY)
        if requirement["identity"] != expected_identity:
            # Resolve first so an absent identity is reported distinctly from
            # a future known-but-not-statically-selected implementation.
            self.registry.resolve(requirement["identity"])
            raise ProviderAccessDenied("provider is not statically selected")
        provider = self.registry.resolve(expected_identity)
        if requirement["api_version"] != PROVIDER_API_VERSION:
            raise ProviderIncompatible("capability requires an unsupported provider API version")
        if provider.metadata.version != "1.0.0":
            raise ProviderIncompatible("selected provider version is not approved")
        if (
            provider.metadata.implementation_identity != (LOCAL_CLOCK_IMPLEMENTATION_IDENTITY if requirement["type"] == CLOCK_PROVIDER_TYPE else
                                                          LOCAL_STORYBOARD_RENDER_IMPLEMENTATION_IDENTITY if requirement["type"] == STORYBOARD_RENDER_PROVIDER_TYPE else
                                                          LOCAL_PICTORIAL_FRAME_IMPLEMENTATION_IDENTITY)
            or provider.metadata.source != "trusted_builtin"
        ):
            raise ProviderIncompatible("selected provider implementation identity is not approved")
        if provider.metadata.lifecycle_status != "active":
            raise ProviderUnavailable("selected provider is unavailable")
        return provider
