from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts/security/validate-repository-governance.py"


class RepositoryGovernanceTests(unittest.TestCase):
    def run_check(self, root: Path, *, justification: str = "milestone") -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "VSS_PROTECTED_UPDATE_JUSTIFICATION": justification}
        return subprocess.run(["python3", str(CHECK), str(root)], cwd=root, text=True, capture_output=True, env=environment)

    def test_authoritative_baseline_scope_rejects_unauthorized_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "config", root / "config")
            for relative in (".secrets.baseline", "scripts/security/validate-repository-governance.py"):
                source = ROOT / relative; destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, destination)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            baseline = json.loads((root / ".secrets.baseline").read_text())
            baseline["results"]["tests/unauthorized.json"] = []
            (root / ".secrets.baseline").write_text(json.dumps(baseline))
            result = self.run_check(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scope expansion", result.stdout)

    def test_protected_artifact_drift_requires_justification(self) -> None:
        result = self.run_check(ROOT, justification="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected artifact", result.stdout)

    def test_digest_reference_preserves_bare_sha256_and_supports_algorithm(self) -> None:
        from vss_reasoning_contracts import DigestReference

        legacy = DigestReference.parse("a" * 64)
        self.assertEqual(legacy.algorithm, "sha256")
        self.assertEqual(DigestReference.parse("blake3:" + "b" * 64).as_string(), "blake3:" + "b" * 64)
        with self.assertRaises(ValueError):
            DigestReference.parse("c" * 63)
