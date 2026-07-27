#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
inputs = sorted((ROOT / "requirements/inputs").glob("*.in"))
locks = sorted((ROOT / "requirements/locks").glob("*.lock.txt"))
payload = {
    "schema_version": "1.0",
    "generator": "uv 0.10.7",
    "inputs": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    "locks": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in locks},
}
(ROOT / "security/lock-metadata.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
