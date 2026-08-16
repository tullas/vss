from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import stat
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning_contracts import canonical_bytes, canonical_digest, load_json_document
from vss_runtime.audit import synchronized_audit_access

from .environment import collect_environment, collect_resources
from .errors import PerformanceCorrectnessFailure, PerformanceTimeout
from .metrics import latency_summary, throughput
from .profiles import get_profile, profile_digest
from .reports import report_digest, write_report

_AUDIT_RELATIVE = Path(".local/runtime/audit/executions.jsonl")
_FIXTURE_RELATIVE = Path("tests/fixtures/reasoning/generate-options-runtime-valid.json")
_MAX_AUDIT_READ_BYTES = 8 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class _Invocation:
    request_id: str
    correlation_id: str
    latency_seconds: float
    success: bool
    content_digest: str | None
    request_digest: str
    result_digest: str | None
    failure: str | None


@dataclass(frozen=True, slots=True)
class _AuditSnapshot:
    existed: bool
    device: int | None
    inode: int | None
    offset: int
    anchor_start: int
    anchor_sha256: str | None


_AUDIT_KEYS = frozenset({
    "event_type", "recorded_at", "execution_id", "request_id", "correlation_id",
    "task_identity", "task_version", "result_family", "result_version",
    "strategy_identity", "strategy_version", "provider_identity", "provider_version",
    "semantic_registry_sha256", "implementation_registry_sha256", "request_sha256",
    "result_sha256", "semantic_content_sha256", "policy_identity", "policy_version",
    "authorization", "lifecycle_status", "duration_ms", "deadline_outcome",
    "budget_outcome", "status", "failure_classification",
})


def _safe_commit(repository_root: Path) -> str | None:
    """Read a loose local HEAD ref without invoking Git or exposing paths."""
    try:
        git_dir = repository_root / ".git"
        head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
        if head.startswith("ref: "):
            ref = head[5:]
            if not ref.startswith("refs/heads/") or ".." in ref:
                return None
            head = (git_dir / ref).read_text(encoding="ascii").strip()
        if len(head) == 40 and all(character in "0123456789abcdef" for character in head):
            return head
    except (OSError, UnicodeError):
        pass
    return None


class PerformanceHarness:
    """Bounded observer of the real M3.2 Gateway; never an authority boundary."""

    __slots__ = ("_gateway", "_repository_root")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("performance harness configuration is immutable")

    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[2]
        object.__setattr__(self, "_gateway", ReasoningGateway.built_in())
        object.__setattr__(self, "_repository_root", root)

    @classmethod
    def _for_testing(cls, gateway: ReasoningGateway, repository_root: Path) -> "PerformanceHarness":
        instance = object.__new__(cls)
        object.__setattr__(instance, "_gateway", gateway)
        object.__setattr__(instance, "_repository_root", repository_root.resolve())
        return instance

    def _fixture(self) -> dict[str, Any]:
        path = (self._repository_root / _FIXTURE_RELATIVE).resolve()
        if not path.is_relative_to(self._repository_root) or path.is_symlink() or not path.is_file():
            raise PerformanceCorrectnessFailure("performance fixture is unavailable")
        try:
            value = load_json_document(path.read_bytes())
        except Exception as exc:
            raise PerformanceCorrectnessFailure("performance fixture is invalid") from exc
        if type(value) is not dict:
            raise PerformanceCorrectnessFailure("performance fixture is invalid")
        return value

    def _audit_snapshot(self) -> _AuditSnapshot:
        with synchronized_audit_access():
            return self._audit_snapshot_synchronized()

    def _audit_snapshot_synchronized(self) -> _AuditSnapshot:
        path = self._repository_root / _AUDIT_RELATIVE
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return _AuditSnapshot(False, None, None, 0, 0, None)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise PerformanceCorrectnessFailure("development audit path is unsafe")
        anchor_start = max(0, metadata.st_size - 4096)
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                metadata.st_dev, metadata.st_ino, metadata.st_size
            ):
                raise PerformanceCorrectnessFailure("development audit output changed during inspection")
            os.lseek(descriptor, anchor_start, os.SEEK_SET)
            anchor = os.read(descriptor, metadata.st_size - anchor_start)
            if len(anchor) != metadata.st_size - anchor_start:
                raise PerformanceCorrectnessFailure("development audit output changed during inspection")
        except OSError as exc:
            raise PerformanceCorrectnessFailure("development audit output is unreadable") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return _AuditSnapshot(
            True, metadata.st_dev, metadata.st_ino, metadata.st_size, anchor_start,
            hashlib.sha256(anchor).hexdigest(),
        )

    def _audit_records(self, snapshot: _AuditSnapshot) -> list[dict[str, Any]]:
        with synchronized_audit_access():
            return self._audit_records_synchronized(snapshot)

    def _audit_records_synchronized(self, snapshot: _AuditSnapshot) -> list[dict[str, Any]]:
        path = self._repository_root / _AUDIT_RELATIVE
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise PerformanceCorrectnessFailure("development audit output is unavailable")
            if snapshot.existed and (before.st_dev, before.st_ino) != (snapshot.device, snapshot.inode):
                raise PerformanceCorrectnessFailure("development audit output was replaced")
            if before.st_size < snapshot.offset:
                raise PerformanceCorrectnessFailure("development audit output was truncated")
            if snapshot.existed:
                os.lseek(descriptor, snapshot.anchor_start, os.SEEK_SET)
                anchor_length = snapshot.offset - snapshot.anchor_start
                anchor = b""
                while len(anchor) < anchor_length:
                    chunk = os.read(descriptor, anchor_length - len(anchor))
                    if not chunk:
                        raise PerformanceCorrectnessFailure("development audit output was replaced")
                    anchor += chunk
                if hashlib.sha256(anchor).hexdigest() != snapshot.anchor_sha256:
                    raise PerformanceCorrectnessFailure("development audit output was replaced")
            length = before.st_size - snapshot.offset
            if length > _MAX_AUDIT_READ_BYTES:
                raise PerformanceCorrectnessFailure("development audit output is oversized")
            os.lseek(descriptor, snapshot.offset, os.SEEK_SET)
            chunks: list[bytes] = []
            remaining = length
            while remaining:
                chunk = os.read(descriptor, min(remaining, 65536))
                if not chunk:
                    raise PerformanceCorrectnessFailure("development audit output changed during reading")
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(descriptor)
            if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino) or after.st_size < before.st_size:
                raise PerformanceCorrectnessFailure("development audit output changed during reading")
            data = b"".join(chunks)
        except FileNotFoundError as exc:
            if not snapshot.existed:
                return []
            raise PerformanceCorrectnessFailure("development audit output is unavailable") from exc
        except OSError as exc:
            raise PerformanceCorrectnessFailure("development audit output is unreadable") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if data and not data.endswith(b"\n"):
            raise PerformanceCorrectnessFailure("development audit output has a partial record")
        records: list[dict[str, Any]] = []
        for line in data.splitlines():
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PerformanceCorrectnessFailure("development audit output is malformed") from exc
            if type(value) is not dict:
                raise PerformanceCorrectnessFailure("development audit output is malformed")
            records.append(value)
        return records

    @staticmethod
    def _validate_audit_associations(
        records: list[dict[str, Any]],
        invocations: list[_Invocation],
        *,
        dry_run: bool,
        expected_digest: str,
    ) -> dict[str, int]:
        expected = {item.correlation_id: item for item in invocations}
        if len(expected) != len(invocations) or len({item.request_id for item in invocations}) != len(invocations):
            raise PerformanceCorrectnessFailure("benchmark request identities collide")
        selected = [record for record in records if record.get("correlation_id") in expected]
        by_correlation: dict[str, list[dict[str, Any]]] = {}
        malformed = 0
        execution_ids: set[str] = set()
        for record in selected:
            if frozenset(record) != _AUDIT_KEYS:
                malformed += 1
            correlation = record.get("correlation_id")
            if type(correlation) is str:
                by_correlation.setdefault(correlation, []).append(record)
        duplicate = sum(max(0, len(group) - 1) for group in by_correlation.values())
        missing = len(set(expected) - set(by_correlation))
        invalid = 0
        for correlation, invocation in expected.items():
            group = by_correlation.get(correlation, [])
            if len(group) != 1:
                continue
            record = group[0]
            expected_event = (
                "reasoning_readiness_completed" if invocation.success and dry_run
                else "reasoning_execution_completed" if invocation.success
                else "reasoning_execution_failed"
            )
            expected_status = "success" if invocation.success else "failed"
            expected_content = expected_digest if invocation.success and not dry_run else None
            expected_result_present = invocation.success and not dry_run
            execution_id = record.get("execution_id")
            execution_identity_invalid = (
                type(execution_id) is not str
                or len(execution_id) != 32
                or any(character not in "0123456789abcdef" for character in execution_id)
                or execution_id in execution_ids
            )
            if type(execution_id) is str:
                execution_ids.add(execution_id)
            if (
                execution_identity_invalid
                or type(record.get("recorded_at")) is not str
                or record.get("request_id") != invocation.request_id
                or record.get("event_type") != expected_event
                or record.get("status") != expected_status
                or record.get("task_identity") != "generate_options"
                or record.get("task_version") != "1"
                or record.get("result_family") != "option_set"
                or record.get("result_version") != "1"
                or record.get("strategy_identity") != "vss.generate-options.deterministic"
                or record.get("strategy_version") != "1.0.0"
                or record.get("provider_identity") != "vss.reasoning.deterministic-options"
                or record.get("provider_version") != "1.0.0"
                or record.get("authorization") != "authorized"
                or record.get("request_sha256") != invocation.request_digest
                or record.get("result_sha256") != invocation.result_digest
                or record.get("semantic_content_sha256") != expected_content
                or (invocation.result_digest is not None) != expected_result_present
            ):
                invalid += 1
        return {
            "records": len(selected),
            "missing": missing,
            "duplicate": duplicate,
            "invalid": invalid,
            "malformed": malformed,
        }

    @staticmethod
    def _request(template: dict[str, Any], request_id: str, correlation_id: str) -> dict[str, Any]:
        value = load_json_document(canonical_bytes(template))
        value["request_id"] = request_id
        value["correlation_id"] = correlation_id
        return value

    def _invoke(
        self,
        template: dict[str, Any],
        *,
        request_id: str,
        correlation_id: str,
        environment: str,
        timeout_seconds: float,
        dry_run: bool,
        expected_digest: str,
        expected_option_count: int,
    ) -> _Invocation:
        request = self._request(template, request_id, correlation_id)
        request_digest = canonical_digest(request)
        started = time.monotonic()
        try:
            outcome = self._gateway.execute(
                request,
                environment=environment,
                correlation_id=correlation_id,
                dry_run=dry_run,
                timeout_seconds=timeout_seconds,
            )
            latency = time.monotonic() - started
            if dry_run:
                if outcome.validated_result is not None or outcome.content_digest is not None:
                    raise PerformanceCorrectnessFailure("dry-run produced semantic output")
                if outcome.output.get("readiness", {}).get("provider_invoked") is not False:
                    raise PerformanceCorrectnessFailure("dry-run invoked the provider")
                return _Invocation(
                    request_id, correlation_id, latency, True, None,
                    request_digest, None, None,
                )
            if outcome.validated_result is None or outcome.content_digest != expected_digest:
                raise PerformanceCorrectnessFailure("semantic content digest mismatch")
            result = outcome.validated_result.value
            if result["request_id"] != request_id or result["correlation_id"] != correlation_id:
                raise PerformanceCorrectnessFailure("request and result were mixed")
            if len(result["payload"]["options"]) != expected_option_count:
                raise PerformanceCorrectnessFailure("semantic option count mismatch")
            return _Invocation(
                request_id, correlation_id, latency, True, outcome.content_digest,
                request_digest, outcome.validated_result.digest, None,
            )
        except Exception as exc:
            return _Invocation(
                request_id, correlation_id, time.monotonic() - started, False, None,
                request_digest, None, type(exc).__name__,
            )

    def _phase(
        self,
        template: dict[str, Any],
        *,
        name: str,
        count: int,
        concurrency: int,
        maximum_outstanding: int,
        environment: str,
        timeout_seconds: float,
        dry_run: bool,
        expected_digest: str,
        expected_option_count: int,
        prefix: str,
        starting_index: int,
        overall_deadline: float,
    ) -> tuple[list[_Invocation], dict[str, Any], int]:
        started = time.monotonic()
        results: list[_Invocation] = []
        next_index = 0
        pending: set[concurrent.futures.Future[_Invocation]] = set()
        timed_out = False
        cancelled = 0
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="vss-performance"
        )
        try:
            while next_index < count or pending:
                if time.monotonic() >= overall_deadline:
                    timed_out = True
                    break
                while next_index < count and len(pending) < maximum_outstanding:
                    sequence = starting_index + next_index
                    request_id = f"req-{prefix}-{sequence:04d}"
                    correlation_id = f"corr-{prefix}-{sequence:04d}"
                    pending.add(executor.submit(
                        self._invoke,
                        template,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        environment=environment,
                        timeout_seconds=timeout_seconds,
                        dry_run=dry_run,
                        expected_digest=expected_digest,
                        expected_option_count=expected_option_count,
                    ))
                    next_index += 1
                done, pending = concurrent.futures.wait(
                    pending, timeout=max(0.001, overall_deadline - time.monotonic()),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                results.extend(future.result() for future in done)
        finally:
            if timed_out:
                for future in pending:
                    if future.cancel():
                        cancelled += 1
            executor.shutdown(wait=True, cancel_futures=True)
        if timed_out:
            for future in pending:
                if not future.cancelled():
                    results.append(future.result())
        elapsed = time.monotonic() - started
        successes = sum(item.success for item in results)
        phase = {
            "name": name,
            "requests": count,
            "submitted": next_index,
            "completed": len(results),
            "cancellations": cancelled,
            "timed_out": timed_out,
            "concurrency": concurrency,
            "maximum_outstanding": maximum_outstanding,
            "successes": successes,
            "failures": len(results) - successes,
            "duration_seconds": round(elapsed, 6),
        }
        return results, phase, starting_index + count

    def run(
        self,
        profile_identity: str,
        *,
        environment: str,
        dry_run: bool = False,
        include_endurance: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if environment != "development" or type(dry_run) is not bool or type(include_endurance) is not bool:
            raise PerformanceCorrectnessFailure("performance environment or mode is unsupported")
        profile = get_profile(profile_identity)
        template = self._fixture()
        fixture_digest = hashlib.sha256(canonical_bytes(template)).hexdigest()
        report_id = f"perf-{uuid.uuid4().hex}"
        prefix = report_id[5:21]
        started_at = _utc_now()
        started = time.monotonic()
        overall_deadline = started + profile.total_timeout_seconds
        audit_snapshot = self._audit_snapshot()
        resources_before = collect_resources()
        all_results: list[_Invocation] = []
        measured: list[_Invocation] = []
        phases: list[dict[str, Any]] = []
        sequence = 1
        failures: dict[str, int] = {}
        warnings: list[str] = []
        run_timed_out = False

        def perform(name: str, count: int, concurrency: int, outstanding: int) -> list[_Invocation]:
            nonlocal sequence, run_timed_out
            items, phase, sequence = self._phase(
                template, name=name, count=count, concurrency=concurrency,
                maximum_outstanding=outstanding, environment=environment,
                timeout_seconds=profile.request_timeout_seconds, dry_run=dry_run,
                expected_digest=profile.expected_content_digest,
                expected_option_count=profile.expected_option_count, prefix=prefix,
                starting_index=sequence, overall_deadline=overall_deadline,
            )
            phases.append(phase)
            all_results.extend(items)
            run_timed_out = run_timed_out or phase["timed_out"]
            return items

        smoke = perform("smoke", 1, 1, 1)
        smoke_audit = self._validate_audit_associations(
            self._audit_records(audit_snapshot), smoke, dry_run=dry_run,
            expected_digest=profile.expected_content_digest,
        ) if profile.verify_audit else {"missing": 0, "duplicate": 0, "invalid": 0, "malformed": 0}
        smoke_valid = not run_timed_out and all(item.success for item in smoke) and not any(
            smoke_audit[key] for key in ("missing", "duplicate", "invalid", "malformed")
        )
        if not smoke_valid:
            warnings.append("smoke phase failed; load phases were not run")
        else:
            ready = True
            if profile.warmup_requests:
                warmup = perform("warmup", profile.warmup_requests, min(profile.concurrency, profile.warmup_requests), profile.maximum_outstanding)
                warmup_audit = self._validate_audit_associations(
                    self._audit_records(audit_snapshot), smoke + warmup, dry_run=dry_run,
                    expected_digest=profile.expected_content_digest,
                ) if profile.verify_audit else {"missing": 0, "duplicate": 0, "invalid": 0, "malformed": 0}
                ready = not run_timed_out and all(item.success for item in warmup) and not any(
                    warmup_audit[key] for key in ("missing", "duplicate", "invalid", "malformed")
                )
                if not ready:
                    warnings.append("warm-up phase failed; measured phases were not run")
            if ready:
                measured = perform("measured", profile.measured_requests, profile.concurrency, profile.maximum_outstanding)
                ready = not run_timed_out and all(item.success for item in measured)
            if ready and not dry_run:
                for step in profile.stress_concurrency_steps:
                    stress = perform(f"stress-{step}", profile.stress_requests_per_step, step, step)
                    if not all(item.success for item in stress):
                        ready = False
                        warnings.append("stress correctness failed; later phases were not run")
                        break
                if ready and include_endurance and profile.endurance_seconds > 0:
                    endurance_started = time.monotonic()
                    remaining = profile.endurance_request_limit
                    while remaining and time.monotonic() - endurance_started < profile.endurance_seconds:
                        batch = min(profile.concurrency, remaining)
                        endurance = perform("endurance", batch, min(profile.concurrency, batch), min(profile.maximum_outstanding, batch))
                        remaining -= batch
                        if not all(item.success for item in endurance):
                            warnings.append("endurance stopped on a correctness failure")
                            break

        for item in all_results:
            if not item.success:
                category = item.failure or "unknown_failure"
                failures[category] = failures.get(category, 0) + 1
        if run_timed_out:
            failures["PerformanceTimeout"] = 1
        audit_records = self._audit_records(audit_snapshot) if profile.verify_audit else []
        try:
            audit_bytes_appended = max(0, (self._repository_root / _AUDIT_RELATIVE).stat().st_size - audit_snapshot.offset)
        except OSError:
            audit_bytes_appended = None
        audit_validation = self._validate_audit_associations(
            audit_records, all_results, dry_run=dry_run,
            expected_digest=profile.expected_content_digest,
        ) if profile.verify_audit else {"records": 0, "missing": 0, "duplicate": 0, "invalid": 0, "malformed": 0}
        duplicate_audit = audit_validation["duplicate"]
        missing_audit = audit_validation["missing"]
        invalid_audit = audit_validation["invalid"]
        malformed_audit = audit_validation["malformed"]
        semantic_mismatches = sum(
            1 for item in all_results if item.success and not dry_run and item.content_digest != profile.expected_content_digest
        )
        successful_measured = [item for item in measured if item.success]
        measured_duration = next((phase["duration_seconds"] for phase in phases if phase["name"] == "measured"), 0.0)
        latency = latency_summary(item.latency_seconds for item in successful_measured) if successful_measured else {
            "sample_count": 0, "min_ms": 0.0, "mean_ms": 0.0, "p50_ms": 0.0,
            "p90_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0,
        }
        throughput_value = throughput(len(successful_measured), measured_duration) if successful_measured and measured_duration > 0 else 0.0
        completed_at = _utc_now()
        resources_after = collect_resources()
        thread_delta = int(resources_after["active_thread_count"] or 0) - int(resources_before["active_thread_count"] or 0)
        if thread_delta != 0:
            warnings.append("process thread count changed during the observation window")
        status = "success" if (
            not failures and semantic_mismatches == 0 and duplicate_audit == 0
            and missing_audit == 0 and invalid_audit == 0 and malformed_audit == 0
            and all(
                phase["submitted"] == phase["requests"]
                and phase["completed"] + phase["cancellations"] == phase["submitted"]
                and not phase["timed_out"]
                for phase in phases
            )
        ) else "failed"
        report: dict[str, Any] = {
            "schema_version": "1", "report_id": report_id, "report_sha256": "",
            "profile": {"identity": profile.identity, "version": profile.version, "sha256": profile_digest(profile)},
            "workload": {"identity": profile.workload_identity, "fixture_identity": profile.fixture_identity, "fixture_sha256": fixture_digest},
            "commit": _safe_commit(self._repository_root),
            "environment": collect_environment(),
            "configuration": {
                "environment": environment, "dry_run": dry_run,
                "warmup_requests": profile.warmup_requests, "measured_requests": profile.measured_requests,
                "concurrency": profile.concurrency, "maximum_outstanding": profile.maximum_outstanding,
                "request_timeout_seconds": profile.request_timeout_seconds,
                "total_timeout_seconds": profile.total_timeout_seconds,
                "endurance_enabled": bool(include_endurance and profile.endurance_seconds),
            },
            "counters": {
                "admitted": sum(phase["submitted"] for phase in phases),
                "completed": len(all_results),
                "successes": sum(item.success for item in all_results),
                "failures": sum(not item.success for item in all_results),
                "timeouts": failures.get("ReasoningDeadlineExceeded", 0) + failures.get("PerformanceTimeout", 0),
                "cancellations": sum(phase["cancellations"] for phase in phases),
                "audit_failures": failures.get("ReasoningAuditFailure", 0),
                "semantic_mismatches": semantic_mismatches,
            },
            "latency": latency, "throughput_requests_per_second": throughput_value,
            "resources": {"before": resources_before, "after": resources_after, "thread_delta": thread_delta, "audit_bytes_appended": audit_bytes_appended},
            "semantic_validation": {
                "expected_content_digest": None if dry_run else profile.expected_content_digest,
                "observed_content_digests": sorted({item.content_digest for item in all_results if item.content_digest}),
                "digest_match": semantic_mismatches == 0 and (dry_run or bool(all_results)),
                "expected_option_count": None if dry_run else profile.expected_option_count,
            },
            "audit_validation": {
                "enabled": profile.verify_audit, "records": audit_validation["records"],
                "missing_terminal_records": missing_audit, "duplicate_terminal_records": duplicate_audit,
                "invalid_associations": invalid_audit, "malformed_records": malformed_audit,
            },
            "phases": phases, "failures": dict(sorted(failures.items())),
            "warnings": warnings + (["high percentiles have limited meaning for this sample size"] if len(successful_measured) < 100 else []),
            "status": status, "started_at": started_at, "completed_at": completed_at,
        }
        report["report_sha256"] = report_digest(report)
        path = write_report(report, self._repository_root)
        summary = {
            "profile": report["profile"], "workload": profile.workload_identity,
            "requests": profile.measured_requests, "concurrency": profile.concurrency,
            "successes": len(successful_measured), "failures": len(measured) - len(successful_measured),
            "duration_ms": round(measured_duration * 1000, 3),
            "throughput_requests_per_second": throughput_value, "latency_ms": latency,
            "semantic_digest_match": report["semantic_validation"]["digest_match"],
            "audit_records_valid": missing_audit == duplicate_audit == invalid_audit == malformed_audit == 0,
            "report_path": path, "report_sha256": report["report_sha256"],
            "warnings": report["warnings"], "status": status,
        }
        if run_timed_out:
            raise PerformanceTimeout("performance profile total timeout exceeded")
        if status != "success":
            raise PerformanceCorrectnessFailure("performance correctness validation failed")
        return summary, report
