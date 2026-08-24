from __future__ import annotations

from collections.abc import Iterable, Mapping

from .errors import InvalidManifest, PermissionDenied
from vss_providers.errors import ProviderAccessDenied

KNOWN_PERMISSION_CATEGORIES = frozenset({
    "filesystem_read",
    "filesystem_write",
    "network",
    "subprocess",
    "secrets",
    "docker_socket",
    "privileged_host",
    "repository_write",
    "provider_access",
})


class RuntimePolicy:
    def __init__(
        self,
        allowed_builtin_permissions: Iterable[str] = (),
        allowed_provider_identities: Iterable[str] = (),
        allowed_capability_permissions: Mapping[str, Iterable[str]] | None = None,
        external_effects_killed: bool = False,
        controlled_media_killed: bool = False,
    ) -> None:
        allowed = frozenset(allowed_builtin_permissions)
        if not allowed.issubset(KNOWN_PERMISSION_CATEGORIES):
            raise ValueError("runtime policy contains an unknown permission")
        self.allowed_builtin_permissions = allowed
        self.allowed_provider_identities = frozenset(allowed_provider_identities)
        self.allowed_capability_permissions = {
            identity: frozenset(permissions)
            for identity, permissions in (allowed_capability_permissions or {}).items()
        }
        if type(external_effects_killed) is not bool or type(controlled_media_killed) is not bool:
            raise ValueError("runtime kill switch state is invalid")
        self.external_effects_killed = external_effects_killed
        self.controlled_media_killed = controlled_media_killed
        if any(
            not permissions.issubset(KNOWN_PERMISSION_CATEGORIES)
            for permissions in self.allowed_capability_permissions.values()
        ):
            raise ValueError("runtime capability policy contains an unknown permission")

    def authorize(
        self,
        declared_permissions: Iterable[str],
        capability_identity: str | None = None,
    ) -> tuple[str, ...]:
        declared = frozenset(declared_permissions)
        unknown = declared - KNOWN_PERMISSION_CATEGORIES
        if unknown:
            raise InvalidManifest(f"unknown permission category: {sorted(unknown)[0]}")
        allowed = self.allowed_builtin_permissions | self.allowed_capability_permissions.get(
            capability_identity or "", frozenset()
        )
        denied = declared - allowed
        if denied:
            raise PermissionDenied(f"permission denied: {sorted(denied)[0]}")
        return tuple(sorted(declared))

    def authorize_providers(self, provider_identities: Iterable[str]) -> tuple[str, ...]:
        requested = frozenset(provider_identities)
        denied = requested - self.allowed_provider_identities
        if denied:
            raise ProviderAccessDenied(f"provider access denied: {sorted(denied)[0]}")
        return tuple(sorted(requested))

    def authorize_controlled_media(self) -> None:
        if self.external_effects_killed or self.controlled_media_killed:
            raise PermissionDenied("controlled media execution is disabled")
