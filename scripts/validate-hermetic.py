#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="vss-hermetic-home-") as home, tempfile.TemporaryDirectory(prefix="vss-hermetic-tmp-") as temp:
    environment = {key: value for key, value in os.environ.items() if key not in {"HOME", "VSS_SEMANTIC_SCHEMA_PATH"}}
    environment.update({"HOME": home, "TMPDIR": temp, "VSS_TEST_CLASSIFICATION": "deterministic"})
    result = subprocess.run([sys.executable, "scripts/run-test-classification.py"], cwd=root, env=environment)
    raise SystemExit(result.returncode)
