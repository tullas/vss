from __future__ import annotations

import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vss_commands import CommandRunner, ExitCode
from vss_commands.registry import get_command


class LifecycleTests(unittest.TestCase):
    def test_lifecycle_commands_are_registered(self) -> None:
        for name in (
            "secrets.init", "secrets.status", "platform.plan", "platform.up",
            "platform.status", "platform.verify", "platform.down",
        ):
            self.assertIsNotNone(get_command(name), name)

    def test_secrets_create_securely_and_do_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".local/secrets/development.auto.tfvars"
            patches = (
                patch("vss_commands.commands.secrets_init.secrets_path", return_value=path),
                patch("vss_commands.commands.secrets_init.ignored_by_git", return_value=True),
                patch("vss_commands.commands.secrets_init.secrets_metadata", side_effect=lambda _: {
                    "environment": "development", "initialized": path.exists(), "git_ignored": True,
                    "permissions": format(path.stat().st_mode & 0o777, "04o") if path.exists() else None,
                    "path": ".local/secrets/development.auto.tfvars",
                }),
            )
            with patches[0], patches[1], patches[2]:
                response, code = CommandRunner().run("secrets.init", "development")
                self.assertEqual(code, ExitCode.SUCCESS)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                contents = path.read_text()
                self.assertNotIn(contents, json.dumps(response))
                original = contents
                response, code = CommandRunner().run("secrets.init", "development")
                self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)
                self.assertEqual(path.read_text(), original)

    def test_rotation_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "development.auto.tfvars"
            path.write_text("existing")
            with (
                patch("vss_commands.commands.secrets_init.secrets_path", return_value=path),
                patch("vss_commands.commands.secrets_init.secrets_metadata", return_value={"initialized": True}),
            ):
                _, code = CommandRunner().run("secrets.init", "development", {"rotate": True, "confirmed": False})
            self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)
            self.assertEqual(path.read_text(), "existing")

    def test_platform_failure_is_sanitized_and_propagated(self) -> None:
        failed = subprocess.CompletedProcess(["iac-local.sh"], 7, "", "token=should-not-leak")
        with (
            patch("vss_commands.commands._lifecycle_support.bootstrap_report", return_value={"docker":{"daemon_accessible":True},"opentofu":{"available":True}}),
            patch("vss_commands.commands._lifecycle_support.secrets_metadata", return_value={"initialized":True,"git_ignored":True,"permissions":"0600"}),
            patch("vss_commands.commands._lifecycle_support.run_capture", return_value=failed),
        ):
            response, code = CommandRunner().run("platform.plan", "development")
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        encoded = json.dumps(response)
        self.assertIn("[REDACTED]", encoded)
        self.assertNotIn("should-not-leak", encoded)

    def test_platform_down_requires_confirmation(self) -> None:
        with patch("vss_commands.commands.platform_down.require_ready"):
            _, code = CommandRunner().run("platform.down", "development", {"non_interactive": True, "confirmed": False})
        self.assertEqual(code, ExitCode.CONFIRMATION_REQUIRED)


if __name__ == "__main__":
    unittest.main()
