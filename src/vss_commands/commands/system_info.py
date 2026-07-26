from __future__ import annotations

import platform

from ..models import CommandContext, CommandMetadata
from ..registry import register

METADATA = CommandMetadata(
    name="system.info",
    version="1.0.0",
    description="Return safe runtime and VSS environment information.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    return {
        "command_name": METADATA.name,
        "command_version": METADATA.version,
        "os": platform.system(),
        "python_version": platform.python_version(),
        "environment": context.environment,
        "dry_run": dry_run,
    }
