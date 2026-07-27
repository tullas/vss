from __future__ import annotations
from ..exit_codes import ExitCode
from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._lifecycle_support import require_development, require_ready, run_iac

METADATA = CommandMetadata(name="platform.down", version="1.0.0", description="Destroy managed local platform resources.", input_schema={"type":"object","properties":{"non_interactive":{"type":"boolean"},"confirmed":{"type":"boolean"}},"additionalProperties":False}, supports_dry_run=True)
@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    require_development(context.environment); require_ready(context.environment)
    if dry_run: return run_iac("plan-destroy", context.environment)
    if not input_data.get("confirmed", False):
        raise SafeCommandError("platform down requires --yes confirmation", exit_code=ExitCode.CONFIRMATION_REQUIRED)
    return run_iac("destroy", context.environment, non_interactive=input_data.get("non_interactive", False))
