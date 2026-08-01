from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
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
