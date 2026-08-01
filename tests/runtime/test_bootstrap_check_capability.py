from __future__ import annotations

import json
import shutil
import subprocess
import threading
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from vss_commands import CommandRunner, ExitCode
from vss_runtime import RuntimeController, RuntimePolicy
from vss_runtime.host_inspection import HostInspectionError, HostInspector
from vss_workflows import WorkflowController
from vss_workflows.operations import OperationRegistry

ROOT = Path(__file__).resolve().parents[2]


def report(**updates) -> dict:
    value = {
        "platform": {"system": "Linux", "release": "test", "is_wsl": False},
        "systemd": {"active": True, "status": "running", "pid1": "systemd"},
        "docker": {
            "cli_available": True,
            "version": "Docker version 27.0",
            "daemon_accessible": True,
            "daemon_version": "27.0",
        },
        "opentofu": {"available": True, "version": "OpenTofu v1.9.0"},
        "ports": {"9000": {"conflict": False, "available": True}, "9001": {"conflict": False, "available": True}},
    }
    value.update(updates)
    return value


class FakeHostInspector:
    def __init__(self, value: dict | None = None, failure: Exception | None = None) -> None:
        self.value = value or report()
        self.failure = failure
        self.calls = 0

    def bootstrap_check(self) -> dict:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.value


class BlockingHostInspector:
    def bootstrap_check(self) -> dict:
        threading.Event().wait(0.05)
        return report()


class BootstrapCheckCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        shutil.copy2(ROOT / "schemas/capability-manifest-v1.schema.json", self.root / "schemas")
        shutil.copy2(ROOT / "schemas/workflow-v1.schema.json", self.root / "schemas")
        shutil.copytree(ROOT / "capabilities/bootstrap", self.root / "capabilities/bootstrap")
        shutil.copytree(ROOT / "capabilities/system", self.root / "capabilities/system")
        shutil.copytree(ROOT / "workflows/builtin", self.root / "workflows/builtin")
        self.host = FakeHostInspector()
        self.runtime = RuntimeController(root=self.root, host_inspector=self.host)
        self.runner = CommandRunner(runtime_controller=self.runtime)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def manifest_path(self) -> Path:
        return self.root / "capabilities/bootstrap/manifest.yaml"

    def audit_records(self) -> list[dict]:
        path = self.root / ".local/runtime/audit/executions.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_manifest_and_shared_implementation_boundary(self) -> None:
        manifest = self.runtime.registry.resolve_command("bootstrap.check").manifest
        self.assertEqual(
            (manifest.schema_version, manifest.runtime_api_version, manifest.sdk_api_version),
            ("1", "1", "1"),
        )
        self.assertEqual(manifest.identity, "bootstrap.check")
        self.assertEqual([command["name"] for command in manifest.commands], ["bootstrap.check"])
        self.assertEqual(set(manifest.permissions), {"filesystem_read", "subprocess"})
        legacy_source = (ROOT / "src/vss_commands/commands/bootstrap_check.py").read_text(encoding="utf-8")
        handler_source = (ROOT / "capabilities/bootstrap/handler.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", legacy_source + handler_source)
        self.assertNotIn("bootstrap_report", legacy_source + handler_source)
        self.assertIn("host_inspection.bootstrap_check()", handler_source)

    def test_legacy_and_runtime_invocations_preserve_envelope_and_audit_once(self) -> None:
        for correlation, dry_run in (("legacy-correlation", False), ("runtime-correlation", True)):
            with self.subTest(correlation=correlation):
                response, code = self.runner.run(
                    "bootstrap.check", "development", correlation_id=correlation, dry_run=dry_run
                )
                self.assertEqual(code, ExitCode.SUCCESS)
                self.assertEqual(response["command"], "bootstrap.check")
                self.assertEqual(response["correlation_id"], correlation)
                self.assertEqual(
                    response["output"],
                    {"environment": "development", "dry_run": dry_run, "checks": report()},
                )
                self.assertNotIn("schema_version", response["output"])
        capability_records = [
            record for record in self.audit_records() if record.get("capability") == "bootstrap.check"
        ]
        self.assertEqual(len(capability_records), 2)
        self.assertEqual(
            {record["correlation_id"] for record in capability_records},
            {"legacy-correlation", "runtime-correlation"},
        )
        self.assertTrue(all(record["execution_id"] for record in capability_records))

    def test_structural_compatibility_for_representative_probe_conditions(self) -> None:
        cases = {
            "tools-unavailable": report(
                docker={"cli_available": False, "version": None, "daemon_accessible": False, "daemon_version": None},
                opentofu={"available": False, "version": None},
            ),
            "daemon-inaccessible": report(
                docker={
                    "cli_available": True,
                    "version": "Docker version 27.0",
                    "daemon_accessible": False,
                    "daemon_version": None,
                }
            ),
            "wsl-systemd-running": report(
                platform={"system": "Linux", "release": "microsoft-wsl2", "is_wsl": True},
                systemd={"active": True, "status": "running", "pid1": "systemd"},
            ),
            "wsl-systemd-unavailable": report(
                platform={"system": "Linux", "release": "microsoft-wsl2", "is_wsl": True},
                systemd={"active": False, "status": "unavailable", "pid1": "init"},
            ),
            "port-conflict": report(
                ports={"9000": {"conflict": True, "available": False}, "9001": {"conflict": False, "available": True}}
            ),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                runtime = RuntimeController(root=self.root, host_inspector=FakeHostInspector(expected))
                response, code = CommandRunner(runtime_controller=runtime).run("bootstrap.check", "development")
                self.assertEqual(code, ExitCode.SUCCESS)
                self.assertEqual(response["output"]["checks"], expected)

    def test_permission_denial_and_inflation_fail_before_probe(self) -> None:
        denied = RuntimeController(root=self.root, policy=RuntimePolicy(), host_inspector=self.host)
        response, code = CommandRunner(runtime_controller=denied).run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.PERMISSION_DENIED)
        self.assertEqual(self.host.calls, 0)
        value = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
        value["permissions"].append("network")
        self.manifest_path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        response, code = self.runner.run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.PERMISSION_DENIED)
        self.assertEqual(self.host.calls, 0)

    def test_probe_boundary_rejects_executable_arguments_path_and_shell_injection(self) -> None:
        for name, arguments in (("bash", ("-c", "id")), ("docker", ("info;id",)), ("tofu", ("version", "--json"))):
            with self.subTest(name=name), self.assertRaises(HostInspectionError):
                HostInspector._run(name, arguments)
        with patch("vss_runtime.host_inspection.shutil.which", return_value="/tmp/attacker/docker"), patch(
            "vss_runtime.host_inspection.Path.resolve", return_value=Path("/tmp/attacker/docker")
        ), patch("vss_runtime.host_inspection.Path.is_file", return_value=True):
            with self.assertRaisesRegex(HostInspectionError, "outside approved"):
                HostInspector._resolve_executable("docker")

    def test_probe_timeout_and_output_injection_are_safe(self) -> None:
        with patch.object(HostInspector, "_resolve_executable", return_value=Path("/usr/bin/docker")), patch(
            "vss_runtime.host_inspection.subprocess.run",
            side_effect=subprocess.TimeoutExpired("docker", 1),
        ):
            self.assertEqual(HostInspector._run("docker", ("--version",)), (False, ""))
        self.assertIsNone(HostInspector._safe_version("token=must-not-leak\nforged"))  # pragma: allowlist secret

    def test_handler_exception_is_normalized_without_environment_leakage(self) -> None:
        secret = "M2_5_PRIVATE_VALUE"  # pragma: allowlist secret
        runtime = RuntimeController(root=self.root, host_inspector=FakeHostInspector(failure=RuntimeError(secret)))
        response, code = CommandRunner(runtime_controller=runtime).run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        encoded = json.dumps(response) + json.dumps(self.audit_records())
        self.assertNotIn(secret, encoded)

    def test_malformed_probe_result_and_timeout_fail_safely(self) -> None:
        malformed = RuntimeController(root=self.root, host_inspector=FakeHostInspector({"unexpected": True}))
        response, code = CommandRunner(runtime_controller=malformed).run("bootstrap.check", "development")
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        self.assertEqual(response["output"], {})
        timed = RuntimeController(root=self.root, host_inspector=BlockingHostInspector())
        response, code = CommandRunner(runtime_controller=timed).run(
            "bootstrap.check", "development", timeout_seconds=0.001
        )
        self.assertEqual(code, ExitCode.TIMEOUT)
        self.assertEqual(response["errors"], ["command timed out"])

    def test_workflow_uses_runtime_controller_and_shared_correlation(self) -> None:
        operations = OperationRegistry(command_runner=self.runner)
        workflow = WorkflowController(root=self.root, operations=operations)
        result, code = workflow.run("runtime-smoke", "development", "workflow-correlation")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual([step["operation"] for step in result["steps"]], ["system.info", "bootstrap.check"])
        capability_records = [record for record in self.audit_records() if "capability" in record]
        self.assertEqual([record["capability"] for record in capability_records], ["system.info", "bootstrap.check"])
        self.assertTrue(all(record["correlation_id"] == "workflow-correlation" for record in capability_records))
