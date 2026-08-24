from __future__ import annotations

import json
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

import yaml

from vss_commands import CommandRunner, ExitCode
from vss_runtime.audit import AuditLogger
from vss_runtime.controller import RuntimeController
from vss_runtime.errors import InvalidManifest, PermissionDenied, RuntimeInternalFailure
from vss_runtime.policy import RuntimePolicy
from vss_runtime.registry import CapabilityRegistry

ROOT = Path(__file__).resolve().parents[2]


def manifest(permissions: list[str] | None = None, **updates) -> dict:
    value = {
        "schema_version": "1",
        "namespace": "system",
        "name": "info",
        "version": "1.0.0",
        "description": "test capability",
        "runtime_api_version": "1",
        "entry_point": "handler.py:execute",
        "commands": [{
            "name": "system.info",
            "input_schema": {"type": "object", "additionalProperties": False},
            "output_schema": {"type": "object"},
            "supports_dry_run": True,
        }],
        "permissions": permissions or [],
        "compatibility": {"python": ">=3.11,<3.15"},
        "lifecycle_status": "active",
    }
    value.update(updates)
    return value


class FailingAuditLogger(AuditLogger):
    def append(self, record: dict) -> None:
        raise RuntimeInternalFailure("runtime audit record could not be written")


class RuntimeKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        shutil.copy2(
            ROOT / "schemas/capability-manifest-v1.schema.json",
            self.root / "schemas/capability-manifest-v1.schema.json",
        )
        self.write_capability()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_capability(self, value: dict | None = None, directory: str = "system", handler: str | None = None) -> Path:
        capability = self.root / "capabilities" / directory
        capability.mkdir(parents=True, exist_ok=True)
        (capability / "manifest.yaml").write_text(yaml.safe_dump(value or manifest(), sort_keys=False), encoding="utf-8")
        (capability / "handler.py").write_text(
            handler
            or "def execute(context, input_data, dry_run):\n"
            "    return {'command_name': 'system.info', 'command_version': '1.0.0', "
            "'os': 'TestOS', 'python_version': '3.test', 'environment': context.environment, 'dry_run': dry_run}\n",
            encoding="utf-8",
        )
        return capability

    def controller(self, **kwargs) -> RuntimeController:
        return RuntimeController(root=self.root, **kwargs)

    def run_controller(self, controller: RuntimeController | None = None, input_data: dict | None = None, correlation: str = "test-correlation"):
        return (controller or self.controller()).run(
            command="system.info",
            environment="development",
            configuration={"schema_version": "1"},
            input_data=input_data or {},
            correlation_id=correlation,
            started_at="2026-07-31T00:00:00.000Z",
            started_clock=0.0,
            dry_run=False,
        )

    def audit_records(self) -> list[dict]:
        path = self.root / ".local/runtime/audit/executions.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_discovers_system_info(self) -> None:
        capabilities = self.controller().registry.discover()
        self.assertEqual(set(capabilities), {"system.info"})
        self.assertEqual(capabilities["system.info"].manifest.command("system.info")["name"], "system.info")

    def test_manifest_schema_rejects_unknown_field(self) -> None:
        self.write_capability(manifest(unexpected="value"))
        with self.assertRaisesRegex(InvalidManifest, "Additional properties"):
            self.controller().registry.discover()

    def test_malformed_and_unsafe_yaml_are_rejected(self) -> None:
        manifest_path = self.root / "capabilities/system/manifest.yaml"
        for content in ("commands: [", "!!python/object/apply:os.system ['echo unsafe']"):
            manifest_path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaisesRegex(InvalidManifest, "malformed"):
                self.controller().registry.discover()

    def test_unsupported_schema_and_runtime_api_are_rejected(self) -> None:
        for field, message in (("schema_version", "schema version"), ("runtime_api_version", "runtime API")):
            self.write_capability(manifest(**{field: "999"}))
            with self.subTest(field=field), self.assertRaisesRegex(InvalidManifest, message):
                self.controller().registry.discover()

    def test_duplicate_capability_identity_is_rejected(self) -> None:
        self.write_capability(directory="duplicate")
        with self.assertRaisesRegex(InvalidManifest, "duplicate capability identity"):
            self.controller().registry.discover()

    def test_path_traversal_and_arbitrary_import_are_rejected(self) -> None:
        for entry_point in ("../outside.py:execute", "os:system", "package.module.py:execute"):
            self.write_capability(manifest(entry_point=entry_point))
            with self.subTest(entry_point=entry_point), self.assertRaisesRegex(InvalidManifest, "entry point is unsafe"):
                self.controller().registry.discover()

    def test_symlink_escape_and_code_outside_trusted_root_are_rejected(self) -> None:
        outside = self.root / "outside.py"
        outside.write_text("def execute(context, input_data, dry_run): return {}\n", encoding="utf-8")
        handler = self.root / "capabilities/system/handler.py"
        handler.unlink()
        handler.symlink_to(outside)
        capability = self.controller().registry.resolve_command("system.info")
        with self.assertRaisesRegex(InvalidManifest, "escapes trusted root"):
            self.controller().loader.load(capability)

    def test_capability_not_found_and_undeclared_command(self) -> None:
        controller = self.controller()
        response, code = controller.run(
            "system.health", "development", {}, {}, "missing", "2026-07-31T00:00:00.000Z", 0.0
        )
        self.assertEqual(code, ExitCode.UNKNOWN_COMMAND)
        self.assertEqual(response["errors"], ["capability not found: system.health"])

    def test_success_preserves_correlation_and_response_shape(self) -> None:
        response, code = self.run_controller(correlation="caller-id")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["correlation_id"], "caller-id")
        self.assertEqual(
            tuple(response),
            ("schema_version", "command", "correlation_id", "started_at", "status", "exit_code", "completed_at", "duration_ms", "output", "errors"),
        )
        self.assertEqual(response["output"]["command_name"], "system.info")

    def test_command_runner_generates_and_preserves_correlation_ids(self) -> None:
        runner = CommandRunner(runtime_controller=self.controller())
        generated, code = runner.run("system.info", "development")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(len(generated["correlation_id"]), 32)
        supplied, code = runner.run("system.info", "development", correlation_id="supplied-id")
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(supplied["correlation_id"], "supplied-id")

    def test_permission_denial_uses_named_exit_code_13(self) -> None:
        self.write_capability(manifest(permissions=["network"]))
        response, code = self.run_controller()
        self.assertEqual(code, ExitCode.PERMISSION_DENIED)
        self.assertEqual(int(code), 13)
        self.assertEqual(response["status"], "error")
        self.assertEqual(self.audit_records()[0]["authorization"], "denied")

    def test_unknown_permission_category_is_rejected(self) -> None:
        self.write_capability(manifest(permissions=["unknown_effect"]))
        response, code = self.run_controller()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("invalid", response["errors"][0])

    def test_malformed_input_is_rejected_before_handler(self) -> None:
        response, code = self.run_controller(input_data={"secret": "must-not-appear"})
        self.assertEqual(code, ExitCode.INVALID_INPUT)
        self.assertNotIn("must-not-appear", json.dumps(response))
        self.assertNotIn("must-not-appear", json.dumps(self.audit_records()))

    def test_handler_exception_has_failure_audit_without_secret_input(self) -> None:
        self.write_capability(handler="def execute(context, input_data, dry_run):\n    raise RuntimeError('secret-value')\n")
        response, code = self.run_controller()
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        self.assertNotIn("secret-value", json.dumps(response))
        record = self.audit_records()[0]
        self.assertEqual(record["status"], "error")
        self.assertEqual(record["exit_code"], ExitCode.EXECUTION_FAILURE)
        self.assertNotIn("secret-value", json.dumps(record))

    def test_legacy_capability_output_is_bounded_and_json_safe(self) -> None:
        self.write_capability(
            handler="def execute(context, input_data, dry_run):\n"
            "    return {'unsafe': object()}\n"
        )
        response, code = self.run_controller()
        self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
        self.assertEqual(response["output"], {})
        self.assertEqual(response["errors"], ["capability returned an invalid result"])
        self.assertEqual(self.audit_records()[0]["status"], "error")

    def test_timeout_uses_existing_named_exit_code(self) -> None:
        self.write_capability(
            handler="import time\ndef execute(context, input_data, dry_run):\n    time.sleep(0.1)\n    return {}\n"
        )
        response, code = self.controller().run(
            "system.info", "development", {}, {}, "timeout", "2026-07-31T00:00:00.000Z", 0.0,
            timeout_seconds=0.001,
        )
        self.assertEqual(code, ExitCode.TIMEOUT)
        self.assertEqual(response["errors"], ["command timed out"])

    def test_audit_is_append_only_json_lines_with_restrictive_modes(self) -> None:
        self.run_controller(correlation="line-one\ninjection")
        self.run_controller(correlation="line-two")
        path = self.root / ".local/runtime/audit/executions.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["correlation_id"], "line-one\ninjection")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(
            set(json.loads(lines[0])),
            {"schema_version", "timestamp", "correlation_id", "execution_id", "capability", "command", "status", "exit_code", "duration_ms", "declared_permissions", "authorization", "manifest_sha256", "source_commit"},
        )

    def test_audit_write_failure_cannot_return_success(self) -> None:
        controller = self.controller(audit_logger=FailingAuditLogger(self.root / "unused"))
        response, code = self.run_controller(controller)
        self.assertEqual(code, ExitCode.INTERNAL_ERROR)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["output"], {})

    def test_audit_symlink_escape_cannot_return_success(self) -> None:
        outside = self.root.parent / "outside-audit"
        audit_root = self.root / ".local/runtime/audit"
        audit_root.parent.mkdir(parents=True)
        audit_root.symlink_to(outside, target_is_directory=True)
        response, code = self.run_controller()
        self.assertEqual(code, ExitCode.INTERNAL_ERROR)
        self.assertEqual(response["status"], "error")
        self.assertFalse(outside.exists())

    def test_manifest_digest_change_before_import_is_rejected(self) -> None:
        controller = self.controller()
        capability = controller.registry.resolve_command("system.info")
        capability.manifest_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(InvalidManifest, "changed before loading"):
            controller.loader.load(capability)

    def test_controlled_media_kill_switches_fail_closed(self) -> None:
        RuntimePolicy().authorize_controlled_media()
        for updates in ({"external_effects_killed": True}, {"controlled_media_killed": True}):
            with self.subTest(updates=updates), self.assertRaises(PermissionDenied):
                RuntimePolicy(**updates).authorize_controlled_media()


if __name__ == "__main__":
    unittest.main()
