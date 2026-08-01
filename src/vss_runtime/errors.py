from __future__ import annotations

from vss_commands.exit_codes import ExitCode


class RuntimeFailure(RuntimeError):
    exit_code = ExitCode.INTERNAL_ERROR
    category = "runtime_internal_failure"


class InvalidManifest(RuntimeFailure):
    exit_code = ExitCode.INVALID_CONFIGURATION
    category = "invalid_manifest"


class IncompatibleRuntimeAPI(InvalidManifest):
    category = "incompatible_runtime_api"


class CapabilityNotFound(RuntimeFailure):
    exit_code = ExitCode.UNKNOWN_COMMAND
    category = "capability_not_found"


class PermissionDenied(RuntimeFailure):
    exit_code = ExitCode.PERMISSION_DENIED
    category = "permission_denied"


class InvalidCapabilityInput(RuntimeFailure):
    exit_code = ExitCode.INVALID_INPUT
    category = "invalid_capability_input"


class CapabilityExecutionFailure(RuntimeFailure):
    exit_code = ExitCode.EXECUTION_FAILURE
    category = "capability_execution_failure"


class RuntimeTimeout(RuntimeFailure):
    exit_code = ExitCode.TIMEOUT
    category = "timeout"


class RuntimeInternalFailure(RuntimeFailure):
    pass
