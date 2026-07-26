from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from vss_commands import CommandRunner, ExitCode
from vss_commands.registry import get_command
from vss_commands.runner import response_json


class CommandEngineTests(unittest.TestCase):
    def test_listing_and_description(self) -> None:
        command = get_command("system.info")
        self.assertIsNotNone(command)
        self.assertEqual(command.metadata.version, "1.0.0")
        self.assertTrue(command.metadata.supports_dry_run)
        self.assertIsNotNone(get_command("system.health"))

    def test_success_and_generated_correlation_id(self) -> None:
        response, code = CommandRunner().run("system.info", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["command"], "system.info")
        self.assertRegex(response["correlation_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(response["output"]["environment"], "development")
        self.assertNotIn("username", json.dumps(response).lower())

    def test_supplied_correlation_id_and_dry_run(self) -> None:
        correlation_id = "a" * 32
        response, code = CommandRunner().run("system.info", "staging", correlation_id=correlation_id, dry_run=True)
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["correlation_id"], correlation_id)
        self.assertTrue(response["output"]["dry_run"])

    def test_health_command_reports_configuration_only(self) -> None:
        response, code = CommandRunner().run("system.health", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["output"]["checks"]["configuration"]["status"], "ok")
        self.assertNotIn("vss", response["output"]["checks"])

    def test_unknown_command(self) -> None:
        response, code = CommandRunner().run("unknown.command", "development")
        self.assertEqual(code, ExitCode.UNKNOWN_COMMAND)
        self.assertEqual(response["output"], {})

    def test_invalid_input_and_unknown_environment(self) -> None:
        response, code = CommandRunner().run("system.info", "development", {"api_token": "do-not-leak"})
        self.assertEqual(code, ExitCode.INVALID_INPUT)
        self.assertNotIn("do-not-leak", json.dumps(response))
        _, code = CommandRunner().run("system.info", "qa")
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)

    def test_response_structure_is_deterministic(self) -> None:
        first, _ = CommandRunner().run("system.info", "production", correlation_id="b" * 32)
        second, _ = CommandRunner().run("system.info", "production", correlation_id="b" * 32)
        self.assertEqual(list(first), list(second))
        encoded = response_json(first)
        self.assertEqual(list(json.loads(encoded)), sorted(first))
        self.assertEqual(first["schema_version"], "1")
        self.assertIn("duration_ms", first)
        self.assertEqual(first["errors"], [])

    def test_cli_exit_codes_and_commands(self) -> None:
        environment = {"PYTHONPATH": str(Path(__file__).parents[2] / "src")}
        listed = subprocess.run([sys.executable, "-m", "vss_commands", "list"], capture_output=True, text=True, env=environment)
        self.assertEqual(listed.returncode, 0)
        self.assertIn("system.info", listed.stdout)
        unknown = subprocess.run([sys.executable, "-m", "vss_commands", "run", "nope", "--environment", "development"], capture_output=True, text=True, env=environment)
        self.assertEqual(unknown.returncode, int(ExitCode.UNKNOWN_COMMAND))
        invalid = subprocess.run([sys.executable, "-m", "vss_commands", "run", "system.info", "--environment", "qa"], capture_output=True, text=True, env=environment)
        self.assertEqual(invalid.returncode, int(ExitCode.INVALID_CONFIGURATION))


if __name__ == "__main__":
    unittest.main()
