#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import tomllib
import yaml
from pathlib import Path
from typing import Any

ACTION_RE = re.compile(r"^\s*-\s*uses:\s*([^\s@]+)@([^\s#]+)", re.MULTILINE)
DIGEST_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}")
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")
REQUIRED_COMPONENT_FIELDS = {
    "id", "name", "ecosystem", "purpose", "version", "source", "license", "owner",
    "maintenance_status", "upstream_security_policy", "provenance", "scorecard",
    "transitive_dependency_considerations", "network_privilege_behavior", "replaceability",
    "eol_support", "upgrade_rollback", "approval_status", "approver", "review_date",
}


class PolicyFailure(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyFailure(f"invalid policy document: {path.name}") from exc
    if not isinstance(value, dict):
        raise PolicyFailure(f"policy document must be an object: {path.name}")
    return value


def component_map(root: Path) -> dict[str, dict[str, Any]]:
    records = load_json(root / "security/components.yml").get("components", [])
    if not isinstance(records, list):
        raise PolicyFailure("component registry is malformed")
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not REQUIRED_COMPONENT_FIELDS.issubset(record):
            raise PolicyFailure("component registry record is incomplete")
        component_id = str(record["id"])
        if component_id in result:
            raise PolicyFailure("component registry contains a duplicate id")
        if record["approval_status"] not in {"approved", "review-required", "prohibited"}:
            raise PolicyFailure(f"component approval status is invalid: {component_id}")
        if not record["approver"] or record["approver"] == record["owner"]:
            raise PolicyFailure(f"component lacks independent approval: {component_id}")
        result[component_id] = record
    return result


def validate_licenses(root: Path) -> None:
    policy = load_json(root / "security/license-policy.yml")
    allowed = set(policy.get("allowed", []))
    review = set(policy.get("review_required", []))
    prohibited = set(policy.get("prohibited", []))
    for record in component_map(root).values():
        license_id = record["license"]
        if license_id in prohibited or license_id not in allowed | review:
            raise PolicyFailure(f"prohibited or unknown license: {record['id']}")
        if license_id in review and record["approval_status"] != "review-required":
            raise PolicyFailure(f"review-required license lacks review status: {record['id']}")


def validate_exceptions(root: Path, today: dt.date | None = None) -> None:
    records = load_json(root / "security/exceptions.yml").get("exceptions", [])
    if not isinstance(records, list):
        raise PolicyFailure("exception registry is malformed")
    required = {"id", "component", "version", "violation", "business_justification", "exposure_assessment", "compensating_controls", "owner", "approval", "expiry_date", "remediation_plan"}
    now = today or dt.datetime.now(dt.timezone.utc).date()
    for record in records:
        if not isinstance(record, dict) or not required.issubset(record):
            raise PolicyFailure("security exception is incomplete")
        if record["owner"] == record["approval"]:
            raise PolicyFailure(f"security exception is self-approved: {record['id']}")
        try:
            expiry = dt.date.fromisoformat(record["expiry_date"])
        except (TypeError, ValueError) as exc:
            raise PolicyFailure(f"security exception expiry is invalid: {record['id']}") from exc
        if expiry < now:
            raise PolicyFailure(f"security exception is expired: {record['id']}")


def validate_component_admission(root: Path) -> None:
    exceptions = load_json(root / "security/exceptions.yml").get("exceptions", [])
    excepted = {
        (str(record.get("component")), str(record.get("version")))
        for record in exceptions
        if isinstance(record, dict)
    }
    for record in component_map(root).values():
        if record["approval_status"] == "prohibited" and (str(record["id"]), str(record["version"])) not in excepted:
            raise PolicyFailure(f"prohibited component is not admitted: {record['id']}")


def validate_actions(root: Path) -> None:
    registered = {record["name"]: record["version"] for record in component_map(root).values() if record["ecosystem"] == "github-action"}
    seen: set[str] = set()
    for path in sorted((root / ".github/workflows").glob("*.yml")):
        for name, reference in ACTION_RE.findall(path.read_text(encoding="utf-8")):
            if name.startswith("./"):
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", reference):
                raise PolicyFailure(f"GitHub Action is not immutable: {path.name}:{name}")
            registry_name = next((candidate for candidate in registered if name == candidate or name.startswith(candidate + "/")), None)
            if registry_name is None or registered[registry_name] != reference:
                raise PolicyFailure(f"GitHub Action is not admitted: {name}")
            seen.add(registry_name)
    missing = set(registered) - seen
    if missing:
        raise PolicyFailure("registered GitHub Action is not used by a workflow")


def validate_images(root: Path) -> None:
    variables = (root / "infrastructure/modules/local/object_storage/variables.tf").read_text(encoding="utf-8")
    production_match = re.search(r'variable "minio_image".*?default\s*=\s*"([^"]+)"', variables, re.DOTALL)
    if not production_match or not DIGEST_RE.fullmatch(production_match.group(1)):
        raise PolicyFailure("mutable production image reference")
    acceptance = (root / "scripts/acceptance-ubuntu-26.04-image.sh").read_text(encoding="utf-8")
    acceptance_match = re.search(r"image=\$\{VSS_ACCEPTANCE_IMAGE:-([^}]+)\}", acceptance)
    if not acceptance_match or not DIGEST_RE.fullmatch(acceptance_match.group(1)):
        raise PolicyFailure("mutable acceptance image reference")
    admitted = {record["source"] for record in component_map(root).values() if record["ecosystem"] == "oci"}
    if production_match.group(1) not in admitted:
        raise PolicyFailure("production image is not admitted")
    if acceptance_match.group(1) not in admitted:
        raise PolicyFailure("acceptance image is not admitted")


def _lock_requirements(path: Path) -> list[tuple[str, str]]:
    requirements: list[tuple[str, str]] = []
    current = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw and not raw[0].isspace() and not raw.startswith(("#", "-")):
            if current:
                requirements.append((current.split()[0], current))
            current = raw
        elif current:
            current += " " + raw.strip(" \\")
    if current:
        requirements.append((current.split()[0], current))
    return requirements


def validate_locks(root: Path) -> None:
    metadata = load_json(root / "security/lock-metadata.json")
    if metadata.get("generator") != "uv 0.10.7":
        raise PolicyFailure("unapproved lock generator")
    for group in ("inputs", "locks", "policy_files"):
        records = metadata.get(group, {})
        if not isinstance(records, dict) or not records:
            raise PolicyFailure("lock metadata is incomplete")
        for relative, expected in records.items():
            path = root / relative
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
            if actual != expected:
                raise PolicyFailure(f"dependency manifest/lock drift: {relative}")
    for relative in metadata["locks"]:
        path = root / relative
        for name, requirement in _lock_requirements(path):
            if "==" not in name or not HASH_RE.search(requirement):
                raise PolicyFailure(f"lock requirement lacks an enforced hash: {path.name}")
    bootstrap = (root / "scripts/bootstrap-host.sh").read_text(encoding="utf-8")
    if "--require-hashes -r \"$bootstrap_lock\"" not in bootstrap:
        raise PolicyFailure("bootstrap does not enforce lock hashes")


def _pins(path: Path) -> set[tuple[str, str]]:
    result = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PIN_RE.match(line.strip())
        if match:
            result.add((match.group(1).lower().replace("_", "-"), match.group(2)))
    return result


def validate_manifest_alignment(root: Path) -> None:
    runtime = _pins(root / "requirements.txt")
    runtime_input = _pins(root / "requirements/inputs/runtime.in")
    if runtime != {pin for pin in runtime_input if pin[0] != "setuptools"}:
        raise PolicyFailure("runtime manifest and lock input drift")
    bootstrap_input = runtime_input | _pins(root / "requirements/inputs/bootstrap.in")
    if not _pins(root / "requirements-bootstrap.txt").issubset(bootstrap_input):
        raise PolicyFailure("bootstrap manifest and lock input drift")
    development_input = bootstrap_input | _pins(root / "requirements/inputs/development.in")
    if not _pins(root / "requirements-dev.txt").issubset(development_input):
        raise PolicyFailure("development manifest and lock input drift")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project_pins = set()
    for requirement in project["project"]["dependencies"]:
        match = PIN_RE.match(requirement)
        if not match:
            raise PolicyFailure("project dependency is not exact-pinned")
        project_pins.add((match.group(1).lower().replace("_", "-"), match.group(2)))
    if project_pins != runtime:
        raise PolicyFailure("project metadata and runtime manifest drift")
    if project["build-system"]["requires"] != ["setuptools==83.0.0"]:
        raise PolicyFailure("build backend is not controlled")


def validate_direct_dependencies(root: Path) -> None:
    registered = {record["name"].lower().replace("_", "-") for record in component_map(root).values() if record["ecosystem"] == "pypi"}
    for manifest in ("requirements.txt", "requirements-bootstrap.txt", "requirements-dev.txt"):
        for line in (root / manifest).read_text(encoding="utf-8").splitlines():
            match = PIN_RE.match(line.strip())
            if match and match.group(1).lower().replace("_", "-") not in registered:
                raise PolicyFailure(f"unreviewed direct dependency: {match.group(1)}")


def validate_vulnerability_admission(root: Path) -> None:
    policy = load_json(root / "security/vulnerability-policy.yml")
    blocked = {str(item).lower() for item in policy.get("blocked_fixtures", [])}
    for manifest in ("requirements.txt", "requirements-bootstrap.txt", "requirements-dev.txt"):
        for line in (root / manifest).read_text(encoding="utf-8").splitlines():
            candidate = line.split(";", 1)[0].strip().lower()
            if candidate in blocked:
                raise PolicyFailure("known vulnerable dependency is prohibited")


def validate_opentofu(root: Path) -> None:
    for path in sorted((root / "infrastructure/modules/local").glob("*/versions.tf")):
        text = path.read_text(encoding="utf-8")
        if 'version = "3.9.0"' not in text:
            raise PolicyFailure(f"OpenTofu provider is not exact-pinned: {path.name}")
    root_versions = root / "infrastructure/environments/development/local/versions.tf"
    if 'version = "3.9.0"' not in root_versions.read_text(encoding="utf-8"):
        raise PolicyFailure("root OpenTofu provider is not exact-pinned")
    lock = root_versions.parent / ".terraform.lock.hcl"
    if not lock.is_file() or "zh:" not in lock.read_text(encoding="utf-8"):
        raise PolicyFailure("OpenTofu provider checksum lock is missing")


def validate_workflow_invariants(root: Path) -> None:
    path = root / ".github/workflows/security.yml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    required = {"policy", "dependency-review", "python-vulnerability", "bootstrap-python311-license", "container-scan", "iac-scan", "static-analysis", "sbom-provenance"}
    missing = {job for job in required if not re.search(rf"^  {re.escape(job)}:\s*$", text, re.MULTILINE)}
    if missing:
        raise PolicyFailure("required security workflow job is missing")
    if not re.search(r"^permissions:\s*\n  contents: read\s*$", text, re.MULTILINE):
        raise PolicyFailure("security workflow weakens fail-closed permissions")
    try:
        workflow = yaml.safe_load(text)
        jobs = workflow["jobs"]
    except (yaml.YAMLError, KeyError, TypeError) as exc:
        raise PolicyFailure("security workflow structure is invalid") from exc
    expected_if = {"dependency-review": "github.event_name == 'pull_request'"}
    required_runs = {
        "policy": {"python3 scripts/security/validate-supply-chain.py"},
        "python-vulnerability": {
            "pip-audit --require-hashes -r requirements/locks/runtime.lock.txt",
            "python3 scripts/security/validate-python-licenses.py",
        },
        "bootstrap-python311-license": {"python3 scripts/security/validate-python-licenses.py --lock requirements/locks/bootstrap-py311.lock.txt"},
        "sbom-provenance": {"scripts/security/build-release-candidate.sh dist/security-evidence"},
    }
    for job_name in required:
        job = jobs.get(job_name)
        if not isinstance(job, dict) or job.get("continue-on-error") is True:
            raise PolicyFailure(f"required security job is disabled: {job_name}")
        if "if" in job and job.get("if") != expected_if.get(job_name):
            raise PolicyFailure(f"required security job has a disabling condition: {job_name}")
        steps = job.get("steps")
        if not isinstance(steps, list):
            raise PolicyFailure(f"required security job lacks steps: {job_name}")
        active_steps = [step for step in steps if isinstance(step, dict) and "if" not in step and step.get("continue-on-error") is not True]
        runs = {str(step.get("run", "")).strip() for step in active_steps}
        for run in runs:
            if "|| true" in run or re.search(r";\s*true\s*$", run):
                raise PolicyFailure(f"security command suppresses failure: {job_name}")
        if not required_runs.get(job_name, set()).issubset(runs):
            raise PolicyFailure(f"canonical security validation step is missing: {job_name}")
    installer = root / "scripts/security/install-trivy.sh"
    installer_text = installer.read_text(encoding="utf-8") if installer.is_file() else ""
    if "version='0.72.0'" not in installer_text or "expected_sha256='bbb64b9695866ce4a7a8f5c9592002c5961cab378577fa3f8a040df362b9b2ea'" not in installer_text:
        raise PolicyFailure("security scanner installer is not checksum pinned")
    for job_name in ("container-scan", "iac-scan"):
        job_runs = {str(step.get("run", "")).strip() for step in jobs[job_name]["steps"] if isinstance(step, dict) and "if" not in step and step.get("continue-on-error") is not True}
        scanner_runs = [run for run in job_runs if '"$RUNNER_TEMP/vss-trivy/trivy"' in run]
        if 'scripts/security/install-trivy.sh "$RUNNER_TEMP/vss-trivy"' not in job_runs or len(scanner_runs) != 1 or "--exit-code 1" not in scanner_runs[0]:
            raise PolicyFailure(f"security scanner does not fail closed: {job_name}")
    codeowners = root / ".github/CODEOWNERS"
    if not codeowners.is_file() or "/.github/workflows/ @tullas" not in codeowners.read_text(encoding="utf-8"):
        raise PolicyFailure("security control paths lack CODEOWNERS review")


def validate_all(root: Path) -> list[str]:
    checks = [
        validate_licenses, validate_exceptions, validate_component_admission, validate_actions, validate_images,
        validate_locks, validate_manifest_alignment, validate_direct_dependencies, validate_vulnerability_admission, validate_opentofu,
        validate_workflow_invariants,
    ]
    completed: list[str] = []
    for check in checks:
        check(root)
        completed.append(check.__name__.removeprefix("validate_"))
    return completed
