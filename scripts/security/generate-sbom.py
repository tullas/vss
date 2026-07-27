#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")


def python_components(root: Path) -> list[dict]:
    scopes: dict[tuple[str, str], set[str]] = {}
    for lock in sorted((root / "requirements/locks").glob("*.lock.txt")):
        for line in lock.read_text(encoding="utf-8").splitlines():
            match = PIN.match(line)
            if match:
                key = (match.group(1).lower().replace("_", "-"), match.group(2))
                scopes.setdefault(key, set()).add(lock.name.removesuffix(".lock.txt"))
    return [
        {
            "type": "library",
            "bom-ref": f"pkg:pypi/{name}@{version}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
            "properties": [{"name": "vss:lock-scopes", "value": ",".join(sorted(scopes[(name, version)]))}],
        }
        for name, version in sorted(scopes)
    ]


def registry_components(root: Path) -> list[dict]:
    registry = json.loads((root / "security/components.yml").read_text(encoding="utf-8"))
    result = []
    for item in registry["components"]:
        if item["ecosystem"] == "pypi":
            continue
        result.append(
            {
                "type": "container" if item["ecosystem"] == "oci" else "framework",
                "bom-ref": f"vss:{item['ecosystem']}:{item['id']}@{item['version']}",
                "name": item["name"],
                "version": item["version"],
                "licenses": [{"license": {"id": item["license"]}}],
                "externalReferences": [{"type": "distribution", "url": item["source"]}],
                "properties": [
                    {"name": "vss:ecosystem", "value": item["ecosystem"]},
                    {"name": "vss:approval-status", "value": item["approval_status"]},
                ],
            }
        )
    return result


def build_sbom(root: Path) -> dict:
    components = python_components(root) + registry_components(root)
    identity = hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest()
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, identity)}",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "bom-ref": "pkg:github/tullas/vss", "name": "vss", "version": "source-candidate"},
            "properties": [{"name": "vss:evidence-scope", "value": "Python locks, images, Actions, provider, approved host components"}],
        },
        "components": sorted(components, key=lambda item: item["bom-ref"]),
    }


parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=ROOT)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
payload = build_sbom(args.root.resolve())
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
