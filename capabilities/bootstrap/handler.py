from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION


def execute(
    context: CapabilityExecutionContext,
    input_data: dict[str, Any],
    dry_run: bool,
) -> CapabilityResult:
    del input_data
    if context.host_inspection is None:
        raise RuntimeError("host inspection is unavailable")
    return CapabilityResult.success(
        {
            "environment": context.environment,
            "dry_run": dry_run,
            "checks": dict(context.host_inspection.bootstrap_check()),
        }
    )


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "bootstrap.check"
execute.command_identity = "bootstrap.check"
