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
CONTAINER_SPEC = importlib.util.spec_from_file_location("validate_container_scan", ROOT / "scripts/security/validate-container-scan.py")
assert CONTAINER_SPEC and CONTAINER_SPEC.loader
CONTAINER_SCAN = importlib.util.module_from_spec(CONTAINER_SPEC)
sys.modules[CONTAINER_SPEC.name] = CONTAINER_SCAN
CONTAINER_SPEC.loader.exec_module(CONTAINER_SCAN)


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
    def _container_scan_fixture(self, root: Path) -> tuple[str, Path]:
        image = "docker.io/library/ubuntu@sha256:" + "a" * 64
        write_json(root / "security/components.yml", {"components": [component("ubuntu", "ubuntu", "oci", "sha256:" + "a" * 64, source=image)]})
        finding = {"VulnerabilityID": "CVE-2026-0001", "PkgName": "stdlib", "Severity": "HIGH"}
        report = root / "report.json"
        write_json(report, {
            "ArtifactName": image,
            "ArtifactType": "container_image",
            "Metadata": {"ImageID": "sha256:" + "a" * 64, "RepoDigests": ["ubuntu@sha256:" + "a" * 64]},
            "Results": [{"Target": "usr/bin/pebble", "Vulnerabilities": [finding]}],
        })
        write_json(root / "security/exceptions.yml", {"exceptions": [{
            "id": "test-exception", "component": "ubuntu", "version": "sha256:" + "a" * 64,
            "owner": "Bootstrap Owner", "approval": "Independent Human Approver", "expiry_date": "2026-08-10",
            "allowed_findings": [{"target": "/usr/bin/pebble", "id": "CVE-2026-0001", "package": "stdlib", "severity": "HIGH"}],
        }]})
        return image, report

    def test_exact_container_exception_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, report = self._container_scan_fixture(root)
            result = CONTAINER_SCAN.validate(root, image, report, today=dt.date(2026, 7, 27))
            self.assertTrue(result["exception"])

    def test_container_exception_scope_change_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, report = self._container_scan_fixture(root)
            value = json.loads(report.read_text(encoding="utf-8"))
            value["Results"][0]["Vulnerabilities"].append({"VulnerabilityID": "CVE-2026-0002", "PkgName": "stdlib", "Severity": "CRITICAL"})
            write_json(report, value)
            with self.assertRaisesRegex(ValueError, "differ from approved scope"):
                CONTAINER_SCAN.validate(root, image, report, today=dt.date(2026, 7, 27))

    def test_container_report_for_different_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, report = self._container_scan_fixture(root)
            value = json.loads(report.read_text(encoding="utf-8"))
            value["ArtifactName"] = "docker.io/library/other@sha256:" + "b" * 64
            write_json(report, value)
            with self.assertRaisesRegex(ValueError, "does not match requested image"):
                CONTAINER_SCAN.validate(root, image, report, today=dt.date(2026, 7, 27))

    def test_container_report_digest_substitution_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, report = self._container_scan_fixture(root)
            value = json.loads(report.read_text(encoding="utf-8"))
            value["Metadata"]["ImageID"] = "sha256:" + "b" * 64
            write_json(report, value)
            with self.assertRaisesRegex(ValueError, "digest evidence is missing"):
                CONTAINER_SCAN.validate(root, image, report, today=dt.date(2026, 7, 27))

    def test_expired_container_exception_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, report = self._container_scan_fixture(root)
            with self.assertRaisesRegex(ValueError, "expired"):
                CONTAINER_SCAN.validate(root, image, report, today=dt.date(2026, 8, 11))

    def test_approved_ubuntu_expiry_change_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = json.loads((ROOT / "security/exceptions.yml").read_text(encoding="utf-8"))
            value["exceptions"][0]["expiry_date"] = "2026-08-11"
            write_json(root / "security/exceptions.yml", value)
            with self.assertRaisesRegex(SC.PolicyFailure, "differs from human approval"):
                SC.validate_exceptions(root, today=dt.date(2026, 7, 27))

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
            script.write_text("readonly image='ubuntu:26.04'\n", encoding="utf-8")
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
            script.write_text(f"readonly image='{accepted}'\ndocker run --rm --mount \"type=bind,source=$project_root,target=/source,readonly\" \"$image\" bash -ceu true\n", encoding="utf-8")
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

    def test_gutted_scanner_installer_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text((ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8"), encoding="utf-8")
            installer = root / "scripts/security/install-trivy.sh"
            installer.parent.mkdir(parents=True)
            source = (ROOT / "scripts/security/install-trivy.sh").read_text(encoding="utf-8")
            installer.write_text("\n".join(source.splitlines()[:9]) + "\n", encoding="utf-8")
            (root / ".github/CODEOWNERS").write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "installer is not checksum pinned"):
                SC.validate_workflow_invariants(root)

    def test_echo_scanner_bypass_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            source = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
            source = source.replace('"$RUNNER_TEMP/vss-trivy/trivy" image --scanners vuln', 'echo "$RUNNER_TEMP/vss-trivy/trivy" image --scanners vuln')
            workflow.write_text(source, encoding="utf-8")
            installer = root / "scripts/security/install-trivy.sh"
            installer.parent.mkdir(parents=True)
            installer.write_bytes((ROOT / "scripts/security/install-trivy.sh").read_bytes())
            (root / ".github/CODEOWNERS").write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "scanner does not fail closed"):
                SC.validate_workflow_invariants(root)

    def test_generic_unfixed_finding_suppression_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/security.yml"
            workflow.parent.mkdir(parents=True)
            source = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
            source = source.replace("image --scanners vuln\n          --severity", "image --scanners vuln --ignore-unfixed\n          --severity")
            workflow.write_text(source, encoding="utf-8")
            installer = root / "scripts/security/install-trivy.sh"
            installer.parent.mkdir(parents=True)
            installer.write_bytes((ROOT / "scripts/security/install-trivy.sh").read_bytes())
            (root / ".github/CODEOWNERS").write_text("/.github/workflows/ @tullas\n", encoding="utf-8")
            with self.assertRaisesRegex(SC.PolicyFailure, "scanner does not fail closed"):
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
            diagnostic_canary = "diagnostic-canary-value"
            write_json(root / "security/components.yml", {"components": [component("checkout", "actions/checkout", "github-action", "a" * 40)]})
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(f"# diagnostic-marker={diagnostic_canary}\nsteps:\n  - uses: actions/checkout@v5\n", encoding="utf-8")
            with self.assertRaises(SC.PolicyFailure) as caught:
                SC.validate_actions(root)
            self.assertNotIn(diagnostic_canary, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
