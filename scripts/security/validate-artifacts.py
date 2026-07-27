#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
allowed = {"vss-source.tar.gz", "vss.cdx.json", "vss-sbom-diff.json", "vss-source.intoto.jsonl"}
patterns = [
    re.compile(rb"(?i)[\"']?(password|secret|token|api[_-]?key)[\"']?\s*[:=]\s*[\"']?[^\s,}\"']+"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?i)minio_root_(?:user|password)\s*="),
]
for path in args.directory.iterdir():
    if not path.is_file() or path.name not in allowed:
        raise SystemExit("artifact staging contains a non-allowlisted file")
    data = path.read_bytes()
    if any(pattern.search(data) for pattern in patterns):
        raise SystemExit(f"artifact contains sensitive-looking content: {path.name}")
print("artifact allowlist and sensitive-content validation passed")
