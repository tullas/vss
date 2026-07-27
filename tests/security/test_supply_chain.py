from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("supply_chain", ROOT / "scripts/security/supply_chain.py")
assert SPEC and SPEC.loader
SC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SC
SPEC.loader.exec_module(SC)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def component(component_id: str, name: str, ecosystem: str, version: str, license_id: str = "MIT", status: str = "approved", source: str = "https://example.invalid/component") -> dict:
    return {
        "id": component_id, "name": name, "ecosystem": ecosystem, "purpose": "test",
        "version": version, "source": source, "license": license_id, "owner": "owner",
        "maintenance_status": "maintained", "upstream_security_policy": "https://example.invalid/security",
        "provenance": "test evidence", "scorecard": "risk signal", "transitive_dependency_considerations": "reviewed",
        "network_privilege_behavior": "none", "replaceability": "yes", "eol_support": "reviewed",
        "upgrade_rollback": "restore pin", "approval_status": status, "approver": "independent reviewer",
        "review_date": "2026-07-27",
    }


class SupplyChainPolicyTests(unittest.TestCase):
    def test_unpinned_action_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "security/components.yml", {"components": [component("checkout", "actions/checkout", "github-action", "a" * 40)]})
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("steps:\n  - uses: actions/checkout@v5\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "not immutable"):
                SC.validate_actions(root)

    def test_mutable_production_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "security/components.yml", {"components": []})
            path = root / "infrastructure/modules/local/object_storage/variables.tf"
            path.parent.mkdir(parents=True)
            path.write_text('variable "minio_image" { default = "minio/minio:latest" }', encoding="utf-8")
            script = root / "scripts/acceptance-ubuntu-26.04-image.sh"
            script.parent.mkdir(parents=True)
            script.write_text("image=${VSS_ACCEPTANCE_IMAGE:-ubuntu:26.04}\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "mutable production"):
                SC.validate_images(root)

    def test_unreviewed_production_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accepted = "registry.example/accepted@sha256:" + "a" * 64
            unreviewed = "registry.example/unreviewed@sha256:" + "b" * 64
            write_json(root / "security/components.yml", {"components": [component("accepted", "accepted", "oci", "digest", source=accepted)]})
            path = root / "infrastructure/modules/local/object_storage/variables.tf"
            path.parent.mkdir(parents=True)
            path.write_text(f'variable "minio_image" {{ default = "{unreviewed}" }}', encoding="utf-8")
            script = root / "scripts/acceptance-ubuntu-26.04-image.sh"
            script.parent.mkdir(parents=True)
            script.write_text(f"image=${{VSS_ACCEPTANCE_IMAGE:-{accepted}}}\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "not admitted"):
                SC.validate_images(root)

    def test_prohibited_license_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "security/components.yml", {"components": [component("bad", "bad", "pypi", "1", "SSPL-1.0")]})
            write_json(root / "security/license-policy.yml", {"allowed": ["MIT"], "review_required": [], "prohibited": ["SSPL-1.0"]})
            with self.assertRaisesRegex(SC.PolicyFailure, "prohibited"):
                SC.validate_licenses(root)

    def test_prohibited_component_without_exception_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "security/components.yml", {"components": [component("blocked", "blocked", "pypi", "1", status="prohibited")]})
            write_json(root / "security/exceptions.yml", {"exceptions": []})
            with self.assertRaisesRegex(SC.PolicyFailure, "prohibited component"):
                SC.validate_component_admission(root)

    def test_expired_exception_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {key: "value" for key in ("id", "component", "version", "violation", "business_justification", "exposure_assessment", "compensating_controls", "owner", "approval", "remediation_plan")}
            record.update({"owner": "owner", "approval": "approver", "expiry_date": "2025-01-01"})
            write_json(root / "security/exceptions.yml", {"exceptions": [record]})
            with self.assertRaisesRegex(SC.PolicyFailure, "expired"):
                SC.validate_exceptions(root, dt.date(2026, 7, 27))

    def test_lock_hashes_and_manifest_drift_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "requirements/inputs/runtime.in"
            lock_path = root / "requirements/locks/runtime.lock.txt"
            input_path.parent.mkdir(parents=True)
            lock_path.parent.mkdir(parents=True)
            input_path.write_text("safe==1\n", encoding="utf-8")
            lock_path.write_text("safe==1\n", encoding="utf-8")
            bootstrap = root / "scripts/bootstrap-host.sh"
            bootstrap.parent.mkdir(parents=True)
            bootstrap.write_text('pip install --require-hashes -r "$bootstrap_lock"\n', encoding="utf-8")
            review_path = root / "security/python-license-reviews.yml"
            review_path.parent.mkdir(parents=True)
            review_path.write_text('{"reviewed": {}}\n', encoding="utf-8")
            write_json(root / "security/lock-metadata.json", {
                "generator": "uv 0.10.7",
                "inputs": {"requirements/inputs/runtime.in": hashlib.sha256(input_path.read_bytes()).hexdigest()},
                "locks": {"requirements/locks/runtime.lock.txt": hashlib.sha256(lock_path.read_bytes()).hexdigest()},
                "policy_files": {"security/python-license-reviews.yml": hashlib.sha256(review_path.read_bytes()).hexdigest()},
            })
            with self.assertRaisesRegex(SC.PolicyFailure, "lacks an enforced hash"):
                SC.validate_locks(root)
            lock_path.write_text("safe==1 \\\n+    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "drift"):
                SC.validate_locks(root)

    def test_vulnerable_dependency_admission_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "security/vulnerability-policy.yml", {"blocked_fixtures": ["insecure-package==0.1.0"]})
            for name in ("requirements.txt", "requirements-bootstrap.txt", "requirements-dev.txt"):
                (root / name).write_text("insecure-package==0.1.0\n" if name == "requirements.txt" else "", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "known vulnerable"):
                SC.validate_vulnerability_admission(root)

    def test_security_workflow_simple_bypass_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            jobs = "\n".join(f"  {job}:" for job in ("policy", "dependency-review", "python-vulnerability", "container-scan", "iac-scan", "static-analysis"))
            workflow.write_text(f"permissions:\n  contents: read\njobs:\n{jobs}\n  # sbom job removed\n  step: python3 scripts/security/validate-supply-chain.py\n", encoding="utf-8")
            codeowners = root / ".github/CODEOWNERS"
            codeowners.write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "job is missing"):
                SC.validate_workflow_invariants(root)

    def test_disabled_security_job_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            source = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
            workflow.write_text(source.replace("  policy:\n", "  policy:\n    if: false\n"), encoding="utf-8")
            codeowners = root / ".github/CODEOWNERS"
            codeowners.write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "disabling condition"):
                SC.validate_workflow_invariants(root)

    def test_expression_disabled_security_job_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            source = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
            workflow.write_text(source.replace("  policy:\n", "  policy:\n    if: ${{ false }}\n"), encoding="utf-8")
            (root / ".github/CODEOWNERS").write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "disabling condition"):
                SC.validate_workflow_invariants(root)

    def test_security_command_failure_suppression_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            source = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
            workflow.write_text(source.replace("python3 scripts/security/validate-supply-chain.py", "python3 scripts/security/validate-supply-chain.py || true"), encoding="utf-8")
            (root / ".github/CODEOWNERS").write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "suppresses failure"):
                SC.validate_workflow_invariants(root)

    def test_disabled_required_security_step_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            source = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
            target = "      - run: python3 scripts/security/validate-supply-chain.py\n"
            workflow.write_text(source.replace(target, target.rstrip() + "\n        if: ${{ false }}\n"), encoding="utf-8")
            (root / ".github/CODEOWNERS").write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "canonical security validation step"):
                SC.validate_workflow_invariants(root)

    def test_sbom_is_valid_and_artifacts_reject_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "vss.cdx.json"
            subprocess.run([sys.executable, str(ROOT / "scripts/security/generate-sbom.py"), "--output", str(output)], check=True)
            subprocess.run([sys.executable, str(ROOT / "scripts/security/validate-sbom.py"), str(output)], check=True)
            output.write_text('{"token":"do-not-leak"}\n', encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/security/validate-artifacts.py"), directory], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("do-not-leak", result.stdout + result.stderr)

    def test_secrets_inside_release_archive_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("-----BEGIN " + "PRIVATE KEY-----\ndo-not-leak\n", encoding="utf-8")
            archive = root / "vss-source.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                output.add(source, arcname="source.txt")
            source.unlink()
            result = subprocess.run([sys.executable, str(ROOT / "scripts/security/validate-artifacts.py"), directory], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("do-not-leak", result.stdout + result.stderr)

    def test_real_repository_release_evidence_builds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([str(ROOT / "scripts/security/build-release-candidate.sh"), directory], cwd=ROOT, check=True, capture_output=True, text=True)

    def test_security_diagnostics_do_not_reveal_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = "sensitive-canary-value"
            write_json(root / "security/components.yml", {"components": [component("checkout", "actions/checkout", "github-action", "a" * 40)]})
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(f"# token={secret}\nsteps:\n  - uses: actions/checkout@v5\n", encoding="utf-8")
            with self.assertRaises(SC.PolicyFailure) as caught:
                SC.validate_actions(root)
            self.assertNotIn(secret, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
