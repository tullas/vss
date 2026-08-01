from __future__ import annotations

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
