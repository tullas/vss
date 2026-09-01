#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid scan input: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid scan input: {path.name}")
    return value


def finding_key(target: str, finding: dict[str, Any]) -> tuple[str, str, str, str]:
    canonical_target = "/" + target.lstrip("/")
    return (
        canonical_target,
        str(finding.get("VulnerabilityID", "")),
        str(finding.get("PkgName", "")),
        str(finding.get("Severity", "")),
    )


def validate(root: Path, image: str, report_path: Path, manifest_path: Path,
             today: dt.date | None = None) -> dict[str, Any]:
    report = load_object(report_path)
    manifest = load_object(manifest_path)
    components = load_object(root / "security/components.yml").get("components", [])
    exceptions = load_object(root / "security/exceptions.yml").get("exceptions", [])
    if not isinstance(report.get("Results"), list) or not isinstance(components, list) or not isinstance(exceptions, list):
        raise ValueError("container scan evidence is malformed")
    if report.get("ArtifactType") != "container_image" or report.get("ArtifactName") != image:
        raise ValueError("container scan evidence does not match requested image")

    component = next((item for item in components if isinstance(item, dict) and item.get("source") == image), None)
    if component is None:
        raise ValueError("container image is not registered")
    expected_manifest_digest = str(component.get("version", ""))
    observed_manifest_digest = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    config = manifest.get("config")
    if (manifest.get("schemaVersion") != 2 or not isinstance(config, dict)
            or observed_manifest_digest != expected_manifest_digest):
        raise ValueError("container manifest digest evidence is missing")
    metadata = report.get("Metadata")
    expected_image_id = component.get("scan_image_id")
    if (not isinstance(metadata, dict) or not isinstance(metadata.get("ImageID"), str)
            or config.get("digest") != expected_image_id
            or metadata.get("ImageID") not in {expected_manifest_digest, expected_image_id}):
        raise ValueError("container scan digest evidence is missing")
    repo_digests = metadata.get("RepoDigests")
    if not isinstance(repo_digests, list) or not any(isinstance(item, str) and item.endswith("@" + str(component.get("version"))) for item in repo_digests):
        raise ValueError("container scan repository digest is missing")

    actual_records: list[tuple[str, str, str, str]] = []
    for result in report["Results"]:
        if not isinstance(result, dict) or not isinstance(result.get("Target"), str) or not result["Target"]:
            raise ValueError("container scan result is malformed")
        vulnerabilities = result.get("Vulnerabilities")
        if vulnerabilities is None:
            continue
        if not isinstance(vulnerabilities, list):
            raise ValueError("container scan findings are malformed")
        for finding in vulnerabilities:
            if not isinstance(finding, dict):
                raise ValueError("container scan finding is malformed")
            if finding.get("Severity") not in {"HIGH", "CRITICAL"}:
                continue
            record = finding_key(result["Target"], finding)
            if not all(record):
                raise ValueError("container scan finding is incomplete")
            actual_records.append(record)
    actual = set(actual_records)
    if len(actual) != len(actual_records):
        raise ValueError("container scan contains duplicate findings")
    if not actual:
        return {"image": component["id"], "findings": 0, "exception": False, "status": "passed"}

    now = today or dt.datetime.now(dt.timezone.utc).date()
    exception = next(
        (
            item for item in exceptions
            if isinstance(item, dict)
            and item.get("component") == component.get("id")
            and item.get("version") == component.get("version")
        ),
        None,
    )
    if exception is None:
        raise ValueError(f"container scan blocked {len(actual)} unexcepted findings for {component['id']}")
    try:
        expiry = dt.date.fromisoformat(str(exception["expiry_date"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("container exception expiry is invalid") from exc
    if expiry < now:
        raise ValueError(f"container exception is expired: {exception.get('id', 'unknown')}")
    if not exception.get("approval") or exception.get("approval") == exception.get("owner"):
        raise ValueError("container exception lacks independent approval")
    allowed_records = exception.get("allowed_findings")
    if not isinstance(allowed_records, list):
        raise ValueError("container exception lacks exact finding scope")
    allowed = {
        (str(item.get("target", "")), str(item.get("id", "")), str(item.get("package", "")), str(item.get("severity", "")))
        for item in allowed_records
        if isinstance(item, dict)
    }
    if len(allowed) != len(allowed_records) or any(not all(item) for item in allowed):
        raise ValueError("container exception finding scope is malformed")
    if actual != allowed:
        raise ValueError(f"container findings differ from approved scope for {component['id']}")
    return {
        "image": component["id"],
        "findings": len(actual),
        "exception": True,
        "exception_id": exception["id"],
        "expires": exception["expiry_date"],
        "status": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        result = validate(args.root, args.image, args.report, args.manifest)
    except ValueError as exc:
        print(json.dumps({"status": "failed", "summary": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
