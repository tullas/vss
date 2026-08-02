from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import unittest
import io
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from vss_performance import PerformanceCorrectnessFailure, PerformanceHarness, get_profile
from vss_performance.environment import collect_environment
from vss_performance.errors import InvalidPerformanceProfile, PerformanceReportFailure
from vss_performance.metrics import latency_summary, nearest_rank, throughput
from vss_performance.profiles import HARD_MAX_CONCURRENCY, PerformanceProfile
from vss_performance.reports import report_digest, validate_report, write_report
from vss_commands.cli import main as cli_main
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning.registry import ReasoningImplementationRegistry

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/reasoning/generate-options-runtime-valid.json"


class JsonlAudit:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: dict) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode())
        finally:
            os.close(descriptor)


class PerformanceLaboratoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        fixture = self.root / "tests/fixtures/reasoning/generate-options-runtime-valid.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(FIXTURE.read_bytes())
        audit = JsonlAudit(self.root / ".local/runtime/audit/executions.jsonl")
        gateway = ReasoningGateway._for_testing(
            implementations=ReasoningImplementationRegistry.built_in(), audit=audit
        )
        self.harness = PerformanceHarness._for_testing(gateway, self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_profiles_are_explicit_immutable_and_bounded(self):
        for identity in ("ci_safe", "laptop_small", "laptop_standard"):
            profile = get_profile(identity)
            self.assertEqual(profile.version, "1")
            self.assertLessEqual(profile.concurrency, HARD_MAX_CONCURRENCY)
            with self.assertRaises(FrozenInstanceError):
                profile.concurrency = 99
        with self.assertRaises(AttributeError):
            self.harness._gateway = object()

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(InvalidPerformanceProfile):
            get_profile("arbitrary")

    def test_profile_rejects_zero_negative_excessive_and_boolean_concurrency(self):
        base = get_profile("ci_safe")
        for value in (0, -1, HARD_MAX_CONCURRENCY + 1, True):
            with self.subTest(value=value), self.assertRaises(InvalidPerformanceProfile):
                replace(base, concurrency=value)

    def test_profile_rejects_invalid_request_counts(self):
        base = get_profile("ci_safe")
        for value in (0, -1, True):
            with self.subTest(value=value), self.assertRaises(InvalidPerformanceProfile):
                replace(base, measured_requests=value)

    def test_profile_rejects_nonfinite_and_negative_timeouts(self):
        base = get_profile("ci_safe")
        for value in (-1.0, 0.0, math.nan, math.inf, -math.inf, True):
            with self.subTest(value=value), self.assertRaises(InvalidPerformanceProfile):
                replace(base, request_timeout_seconds=value)

    def test_profile_rejects_excessive_endurance(self):
        with self.assertRaises(InvalidPerformanceProfile):
            replace(get_profile("ci_safe"), endurance_seconds=61.0)

    def test_profile_rejects_arbitrary_workload_and_fixture(self):
        base = get_profile("ci_safe")
        for field, value in (("workload_identity", "shell/1"), ("fixture_identity", "../../secret")):
            with self.subTest(field=field), self.assertRaises(InvalidPerformanceProfile):
                replace(base, **{field: value})

    def test_nearest_rank_one_and_small_samples(self):
        self.assertEqual(nearest_rank([0.5], 99), 0.5)
        self.assertEqual(nearest_rank([4, 1, 3, 2], 50), 2)
        self.assertEqual(nearest_rank([1, 2, 3, 4, 5], 90), 5)

    def test_latency_summary_is_deterministic_and_complete(self):
        first = latency_summary([0.004, 0.001, 0.002, 0.002])
        second = latency_summary([0.002, 0.004, 0.002, 0.001])
        self.assertEqual(first, second)
        self.assertEqual(first["p50_ms"], 2.0)
        self.assertEqual(first["p90_ms"], 4.0)
        self.assertEqual(first["p95_ms"], 4.0)
        self.assertEqual(first["p99_ms"], 4.0)

    def test_metrics_reject_nonfinite_and_zero_duration(self):
        for value in (math.nan, math.inf, -1.0):
            with self.assertRaises(PerformanceCorrectnessFailure):
                nearest_rank([value], 50)
        with self.assertRaises(PerformanceCorrectnessFailure):
            throughput(1, 0)

    def test_throughput_uses_successes_over_elapsed_time(self):
        self.assertEqual(throughput(8, 2.0), 4.0)

    def test_ci_safe_exercises_shared_gateway_concurrently(self):
        summary, report = self.harness.run("ci_safe", environment="development")
        self.assertEqual(summary["successes"], 8)
        self.assertEqual(report["configuration"]["concurrency"], 2)
        self.assertTrue(summary["semantic_digest_match"])
        self.assertTrue(summary["audit_records_valid"])
        self.assertEqual(report["audit_validation"]["records"], 10)
        self.assertGreater(report["resources"]["audit_bytes_appended"], 0)
        self.assertEqual(len(report["profile"]["sha256"]), 64)
        self.assertEqual(len(report["workload"]["fixture_sha256"]), 64)

    def test_all_requests_have_unique_bound_audit_identities(self):
        self.harness.run("ci_safe", environment="development")
        path = self.root / ".local/runtime/audit/executions.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(records), len({record["request_id"] for record in records}))
        self.assertEqual(len(records), len({record["correlation_id"] for record in records}))

    def test_dry_run_is_separate_and_has_no_semantic_digest(self):
        summary, report = self.harness.run("ci_safe", environment="development", dry_run=True)
        self.assertTrue(summary["semantic_digest_match"])
        self.assertIsNone(report["semantic_validation"]["expected_content_digest"])
        self.assertEqual(report["semantic_validation"]["observed_content_digests"], [])

    def test_repeated_runs_have_same_semantic_digest(self):
        _, first = self.harness.run("ci_safe", environment="development")
        _, second = self.harness.run("ci_safe", environment="development")
        self.assertEqual(first["semantic_validation"]["observed_content_digests"], second["semantic_validation"]["observed_content_digests"])

    def test_concurrent_harness_runs_do_not_mix_requests(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            reports = list(executor.map(lambda _: self.harness.run("ci_safe", environment="development")[1], range(2)))
        self.assertTrue(all(report["status"] == "success" for report in reports))

    def test_prior_unrelated_audit_records_are_ignored(self):
        path = self.root / ".local/runtime/audit/executions.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"correlation_id":"unrelated"}\n')
        _, report = self.harness.run("ci_safe", environment="development")
        self.assertEqual(report["audit_validation"]["records"], 10)

    def test_environment_metadata_is_allowlisted(self):
        metadata = collect_environment()
        self.assertEqual(set(metadata), {
            "operating_system", "platform_release", "architecture", "python_version",
            "logical_cpu_count", "available_memory_bytes", "wsl", "ci",
        })
        rendered = json.dumps(metadata).lower()
        self.assertNotIn("hostname", rendered)
        self.assertNotIn("username", rendered)

    def test_report_is_bounded_payload_free_and_digest_valid(self):
        _, report = self.harness.run("ci_safe", environment="development")
        validate_report(report)
        self.assertEqual(report["report_sha256"], report_digest(report))
        rendered = json.dumps(report)
        self.assertNotIn("Select an implementation approach", rendered)
        self.assertNotIn("constraints_satisfied", rendered)

    def test_report_writer_rejects_existing_and_symlink_destinations(self):
        _, report = self.harness.run("ci_safe", environment="development")
        with self.assertRaises(PerformanceReportFailure):
            write_report(report, self.root)

    def test_report_writer_rejects_symlinked_output_directory(self):
        _, report = self.harness.run("ci_safe", environment="development")
        other_root = self.root / "other"
        other_root.mkdir()
        symlink_root = self.root / "symlink-case"
        symlink_root.mkdir()
        (symlink_root / ".local").symlink_to(other_root, target_is_directory=True)
        with self.assertRaises(PerformanceReportFailure):
            write_report(report, symlink_root)

    def test_report_validation_rejects_unknown_fields(self):
        _, report = self.harness.run("ci_safe", environment="development")
        report["extension"] = {}
        report["report_sha256"] = report_digest(report)
        with self.assertRaises(PerformanceReportFailure):
            validate_report(report)

    def test_unsupported_environment_fails_closed_without_payload_error(self):
        with self.assertRaisesRegex(PerformanceCorrectnessFailure, "unsupported") as caught:
            self.harness.run("ci_safe", environment="production")
        self.assertNotIn("Select an implementation", str(caught.exception))

    def test_worker_threads_are_cleaned_up(self):
        before = threading.active_count()
        self.harness.run("ci_safe", environment="development")
        self.assertEqual(threading.active_count(), before)

    def test_report_path_is_fixed_under_local_performance(self):
        summary, _ = self.harness.run("ci_safe", environment="development")
        self.assertTrue(summary["report_path"].startswith(".local/performance/reports/perf-"))
        self.assertTrue((self.root / summary["report_path"]).is_file())

    def test_cli_preserves_outer_envelope_and_prints_no_payload(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = cli_main([
                "performance", "reasoning", "--profile", "ci_safe",
                "--environment", "development", "--dry-run",
            ])
        response = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(response["command"], "performance.reasoning")
        self.assertEqual(response["status"], "success")
        self.assertNotIn("objective_summary", output.getvalue())

    def test_one_failed_invocation_does_not_corrupt_successes(self):
        base = self.harness._gateway

        class OneFailureGateway:
            def execute(self, request, **kwargs):
                if kwargs["correlation_id"].endswith("0002"):
                    raise RuntimeError("controlled failure")
                return base.execute(request, **kwargs)

        harness = PerformanceHarness._for_testing(OneFailureGateway(), self.root)
        results, _, _ = harness._phase(
            harness._fixture(), name="fault", count=4, concurrency=2,
            maximum_outstanding=2, environment="development", timeout_seconds=2.0,
            dry_run=False, expected_digest=get_profile("ci_safe").expected_content_digest,
            expected_option_count=4, prefix="faultisolation", starting_index=1,
            overall_deadline=__import__("time").monotonic() + 10,
        )
        self.assertEqual(sum(item.success for item in results), 3)
        self.assertEqual(sum(not item.success for item in results), 1)
        self.assertEqual(len({item.request_id for item in results}), 4)


if __name__ == "__main__":
    unittest.main()
