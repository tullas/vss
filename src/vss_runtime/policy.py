from __future__ import annotations

from collections.abc import Iterable

from .errors import InvalidManifest, PermissionDenied

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
    def __init__(self, allowed_builtin_permissions: Iterable[str] = ()) -> None:
        allowed = frozenset(allowed_builtin_permissions)
        if not allowed.issubset(KNOWN_PERMISSION_CATEGORIES):
            raise ValueError("runtime policy contains an unknown permission")
        self.allowed_builtin_permissions = allowed

    def authorize(self, declared_permissions: Iterable[str]) -> tuple[str, ...]:
        declared = frozenset(declared_permissions)
        unknown = declared - KNOWN_PERMISSION_CATEGORIES
        if unknown:
            raise InvalidManifest(f"unknown permission category: {sorted(unknown)[0]}")
        denied = declared - self.allowed_builtin_permissions
        if denied:
            raise PermissionDenied(f"permission denied: {sorted(denied)[0]}")
        return tuple(sorted(declared))
