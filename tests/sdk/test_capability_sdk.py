from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from vss_capabilities import (
    MANIFEST_SCHEMA_VERSION,
    RUNTIME_API_VERSION,
    SDK_API_VERSION,
    CapabilityResult,
    SafeCapabilityError,
)
from vss_capabilities.testing import CapabilityTestHarness
from vss_commands import ExitCode
from vss_runtime.errors import IncompatibleRuntimeAPI

ROOT = Path(__file__).resolve().parents[2]
CAPABILITY = ROOT / "capabilities/runtime"
SCHEMA = ROOT / "schemas/capability-manifest-v1.schema.json"


class CapabilitySDKTests(unittest.TestCase):
    def harness(self):
        return CapabilityTestHarness(CAPABILITY, SCHEMA)

    @staticmethod
    def write_handler(harness: CapabilityTestHarness, source: str) -> None:
        (harness.root / "capabilities/runtime/handler.py").write_text(source, encoding="utf-8")

    @staticmethod
    def update_manifest(harness: CapabilityTestHarness, **updates) -> None:
        path = harness.root / "capabilities/runtime/manifest.yaml"
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        value.update(updates)
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    def test_versions_and_manifest_contract(self) -> None:
        self.assertEqual((MANIFEST_SCHEMA_VERSION, RUNTIME_API_VERSION, SDK_API_VERSION), ("1", "1", "1"))
        with self.harness() as harness:
            manifest = harness.manifest()
            self.assertEqual(manifest.identity, "runtime.echo")
            self.assertEqual(manifest.sdk_api_version, SDK_API_VERSION)
            self.assertEqual(manifest.permissions, ())

    def test_runtime_echo_uses_controller_and_normalizes_result(self) -> None:
        value = {"text": "hello", "items": [1, True, None, {"nested": "safe"}]}
        with self.harness() as harness:
            response, code = harness.execute("runtime.echo", {"value": value}, correlation_id="sdk-test")
            self.assertEqual(code, ExitCode.SUCCESS)
            self.assertEqual(response["output"], {"value": value})
            self.assertEqual(response["correlation_id"], "sdk-test")
            self.assertEqual(harness.audit_records()[0]["capability"], "runtime.echo")

    def test_unknown_input_field_and_dry_run_are_rejected(self) -> None:
        with self.harness() as harness:
            response, code = harness.execute("runtime.echo", {"value": "safe", "extra": True})
            self.assertEqual(code, ExitCode.INVALID_INPUT)
            self.assertEqual(response["output"], {})

            response, code = harness.controller.run(
                "runtime.echo", "development", {}, {"value": "safe"}, "dry-run",
                "2026-01-01T00:00:00.000Z", 0.0, dry_run=True,
            )
            self.assertEqual(code, ExitCode.INVALID_INPUT)

    def test_size_nesting_and_non_json_values_are_rejected_before_handler_import(self) -> None:
        cases = (
            {"value": "x" * 4097},
            {"value": {"a": {"b": {"c": {"d": {"e": {"f": "too-deep"}}}}}}},
            {"value": object()},
            {"value": float("nan")},
        )
        for value in cases:
            with self.subTest(value=type(value["value"]).__name__), self.harness() as harness:
                marker = harness.root / "handler-imported"
                self.write_handler(
                    harness,
                    "from pathlib import Path\n"
                    f"Path({str(marker)!r}).write_text('imported')\n"
                    "def execute(context, input_data, dry_run):\n    return {}\n"
                    "execute.sdk_api_version = '1'\n"
                    "execute.capability_identity = 'runtime.echo'\n"
                    "execute.command_identity = 'runtime.echo'\n",
                )
                response, code = harness.execute("runtime.echo", value)
                self.assertEqual(code, ExitCode.INVALID_INPUT)
                self.assertFalse(marker.exists())
                self.assertEqual(response["output"], {})

    def test_context_is_bounded_and_immutable(self) -> None:
        with self.harness() as harness:
            self.write_handler(
                harness,
                "from dataclasses import FrozenInstanceError\n"
                "from vss_capabilities import CapabilityResult\n"
                "def execute(context, input_data, dry_run):\n"
                "    assert not hasattr(context, 'secrets')\n"
                "    assert not hasattr(context, 'environment_variables')\n"
                "    assert not hasattr(context, 'docker_socket')\n"
                "    assert context.capability_identity == 'runtime.echo'\n"
                "    assert context.command_identity == 'runtime.echo'\n"
                "    assert len(context.execution_id) == 32\n"
                "    assert context.safe_configuration == {}\n"
                "    try:\n        context.environment = 'changed'\n"
                "    except FrozenInstanceError:\n        pass\n"
                "    else:\n        raise AssertionError('context was mutable')\n"
                "    try:\n        context.safe_configuration['new'] = 'value'\n"
                "    except TypeError:\n        pass\n"
                "    else:\n        raise AssertionError('configuration was mutable')\n"
                "    return CapabilityResult.success({'value': input_data['value']})\n"
                "execute.sdk_api_version = '1'\n"
                "execute.capability_identity = 'runtime.echo'\n"
                "execute.command_identity = 'runtime.echo'\n",
            )
            response, code = harness.execute("runtime.echo", {"value": "safe"})
            self.assertEqual(code, ExitCode.SUCCESS)
            self.assertEqual(response["output"], {"value": "safe"})

    def test_context_defensively_freezes_constructor_inputs(self) -> None:
        from vss_capabilities import CapabilityExecutionContext

        configuration = {"nested": {"items": ["one"]}}
        permissions = ["network"]
        context = CapabilityExecutionContext(
            environment="development",
            correlation_id="correlation",
            execution_id="execution",
            capability_identity="runtime.echo",
            command_identity="runtime.echo",
            authorized_permissions=permissions,
            safe_configuration=configuration,
        )
        configuration["nested"]["items"].append("two")
        permissions.append("secrets")
        self.assertEqual(context.authorized_permissions, ("network",))
        self.assertEqual(context.safe_configuration["nested"]["items"], ("one",))
        with self.assertRaises(TypeError):
            context.safe_configuration["nested"]["new"] = "value"

    def test_arbitrary_result_and_raw_exception_are_normalized(self) -> None:
        handlers = (
            "def execute(context, input_data, dry_run):\n    return object()\nexecute.sdk_api_version = '1'\nexecute.capability_identity = 'runtime.echo'\nexecute.command_identity = 'runtime.echo'\n",
            "def execute(context, input_data, dry_run):\n    raise RuntimeError('API_TOKEN=must-not-leak')\nexecute.sdk_api_version = '1'\nexecute.capability_identity = 'runtime.echo'\nexecute.command_identity = 'runtime.echo'\n",
            "from vss_capabilities import CapabilityResult\n"
            "def execute(context, input_data, dry_run):\n    return CapabilityResult.success({'value': object()})\n"
            "execute.sdk_api_version = '1'\n"
            "execute.capability_identity = 'runtime.echo'\n"
            "execute.command_identity = 'runtime.echo'\n",
        )
        for source in handlers:
            with self.subTest(source=source[:30]), self.harness() as harness:
                self.write_handler(harness, source)
                response, code = harness.execute("runtime.echo", {"value": "safe"})
                self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
                self.assertEqual(response["output"], {})
                self.assertNotIn("must-not-leak", json.dumps(response))
                self.assertNotIn("must-not-leak", json.dumps(harness.audit_records()))

    def test_capability_result_rejects_unsafe_values_at_construction(self) -> None:
        with self.assertRaises((TypeError, ValueError)):
            CapabilityResult.success({"value": object()})
        with self.assertRaises(ValueError):
            CapabilityResult.success({"value": "x" * 4097})
        with self.assertRaises(ValueError):
            CapabilityResult(output={"value": "partial"}, error=SafeCapabilityError("failed"))

    def test_typed_safe_failure_uses_named_exit_code(self) -> None:
        error = SafeCapabilityError("request was safely rejected", ExitCode.INVALID_INPUT)
        result = CapabilityResult.failure(error)
        self.assertEqual(result.error.exit_code, ExitCode.INVALID_INPUT)
        with self.assertRaises(ValueError):
            SafeCapabilityError("invalid", ExitCode.INTERNAL_ERROR)
        with self.harness() as harness:
            self.write_handler(
                harness,
                "from vss_capabilities import CapabilityResult, SafeCapabilityError\n"
                "from vss_commands import ExitCode\n"
                "def execute(context, input_data, dry_run):\n"
                "    return CapabilityResult.failure(SafeCapabilityError('request was safely rejected', ExitCode.INVALID_INPUT))\n"
                "execute.sdk_api_version = '1'\n"
                "execute.capability_identity = 'runtime.echo'\n"
                "execute.command_identity = 'runtime.echo'\n",
            )
            response, code = harness.execute("runtime.echo", {"value": "safe"})
            self.assertEqual(code, ExitCode.INVALID_INPUT)
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["errors"], ["request was safely rejected"])

    def test_handler_cannot_claim_undeclared_permission_or_mutate_context(self) -> None:
        with self.harness() as harness:
            self.write_handler(
                harness,
                "from vss_capabilities import CapabilityResult\n"
                "def execute(context, input_data, dry_run):\n"
                "    context.authorized_permissions += ('network',)\n"
                "    return CapabilityResult.success({'value': 'unsafe'})\n"
                "execute.sdk_api_version = '1'\n"
                "execute.capability_identity = 'runtime.echo'\n"
                "execute.command_identity = 'runtime.echo'\n",
            )
            response, code = harness.execute("runtime.echo", {"value": "safe"})
            self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
            self.assertEqual(response["output"], {})
            self.assertEqual(harness.audit_records()[0]["declared_permissions"], [])

    def test_declared_permission_still_requires_runtime_policy_authorization(self) -> None:
        with self.harness() as harness:
            self.update_manifest(harness, permissions=["network"])
            response, code = harness.execute("runtime.echo", {"value": "safe"})
            self.assertEqual(code, ExitCode.PERMISSION_DENIED)
            self.assertEqual(harness.audit_records()[0]["authorization"], "denied")

    def test_output_and_audit_injection_remain_structured_and_input_free(self) -> None:
        value = "line-one\n{\"event_type\":\"forged\",\"api_token\":\"secret-value\"}"
        with self.harness() as harness:
            response, code = harness.execute("runtime.echo", {"value": value})
            self.assertEqual(code, ExitCode.SUCCESS)
            self.assertEqual(response["output"]["value"], value)
            records = harness.audit_records()
            self.assertEqual(len(records), 1)
            self.assertNotIn("secret-value", json.dumps(records))
            self.assertNotIn("forged", json.dumps(records))

    def test_manifest_and_handler_sdk_mismatch_and_incompatible_version_fail(self) -> None:
        with self.harness() as harness:
            self.write_handler(
                harness,
                "def execute(context, input_data, dry_run): return {}\nexecute.sdk_api_version = '999'\nexecute.capability_identity = 'runtime.echo'\nexecute.command_identity = 'runtime.echo'\n",
            )
            response, code = harness.execute("runtime.echo", {"value": "safe"})
            self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
            self.assertIn("do not match", response["errors"][0])
        with self.harness() as harness:
            self.update_manifest(harness, sdk_api_version="999")
            with self.assertRaises(IncompatibleRuntimeAPI):
                harness.controller.registry.discover()

    def test_manifest_and_handler_identity_mismatch_fails_closed(self) -> None:
        with self.harness() as harness:
            self.write_handler(
                harness,
                "def execute(context, input_data, dry_run): return {}\n"
                "execute.sdk_api_version = '1'\n"
                "execute.capability_identity = 'runtime.other'\n"
                "execute.command_identity = 'runtime.echo'\n",
            )
            response, code = harness.execute("runtime.echo", {"value": "safe"})
            self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
            self.assertIn("identities do not match", response["errors"][0])

    def test_harness_reports_deterministic_outcomes(self) -> None:
        with self.harness() as harness:
            first, _ = harness.execute("runtime.echo", {"value": {"b": 2, "a": 1}})
            second, _ = harness.execute("runtime.echo", {"value": {"b": 2, "a": 1}})
            self.assertEqual(harness.deterministic_outcome(first), harness.deterministic_outcome(second))

    def test_exact_cli_invocation_uses_existing_input_file_contract(self) -> None:
        input_path = ROOT / ".local/runtime/echo-sdk-test.json"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text('{"value":{"message":"hello"}}\n', encoding="utf-8")
        try:
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            completed = subprocess.run(
                [
                    sys.executable, "-m", "vss_commands", "run", "runtime.echo",
                    "--environment", "development", "--input", str(input_path),
                    "--correlation-id", "runtime-echo-acceptance",
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            input_path.unlink(missing_ok=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        response = json.loads(completed.stdout)
        self.assertEqual(response["command"], "runtime.echo")
        self.assertEqual(response["correlation_id"], "runtime-echo-acceptance")
        self.assertEqual(response["output"], {"value": {"message": "hello"}})


if __name__ == "__main__":
    unittest.main()
