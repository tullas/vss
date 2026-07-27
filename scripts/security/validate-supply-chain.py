#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from supply_chain import PolicyFailure, validate_all

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
args = parser.parse_args()
try:
    checks = validate_all(args.root.resolve())
except (OSError, PolicyFailure) as exc:
    print(json.dumps({"status": "failed", "summary": str(exc)[:240]}, sort_keys=True))
    raise SystemExit(1)
print(json.dumps({"status": "passed", "checks": checks}, sort_keys=True))
