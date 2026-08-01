from __future__ import annotations

from ..models import CommandContext, CommandMetadata
from ..registry import register

METADATA = CommandMetadata(
    name="bootstrap.check",
    version="1.0.0",
    description="Inspect local Docker, OpenTofu, WSL, systemd, and port readiness.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    # CommandRunner routes this registered legacy name through RuntimeController.
    # Keeping the registration preserves discovery and CLI compatibility; direct
    # handler invocation is deliberately unsupported to prevent audit bypass.
    raise RuntimeError("bootstrap.check must be invoked through CommandRunner")
