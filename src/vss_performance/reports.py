from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from vss_reasoning_contracts import canonical_bytes, canonical_digest

from .errors import PerformanceReportFailure

REPORT_SCHEMA_VERSION = "1"
MAX_REPORT_BYTES = 256 * 1024
_REQUIRED = frozenset({
    "schema_version", "report_id", "report_sha256", "profile", "workload",
    "commit", "environment", "configuration", "counters", "latency",
    "throughput_requests_per_second", "resources", "semantic_validation",
    "audit_validation", "phases", "failures", "warnings", "status",
    "started_at", "completed_at",
})
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/performance-report-v1.schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)


def report_digest(report: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in report.items() if key != "report_sha256"}
    return canonical_digest(unsigned)


def validate_report(report: dict[str, Any]) -> None:
    if type(report) is not dict or frozenset(report) != _REQUIRED:
        raise PerformanceReportFailure("performance report structure is invalid")
    if next(_VALIDATOR.iter_errors(report), None) is not None:
        raise PerformanceReportFailure("performance report schema validation failed")
    if report["schema_version"] != REPORT_SCHEMA_VERSION or report["status"] not in {"success", "failed"}:
        raise PerformanceReportFailure("performance report metadata is invalid")
    counters = report["counters"]
    phases = report["phases"]
    if (
        counters["admitted"] != counters["completed"] + counters["cancellations"]
        or counters["successes"] + counters["failures"] != counters["completed"]
        or sum(phase["submitted"] for phase in phases) != counters["admitted"]
        or sum(phase["completed"] for phase in phases) != counters["completed"]
        or sum(phase["cancellations"] for phase in phases) != counters["cancellations"]
        or any(
            phase["submitted"] > phase["requests"]
            or phase["completed"] + phase["cancellations"] != phase["submitted"]
            or phase["successes"] + phase["failures"] != phase["completed"]
            for phase in phases
        )
    ):
        raise PerformanceReportFailure("performance report accounting is invalid")
    measured = [phase for phase in phases if phase["name"] == "measured"]
    if len(measured) > 1:
        raise PerformanceReportFailure("performance report measured phase is ambiguous")
    measured_successes = measured[0]["successes"] if measured else 0
    if report["latency"]["sample_count"] != measured_successes:
        raise PerformanceReportFailure("performance report latency accounting is invalid")
    expected_throughput = 0.0
    if measured_successes:
        if measured[0]["duration_seconds"] <= 0:
            raise PerformanceReportFailure("performance report measured duration is invalid")
        expected_throughput = round(measured_successes / measured[0]["duration_seconds"], 3)
    if report["throughput_requests_per_second"] != expected_throughput:
        raise PerformanceReportFailure("performance report throughput is invalid")
    if report["status"] == "success" and (
        len(measured) != 1
        or any(
            phase["submitted"] != phase["requests"]
            or phase["timed_out"]
            or phase["failures"]
            or phase["cancellations"]
            for phase in phases
        )
        or report["audit_validation"]["records"] != counters["completed"]
    ):
        raise PerformanceReportFailure("successful performance report is incomplete")
    semantic = report["semantic_validation"]
    if report["configuration"]["dry_run"]:
        if semantic["expected_content_digest"] is not None or semantic["observed_content_digests"] or semantic["expected_option_count"] is not None:
            raise PerformanceReportFailure("dry-run report claims semantic output")
    elif report["status"] == "success" and (
        semantic["digest_match"] is not True
        or semantic["observed_content_digests"] != [semantic["expected_content_digest"]]
    ):
        raise PerformanceReportFailure("performance report semantic evidence is inconsistent")
    if report.get("report_sha256") != report_digest(report):
        raise PerformanceReportFailure("performance report digest is invalid")
    payload = canonical_bytes(report)
    if len(payload) > MAX_REPORT_BYTES:
        raise PerformanceReportFailure("performance report is oversized")


def write_report(report: dict[str, Any], repository_root: Path) -> str:
    validate_report(report)
    unresolved_root = repository_root / ".local/performance/reports"
    current = repository_root
    for component in (".local", "performance", "reports"):
        current = current / component
        if current.is_symlink():
            raise PerformanceReportFailure("performance report directory is unsafe")
    root = unresolved_root.resolve()
    trusted = repository_root.resolve()
    if not root.is_relative_to(trusted):
        raise PerformanceReportFailure("performance report path is unsafe")
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        destination = root / f"{report['report_id']}.json"
        if destination.exists() or destination.is_symlink():
            raise PerformanceReportFailure("performance report destination exists")
        descriptor, temporary = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=root)
        try:
            os.fchmod(descriptor, 0o600)
            data = canonical_bytes(report) + b"\n"
            os.write(descriptor, data)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            if os.path.islink(temporary) or not stat.S_ISREG(os.stat(temporary, follow_symlinks=False).st_mode):
                raise PerformanceReportFailure("performance report temporary file is unsafe")
            # A hard link in the same directory is atomic and refuses to
            # overwrite a destination created after the existence check.
            os.link(temporary, destination, follow_symlinks=False)
            os.unlink(temporary)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    except PerformanceReportFailure:
        raise
    except OSError as exc:
        raise PerformanceReportFailure("performance report could not be written") from exc
    return str(destination.relative_to(repository_root))
