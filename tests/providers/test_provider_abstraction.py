from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import yaml

from vss_commands import ExitCode
from vss_providers import CONTROLLED_FRAME_PROVIDER_IDENTITY, ProviderAccess, ProviderIncompatible, ProviderRegistry, ProviderSelector
from vss_runtime import RuntimeController, RuntimePolicy

ROOT = Path(__file__).resolve().parents[2]


class ProviderAbstractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        (self.root / "capabilities").mkdir()
        (self.root / "providers/builtin").mkdir(parents=True)
        shutil.copy2(ROOT / "schemas/capability-manifest-v1.schema.json", self.root / "schemas")
        shutil.copy2(ROOT / "schemas/provider-v1.schema.json", self.root / "schemas")
        shutil.copytree(ROOT / "capabilities/time", self.root / "capabilities/time")
        shutil.copytree(
            ROOT / "providers/builtin/system-clock-local",
            self.root / "providers/builtin/system-clock-local",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def provider_manifest_path(self) -> Path:
        return self.root / "providers/builtin/system-clock-local/provider.yaml"

    @property
    def capability_manifest_path(self) -> Path:
        return self.root / "capabilities/time/manifest.yaml"

    @property
    def implementation_path(self) -> Path:
        return self.root / "providers/builtin/system-clock-local/implementation.py"

    @property
    def handler_path(self) -> Path:
        return self.root / "capabilities/time/handler.py"

    def update_yaml(self, path: Path, **updates) -> None:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        value.update(updates)
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    def controller(self, policy: RuntimePolicy | None = None) -> RuntimeController:
        return RuntimeController(root=self.root, policy=policy)

    def invoke(self, controller: RuntimeController | None = None):
        return (controller or self.controller()).run(
            command="runtime.time",
            environment="development",
            configuration={"schema_version": "1", "secret": "must-not-leak"},  # pragma: allowlist secret
            input_data={},
            correlation_id="provider-correlation",
            started_at="2026-08-01T00:00:00.000Z",
            started_clock=time.monotonic(),
        )

    def audit_records(self) -> list[dict]:
        path = self.root / ".local/runtime/audit/executions.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def use_fake_clock(self, utc: str = "2030-01-02T03:04:05.678Z", monotonic: float = 42.5) -> None:
        self.implementation_path.write_text(
            "from vss_providers.contracts import MonotonicReading, UtcTimestamp\n"
            "class FakeClock:\n"
            f"    def now_utc(self): return UtcTimestamp({utc!r})\n"
            f"    def monotonic_time(self): return MonotonicReading({monotonic!r})\n"
            "def create_provider(): return FakeClock()\n",
            encoding="utf-8",
        )

    def test_discovers_immutable_local_clock_identity(self) -> None:
        registry = ProviderRegistry(
            self.root / "providers/builtin", self.root / "schemas/provider-v1.schema.json"
        )
        providers = registry.discover()
        self.assertEqual(set(providers), {"system.clock.local"})
        metadata = providers["system.clock.local"].metadata
        self.assertEqual(
            (metadata.provider_type, metadata.name, metadata.version, metadata.provider_api_version, metadata.source),
            ("clock", "local", "1.0.0", "1", "trusted_builtin"),
        )
        with self.assertRaises(FrozenInstanceError):
            metadata.version = "changed"
        with self.assertRaises(FrozenInstanceError):
            registry.builtins_root = self.root

    def test_controlled_external_provider_is_exactly_registered_without_fallback(self) -> None:
        shutil.copytree(
            ROOT / "providers/builtin/movie-storyboard-image-openai",
            self.root / "providers/builtin/movie-storyboard-image-openai",
        )
        registry = ProviderRegistry(
            self.root / "providers/builtin", self.root / "schemas/provider-v1.schema.json")
        registration = ProviderSelector(registry).registration({
            "type": "controlled_storyboard_image_generation",
            "identity": CONTROLLED_FRAME_PROVIDER_IDENTITY, "api_version": "1",
        })
        self.assertEqual(registration.metadata.version, "1.1.0")
        self.assertEqual(registration.metadata.implementation_identity, "vss.openai-gpt-image-2-opaque-cabx")
        with self.assertRaises(Exception):
            ProviderSelector(registry).registration({
                "type": "controlled_storyboard_image_generation",
                "identity": "movie.storyboard-image.other", "api_version": "1",
            })

    def test_deterministic_fake_provider_uses_production_controller_path(self) -> None:
        self.use_fake_clock()
        first, first_code = self.invoke()
        second, second_code = self.invoke()
        self.assertEqual((first_code, second_code), (ExitCode.SUCCESS, ExitCode.SUCCESS))
        self.assertEqual(first["output"], {"utc": "2030-01-02T03:04:05.678Z"})
        self.assertEqual(first["output"], second["output"])
        registry = self.controller().provider_registry
        registration = registry.resolve("system.clock.local")
        handle = ProviderAccess(clock=registry.initialize(registration)).get_clock()
        timestamp = handle.now_utc()
        monotonic = handle.monotonic_time()
        self.assertEqual((timestamp.value, monotonic.seconds), ("2030-01-02T03:04:05.678Z", 42.5))
        with self.assertRaises(FrozenInstanceError):
            monotonic.seconds = 0
        with self.assertRaises(AttributeError):
            handle._SafeClockHandle__provider = object()
        access = ProviderAccess(clock=registry.initialize(registration))
        with self.assertRaises(AttributeError):
            access._ProviderAccess__clock = None

    def test_runtime_time_audit_has_only_safe_provider_metadata(self) -> None:
        self.use_fake_clock()
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.SUCCESS)
        record = self.audit_records()[0]
        self.assertEqual(
            record["providers"],
            [{
                "type": "clock",
                "identity": "system.clock.local",
                "version": "1.0.0",
                "authorization": "approved",
            }],
        )
        encoded = json.dumps(record)
        self.assertNotIn("2030-01-02", encoded)
        self.assertNotIn("must-not-leak", encoded)
        self.assertEqual(response["correlation_id"], record["correlation_id"])

    def test_declared_but_unauthorized_provider_is_denied_before_initialization(self) -> None:
        marker = self.root / "provider-initialized"
        self.implementation_path.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('initialized')\n"
            "def create_provider(): return object()\n",
            encoding="utf-8",
        )
        policy = RuntimePolicy(allowed_builtin_permissions=("provider_access",), allowed_provider_identities=())
        response, code = self.invoke(self.controller(policy))
        self.assertEqual(code, ExitCode.PERMISSION_DENIED)
        self.assertFalse(marker.exists())
        self.assertEqual(response["status"], "error")
        self.assertEqual(self.audit_records()[0]["providers"][0]["authorization"], "denied")

    def test_undeclared_provider_request_fails_through_empty_context_accessor(self) -> None:
        self.update_yaml(self.capability_manifest_path, permissions=[], required_providers=[])
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.PERMISSION_DENIED)
        self.assertEqual(response["errors"], ["clock provider access was not declared and authorized"])

    def test_required_provider_without_permission_and_unscoped_permission_are_invalid(self) -> None:
        self.update_yaml(self.capability_manifest_path, permissions=[])
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("provider_access", response["errors"][0])
        self.update_yaml(self.capability_manifest_path, permissions=["provider_access"], required_providers=[])
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("scoped provider", response["errors"][0])

    def test_malformed_duplicate_and_wildcard_requirements_are_rejected(self) -> None:
        value = yaml.safe_load(self.capability_manifest_path.read_text(encoding="utf-8"))
        requirement = value["required_providers"][0]
        cases = (
            [requirement, dict(requirement)],
            [{"type": "clock", "identity": "*", "api_version": "1"}],
            [{"type": "clock", "identity": "system.clock.local", "api_version": "1", "implementation": "evil.py"}],
        )
        for requirements in cases:
            with self.subTest(requirements=requirements):
                value["required_providers"] = requirements
                self.capability_manifest_path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
                response, code = self.invoke()
                self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
                self.assertEqual(response["status"], "error")

    def test_unknown_provider_and_requirement_api_mismatch_fail_closed(self) -> None:
        value = yaml.safe_load(self.capability_manifest_path.read_text(encoding="utf-8"))
        value["required_providers"][0]["identity"] = "system.clock.unknown"
        self.capability_manifest_path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.NOT_READY)
        self.assertEqual(response["errors"], ["provider not found: system.clock.unknown"])
        value["required_providers"][0] = {
            "type": "clock", "identity": "system.clock.local", "api_version": "999"
        }
        self.capability_manifest_path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("unsupported provider API", response["errors"][0])

    def test_provider_api_mismatch_and_unavailable_lifecycle_fail_closed(self) -> None:
        self.update_yaml(self.provider_manifest_path, provider_api_version="999")
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("unsupported provider API", response["errors"][0])
        self.update_yaml(self.provider_manifest_path, provider_api_version="1", lifecycle_status="retired")
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.NOT_READY)
        self.assertIn("unavailable", response["errors"][0])

    def test_unapproved_implementation_identity_and_initialization_failure_are_safe(self) -> None:
        self.update_yaml(self.provider_manifest_path, implementation_identity="substituted.provider")
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("not approved", response["errors"][0])
        self.update_yaml(self.provider_manifest_path, implementation_identity="vss.local-clock")
        self.implementation_path.write_text(
            "def create_provider(): raise RuntimeError('credential=must-not-leak')\n", encoding="utf-8"
        )
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.NOT_READY)
        self.assertNotIn("must-not-leak", json.dumps(response) + json.dumps(self.audit_records()))

    def test_arbitrary_import_path_traversal_and_symlink_escape_are_rejected(self) -> None:
        for implementation in ("os:system", "../outside.py:create_provider", "package.module.py:create_provider"):
            with self.subTest(implementation=implementation):
                self.update_yaml(self.provider_manifest_path, implementation=implementation)
                response, code = self.invoke()
                self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
                self.assertIn("provider", response["errors"][0])
        self.update_yaml(self.provider_manifest_path, implementation="implementation.py:create_provider")
        outside = self.root / "outside.py"
        outside.write_text("def create_provider(): return object()\n", encoding="utf-8")
        self.implementation_path.unlink()
        self.implementation_path.symlink_to(outside)
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("escapes trusted root", response["errors"][0])

    def test_duplicate_registration_and_provider_substitution_are_rejected(self) -> None:
        shutil.copytree(
            self.root / "providers/builtin/system-clock-local",
            self.root / "providers/builtin/duplicate",
        )
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.INVALID_CONFIGURATION)
        self.assertIn("duplicate provider identity", response["errors"][0])
        shutil.rmtree(self.root / "providers/builtin/duplicate")
        registry = ProviderRegistry(
            self.root / "providers/builtin", self.root / "schemas/provider-v1.schema.json"
        )
        registration = registry.resolve("system.clock.local")
        self.implementation_path.write_text("def create_provider(): return object()\n", encoding="utf-8")
        with self.assertRaisesRegex(ProviderIncompatible, "changed before initialization"):
            registry.initialize(registration)

    def test_provider_exception_and_output_injection_are_normalized(self) -> None:
        implementations = (
            "from vss_providers.contracts import MonotonicReading\n"
            "class Clock:\n"
            "    def now_utc(self): raise RuntimeError('API_TOKEN=must-not-leak')\n"
            "    def monotonic_time(self): return MonotonicReading(1.0)\n"
            "def create_provider(): return Clock()\n",
            "from vss_providers.contracts import MonotonicReading, UtcTimestamp\n"
            "class Clock:\n"
            "    def now_utc(self): return UtcTimestamp('2030-01-01T00:00:00.000Z\\n{\"forged\":true}')\n"
            "    def monotonic_time(self): return MonotonicReading(1.0)\n"
            "def create_provider(): return Clock()\n",
        )
        for implementation in implementations:
            with self.subTest(implementation=implementation[:40]):
                self.implementation_path.write_text(implementation, encoding="utf-8")
                response, code = self.invoke()
                self.assertEqual(code, ExitCode.EXECUTION_FAILURE)
                encoded = json.dumps(response) + json.dumps(self.audit_records())
                self.assertNotIn("must-not-leak", encoded)
                self.assertNotIn("forged", encoded)

    def test_capability_cannot_enumerate_or_mutate_provider_accessor(self) -> None:
        self.use_fake_clock()
        self.handler_path.write_text(
            "from vss_capabilities import CapabilityResult\n"
            "def execute(context, input_data, dry_run):\n"
            "    assert not hasattr(context.providers, 'list')\n"
            "    assert not hasattr(context.providers, 'all')\n"
            "    assert not hasattr(context.providers, 'get_provider')\n"
            "    try:\n        context.providers.clock = object()\n"
            "    except AttributeError:\n        pass\n"
            "    else:\n        raise AssertionError('provider accessor was mutable')\n"
            "    return CapabilityResult.success({'utc': context.providers.get_clock().now_utc().value})\n"
            "execute.sdk_api_version = '1'\n"
            "execute.capability_identity = 'runtime.time'\n"
            "execute.command_identity = 'runtime.time'\n",
            encoding="utf-8",
        )
        response, code = self.invoke()
        self.assertEqual(code, ExitCode.SUCCESS)
        self.assertEqual(response["output"], {"utc": "2030-01-02T03:04:05.678Z"})

    def test_runtime_time_handler_has_no_direct_provider_or_clock_instantiation(self) -> None:
        source = (ROOT / "capabilities/time/handler.py").read_text(encoding="utf-8")
        for prohibited in ("import time", "import datetime", "vss_providers", "LocalClockProvider", "importlib"):
            self.assertNotIn(prohibited, source)
        self.assertIn("context.providers.get_clock()", source)

    def test_exact_cli_invocation_preserves_response_contract(self) -> None:
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        completed = subprocess.run(
            [
                sys.executable, "-m", "vss_commands", "run", "runtime.time",
                "--environment", "development", "--correlation-id", "runtime-time-acceptance",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        response = json.loads(completed.stdout)
        self.assertEqual(tuple(response), (
            "command", "completed_at", "correlation_id", "duration_ms", "errors",
            "exit_code", "output", "schema_version", "started_at", "status",
        ))
        self.assertEqual(response["correlation_id"], "runtime-time-acceptance")


if __name__ == "__main__":
    unittest.main()
