#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
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
    return (
        target,
        str(finding.get("VulnerabilityID", "")),
        str(finding.get("PkgName", "")),
        str(finding.get("Severity", "")),
    )


def validate(root: Path, image: str, report_path: Path, today: dt.date | None = None) -> dict[str, Any]:
    report = load_object(report_path)
    components = load_object(root / "security/components.yml").get("components", [])
    exceptions = load_object(root / "security/exceptions.yml").get("exceptions", [])
    if not isinstance(report.get("Results"), list) or not isinstance(components, list) or not isinstance(exceptions, list):
        raise ValueError("container scan evidence is malformed")
    if report.get("ArtifactType") != "container_image" or report.get("ArtifactName") != image:
        raise ValueError("container scan evidence does not match requested image")

    component = next((item for item in components if isinstance(item, dict) and item.get("source") == image), None)
    if component is None:
        raise ValueError("container image is not registered")

    actual = {
        finding_key(str(result.get("Target", "")), finding)
        for result in report["Results"]
        if isinstance(result, dict)
        for finding in (result.get("Vulnerabilities") or [])
        if isinstance(finding, dict) and finding.get("Severity") in {"HIGH", "CRITICAL"}
    }
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
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        result = validate(args.root, args.image, args.report)
    except ValueError as exc:
        print(json.dumps({"status": "failed", "summary": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
