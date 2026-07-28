#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("artifact", type=Path)
parser.add_argument("--source", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
digest = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
workflow = os.environ.get("GITHUB_WORKFLOW_REF", "local-untrusted-builder")
run_id = os.environ.get("GITHUB_RUN_ID", "local")
payload = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": args.artifact.name, "digest": {"sha256": digest}}],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
        "buildDefinition": {
            "buildType": "https://github.com/tullas/vss/security/release-candidate/v1",
            "externalParameters": {"source": args.source},
            "internalParameters": {},
            "resolvedDependencies": [{"uri": args.source, "digest": {"gitCommit": args.source.rsplit("@", 1)[-1]}}],
        },
        "runDetails": {
            "builder": {"id": f"https://github.com/{workflow}"},
            "metadata": {"invocationId": f"https://github.com/tullas/vss/actions/runs/{run_id}"},
        },
    },
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
