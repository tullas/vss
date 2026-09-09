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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "config", root / "config")
            shutil.copy2(ROOT / ".secrets.baseline", root / ".secrets.baseline")
            destination = root / "scripts/security/validate-repository-governance.py"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/security/validate-repository-governance.py", destination)
            (root / "tests/movie_storyboard").mkdir(parents=True)
            (root / "tests/performance").mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "fixture"], cwd=root, check=True)
            (root / "config/repository-governance-v1.json").write_text(
                (root / "config/repository-governance-v1.json").read_text() + "\n", encoding="utf-8")
            result = self.run_check(root, justification="")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("protected artifact", result.stdout)

    def test_digest_reference_preserves_bare_sha256_and_supports_algorithm(self) -> None:
        from vss_reasoning_contracts import DigestReference

        legacy = DigestReference.parse("a" * 64)
        self.assertEqual(legacy.algorithm, "sha256")
        self.assertEqual(DigestReference.parse("blake3:" + "b" * 64).as_string(), "blake3:" + "b" * 64)
        with self.assertRaises(ValueError):
            DigestReference.parse("c" * 63)

    def test_l0_gate_bootstrap_provisions_every_dependency_it_executes(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        scanner = workflow.index("requirements/locks/security-tools.lock.txt")
        runtime = workflow.index("requirements/locks/runtime.lock.txt")
        project = workflow.index("--no-deps --no-build-isolation -e .")
        gate = workflow.index("./scripts/validate-change.sh --level L0")
        self.assertLess(scanner, runtime)
        self.assertLess(runtime, project)
        self.assertLess(project, gate)
        self.assertIn("scripts/validate-hermetic.py", (ROOT / "scripts/validate-change.sh").read_text())
