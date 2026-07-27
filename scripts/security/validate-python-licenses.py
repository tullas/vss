#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--lock", type=Path, default=root / "requirements/locks/development.lock.txt")
args = parser.parse_args()
policy = json.loads((root / "security/license-policy.yml").read_text(encoding="utf-8"))
reviews = json.loads((root / "security/python-license-reviews.yml").read_text(encoding="utf-8"))["reviewed"]
allowed = set(policy["allowed"])
review_required = set(policy["review_required"])
prohibited = set(policy["prohibited"])
aliases = {
    "Apache 2.0": "Apache-2.0", "Apache License, Version 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0", "BSD License": "BSD-3-Clause",
    "ISC License": "ISC", "ISC License (ISCL)": "ISC", "MIT License": "MIT",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "PSFL": "PSF-2.0", "Python Software Foundation License": "PSF-2.0",
}
failures: list[str] = []
checked = 0
for line in args.lock.read_text(encoding="utf-8").splitlines():
    match = re.match(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
    if not match:
        continue
    name, version = match.groups()
    key = f"{name}=={version}"
    try:
        metadata = distribution(name).metadata
    except PackageNotFoundError:
        failures.append(f"package not installed: {name}")
        continue
    raw = metadata.get("License-Expression") or metadata.get("License") or ""
    if raw.startswith("MIT License\n"):
        raw = "MIT"
    if not raw:
        classifiers = [item.rsplit(" :: ", 1)[-1] for item in metadata.get_all("Classifier", []) if item.startswith("License ::")]
        raw = classifiers[0] if classifiers else "NOASSERTION"
    expression = aliases.get(raw, raw)
    identifiers = {item for item in re.split(r"\s+(?:AND|OR|WITH)\s+|[()]", expression) if item}
    if identifiers & prohibited or not identifiers.issubset(allowed | review_required):
        failures.append(f"prohibited or unknown license metadata: {name}")
    elif identifiers & review_required and reviews.get(key) != expression:
        failures.append(f"review-required transitive license lacks evidence: {name}")
    checked += 1
if failures:
    raise SystemExit("Python license validation failed: " + "; ".join(failures))
print(json.dumps({"status": "passed", "packages_checked": checked}, sort_keys=True))
