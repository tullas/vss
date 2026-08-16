from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
import unittest
import io
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from unittest.mock import patch
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from vss_performance import PerformanceCorrectnessFailure, PerformanceHarness, PerformanceTimeout, get_profile
from vss_performance.environment import collect_environment
from vss_performance.errors import InvalidPerformanceProfile, PerformanceReportFailure
from vss_performance.metrics import latency_summary, nearest_rank, throughput
from vss_performance.profiles import HARD_MAX_CONCURRENCY, HARD_MAX_REQUESTS, PerformanceProfile
from vss_performance.reports import report_digest, validate_report, write_report
from vss_commands.cli import main as cli_main
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning.registry import ReasoningImplementationRegistry
from vss_runtime.audit import AuditLogger, synchronized_audit_access

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/reasoning/generate-options-runtime-valid.json"


class JsonlAudit:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._logger = AuditLogger(path.parent)

    def append(self, record: dict) -> None:
        self._logger.append(record)


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
        for value in (0, -1, HARD_MAX_REQUESTS + 1, True):
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

    def test_profile_rejects_unknown_identity_version_and_nonhex_digest(self):
        base = get_profile("ci_safe")
        for field, value in (("identity", "custom"), ("version", "2"), ("expected_content_digest", "z" * 64)):
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
        for value in (math.nan, math.inf, -1.0, True):
            with self.assertRaises(PerformanceCorrectnessFailure):
                nearest_rank([value], 50)
        with self.assertRaises(PerformanceCorrectnessFailure):
            nearest_rank([], 50)
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
        for _ in range(10):
            with ThreadPoolExecutor(max_workers=4) as executor:
                reports = list(executor.map(
                    lambda _: self.harness.run("ci_safe", environment="development")[1],
                    range(4),
                ))
            self.assertTrue(all(report["status"] == "success" for report in reports))
            self.assertTrue(all(report["audit_validation"]["records"] == 10 for report in reports))
            self.assertEqual(
                {tuple(report["semantic_validation"]["observed_content_digests"]) for report in reports},
                {(get_profile("ci_safe").expected_content_digest,)},
            )
        records = [
            json.loads(line)
            for line in (self.root / ".local/runtime/audit/executions.jsonl").read_bytes().splitlines()
        ]
        self.assertEqual(len(records), 400)
        self.assertEqual(len({record["request_id"] for record in records}), 400)
        self.assertEqual(len({record["correlation_id"] for record in records}), 400)

    def test_audit_reader_waits_for_complete_record_publication(self):
        path = self.root / ".local/runtime/audit/executions.jsonl"
        path.parent.mkdir(parents=True)
        snapshot = self.harness._audit_snapshot()
        partial_published = threading.Event()
        complete_publication = threading.Event()

        def publish_record() -> None:
            with synchronized_audit_access():
                descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
                try:
                    os.write(descriptor, b'{"correlation_id":"concurrent"')
                    partial_published.set()
                    self.assertTrue(complete_publication.wait(timeout=2))
                    os.write(descriptor, b'}\n')
                finally:
                    os.close(descriptor)

        with ThreadPoolExecutor(max_workers=2) as executor:
            writer = executor.submit(publish_record)
            self.assertTrue(partial_published.wait(timeout=2))
            reader = executor.submit(self.harness._audit_records, snapshot)
            self.assertFalse(reader.done())
            complete_publication.set()
            writer.result(timeout=2)
            self.assertEqual(reader.result(timeout=2), [{"correlation_id": "concurrent"}])

    def test_prior_unrelated_audit_records_are_ignored(self):
        path = self.root / ".local/runtime/audit/executions.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"correlation_id":"unrelated"}\n')
        _, report = self.harness.run("ci_safe", environment="development")
        self.assertEqual(report["audit_validation"]["records"], 10)

    def test_audit_rotation_truncation_and_partial_tail_fail_closed(self):
        path = self.root / ".local/runtime/audit/executions.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"correlation_id":"prior"}\n')
        snapshot = self.harness._audit_snapshot()
        path.write_text("")
        with self.assertRaisesRegex(PerformanceCorrectnessFailure, "truncated"):
            self.harness._audit_records(snapshot)

        path.write_text('{"correlation_id":"prior"}\n')
        snapshot = self.harness._audit_snapshot()
        path.unlink()
        path.write_text('{"correlation_id":"replacement"}\n')
        with self.assertRaisesRegex(PerformanceCorrectnessFailure, "replaced"):
            self.harness._audit_records(snapshot)

        snapshot = self.harness._audit_snapshot()
        with path.open("ab") as stream:
            stream.write(b'{"correlation_id":"partial"}')
        with self.assertRaisesRegex(PerformanceCorrectnessFailure, "partial"):
            self.harness._audit_records(snapshot)

        path.write_text('{"correlation_id":"prior"}\n')
        snapshot = self.harness._audit_snapshot()
        with path.open("ab") as stream:
            stream.write(b'{"correlation_id":not-json}\n')
        with self.assertRaisesRegex(PerformanceCorrectnessFailure, "malformed"):
            self.harness._audit_records(snapshot)

    def test_audit_association_rejects_duplicate_and_wrong_status(self):
        self.harness.run("ci_safe", environment="development")
        records = [json.loads(line) for line in (self.root / ".local/runtime/audit/executions.jsonl").read_text().splitlines()]
        record = records[-1]
        invocation = type("Invocation", (), {
            "correlation_id": record["correlation_id"], "request_id": record["request_id"], "success": True,
            "request_digest": record["request_sha256"], "result_digest": record["result_sha256"],
        })()
        duplicate = self.harness._validate_audit_associations(
            [record, record], [invocation], dry_run=False,
            expected_digest=get_profile("ci_safe").expected_content_digest,
        )
        self.assertEqual(duplicate["duplicate"], 1)
        wrong = dict(record)
        wrong["status"] = "failed"
        invalid = self.harness._validate_audit_associations(
            [wrong], [invocation], dry_run=False,
            expected_digest=get_profile("ci_safe").expected_content_digest,
        )
        self.assertEqual(invalid["invalid"], 1)
        with self.assertRaisesRegex(PerformanceCorrectnessFailure, "collide"):
            self.harness._validate_audit_associations(
                [record], [invocation, invocation], dry_run=False,
                expected_digest=get_profile("ci_safe").expected_content_digest,
            )

    def test_concurrent_audit_writes_remain_complete_json_lines(self):
        logger = AuditLogger(self.root / "audit", trusted_root=self.root)
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda index: logger.append({"index": index}), range(100)))
        lines = (self.root / "audit/executions.jsonl").read_bytes().splitlines()
        self.assertEqual(len(lines), 100)
        self.assertEqual({json.loads(line)["index"] for line in lines}, set(range(100)))

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
        path = self.root / ".local/performance/reports" / f"{report['report_id']}.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_report_digest_changes_with_material_evidence(self):
        _, report = self.harness.run("ci_safe", environment="development")
        original = report["report_sha256"]
        report["warnings"].append("material review warning")
        self.assertNotEqual(original, report_digest(report))

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

    def test_report_schema_rejects_false_success_and_dry_run_digest(self):
        _, report = self.harness.run("ci_safe", environment="development")
        report["counters"]["failures"] = 1
        report["report_sha256"] = report_digest(report)
        with self.assertRaises(PerformanceReportFailure):
            validate_report(report)

        _, dry_report = self.harness.run("ci_safe", environment="development", dry_run=True)
        dry_report["semantic_validation"]["expected_content_digest"] = "0" * 64
        dry_report["report_sha256"] = report_digest(dry_report)
        with self.assertRaises(PerformanceReportFailure):
            validate_report(dry_report)

    def test_report_validation_rejects_accounting_and_throughput_mismatch(self):
        _, report = self.harness.run("ci_safe", environment="development")
        report["counters"]["admitted"] += 1
        report["report_sha256"] = report_digest(report)
        with self.assertRaises(PerformanceReportFailure):
            validate_report(report)

        _, report = self.harness.run("ci_safe", environment="development")
        report["throughput_requests_per_second"] += 1
        report["report_sha256"] = report_digest(report)
        with self.assertRaises(PerformanceReportFailure):
            validate_report(report)

    def test_report_writer_rejects_special_file_destination(self):
        _, report = self.harness.run("ci_safe", environment="development")
        report["report_id"] = "perf-" + "a" * 32
        report["report_sha256"] = report_digest(report)
        destination = self.root / ".local/performance/reports" / f"{report['report_id']}.json"
        os.mkfifo(destination)
        with self.assertRaises(PerformanceReportFailure):
            write_report(report, self.root)

    def test_missing_smoke_audit_stops_before_measured_phase_and_writes_failure(self):
        class DiscardingAudit:
            def append(self, record):
                pass

        gateway = ReasoningGateway._for_testing(
            implementations=ReasoningImplementationRegistry.built_in(), audit=DiscardingAudit()
        )
        harness = PerformanceHarness._for_testing(gateway, self.root)
        with self.assertRaises(PerformanceCorrectnessFailure):
            harness.run("ci_safe", environment="development")
        reports = list((self.root / ".local/performance/reports").glob("*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual([phase["name"] for phase in report["phases"]], ["smoke"])

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

    def test_cli_unknown_profile_uses_existing_invalid_input_exit(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = cli_main([
                "performance", "reasoning", "--profile", "unknown",
                "--environment", "development",
            ])
        response = json.loads(output.getvalue())
        self.assertEqual(exit_code, 11)
        self.assertEqual(response["exit_code"], 11)
        self.assertEqual(response["status"], "error")

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

    def test_sliding_window_never_exceeds_profile_outstanding_bound(self):
        base = self.harness._gateway
        active = 0
        maximum = 0
        lock = threading.Lock()

        class ObservedGateway:
            def execute(self, request, **kwargs):
                nonlocal active, maximum
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                try:
                    time.sleep(0.005)
                    return base.execute(request, **kwargs)
                finally:
                    with lock:
                        active -= 1

        harness = PerformanceHarness._for_testing(ObservedGateway(), self.root)
        results, phase, _ = harness._phase(
            harness._fixture(), name="bounded", count=12, concurrency=2,
            maximum_outstanding=2, environment="development", timeout_seconds=2,
            dry_run=False, expected_digest=get_profile("ci_safe").expected_content_digest,
            expected_option_count=4, prefix="boundedwindow", starting_index=1,
            overall_deadline=time.monotonic() + 10,
        )
        self.assertEqual(maximum, 2)
        self.assertEqual(len(results), 12)
        self.assertEqual(phase["submitted"], phase["completed"])
        self.assertEqual(phase["cancellations"], 0)

    def test_total_timeout_cancels_queued_work_and_accounts_for_running_work(self):
        base = self.harness._gateway

        class SlowGateway:
            def execute(self, request, **kwargs):
                time.sleep(0.05)
                return base.execute(request, **kwargs)

        harness = PerformanceHarness._for_testing(SlowGateway(), self.root)
        results, phase, _ = harness._phase(
            harness._fixture(), name="timeout", count=4, concurrency=1,
            maximum_outstanding=4, environment="development", timeout_seconds=2,
            dry_run=False, expected_digest=get_profile("ci_safe").expected_content_digest,
            expected_option_count=4, prefix="timeoutwindow", starting_index=1,
            overall_deadline=time.monotonic() + 0.01,
        )
        self.assertTrue(phase["timed_out"])
        self.assertEqual(phase["submitted"], 4)
        self.assertEqual(phase["completed"] + phase["cancellations"], 4)
        self.assertEqual(len(results), phase["completed"])

    def test_total_timeout_writes_failed_report_and_never_returns_success(self):
        profile = replace(get_profile("ci_safe"), total_timeout_seconds=0.001)
        base = self.harness._gateway

        class SlowGateway:
            def execute(self, request, **kwargs):
                time.sleep(0.02)
                return base.execute(request, **kwargs)

        harness = PerformanceHarness._for_testing(SlowGateway(), self.root)
        with patch("vss_performance.harness.get_profile", return_value=profile):
            with self.assertRaises(PerformanceTimeout):
                harness.run("ci_safe", environment="development")
        reports = list((self.root / ".local/performance/reports").glob("*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counters"]["timeouts"], 1)
        self.assertTrue(any(phase["timed_out"] for phase in report["phases"]))

    def test_concurrent_dry_run_and_generation_remain_isolated(self):
        template = self.harness._fixture()
        profile = get_profile("ci_safe")
        with ThreadPoolExecutor(max_workers=2) as executor:
            normal = executor.submit(
                self.harness._invoke, template, request_id="req-mixed-normal",
                correlation_id="corr-mixed-normal", environment="development",
                timeout_seconds=2, dry_run=False,
                expected_digest=profile.expected_content_digest, expected_option_count=4,
            )
            dry = executor.submit(
                self.harness._invoke, template, request_id="req-mixed-dry",
                correlation_id="corr-mixed-dry", environment="development",
                timeout_seconds=2, dry_run=True,
                expected_digest=profile.expected_content_digest, expected_option_count=4,
            )
        self.assertTrue(normal.result().success)
        self.assertEqual(normal.result().content_digest, profile.expected_content_digest)
        self.assertTrue(dry.result().success)
        self.assertIsNone(dry.result().content_digest)

    def test_provider_strategy_invalid_result_and_audit_faults_are_isolated(self):
        base = ReasoningImplementationRegistry.built_in()

        class SelectiveProvider:
            def generate_option_primitives(self, context):
                if context.correlation_id.endswith("0002"):
                    raise RuntimeError("controlled provider failure")
                return base.provider.generate_option_primitives(context)

        class SelectiveStrategy:
            def generate(self, context, provider):
                if context.correlation_id.endswith("0002"):
                    raise RuntimeError("controlled strategy failure")
                return base.strategy.generate(context, provider)

        class InvalidResultStrategy:
            def generate(self, context, provider):
                payload, calls, iterations = base.strategy.generate(context, provider)
                if context.correlation_id.endswith("0002"):
                    payload["common_sections"]["facts"] = [{
                        "id": "fabricated", "statement": "Not admitted.", "evidence_references": [],
                    }]
                return payload, calls, iterations

        class SelectiveAudit(JsonlAudit):
            def append(self, record):
                if record["correlation_id"].endswith("0002"):
                    raise RuntimeError("controlled audit failure")
                super().append(record)

        class SelectiveSlowProvider:
            def generate_option_primitives(self, context):
                if context.correlation_id.endswith("0002"):
                    time.sleep(0.2)
                return base.provider.generate_option_primitives(context)

        cases = (
            (base.strategy, SelectiveProvider(), JsonlAudit, 2.0),
            (SelectiveStrategy(), base.provider, JsonlAudit, 2.0),
            (InvalidResultStrategy(), base.provider, JsonlAudit, 2.0),
            (base.strategy, base.provider, SelectiveAudit, 2.0),
            (base.strategy, SelectiveSlowProvider(), JsonlAudit, 0.1),
        )
        for case_index, (strategy, provider, audit_type, timeout_seconds) in enumerate(cases, start=1):
            case_root = self.root / f"fault-{case_index}"
            fixture = case_root / "tests/fixtures/reasoning/generate-options-runtime-valid.json"
            fixture.parent.mkdir(parents=True)
            fixture.write_bytes(FIXTURE.read_bytes())
            audit = audit_type(case_root / ".local/runtime/audit/executions.jsonl")
            implementations = ReasoningImplementationRegistry(
                base.strategy_identity, base.provider_identity, strategy, provider,
            )
            gateway = ReasoningGateway._for_testing(implementations=implementations, audit=audit)
            harness = PerformanceHarness._for_testing(gateway, case_root)
            results, _, _ = harness._phase(
                harness._fixture(), name="fault", count=4, concurrency=2,
                maximum_outstanding=2, environment="development", timeout_seconds=timeout_seconds,
                dry_run=False, expected_digest=get_profile("ci_safe").expected_content_digest,
                expected_option_count=4, prefix="faultisolation", starting_index=1,
                overall_deadline=time.monotonic() + 10,
            )
            self.assertEqual(sum(item.success for item in results), 3)
            self.assertEqual(sum(not item.success for item in results), 1)

    def test_warmup_and_stress_failures_stop_later_phases(self):
        base = self.harness._gateway

        class SelectiveFailureGateway:
            def __init__(self, suffix):
                self.suffix = suffix

            def execute(self, request, **kwargs):
                if kwargs["correlation_id"].endswith(self.suffix):
                    raise RuntimeError("controlled phase failure")
                return base.execute(request, **kwargs)

        warmup_harness = PerformanceHarness._for_testing(SelectiveFailureGateway("0002"), self.root)
        with self.assertRaises(PerformanceCorrectnessFailure):
            warmup_harness.run("ci_safe", environment="development")
        report_path = max((self.root / ".local/performance/reports").glob("*.json"), key=lambda path: path.stat().st_mtime_ns)
        warmup_report = json.loads(report_path.read_text())
        self.assertEqual([phase["name"] for phase in warmup_report["phases"]], ["smoke", "warmup"])

        stress_root = self.root / "stress-stop"
        fixture = stress_root / "tests/fixtures/reasoning/generate-options-runtime-valid.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(FIXTURE.read_bytes())
        audit = JsonlAudit(stress_root / ".local/runtime/audit/executions.jsonl")
        gateway = ReasoningGateway._for_testing(
            implementations=ReasoningImplementationRegistry.built_in(), audit=audit
        )

        class StressFailureGateway:
            def execute(self, request, **kwargs):
                if kwargs["correlation_id"].endswith("0011"):
                    raise RuntimeError("controlled stress failure")
                return gateway.execute(request, **kwargs)

        stress_harness = PerformanceHarness._for_testing(StressFailureGateway(), stress_root)
        stress_profile = replace(
            get_profile("ci_safe"), stress_concurrency_steps=(1,),
            stress_requests_per_step=2, endurance_seconds=0.1, endurance_request_limit=2,
        )
        with patch("vss_performance.harness.get_profile", return_value=stress_profile):
            with self.assertRaises(PerformanceCorrectnessFailure):
                stress_harness.run("ci_safe", environment="development")
        report_path = next((stress_root / ".local/performance/reports").glob("*.json"))
        stress_report = json.loads(report_path.read_text())
        self.assertEqual(stress_report["phases"][-1]["name"], "stress-1")
        self.assertNotIn("endurance", [phase["name"] for phase in stress_report["phases"]])


if __name__ == "__main__":
    unittest.main()
