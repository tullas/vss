from __future__ import annotations

import os
import secrets
import tempfile

from ..exit_codes import ExitCode
from ..models import CommandContext, CommandMetadata, SafeCommandError
from ..registry import register
from ._lifecycle_support import ignored_by_git, require_development, safe_username, secrets_metadata, secrets_path

METADATA = CommandMetadata(
    name="secrets.init", version="1.0.0", description="Initialize ignored local platform credentials.",
    input_schema={"type": "object", "properties": {"rotate": {"type": "boolean"}, "confirmed": {"type": "boolean"}}, "additionalProperties": False},
    supports_dry_run=True,
)


@register(METADATA)
def execute(context: CommandContext, input_data: dict, dry_run: bool) -> dict:
    require_development(context.environment)
    path = secrets_path(context.environment)
    rotate = input_data.get("rotate", False)
    confirmed = input_data.get("confirmed", False)
    metadata = secrets_metadata(context.environment)
    content_complete = (
        metadata["file_exists"]
        and all(metadata["required_keys_present"].values())
        and not metadata["validation_errors"]
    )
    if path.exists() and not rotate and content_complete:
        raise SafeCommandError("secrets already exist; refusing to overwrite without --rotate", metadata, ExitCode.CONFIRMATION_REQUIRED)
    if path.exists() and not rotate:
        raise SafeCommandError(
            f"local secrets are incomplete; run vss secrets init --environment {context.environment} --rotate",
            metadata,
            ExitCode.CONFIRMATION_REQUIRED,
        )
    if rotate and not confirmed:
        raise SafeCommandError("secret rotation requires --yes confirmation", secrets_metadata(context.environment), ExitCode.CONFIRMATION_REQUIRED)
    if not ignored_by_git(path):
        raise SafeCommandError("secrets path is not ignored by Git; refusing to write", exit_code=ExitCode.NOT_READY)
    if dry_run:
        return {**metadata, "would_create": not path.exists(), "would_rotate": path.exists()}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    username = safe_username()
    password = secrets.token_urlsafe(32)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".vss-secrets-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f'minio_root_user = "{username}"\nminio_root_password = "{password}"\n')
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return {**secrets_metadata(context.environment), "rotated": rotate}
