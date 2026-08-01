from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from vss_commands import ExitCode
from vss_runtime.audit import AuditLogger
from vss_runtime.errors import RuntimeInternalFailure
from vss_workflows.controller import WorkflowController
from vss_workflows.errors import InvalidWorkflow, WorkflowNotFound
from vss_workflows.operations import OperationRegistry

ROOT = Path(__file__).resolve().parents[2]


def workflow(**updates) -> dict:
    value = {
        "schema_version": "1",
        "name": "runtime-smoke",
        "version": "1.0.0",
        "description": "test workflow",
        "runtime_api_version": "1",
        "execution_policy": {"mode": "sequential", "stop_on_failure": True},
        "steps": [
            {"id": "runtime-info", "operation": "system.info", "input": {}, "timeout_seconds": 10, "continue_on_error": False},
            {"id": "bootstrap-readiness", "operation": "bootstrap.check", "input": {}, "timeout_seconds": 30, "continue_on_error": False},
        ],
    }
    value.update(updates)
    return value


class FakeRunner:
    def __init__(self, responses: list[tuple[dict, int]] | None = None, raises: bool = False) -> None:
        self.responses = responses or []
        self.raises = raises
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise RuntimeError("unsafe exception detail")
        if self.responses:
            return self.responses.pop(0)
        operation = kwargs["command"]
        output = (
            {"command_name": "system.info", "command_version": "1.0.0", "os": "TestOS", "python_version": "3.test", "environment": kwargs["environment"], "dry_run": False}
            if operation == "system.info"
            else {"environment": kwargs["environment"], "dry_run": False, "checks": {}}
        )
        return {"status": "success", "output": output, "errors": []}, int(ExitCode.SUCCESS)


class FailingAuditLogger(AuditLogger):
    def append(self, record: dict) -> None:
        raise RuntimeInternalFailure("runtime audit record could not be written")


class WorkflowEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        shutil.copy2(ROOT / "schemas/workflow-v1.schema.json", self.root / "schemas/workflow-v1.schema.json")
        self.write_workflow()
        self.runner = FakeRunner()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_workflow(self, value: dict | None = None, filename: str = "runtime-smoke.yaml", content: str | None = None) -> Path:
        directory = self.root / "workflows/builtin"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_text(content if content is not None else yaml.safe_dump(value or workflow(), sort_keys=False), encoding="utf-8")
        return path

    def controller(self, runner: FakeRunner | None = None, audit_logger: AuditLogger | None = None) -> WorkflowController:
        operations = OperationRegistry(command_runner=runner or self.runner)
        return WorkflowController(root=self.root, operations=operations, audit_logger=audit_logger)

    def audit_records(self) -> list[dict]:
        path = self.root / ".local/runtime/audit/executions.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_discovers_and_describes_runtime_smoke(self) -> None:
        controller = self.controller()
        self.assertEqual(controller.list_workflows(), [{"name": "runtime-smoke", "version": "1.0.0", "description": "test workflow"}])
        description = controller.describe_workflow("runtime-smoke")
        self.assertEqual([step["operation"] for step in description["steps"]], ["system.info", "bootstrap.check"])
        self.assertNotIn("input", description["steps"][0])

    def test_unsafe_and_malformed_yaml_are_rejected(self) -> None:
        path = self.root / "workflows/builtin/runtime-smoke.yaml"
        for content in ("steps: [", "!!python/object/apply:os.system ['echo unsafe']"):
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaisesRegex(InvalidWorkflow, "malformed"):
                self.controller().registry.discover()

    def test_path_traversal_is_not_resolved(self) -> None:
        with self.assertRaises(WorkflowNotFound):
            self.controller().registry.resolve("../runtime-smoke")

    def test_workflow_not_found_has_named_exit_code(self) -> None:
        result, code = self.controller().run("missing-workflow", "development")
        self.assertEqual(code, ExitCode.WORKFLOW_NOT_FOUND)
        self.assertEqual(result["errors"], ["workflow not found: missing-workflow"])

    def test_symlink_escape_is_rejected(self) -> None:
        outside = self.root / "outside.yaml"
        outside.write_text(yaml.safe_dump(workflow()), encoding="utf-8")
        path = self.root / "workflows/builtin/runtime-smoke.yaml"
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(InvalidWorkflow, "escapes trusted root"):
            self.controller().registry.discover()

    def test_duplicate_workflow_name_is_rejected(self) -> None:
        self.write_workflow(filename="duplicate.yaml")
        with self.assertRaisesRegex(InvalidWorkflow, "duplicate workflow name"):
            self.controller().registry.discover()

    def test_duplicate_step_id_is_rejected(self) -> None:
        value = workflow()
        value["steps"][1]["id"] = value["steps"][0]["id"]
        self.write_workflow(value)
        with self.assertRaisesRegex(InvalidWorkflow, "duplicate step IDs"):
            self.controller().registry.discover()

    def test_unsupported_versions_have_named_exit_code(self) -> None:
        for field in ("schema_version", "runtime_api_version"):
            self.write_workflow(workflow(**{field: "999"}))
            result, code = self.controller().run("runtime-smoke", "development")
            self.assertEqual(code, ExitCode.UNSUPPORTED_WORKFLOW_VERSION)
            self.assertEqual(result["status"], "failed")

    def test_unknown_operation_and_recursive_invocation_are_rejected(self) -> None:
        for operation, message in (("unknown.operation", "unknown workflow operation"), ("workflow.runtime-smoke", "recursive")):
            value = workflow()
            value["steps"][0]["operation"] = operation
            self.write_workflow(value)
            result, code = self.controller().run("runtime-smoke", "development")
            self.assertEqual(code, ExitCode.UNKNOWN_WORKFLOW_OPERATION)
            self.assertIn(message, result["errors"][0])

    def test_arbitrary_executable_and_embedded_shell_are_rejected(self) -> None:
        executable = workflow()
        executable["steps"][0]["executable"] = "/bin/sh"
        shell = workflow()
        shell["steps"][0]["input"] = {"value": "$(touch /tmp/unsafe)"}
        for value, message in ((executable, "Additional properties"), (shell, "shell fragment")):
            self.write_workflow(value)
            with self.subTest(message=message), self.assertRaisesRegex(InvalidWorkflow, message):
                self.controller().registry.discover()

    def test_unknown_fields_continue_on_error_step_limit_and_timeout_fail(self) -> None:
        unknown = workflow(unexpected=True)
        continuation = workflow()
        continuation["steps"][0]["continue_on_error"] = True
        excessive = workflow(steps=[workflow()["steps"][0] | {"id": f"step-{index}"} for index in range(33)])
        timeout = workflow()
        timeout["steps"][0]["timeout_seconds"] = 0
        for value in (unknown, continuation, excessive, timeout):
            self.write_workflow(value)
            with self.assertRaises(InvalidWorkflow):
                self.controller().registry.discover()

    def test_success_is_sequential_deterministic_and_audited(self) -> None:
        result, code = self.controller().run("runtime-smoke", "development", "caller-correlation")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["correlation_id"], "caller-correlation")
        self.assertEqual([step["operation"] for step in result["steps"]], ["system.info", "bootstrap.check"])
        self.assertEqual([call["command"] for call in self.runner.calls], ["system.info", "bootstrap.check"])
        self.assertEqual(
            tuple(result),
            ("schema_version", "workflow", "workflow_version", "workflow_execution_id", "correlation_id", "status", "started_at", "completed_at", "duration_ms", "steps", "errors"),
        )
        records = self.audit_records()
        self.assertEqual([record["event_type"] for record in records], ["workflow_started", "step_started", "step_completed", "step_started", "step_completed", "workflow_completed"])
        self.assertEqual(stat.S_IMODE((self.root / ".local/runtime/audit").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root / ".local/runtime/audit/executions.jsonl").stat().st_mode), 0o600)

    def test_generated_execution_and_correlation_ids(self) -> None:
        result, code = self.controller().run("runtime-smoke", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(len(result["workflow_execution_id"]), 32)
        self.assertEqual(len(result["correlation_id"]), 32)

    def test_first_step_failure_stops_and_marks_second_skipped(self) -> None:
        failure = ({"status": "error", "output": {}, "errors": ["safe failure"]}, int(ExitCode.EXECUTION_FAILURE))
        runner = FakeRunner(responses=[failure])
        result, code = self.controller(runner).run("runtime-smoke", "development")
        self.assertEqual(code, ExitCode.WORKFLOW_EXECUTION_FAILURE)
        self.assertEqual([step["status"] for step in result["steps"]], ["failed", "skipped"])
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual([record["event_type"] for record in self.audit_records()][-3:], ["step_failed", "step_completed", "workflow_failed"])

    def test_step_timeout_maps_to_workflow_timeout(self) -> None:
        failure = ({"status": "error", "output": {}, "errors": ["command timed out"]}, int(ExitCode.TIMEOUT))
        result, code = self.controller(FakeRunner(responses=[failure])).run("runtime-smoke", "development")
        self.assertEqual(code, ExitCode.WORKFLOW_TIMEOUT)
        self.assertEqual(result["steps"][1]["status"], "skipped")

    def test_handler_exception_is_filtered_and_stops(self) -> None:
        result, code = self.controller(FakeRunner(raises=True)).run("runtime-smoke", "development")
        self.assertEqual(code, ExitCode.WORKFLOW_EXECUTION_FAILURE)
        self.assertNotIn("unsafe exception detail", json.dumps(result))
        self.assertEqual(result["steps"][1]["status"], "skipped")

    def test_secret_like_input_and_audit_injection_do_not_leak(self) -> None:
        value = workflow()
        value["steps"][0]["input"] = {"api_token": "do-not-record"}
        self.write_workflow(value)
        result, _ = self.controller().run("runtime-smoke", "development", "line-one\ninjection")
        encoded = json.dumps(self.audit_records())
        self.assertNotIn("do-not-record", encoded)
        lines = (self.root / ".local/runtime/audit/executions.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 6)
        self.assertEqual(json.loads(lines[0])["correlation_id"], "line-one\ninjection")
        self.assertEqual(result["status"], "succeeded")

    def test_audit_write_failure_prevents_execution(self) -> None:
        logger = FailingAuditLogger(self.root / "unused")
        result, code = self.controller(audit_logger=logger).run("runtime-smoke", "development")
        self.assertEqual(code, ExitCode.WORKFLOW_INTERNAL_ERROR)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.runner.calls, [])

    def test_manifest_change_before_execution_is_rejected(self) -> None:
        controller = self.controller()
        registered = controller.registry.resolve("runtime-smoke")
        registered.manifest_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(InvalidWorkflow, "changed before execution"):
            controller.registry.verify_integrity(registered)

    def test_cli_list_describe_and_exact_run(self) -> None:
        environment = {"PYTHONPATH": str(ROOT / "src")}
        listed = subprocess.run([sys.executable, "-m", "vss_commands", "workflow", "list"], capture_output=True, text=True, env=environment)
        described = subprocess.run([sys.executable, "-m", "vss_commands", "workflow", "describe", "runtime-smoke"], capture_output=True, text=True, env=environment)
        executed = subprocess.run(
            [sys.executable, "-m", "vss_commands", "workflow", "run", "runtime-smoke", "--environment", "development", "--correlation-id", "workflow-acceptance"],
            capture_output=True, text=True, env=environment,
        )
        self.assertEqual((listed.returncode, described.returncode, executed.returncode), (0, 0, 0))
        self.assertEqual(json.loads(executed.stdout)["correlation_id"], "workflow-acceptance")
        self.assertEqual([step["operation"] for step in json.loads(executed.stdout)["steps"]], ["system.info", "bootstrap.check"])


if __name__ == "__main__":
    unittest.main()
