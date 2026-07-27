#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("artifact", type=Path)
parser.add_argument("provenance", type=Path)
args = parser.parse_args()
value = json.loads(args.provenance.read_text(encoding="utf-8"))
expected = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
if value.get("_type") != "https://in-toto.io/Statement/v1" or value.get("predicateType") != "https://slsa.dev/provenance/v1":
    raise SystemExit("provenance statement type is invalid")
subjects = value.get("subject", [])
if len(subjects) != 1 or subjects[0].get("name") != args.artifact.name or subjects[0].get("digest", {}).get("sha256") != expected:
    raise SystemExit("provenance subject digest does not match artifact")
print(json.dumps({"status": "valid", "subject": args.artifact.name}, sort_keys=True))
