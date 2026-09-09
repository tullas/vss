#!/usr/bin/env python3
"""Run only tests whose repository classification permits ordinary CI."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    requested = Path(sys.argv[1]).as_posix().rstrip("/") if len(sys.argv) == 2 else None
    classification = json.loads((ROOT / "config/test-classification-v1.json").read_text())
    excluded = {Path(item).as_posix() for item in classification["external_media"] + classification["host_integration"]}
    commands = []
    for directory in sorted(path for path in (ROOT / "tests").iterdir()
                            if path.is_dir() and path.name != "__pycache__"
                            and any(path.glob("test_*.py"))):
        if requested and directory.relative_to(ROOT).as_posix() != requested:
            continue
        relative = directory.relative_to(ROOT).as_posix() + "/"
        if any(relative.startswith(item.rstrip("/") + "/") or relative == item for item in excluded):
            continue
        commands.append([sys.executable, "-m", "unittest", "discover", "-s", relative, "-p", "test_*.py"])
    for command in commands:
        if subprocess.run(command, cwd=ROOT).returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
