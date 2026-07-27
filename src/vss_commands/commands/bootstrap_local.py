from __future__ import annotations

import json
import shutil

from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._bootstrap_support import repository_root, run_quiet

METADATA = CommandMetadata(
    name="bootstrap.local",
    version="1.0.0",
    description="Run the idempotent Ansible local toolchain bootstrap.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    root = repository_root()
    ansible = shutil.which("ansible-playbook")
    if ansible is None:
        raise SafeCommandError("ansible-playbook is unavailable; install Ansible before bootstrapping")
    command = [
        ansible,
        "-i",
        "ansible/inventories/development/hosts.yml",
        "ansible/playbooks/bootstrap-local.yml",
        "--extra-vars",
        json.dumps({"local_toolchain_environment": context.environment}),
    ]
    if dry_run:
        command.append("--check")
    if not run_quiet(command, root):
        raise SafeCommandError(
            "local toolchain bootstrap failed; verify privilege escalation and WSL systemd before retrying"
        )
    return {"environment": context.environment, "dry_run": dry_run, "playbook": "ansible/playbooks/bootstrap-local.yml"}
