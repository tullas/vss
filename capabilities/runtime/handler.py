from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION


def execute(
    context: CapabilityExecutionContext,
    input_data: dict[str, Any],
    dry_run: bool,
) -> CapabilityResult:
    del context, dry_run
    return CapabilityResult.success({"value": input_data["value"]})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "runtime.echo"
execute.command_identity = "runtime.echo"
