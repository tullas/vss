from __future__ import annotations

import os
import re
import socket
import threading
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.parse import urlsplit

from .errors import CapabilityExecutionFailure


_SAFE_SECRET_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SAFE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SAFE_COST = re.compile(r"^[0-9]{1,4}\.[0-9]{1,6}$")
_ROUTING_PROXY_NAMES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
)


class ExternalExecutionPreflightFailure(CapabilityExecutionFailure):
    """A closed readiness failure that occurs before attempt reservation."""

    def __init__(self, classification: str) -> None:
        if classification not in {
            "configuration", "credential_unavailable", "dns", "dns_timeout",
            "proxy_environment_unsupported",
        }:
            classification = "configuration"
        super().__init__(f"external execution preflight failed: {classification}")
        self.preflight_diagnostic = {
            "classification": classification,
            "provider_call_count": 0,
            "attempt_reserved": False,
        }


@dataclass(frozen=True, slots=True)
class ExternalExecutionPreflightSpec:
    endpoint: str
    credential_environment_variable: str
    provider_request_digest: str
    authoritative_provider_request_digest: str
    maximum_provider_attempts: int
    maximum_estimated_cost_usd: str
    authorized_cost_ceiling_usd: str
    dns_timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if (not _SAFE_COST.fullmatch(self.maximum_estimated_cost_usd)
                or not _SAFE_COST.fullmatch(self.authorized_cost_ceiling_usd)):
            raise ExternalExecutionPreflightFailure("configuration")
        try:
            endpoint = urlsplit(self.endpoint)
            hostname = endpoint.hostname
            port = endpoint.port
            maximum_cost = Decimal(self.maximum_estimated_cost_usd)
            authorized_cost = Decimal(self.authorized_cost_ceiling_usd)
        except (ValueError, InvalidOperation) as exc:
            raise ExternalExecutionPreflightFailure("configuration") from exc
        if (
            endpoint.scheme != "https"
            or not hostname
            or endpoint.username is not None
            or endpoint.password is not None
            or port not in (None, 443)
            or endpoint.query
            or endpoint.fragment
            or not endpoint.path.startswith("/")
            or not _SAFE_SECRET_NAME.fullmatch(self.credential_environment_variable)
            or not _SAFE_DIGEST.fullmatch(self.provider_request_digest)
            or self.provider_request_digest != self.authoritative_provider_request_digest
            or self.maximum_provider_attempts != 1
            or not maximum_cost.is_finite()
            or not authorized_cost.is_finite()
            or maximum_cost <= 0
            or maximum_cost > authorized_cost
            or not 0.1 <= self.dns_timeout_seconds <= 10.0
        ):
            raise ExternalExecutionPreflightFailure("configuration")

    @property
    def hostname(self) -> str:
        hostname = urlsplit(self.endpoint).hostname
        if hostname is None:  # guarded by __post_init__
            raise ExternalExecutionPreflightFailure("configuration")
        return hostname


@dataclass(frozen=True, slots=True)
class ExternalExecutionReadiness:
    credential_available: bool
    direct_egress_environment: bool
    dns_ready: bool
    provider_call_count: int = 0
    attempt_reserved: bool = False


EnvironmentContains = Callable[[str], bool]
Resolver = Callable[[str, int], object]


def _environment_contains(name: str) -> bool:
    # Membership checks the child process environment without retrieving the value.
    return name in os.environ


def _resolve(hostname: str, port: int) -> object:
    return socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)


class ExternalExecutionPreflight:
    """Perform closed host readiness checks without provider access or state mutation."""

    def __init__(
        self,
        *,
        environment_contains: EnvironmentContains = _environment_contains,
        resolver: Resolver = _resolve,
    ) -> None:
        self._environment_contains = environment_contains
        self._resolver = resolver

    def _present(self, name: str) -> bool:
        try:
            return self._environment_contains(name) is True
        except Exception as exc:
            raise ExternalExecutionPreflightFailure("configuration") from exc

    def _dns_ready(self, hostname: str, timeout_seconds: float) -> None:
        outcome: list[bool] = []

        def resolve() -> None:
            try:
                outcome.append(bool(self._resolver(hostname, 443)))
            except (OSError, socket.gaierror):
                outcome.append(False)
            except Exception:
                outcome.append(False)

        worker = threading.Thread(target=resolve, name="vss-external-preflight-dns", daemon=True)
        worker.start()
        worker.join(timeout_seconds)
        if worker.is_alive():
            raise ExternalExecutionPreflightFailure("dns_timeout")
        if outcome != [True]:
            raise ExternalExecutionPreflightFailure("dns")

    def run(self, spec: ExternalExecutionPreflightSpec) -> ExternalExecutionReadiness:
        if type(spec) is not ExternalExecutionPreflightSpec:
            raise ExternalExecutionPreflightFailure("configuration")
        if any(self._present(name) for name in _ROUTING_PROXY_NAMES):
            raise ExternalExecutionPreflightFailure("proxy_environment_unsupported")
        if not self._present(spec.credential_environment_variable):
            raise ExternalExecutionPreflightFailure("credential_unavailable")
        self._dns_ready(spec.hostname, spec.dns_timeout_seconds)
        return ExternalExecutionReadiness(True, True, True)
