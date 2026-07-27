#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import re
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
allowed = {"vss-source.tar.gz", "vss.cdx.json", "vss-sbom-diff.json", "vss-source.intoto.jsonl"}
generated_patterns = [
    re.compile(rb"(?i)[\"']?(password|secret|token|api[_-]?key)[\"']?\s*[:=]\s*[\"']?[^\s,}\"']+"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?i)minio_root_(?:user|password)\s*="),
]
source_patterns = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"gh[opsu]_[A-Za-z0-9]{36,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"(?i)(?:password|secret|token|api[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{32,}"),
]
for path in args.directory.iterdir():
    if not path.is_file() or path.name not in allowed:
        raise SystemExit("artifact staging contains a non-allowlisted file")
    artifact_data = path.read_bytes()
    sensitive = any(pattern.search(artifact_data) for pattern in generated_patterns)
    if path.name == "vss-source.tar.gz":
        sensitive = False
        try:
            with tarfile.open(fileobj=io.BytesIO(artifact_data), mode="r:gz") as archive:
                for member in archive.getmembers():
                    if not member.isfile() or (extracted := archive.extractfile(member)) is None:
                        continue
                    patterns = source_patterns[:-1] if member.name.endswith((".example", ".example.yml")) else source_patterns
                    if any(pattern.search(extracted.read()) for pattern in patterns):
                        sensitive = True
                        break
        except (tarfile.TarError, OSError):
            raise SystemExit("release archive is not a valid gzip-compressed tar file")
    if sensitive:
        raise SystemExit(f"artifact contains sensitive-looking content: {path.name}")
print("artifact allowlist and sensitive-content validation passed")
