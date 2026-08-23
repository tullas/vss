from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from vss_providers.contracts import ClockProvider


class ProviderAccessor(Protocol):
    def get_clock(self) -> ClockProvider: ...
    def get_storyboard_renderer(self) -> Any: ...
    def get_pictorial_frame_generator(self) -> Any: ...


class HostInspectionAccessor(Protocol):
    def bootstrap_check(self) -> Mapping[str, Any]: ...


class ArtifactPublisherAccessor(Protocol):
    def stage(self, digest: str, content: bytes) -> str: ...


class PictorialArtifactPublisherAccessor(Protocol):
    def stage(self, storyboard_digest: str, frame_id: str, content_digest: str, content: bytes) -> str: ...


class CreativeSmokeAccessor(Protocol):
    def prepare(self, request: Any) -> str: ...
    def generate(self, request: Any, *, timeout_seconds: float = 120.0) -> Any: ...


class CreativeSmokeArtifactPublisherAccessor(Protocol):
    def stage(self, admitted: Any, result: Any, attempt_id: str) -> Mapping[str, str]: ...


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def freeze_configuration(configuration: dict[str, Any]) -> Mapping[str, Any]:
    """Return a recursively immutable view of already-approved configuration."""
    return _freeze(configuration)


@dataclass(frozen=True, slots=True)
class CapabilityExecutionContext:
    environment: str
    correlation_id: str
    execution_id: str
    capability_identity: str
    command_identity: str
    authorized_permissions: tuple[str, ...]
    safe_configuration: Mapping[str, Any]
    providers: ProviderAccessor | None = None
    host_inspection: HostInspectionAccessor | None = None
    artifact_publisher: ArtifactPublisherAccessor | None = None
    pictorial_artifact_publisher: PictorialArtifactPublisherAccessor | None = None
    creative_smoke_access: CreativeSmokeAccessor | None = None
    creative_smoke_artifact_publisher: CreativeSmokeArtifactPublisherAccessor | None = None
    admitted_request: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "authorized_permissions", tuple(self.authorized_permissions))
        object.__setattr__(self, "safe_configuration", _freeze(dict(self.safe_configuration)))
