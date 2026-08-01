from __future__ import annotations

from typing import Any

from vss_capabilities import CapabilityExecutionContext, CapabilityResult, SDK_API_VERSION


def execute(
    context: CapabilityExecutionContext,
    input_data: dict[str, Any],
    dry_run: bool,
) -> CapabilityResult:
    del input_data, dry_run
    if context.providers is None:
        raise RuntimeError("provider accessor is unavailable")
    timestamp = context.providers.get_clock().now_utc()
    return CapabilityResult.success({"utc": timestamp.value})


execute.sdk_api_version = SDK_API_VERSION
execute.capability_identity = "runtime.time"
execute.command_identity = "runtime.time"
