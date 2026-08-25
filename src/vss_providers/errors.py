from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from vss_commands.exit_codes import ExitCode


class ProviderFailure(RuntimeError):
    exit_code = ExitCode.EXECUTION_FAILURE
    category = "provider_execution_failure"


class ProviderNotFound(ProviderFailure):
    exit_code = ExitCode.NOT_READY
    category = "provider_not_found"


class ProviderUnavailable(ProviderFailure):
    exit_code = ExitCode.NOT_READY
    category = "provider_unavailable"


class ProviderIncompatible(ProviderFailure):
    exit_code = ExitCode.INVALID_CONFIGURATION
    category = "provider_incompatible"


class ProviderAccessDenied(ProviderFailure):
    exit_code = ExitCode.PERMISSION_DENIED
    category = "provider_access_denied"


class ProviderExecutionFailure(ProviderFailure):
    pass


class ControlledFrameProviderFailure(ProviderExecutionFailure):
    """Sanitized terminal evidence for one already-reserved controlled call."""

    _CLASSIFICATIONS = {"response_invalid", "output_invalid", "cost_exceeded", "provider_failed"}

    def __init__(self, message: str, *, classification: str,
                 evidence: Mapping[str, Any] | None = None) -> None:
        if classification not in self._CLASSIFICATIONS:
            raise ValueError("controlled frame failure classification is invalid")
        super().__init__(message)
        self.classification = classification
        self.evidence = MappingProxyType(dict(evidence or {}))
