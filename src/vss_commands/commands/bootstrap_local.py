from __future__ import annotations

import json
import shutil
import sys

from ..exit_codes import ExitCode
from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._bootstrap_support import (
    ansible_failure_summary,
    repository_root,
    run_capture,
    run_interactive,
    sanitize_text,
)

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
    if context.ask_become_pass:
        if not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)):
            raise SafeCommandError(
                "bootstrap requires an interactive terminal for privilege escalation",
                exit_code=ExitCode.NOT_READY,
            )
        command.append("--ask-become-pass")
        result = run_interactive(command, root)
        if result is None:
            raise SafeCommandError(
                "local toolchain bootstrap could not start",
                {"ansible": {"return_code": int(ExitCode.EXECUTION_FAILURE)}},
            )
        if result.returncode != 0:
            return_code = 128 + abs(result.returncode) if result.returncode < 0 else result.returncode
            raise SafeCommandError(
                "local toolchain bootstrap failed during interactive Ansible execution",
                {"ansible": {"return_code": return_code}},
                return_code,
            )
        return {"environment": context.environment, "dry_run": dry_run, "playbook": "ansible/playbooks/bootstrap-local.yml"}

    result = run_capture(command, root)
    if result is None or result.returncode != 0:
        summary = ansible_failure_summary(result)
        if context.verbose and result is not None:
            print(sanitize_text(f"{result.stdout}\n{result.stderr}"), file=sys.stderr)
        raise SafeCommandError(
            "local toolchain bootstrap failed; verify privilege escalation and WSL systemd before retrying",
            {"ansible": summary},
        )
    if context.verbose and result.stdout:
        print(sanitize_text(result.stdout), file=sys.stderr)
    return {"environment": context.environment, "dry_run": dry_run, "playbook": "ansible/playbooks/bootstrap-local.yml"}
