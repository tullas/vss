#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("base", type=Path)
parser.add_argument("candidate", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

def refs(path: Path) -> set[str]:
    return {item["bom-ref"] for item in json.loads(path.read_text(encoding="utf-8"))["components"]}

old, new = refs(args.base), refs(args.candidate)
payload = {"schema_version": "1.0", "added": sorted(new - old), "removed": sorted(old - new)}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
