from __future__ import annotations
from ..exit_codes import ExitCode
from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._lifecycle_support import require_development, require_ready, run_iac

METADATA = CommandMetadata(name="platform.up", version="1.0.0", description="Apply and verify the local platform.", input_schema={"type":"object","properties":{"non_interactive":{"type":"boolean"}},"additionalProperties":False}, supports_dry_run=True)
@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    require_development(context.environment); require_ready(context.environment)
    if dry_run: return run_iac("plan", context.environment)
    non_interactive = input_data.get("non_interactive", False)
    if non_interactive is False and not __import__("sys").stdin.isatty():
        raise SafeCommandError("platform up requires an interactive terminal or --non-interactive", exit_code=ExitCode.CONFIRMATION_REQUIRED)
    applied = run_iac("apply", context.environment, non_interactive=non_interactive)
    applied["health"] = run_iac("health", context.environment)["health"]
    return applied
