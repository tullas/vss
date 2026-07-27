from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
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

    def test_bootstrap_commands_are_registered(self) -> None:
        for name in ("bootstrap.check", "bootstrap.local", "bootstrap.verify"):
            command = get_command(name)
            self.assertIsNotNone(command)
            self.assertTrue(command.metadata.supports_dry_run)

    def test_bootstrap_check_reports_missing_tools_without_changes(self) -> None:
        with patch("vss_commands.commands._bootstrap_support.shutil.which", return_value=None):
            response, code = CommandRunner().run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertFalse(response["output"]["checks"]["docker"]["cli_available"])
        self.assertFalse(response["output"]["checks"]["opentofu"]["available"])
        self.assertNotIn("password", json.dumps(response).lower())

    def test_bootstrap_check_detects_systemd_disabled_wsl(self) -> None:
        with (
            patch("vss_commands.commands._bootstrap_support.platform.release", return_value="5.15.90-microsoft-standard-WSL2"),
            patch("vss_commands.commands._bootstrap_support.shutil.which", return_value=None),
        ):
            response, code = CommandRunner().run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertTrue(response["output"]["checks"]["platform"]["is_wsl"])
        self.assertFalse(response["output"]["checks"]["systemd"]["active"])

    def test_systemd_running_is_usable_when_pid1_is_systemd(self) -> None:
        with (
            patch("vss_commands.commands._bootstrap_support.shutil.which", return_value="/usr/bin/systemctl"),
            patch("vss_commands.commands._bootstrap_support._pid1_name", return_value="systemd"),
            patch("vss_commands.commands._bootstrap_support._run", return_value=(True, "running")),
        ):
            from vss_commands.commands._bootstrap_support import systemd_status

            self.assertEqual(systemd_status(), {"active": True, "status": "running", "pid1": "systemd"})

    def test_wsl_with_systemd_pid1_reports_ready(self) -> None:
        with (
            patch("vss_commands.commands._bootstrap_support.platform.release", return_value="5.15-microsoft-standard-WSL2"),
            patch(
                "vss_commands.commands._bootstrap_support.shutil.which",
                side_effect=lambda name: "/usr/bin/systemctl" if name == "systemctl" else None,
            ),
            patch("vss_commands.commands._bootstrap_support._pid1_name", return_value="systemd"),
            patch("vss_commands.commands._bootstrap_support._run", return_value=(True, "running")),
        ):
            from vss_commands.commands._bootstrap_support import bootstrap_report

            report = bootstrap_report()
        self.assertTrue(report["platform"]["is_wsl"])
        self.assertTrue(report["systemd"]["active"])

    def test_systemd_degraded_is_usable_despite_nonzero_status(self) -> None:
        with (
            patch("vss_commands.commands._bootstrap_support.shutil.which", return_value="/usr/bin/systemctl"),
            patch("vss_commands.commands._bootstrap_support._pid1_name", return_value="systemd"),
            patch("vss_commands.commands._bootstrap_support._run", return_value=(False, "degraded")),
        ):
            from vss_commands.commands._bootstrap_support import systemd_status

            self.assertTrue(systemd_status()["active"])
            self.assertEqual(systemd_status()["status"], "degraded")

    def test_systemd_is_unavailable_without_systemctl(self) -> None:
        with patch("vss_commands.commands._bootstrap_support.shutil.which", return_value=None):
            from vss_commands.commands._bootstrap_support import systemd_status

            self.assertEqual(systemd_status()["status"], "unavailable")
            self.assertFalse(systemd_status()["active"])

    def test_bootstrap_check_reuses_accessible_docker_daemon(self) -> None:
        def which(name: str) -> str | None:
            return f"/usr/bin/{name}" if name in {"docker", "tofu", "systemctl"} else None

        with (
            patch("vss_commands.commands._bootstrap_support.shutil.which", side_effect=which),
            patch(
                "vss_commands.commands._bootstrap_support._run",
                side_effect=[(True, "systemd"), (True, "Docker version 27.0"), (True, "27.0") , (True, "OpenTofu v1.9.0")],
            ),
            patch("vss_commands.commands._bootstrap_support.socket.socket"),
        ):
            response, code = CommandRunner().run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertTrue(response["output"]["checks"]["docker"]["daemon_accessible"])

    def test_bootstrap_verify_missing_tool_fails_without_leaking_values(self) -> None:
        with patch("vss_commands.commands._bootstrap_support.shutil.which", return_value=None):
            response, code = CommandRunner().run("bootstrap.verify", "development")
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        self.assertNotIn("password", json.dumps(response).lower())

    def test_bootstrap_local_propagates_safe_ansible_diagnostics(self) -> None:
        failed = subprocess.CompletedProcess(
            args=["ansible-playbook"],
            returncode=1,
            stdout='TASK [local_toolchain : Enable Docker] ***\nfatal: [localhost]: FAILED! => {"msg":"Missing privilege credential", "credential":"dont-leak"}',
            stderr="",
        )
        with (
            patch("vss_commands.commands.bootstrap_local.shutil.which", return_value="/usr/bin/ansible-playbook"),
            patch("vss_commands.commands.bootstrap_local.run_capture", return_value=failed),
        ):
            response, code = CommandRunner().run("bootstrap.local", "development")
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        self.assertEqual(response["output"]["ansible"]["failed_task"], "local_toolchain : Enable Docker")
        encoded = json.dumps(response)
        self.assertNotIn("dont-leak", encoded)

    def test_bootstrap_local_discovers_ansible_from_managed_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ansible = Path(directory) / "ansible-playbook"
            ansible.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            ansible.chmod(0o755)
            completed = subprocess.CompletedProcess(args=[str(ansible)], returncode=0, stdout="", stderr="")
            with (
                patch.dict(os.environ, {"PATH": directory}),
                patch("vss_commands.commands.bootstrap_local.run_capture", return_value=completed) as run_capture,
            ):
                response, code = CommandRunner().run("bootstrap.local", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["status"], "success")
        self.assertEqual(run_capture.call_args.args[0][0], str(ansible))

    def test_bootstrap_local_interactive_uses_inherited_terminal(self) -> None:
        completed = subprocess.CompletedProcess(args=["ansible-playbook"], returncode=0)
        with (
            patch("vss_commands.commands.bootstrap_local.shutil.which", return_value="/venv/bin/ansible-playbook"),
            patch("vss_commands.commands.bootstrap_local.sys.stdin.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stdout.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stderr.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.run_interactive", return_value=completed) as interactive,
            patch("vss_commands.commands.bootstrap_local.run_capture") as capture,
        ):
            response, code = CommandRunner().run("bootstrap.local", "development", ask_become_pass=True)
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["status"], "success")
        self.assertIn("--ask-become-pass", interactive.call_args.args[0])
        capture.assert_not_called()

    def test_bootstrap_local_terminal_without_password_flag_stays_interactive(self) -> None:
        completed = subprocess.CompletedProcess(args=["ansible-playbook"], returncode=0)
        with (
            patch("vss_commands.commands.bootstrap_local.shutil.which", return_value="/venv/bin/ansible-playbook"),
            patch("vss_commands.commands.bootstrap_local.sys.stdin.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stdout.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stderr.isatty", return_value=True),
            patch("vss_commands.runner.sys.stdin.isatty", return_value=True),
            patch("vss_commands.runner.sys.stdout.isatty", return_value=True),
            patch("vss_commands.runner.sys.stderr.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.run_interactive", return_value=completed) as interactive,
            patch("vss_commands.commands.bootstrap_local.run_capture") as capture,
        ):
            response, code = CommandRunner().run("bootstrap.local", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertNotIn("--ask-become-pass", interactive.call_args.args[0])
        capture.assert_not_called()
        self.assertNotIn("password", json.dumps(response).lower())

    def test_bootstrap_local_interactive_requires_terminal_before_launch(self) -> None:
        with (
            patch("vss_commands.commands.bootstrap_local.shutil.which", return_value="/venv/bin/ansible-playbook"),
            patch("vss_commands.commands.bootstrap_local.sys.stdin.isatty", return_value=False),
            patch("vss_commands.commands.bootstrap_local.run_interactive") as interactive,
        ):
            response, code = CommandRunner().run("bootstrap.local", "development", ask_become_pass=True)
        self.assertEqual(code, ExitCode.NOT_READY)
        self.assertEqual(response["errors"], ["bootstrap requires an interactive terminal for privilege escalation"])
        interactive.assert_not_called()

    def test_bootstrap_local_interactive_failure_is_generic_and_preserves_status(self) -> None:
        completed = subprocess.CompletedProcess(args=["ansible-playbook"], returncode=7)
        with (
            patch("vss_commands.commands.bootstrap_local.shutil.which", return_value="/venv/bin/ansible-playbook"),
            patch("vss_commands.commands.bootstrap_local.sys.stdin.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stdout.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stderr.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.run_interactive", return_value=completed),
        ):
            response, code = CommandRunner().run("bootstrap.local", "development", ask_become_pass=True)
        self.assertEqual(code, 7)
        self.assertEqual(response["output"], {"ansible": {"return_code": 7}})
        encoded = json.dumps(response).lower()
        for forbidden in ("become password", "sudo prompt", "typed-secret"):
            self.assertNotIn(forbidden, encoded)

    def test_run_interactive_inherits_descriptors_and_normalizes_interrupt(self) -> None:
        from vss_commands.commands._bootstrap_support import run_interactive

        command = ["ansible-playbook", "--ask-become-pass"]
        with patch("vss_commands.commands._bootstrap_support.subprocess.run", side_effect=KeyboardInterrupt) as launched:
            result = run_interactive(command, Path("/tmp"))
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, ExitCode.INTERRUPTED)
        launched.assert_called_once_with(command, cwd=Path("/tmp"), check=False)

    def test_bootstrap_local_ctrl_c_returns_interrupted_json(self) -> None:
        with (
            patch("vss_commands.commands.bootstrap_local.shutil.which", return_value="/venv/bin/ansible-playbook"),
            patch("vss_commands.commands.bootstrap_local.sys.stdin.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stdout.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.sys.stderr.isatty", return_value=True),
            patch("vss_commands.commands.bootstrap_local.run_interactive", side_effect=KeyboardInterrupt),
        ):
            response, code = CommandRunner().run("bootstrap.local", "development", ask_become_pass=True)
        self.assertEqual(code, ExitCode.INTERRUPTED)
        self.assertEqual(response["errors"], ["command interrupted"])
        self.assertNotIn("password", json.dumps(response).lower())

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
        checked = subprocess.run(
            [sys.executable, "-m", "vss_commands", "bootstrap", "check", "--environment", "development"],
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(checked.returncode, 0)
        self.assertIn('"checks"', checked.stdout)


if __name__ == "__main__":
    unittest.main()
