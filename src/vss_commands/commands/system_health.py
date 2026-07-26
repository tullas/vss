from __future__ import annotations

from vss_config import load_configuration

from ..models import CommandContext, CommandMetadata
from ..registry import register

METADATA = CommandMetadata(
    name="system.health",
    version="1.0.0",
    description="Verify the selected VSS configuration is available and valid.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    # The runner already loads configuration; revalidation makes this command's
    # health assertion explicit while keeping the output free of config values.
    load_configuration(context.environment)
    return {
        "command_name": METADATA.name,
        "command_version": METADATA.version,
        "environment": context.environment,
        "dry_run": dry_run,
        "checks": {"configuration": {"status": "ok", "schema_version": "1"}},
    }
