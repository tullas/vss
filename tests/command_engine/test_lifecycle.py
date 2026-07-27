from __future__ import annotations

import json
import stat
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from vss_commands import CommandRunner, ExitCode
from vss_commands.commands._bootstrap_support import sanitize_text
from vss_commands.commands._lifecycle_support import secrets_metadata
from vss_commands.registry import get_command


class LifecycleTests(unittest.TestCase):
    def _metadata(self, path: Path, *, ignored: bool = True) -> dict:
        with (
            patch("vss_commands.commands._lifecycle_support.secrets_path", return_value=path),
            patch("vss_commands.commands._lifecycle_support.ignored_by_git", return_value=ignored),
        ):
            return secrets_metadata("development")

    def _run_init(self, path: Path, payload: dict | None = None, *, ignored: bool = True):
        def metadata(_: str) -> dict:
            return self._metadata(path, ignored=ignored)

        with ExitStack() as stack:
            stack.enter_context(patch("vss_commands.commands.secrets_init.secrets_path", return_value=path))
            stack.enter_context(patch("vss_commands.commands.secrets_init.ignored_by_git", return_value=ignored))
            stack.enter_context(patch("vss_commands.commands.secrets_init.secrets_metadata", side_effect=metadata))
            return CommandRunner().run("secrets.init", "development", payload or {})

    def test_lifecycle_commands_are_registered(self) -> None:
        for name in (
            "secrets.init", "secrets.status", "platform.plan", "platform.up",
            "platform.status", "platform.verify", "platform.down",
        ):
            self.assertIsNotNone(get_command(name), name)

    def test_nonexistent_secrets_file_is_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metadata = self._metadata(Path(directory) / "missing.tfvars")
        self.assertFalse(metadata["file_exists"])
        self.assertFalse(metadata["initialized"])
        self.assertEqual(metadata["validation_errors"], ["minio_root_user", "minio_root_password"])

    def test_commented_example_password_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            path.write_text('minio_root_user = "safe-user"\n# minio_root_password = "example-only"\n')  # pragma: allowlist secret
            path.chmod(0o600)
            metadata = self._metadata(path)
        self.assertFalse(metadata["initialized"])
        self.assertEqual(metadata["required_keys_present"], {"minio_root_user": True, "minio_root_password": False})
        self.assertEqual(metadata["validation_errors"], ["minio_root_password"])
        self.assertNotIn("example-only", json.dumps(metadata))

    def test_user_only_file_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            path.write_text('minio_root_user = "safe-user"\n')
            path.chmod(0o600)
            metadata = self._metadata(path)
        self.assertFalse(metadata["initialized"])
        self.assertEqual(metadata["validation_errors"], ["minio_root_password"])

    def test_complete_valid_file_is_initialized_without_value_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            secret_value = "NeverReturnThisValue-123"  # pragma: allowlist secret
            path.write_text(f'minio_root_user = "safe-user"\nminio_root_password = "{secret_value}"\n')
            path.chmod(0o600)
            metadata = self._metadata(path)
        self.assertTrue(metadata["initialized"])
        self.assertEqual(metadata["validation_errors"], [])
        self.assertNotIn(secret_value, json.dumps(metadata))
        self.assertNotIn("safe-user", json.dumps(metadata))

    def test_malformed_tfvars_is_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            path.write_text('minio_root_user = "safe-user"\nminio_root_password = "unterminated\n')
            path.chmod(0o600)
            metadata = self._metadata(path)
        self.assertFalse(metadata["initialized"])
        self.assertEqual(metadata["validation_errors"], ["minio_root_password"])

    def test_insecure_permissions_are_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            path.write_text('minio_root_user = "safe-user"\nminio_root_password = "safe-password"\n')  # pragma: allowlist secret
            path.chmod(0o644)
            metadata = self._metadata(path)
        self.assertFalse(metadata["initialized"])
        self.assertEqual(metadata["permissions"], "0644")

    def test_git_not_ignored_is_not_initialized_and_init_refuses_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            path.write_text('minio_root_user = "safe-user"\nminio_root_password = "safe-password"\n')  # pragma: allowlist secret
            path.chmod(0o600)
            metadata = self._metadata(path, ignored=False)
            self.assertFalse(metadata["initialized"])
            self.assertFalse(metadata["git_ignored"])
            path.unlink()
            response, code = self._run_init(path, ignored=False)
        self.assertEqual(code, ExitCode.NOT_READY)
        self.assertFalse(response["output"])
        self.assertFalse(path.exists())

    def test_secrets_create_securely_and_complete_file_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".local/secrets/development.auto.tfvars"
            response, code = self._run_init(path)
            self.assertEqual(code, ExitCode.SUCCESS)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertTrue(response["output"]["initialized"])
            contents = path.read_text()
            self.assertNotIn(contents, json.dumps(response))
            original = contents
            _, code = self._run_init(path)
            self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)
            self.assertEqual(path.read_text(), original)

    def test_incomplete_secrets_require_rotation_and_can_be_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            old_example = '# minio_root_user = "example"\n# minio_root_password = "example"\n'  # pragma: allowlist secret
            path.write_text(old_example)
            path.chmod(0o600)
            response, code = self._run_init(path)
            self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)
            self.assertFalse(response["output"]["initialized"])
            self.assertEqual(path.read_text(), old_example)
            _, code = self._run_init(path, {"rotate": True, "confirmed": False})
            self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)
            response, code = self._run_init(path, {"rotate": True, "confirmed": True})
            self.assertEqual(code, ExitCode.SUCCESS)
            self.assertTrue(response["output"]["initialized"])
            self.assertNotIn(path.read_text(), json.dumps(response))

    def test_platform_plan_and_up_refuse_incomplete_secrets_before_subprocess(self) -> None:
        incomplete = {
            "file_exists": True, "initialized": False,
            "required_keys_present": {"minio_root_user": True, "minio_root_password": False},
            "permissions": "0600", "git_ignored": True,
            "validation_errors": ["minio_root_password"],
        }
        for command in ("platform.plan", "platform.up"):
            with (
                patch("vss_commands.commands._lifecycle_support.secrets_metadata", return_value=incomplete),
                patch("vss_commands.commands._lifecycle_support.bootstrap_report") as bootstrap,
                patch("vss_commands.commands._lifecycle_support.run_capture") as subprocess_run,
            ):
                response, code = CommandRunner().run(command, "development")
            self.assertEqual(code, ExitCode.NOT_READY)
            self.assertIn("local secrets are incomplete", response["errors"][0])
            bootstrap.assert_not_called()
            subprocess_run.assert_not_called()

    def test_platform_failure_strips_ansi_and_redacts_secret(self) -> None:
        failed = subprocess.CompletedProcess(["iac-local.sh"], 7, "", "\x1b[31mtoken=should-not-leak\x1b[0m")
        ready = {"initialized": True}
        with (
            patch("vss_commands.commands._lifecycle_support.secrets_metadata", return_value=ready),
            patch("vss_commands.commands._lifecycle_support.bootstrap_report", return_value={"docker":{"daemon_accessible":True},"opentofu":{"available":True}}),
            patch("vss_commands.commands._lifecycle_support.run_capture", return_value=failed),
        ):
            response, code = CommandRunner().run("platform.plan", "development")
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        encoded = json.dumps(response)
        self.assertIn("[REDACTED]", encoded)
        self.assertNotIn("should-not-leak", encoded)
        self.assertNotIn("\\u001b", encoded)
        self.assertEqual(sanitize_text("\x1b[31mplain failure\x1b[0m"), "plain failure")

    def test_platform_down_requires_confirmation(self) -> None:
        with patch("vss_commands.commands.platform_down.require_ready"):
            _, code = CommandRunner().run("platform.down", "development", {"non_interactive": True, "confirmed": False})
        self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)


if __name__ == "__main__":
    unittest.main()
