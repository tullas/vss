from __future__ import annotations

import shutil

from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._bootstrap_support import repository_root, run_quiet

METADATA = CommandMetadata(
    name="bootstrap.verify",
    version="1.0.0",
    description="Verify the local toolchain and validate local IaC without applying it.",
    input_schema={"type": "object", "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    root = repository_root()
    docker_ok = shutil.which("docker") is not None and run_quiet(["docker", "info"], root)
    tofu_ok = shutil.which("tofu") is not None and run_quiet(["tofu", "version"], root)
    config_ok = all(
        (root / path).exists()
        for path in (
            "ansible/playbooks/bootstrap-local.yml",
            "ansible/roles/local_toolchain/tasks/main.yml",
            "infrastructure/environments/development/local",
            ".local/secrets",
            ".local/state/development",
        )
    )
    iac_ok = run_quiet(["scripts/iac-local.sh", "validate"], root) if tofu_ok else False
    checks = {"docker_info": docker_ok, "tofu_version": tofu_ok, "repository": config_ok, "iac_validate": iac_ok}
    if not all(checks.values()):
        raise SafeCommandError(
            "local toolchain verification failed; run bootstrap local and confirm Docker/OpenTofu are available"
        )
    return {"environment": context.environment, "dry_run": dry_run, "checks": checks, "apply_performed": False}
