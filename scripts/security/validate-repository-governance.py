#!/usr/bin/env python3
"""Fail-closed repository reproducibility and protected-artifact checks."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


class GovernanceFailure(RuntimeError):
    pass


def load(root: Path, relative: str) -> dict:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise GovernanceFailure(f"{relative} must be an object")
    return value


def tracked_changed(root: Path) -> set[str]:
    result = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root,
                            capture_output=True, check=True).stdout
    return {item[3:].decode() for item in result.split(b"\0") if item and len(item) >= 4}


def validate(root: Path) -> dict[str, object]:
    governance = load(root, "config/repository-governance-v1.json")
    if governance.get("schema_version") != "1" or governance.get("protocol") != "vss.repository-governance":
        raise GovernanceFailure("repository governance identity is invalid")
    authority = governance.get("authority")
    if type(authority) is not dict or not authority or any(value is not False for value in authority.values()):
        raise GovernanceFailure("repository governance grants authority")
    scope = load(root, governance["secrets_baseline"]["scope_path"])
    paths = scope.get("paths")
    if type(paths) is not list or paths != sorted(set(paths)) or any(type(path) is not str for path in paths):
        raise GovernanceFailure("secrets baseline scope is malformed")
    baseline = load(root, governance["secrets_baseline"]["path"])
    actual = sorted(baseline.get("results", {}))
    if actual != paths:
        raise GovernanceFailure("secrets baseline scope expansion or drift detected")
    classification = load(root, "config/test-classification-v1.json")
    classified = classification.get("external_media", []) + classification.get("host_integration", [])
    if len(classified) != len(set(classified)):
        raise GovernanceFailure("test classification contains duplicate entries")
    for path in classified:
        if not (root / path).is_file() and not (root / path).is_dir():
            raise GovernanceFailure(f"classified test is missing: {path}")
    changed = tracked_changed(root)
    protected = governance["protected_paths"]
    baseline_path = governance["secrets_baseline"]["path"]
    if (baseline_path != ".secrets.baseline"
            or governance["secrets_baseline"]["scope_path"] != "config/secrets-baseline-scope-v1.json"
            or governance["secrets_baseline"]["updater"] != "scripts/security/update-secrets-baseline.sh"):
        raise GovernanceFailure("secrets baseline governance binding is invalid")
    def matches(pattern: str, path: str) -> bool:
        if pattern.endswith("/**"):
            return path.startswith(pattern[:-3])
        if pattern.startswith("**/"):
            return path.endswith(pattern[3:])
        return path == pattern
    changed_protected = sorted(path for path in changed if any(matches(pattern, path) for pattern in protected))
    sanctioned_baseline_change = changed_protected == [baseline_path]
    if (changed_protected and not sanctioned_baseline_change
            and not os.environ.get("VSS_PROTECTED_UPDATE_JUSTIFICATION", "").strip()):
        raise GovernanceFailure("protected artifact drift requires VSS_PROTECTED_UPDATE_JUSTIFICATION: " + ", ".join(changed_protected))
    return {"baseline_scope": paths, "classified_external_or_host": len(classified), "protected_changes": changed_protected}


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else Path(__file__).resolve().parents[2]
    try:
        print(json.dumps({"status": "passed", "checks": validate(root)}, sort_keys=True))
    except (OSError, KeyError, TypeError, ValueError, GovernanceFailure) as exc:
        print(json.dumps({"status": "failed", "summary": str(exc)[:240]}, sort_keys=True))
        raise SystemExit(1)
