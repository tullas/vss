from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from vss_providers.contracts import ClockProvider


class ProviderAccessor(Protocol):
    def get_clock(self) -> ClockProvider: ...
    def get_storyboard_renderer(self) -> Any: ...


class HostInspectionAccessor(Protocol):
    def bootstrap_check(self) -> Mapping[str, Any]: ...


class ArtifactPublisherAccessor(Protocol):
    def stage(self, digest: str, content: bytes) -> str: ...


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
    admitted_request: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "authorized_permissions", tuple(self.authorized_permissions))
        object.__setattr__(self, "safe_configuration", _freeze(dict(self.safe_configuration)))
