from __future__ import annotations

from vss_commands.commands.system_info import execute as execute_command
from vss_runtime.models import ExecutionContext


def execute(context: ExecutionContext, input_data: dict, dry_run: bool) -> dict:
    return execute_command(context, input_data, dry_run)
