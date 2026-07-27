from __future__ import annotations
from ..models import CommandContext, CommandMetadata
from ..registry import register
from ._lifecycle_support import require_development, require_ready, run_iac

METADATA = CommandMetadata(name="platform.plan", version="1.0.0", description="Plan the local platform.", input_schema={"type":"object","additionalProperties":False}, supports_dry_run=True)
@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    require_development(context.environment); require_ready(context.environment)
    return run_iac("plan", context.environment)
