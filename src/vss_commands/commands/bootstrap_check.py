from __future__ import annotations

from ..models import CommandContext, CommandMetadata
from ..registry import register
from ._bootstrap_support import bootstrap_report

METADATA = CommandMetadata(
    name="bootstrap.check",
    version="1.0.0",
    description="Inspect local Docker, OpenTofu, WSL, systemd, and port readiness.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    return {"environment": context.environment, "dry_run": dry_run, "checks": bootstrap_report()}
