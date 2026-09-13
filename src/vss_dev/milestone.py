from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator

from .improvement_backlog import ImprovementBacklog, ImprovementBacklogFailure


PROTOCOL = "vss.dev-milestone"
PACKET_PROTOCOL = "vss.dev-milestone-execution-packet"
AUTHORITY = {"runtime_execution": False, "provider_execution": False, "production": False,
             "publication": False, "workflow_activation": False, "security_exception": False,
             "product_authority": False, "merge": False, "push": False}
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MILESTONE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
PROTECTED_RESIDUE = ".local/secrets/development.auto.tfvars.example"
BASELINE_RESIDUE = ".secrets.baseline"
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
CI_WORKFLOW_BLOB = "854774e24c3e7bc79838a20f9296dbf14d12891a"  # pragma: allowlist secret -- public workflow Git blob identity
CI_REQUIRED_CHECKS = ("Scan for secrets", "Validate", "Test")
RECONCILIATION_AUTHORIZATION = ("I authorize reconciliation of the m11-0-veo-shot controller source identity "
    "from a9c6ea... to descendant HEAD cf9106298ad485a55475099249d533b3908cf69b, provided "
    "canonical/governed validation passes, Attempts 1–5 remain unchanged, and no execution authority is granted.")
POST_MERGE_RECONCILIATION_AUTHORIZATION = ("I authorize reconciliation of the m11-0-veo-shot controller source identity "
    "from the reviewed PR #141 head b8bed0e973959521a5a67ed592e239c381b176d4 to the resulting merged main HEAD "
    "953b32772f0381d1c2842032ee3c05cff82142af, provided the merge ancestry is verified, canonical/governed validation passes, "
    "Attempts 1–5 remain unchanged, and no execution authority is granted.")
POST_REPAIR_RECONCILIATION_AUTHORIZATION = ("I authorize post-repair reconciliation of the m11-0-veo-shot controller source identity "
    "from the reviewed PR #141 head b8bed0e973959521a5a67ed592e239c381b176d4 through the verified merged-main history to current committed HEAD "
    "841fa9c55733beec26ca0429e88edf443dd180ad, provided descendant ancestry is verified, fresh canonical/governed L3 validation passes, "
    "Attempts 1–5 and historical execution evidence remain unchanged, and no execution authority is granted. This does not authorize Attempt 6, "
    "provider execution, spending, retry, production, publication, merge, push, or workflow activation.")
BOOTSTRAP_MILESTONE = "dev-wf-2-engineering-observability"
ISSUE160_LEGACY_MILESTONE = "review-ready-source-identity-recovery"
ISSUE160_LEGACY_HISTORY_TAIL = "10edae8b275176922895c1addef190ba4872b322d4a545fdd8464e774afb5482"  # pragma: allowlist secret -- public legacy-history digest
ISSUE160_LEGACY_ASSESSMENT_EVENT = "41e0bfb7ca1121402576aeb19eed0ff45537acf14cdabe56414cb43114a39b31"  # pragma: allowlist secret -- public event digest
ISSUE160_LEGACY_BASE_HEAD = "f4c092f5810d5fac98c1b6623d37f8cb14b64c3a"  # pragma: allowlist secret -- public Git commit identity
ISSUE160_RECOVERY_ANCHOR_HEAD = "0e24a3d4f94d60fd3f704195b35749e4ed2bb059"  # pragma: allowlist secret -- public Git commit identity
ISSUE160_RECOVERY_ANCHOR_IDENTITY = "13b880ade7718d6b122fded2f8782629ef2de91b8702217cb6f0b73d68e88e3a"  # pragma: allowlist secret -- public governed change identity
ISSUE160_RECOVERY_BRANCH = "feature/issue-160-legacy-state-recovery"
ISSUE160_REPOSITORY_NAME = "tullas/vss"
ISSUE160_LEGACY_RECOVERY_DISPOSITION = (
    "I authorize the issue #160 legacy-state migration with validation and CI invalidation.")
IDENTITY_REPAIR_PATHS = tuple(sorted((
    "src/vss_commands/cli.py",
    "src/vss_dev/milestone.py",
    "tests/dev_milestone/test_milestone.py",
)))
BOOTSTRAP_REPAIR_PATHS = tuple(sorted((
    "docs/agent-coordination.md",
    "schemas/dev-milestone-record-v1.schema.json",
    "src/vss_commands/cli.py",
    "src/vss_dev/milestone.py",
    "tests/dev_milestone/test_milestone.py",
)))
LEVELS = {"none": -1, "L0": 0, "L1": 1, "L2": 2, "L3": 3}
MAX_PACKET_BYTES = 16_384
MAX_PACKET_PATHS = 64
CHECKPOINT_PROTOCOL = "vss.agent-checkpoint"
CHECKPOINT_MANIFEST_PROTOCOL = "vss.dev-milestone-checkpoint-artifact-manifest"
CHECKPOINT_MANIFEST_SCHEMA = "schemas/dev-milestone-checkpoint-artifact-manifest-v1.schema.json"
CHECKPOINT_MAX_ARTIFACTS = 4
CHECKPOINT_MAX_ENVELOPE_BYTES = 16 * 1024
CHECKPOINT_MAX_MANIFEST_BYTES = 16 * 1024
CHECKPOINT_MAX_BUNDLE_BYTES = 80 * 1024
CHECKPOINT_MANIFEST_MODE = "100644"
MISSION_REVIEWS = {
    "strategic_concern": {"strategic"},
    "creative_production_authority": {"strategic", "constitutional", "unknown_unknown"},
    "provider_media_transition": {"constitutional"},
    "architecture_boundary": {"constitutional", "unknown_unknown"},
}
DECISION_INDEX = "docs/architecture/decisions/index.json"


class MilestoneFailure(Exception):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


CI_CHECK_INVENTORY_SHA256 = _digest({"workflow_blob": CI_WORKFLOW_BLOB,
                                     "required_checks": list(CI_REQUIRED_CHECKS), "version": 1})


def _read_json(path: Path, limit: int = 65536) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if len(raw) > limit:
            raise ValueError
        value = json.loads(raw)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise MilestoneFailure("milestone JSON is malformed") from exc
    if type(value) is not dict:
        raise MilestoneFailure("milestone JSON is malformed")
    return value


class MilestoneController:
    """Strict local state machine for repo development; never invokes Runtime/providers."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path.cwd()).resolve()
        self.state_root = self.root / ".vss" / "milestones"
        self.policy = _read_json(self.root / "config/dev-milestone-policy-v1.json")
        self.policy_schema = _read_json(self.root / "schemas/dev-milestone-policy-v1.schema.json")
        self.record_schema = _read_json(self.root / "schemas/dev-milestone-record-v1.schema.json")
        self.packet_schema = _read_json(self.root / "schemas/dev-milestone-execution-packet-v1.schema.json")
        if list(Draft202012Validator(self.policy_schema).iter_errors(self.policy)):
            raise MilestoneFailure("milestone policy is malformed")
        if self.policy.get("authority") != AUTHORITY:
            raise MilestoneFailure("milestone policy grants authority")
        self.policy_digest = _digest(self.policy)

    def _run(self, argv: list[str], maximum: int = 1_048_576,
             env: Mapping[str, str] | None = None) -> bytes:
        try:
            result = subprocess.run(argv, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    check=False, env=dict(env) if env is not None else None)
        except OSError as exc:
            raise MilestoneFailure("required command is unavailable") from exc
        if result.returncode != 0 or len(result.stdout) > maximum:
            raise MilestoneFailure("required command failed")
        return result.stdout

    def _line(self, argv: list[str]) -> str:
        value = self._run(argv, 4096).decode("utf-8").strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise MilestoneFailure("repository identity is invalid")
        return value

    def _repository(self, base: str | None = None,
                    residue_provenance: dict[str, Any] | None = None) -> dict[str, str]:
        branch = self._line(["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
        head = self._line(["git", "rev-parse", "HEAD"])
        origin = self._line(["git", "remote", "get-url", "origin"])
        match = re.fullmatch(r"(?:git@github\.com:|https://github\.com/)([^/]+/[^/]+?)(?:\.git)?/?", origin)
        if not SHA1.fullmatch(head) or match is None or not MILESTONE.fullmatch(branch.replace("/", "-")):
            raise MilestoneFailure("repository identity is invalid")
        base_value = base or head
        if not SHA1.fullmatch(base_value):
            raise MilestoneFailure("base SHA is invalid")
        self._run(["git", "cat-file", "-e", f"{base_value}^{{commit}}"])
        if subprocess.run(["git", "merge-base", "--is-ancestor", base_value, head], cwd=self.root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode != 0:
            raise MilestoneFailure("base SHA is not an ancestor of HEAD")
        return {"name_with_owner": match.group(1), "branch": branch, "base_sha": base_value, "head_sha": head,
                "change_identity": self._change_identity(base_value, residue_provenance)}

    def _tree_entry(self, revision: str, path: str) -> dict[str, str] | None:
        raw = self._run(["git", "ls-tree", "-z", revision, "--", path], 4096)
        records = [item for item in raw.split(b"\0") if item]
        if not records:
            return None
        if len(records) != 1:
            raise MilestoneFailure("residue Git tree entry is ambiguous")
        try:
            metadata, found_path = records[0].split(b"\t", 1)
            mode, object_type, oid = metadata.split(b" ")
        except ValueError as exc:
            raise MilestoneFailure("residue Git tree entry is malformed") from exc
        if found_path != path.encode("utf-8") or object_type != b"blob" or mode not in {b"100644", b"100755"}:
            raise MilestoneFailure("residue Git tree entry is unsupported")
        return {"mode": mode.decode("ascii"), "oid": oid.decode("ascii"), "type": "blob"}

    def _index_entry(self, path: str) -> dict[str, str] | None:
        records = [item for item in self._run(["git", "ls-files", "--stage", "-z", "--", path], 4096).split(b"\0") if item]
        if not records:
            return None
        if len(records) != 1:
            raise MilestoneFailure("residue index entry is ambiguous")
        try:
            metadata, found_path = records[0].split(b"\t", 1)
            mode, oid, stage = metadata.split(b" ")
        except ValueError as exc:
            raise MilestoneFailure("residue index entry is malformed") from exc
        if (found_path != path.encode("utf-8") or stage != b"0" or mode not in {b"100644", b"100755"}
                or not SHA1.fullmatch(oid.decode("ascii"))):
            raise MilestoneFailure("residue index entry is unsupported")
        return {"mode": mode.decode("ascii"), "oid": oid.decode("ascii"), "stage": "0"}

    def _worktree_entry(self, path: str) -> dict[str, str] | None:
        candidate = self.root / path
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise MilestoneFailure("residue worktree entry is unreadable") from exc
        if not candidate.is_file() or candidate.is_symlink():
            raise MilestoneFailure("residue worktree entry is unsupported")
        mode = metadata.st_mode & 0o777
        if mode not in {0o644, 0o755}:
            raise MilestoneFailure("residue worktree mode is unsupported")
        try:
            content = candidate.read_bytes()
        except OSError as exc:
            raise MilestoneFailure("residue worktree entry is unreadable") from exc
        return {"kind": "file", "mode": f"{mode:04o}", "sha256": hashlib.sha256(content).hexdigest()}

    def _capture_residue(self, base: str) -> dict[str, Any] | None:
        status = self._run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], 2_000_000)
        dirty = any(entry[3:] == BASELINE_RESIDUE.encode("utf-8") for entry in status.split(b"\0") if entry)
        if not dirty:
            return None
        head = self._line(["git", "rev-parse", "HEAD"])
        head_entry = self._tree_entry(head, BASELINE_RESIDUE)
        base_entry = self._tree_entry(base, BASELINE_RESIDUE)
        index_entry = self._index_entry(BASELINE_RESIDUE)
        worktree_entry = self._worktree_entry(BASELINE_RESIDUE)
        validator = self.root / "scripts/security/validate-repository-governance.py"
        if (head_entry is None or head_entry != base_entry or index_entry is None or worktree_entry is None or not validator.is_file()
                or subprocess.run([sys.executable, str(validator)], cwd=self.root,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode != 0):
            raise MilestoneFailure("pre-existing baseline residue is not admissible")
        return {"path": BASELINE_RESIDUE, "captured_head_sha": head,
                "head_entry": head_entry, "index_entry": index_entry,
                "worktree_entry": worktree_entry, "governance_validator": "passed"}

    def _verify_residue(self, base: str, provenance: dict[str, Any] | None) -> None:
        if provenance is None:
            return
        if (set(provenance) != {"path", "captured_head_sha", "head_entry", "index_entry",
                               "worktree_entry", "governance_validator"}
                or provenance["path"] != BASELINE_RESIDUE
                or provenance["governance_validator"] != "passed"
                or self._tree_entry("HEAD", BASELINE_RESIDUE) != provenance["head_entry"]):
            raise MilestoneFailure("captured baseline residue provenance changed")
        if self._index_entry(BASELINE_RESIDUE) != provenance["index_entry"]:
            raise MilestoneFailure("captured baseline residue index changed")
        current = self._worktree_entry(BASELINE_RESIDUE)
        head_bytes = self._run(["git", "show", f"{provenance['captured_head_sha']}:{BASELINE_RESIDUE}"], 4 * 1024 * 1024)
        head_mode = f"{int(provenance['head_entry']['mode'], 8) & 0o777:04o}"
        head_worktree = {"kind": "file", "mode": head_mode,
                         "sha256": hashlib.sha256(head_bytes).hexdigest()}
        if current is not None and current not in {"worktree_entry": provenance["worktree_entry"],
                                                   "head_worktree": head_worktree}.values():
            raise MilestoneFailure("captured baseline residue content changed")
        if current is not None:
            validator = self.root / "scripts/security/validate-repository-governance.py"
            if (not validator.is_file() or subprocess.run(
                    [sys.executable, str(validator)], cwd=self.root,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode != 0):
                raise MilestoneFailure("captured baseline residue is no longer admissible")
        # A tracked baseline change committed after capture is governed work, never residue.
        if self._tree_entry(base, BASELINE_RESIDUE) != self._tree_entry("HEAD", BASELINE_RESIDUE):
            raise MilestoneFailure("captured baseline residue became committed work")

    @staticmethod
    def _residue_from_events(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        value = events[0]["data"].get("residue_provenance")
        return value if type(value) is dict else None

    @staticmethod
    def _residue_digest(provenance: dict[str, Any] | None) -> str:
        return _digest({"residue_provenance": provenance})

    def _changed_paths(self, base: str, residue_provenance: dict[str, Any] | None = None) -> list[str]:
        self._verify_residue(base, residue_provenance)
        raw = self._run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], 2_000_000)
        entries = raw.split(b"\0")
        paths: list[str] = []
        for entry in entries:
            if not entry:
                continue
            if len(entry) < 4 or entry[2:3] != b" ":
                raise MilestoneFailure("repository status is malformed")
            path = entry[3:].decode("utf-8")
            if path == PROTECTED_RESIDUE or path.startswith(".vss/milestones/"):
                continue
            if path == BASELINE_RESIDUE and residue_provenance is not None:
                continue
            if path == BASELINE_RESIDUE:
                validator = self.root / "scripts/security/validate-repository-governance.py"
                governed = validator.is_file() and subprocess.run(
                    [sys.executable, str(validator)], cwd=self.root,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                ).returncode == 0
                if governed:
                    paths.append(path)
                    continue
                raise MilestoneFailure("unexpected sensitive changed path")
            if path.startswith(".local/") or re.search(r"(?i)(secret|credential|token|api[_-]?key|private[_-]?key)", path):
                raise MilestoneFailure("unexpected sensitive changed path")
            paths.append(path)
        diff_paths = self._run(["git", "diff", "--name-only", "-z", base, "--"], 1_048_576).split(b"\0")
        paths.extend(path.decode("utf-8") for path in diff_paths
                     if path and not (residue_provenance is not None and path == BASELINE_RESIDUE.encode("utf-8")))
        return sorted(set(paths))

    def _change_identity(self, base: str, residue_provenance: dict[str, Any] | None = None) -> str:
        """Hash one complete worktree snapshot so commit state cannot change identity."""
        paths = self._changed_paths(base, residue_provenance)
        snapshot: list[dict[str, Any]] = []
        for path in paths:
            candidate = self.root / path
            try:
                if not candidate.exists() and not candidate.is_symlink():
                    snapshot.append({"path": path, "kind": "deleted"})
                    continue
                mode = candidate.lstat().st_mode & 0o777
                if candidate.is_symlink():
                    content = os.readlink(candidate).encode("utf-8")
                    kind = "symlink"
                elif candidate.is_file():
                    content = candidate.read_bytes()
                    kind = "file"
                else:
                    raise OSError("unsupported worktree entry")
            except OSError as exc:
                raise MilestoneFailure("change identity snapshot is unreadable") from exc
            if len(content) > 16 * 1024 * 1024:
                raise MilestoneFailure("change identity snapshot exceeded its bound")
            snapshot.append({"path": path, "kind": kind, "mode": f"{mode:04o}",
                             "sha256": hashlib.sha256(content).hexdigest()})
        return _digest({"base": base, "paths": paths, "snapshot": snapshot})

    def _committed_change_identity(self, base: str, head: str,
                                   excluded: tuple[str, ...] = ()) -> str:
        names = [path.decode("utf-8") for path in self._run(
            ["git", "diff", "--name-only", "-z", base, head, "--"], 1_048_576).split(b"\0") if path]
        paths = sorted(set(names) - set(excluded))
        snapshot: list[dict[str, Any]] = []
        for path in paths:
            exists = subprocess.run(["git", "cat-file", "-e", f"{head}:{path}"], cwd=self.root,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0
            if not exists:
                snapshot.append({"path": path, "kind": "deleted"})
                continue
            content = self._run(["git", "show", f"{head}:{path}"], 16 * 1024 * 1024)
            tree = self._run(["git", "ls-tree", "-r", head, "--", path], 4096).decode("utf-8")
            mode = tree.split(" ", 1)[0]
            kind = "symlink" if mode == "120000" else "file"
            snapshot.append({"path": path, "kind": kind, "mode": f"{int(mode, 8) & 0o777:04o}",
                             "sha256": hashlib.sha256(content).hexdigest()})
        return _digest({"base": base, "paths": paths, "snapshot": snapshot})

    def _tree_entries(self, commit: str) -> dict[bytes, tuple[bytes, bytes, bytes]]:
        """Return exact Git path bytes mapped to mode, type, and object ID."""
        raw = self._run(["git", "ls-tree", "-rz", "--full-tree", commit], 16 * 1024 * 1024)
        entries: dict[bytes, tuple[bytes, bytes, bytes]] = {}
        for record in raw.split(b"\0"):
            if not record:
                continue
            try:
                metadata, path = record.split(b"\t", 1)
                mode, object_type, oid = metadata.split(b" ")
            except ValueError as exc:
                raise MilestoneFailure("checkpoint artifact Git tree is malformed") from exc
            if not path or path in entries:
                raise MilestoneFailure("checkpoint artifact Git paths are ambiguous")
            entries[path] = (mode, object_type, oid)
        return entries

    def _checkpoint_manifest_path(self, milestone_id: str) -> str:
        return f"docs/reviews/{milestone_id}-checkpoint-artifact-manifest.json"

    def _checkpoint_artifact_path(self, milestone_id: str, raw_sha256: str) -> str:
        return f"docs/reviews/{milestone_id}-checkpoint-artifacts/{raw_sha256}.json"

    def _checkpoint_receipts(self, events: list[dict[str, Any]], state: dict[str, Any],
                             head: str) -> list[dict[str, Any]]:
        assessment_sha = state.get("mission_gate", {}).get("assessment_sha256")
        required = state.get("mission_gate", {}).get("required_reviews", [])
        if (state.get("mission_gate", {}).get("outcome") != "PROCEED"
                or not required or not SHA256.fullmatch(assessment_sha or "")):
            raise MilestoneFailure("checkpoint recovery requires complete current review receipts")
        assessment_event = next((event for event in reversed(events)
                                 if event["event_type"] in {"initialized", "mission_assessed"}
                                 and event["event_sha256"] == assessment_sha), None)
        if (assessment_event is None or assessment_event["subject_head_sha"] != head
                or assessment_event["data"].get("change_identity") != state["repository"]["change_identity"]):
            raise MilestoneFailure("checkpoint recovery assessment subject is stale")
        tree = self._tree_entries(head)
        latest: dict[str, dict[str, Any]] = {}
        for event in events:
            if (event["event_type"] == "mission_reviewed"
                    and event["data"].get("assessment_sha256") == assessment_sha):
                latest[event["data"]["review"]["mechanism"]] = event
        receipts: list[dict[str, Any]] = []
        for mechanism in sorted(required):
            event = latest.get(mechanism)
            accepted = {"CONTINUE", "CONTINUE_WITH_GUARDRAIL"} if mechanism == "strategic" else {"ACCEPT"}
            if (event is None or event["subject_head_sha"] != head
                    or event["data"].get("change_identity") != state["repository"]["change_identity"]
                    or event["data"]["review"]["disposition"] not in accepted):
                raise MilestoneFailure("checkpoint recovery review receipt is stale or non-accepting")
            evidence: list[dict[str, str]] = []
            evidence_path = self._packet_reference(event["data"]["review"]["evidence"])
            path_bytes = evidence_path.encode("utf-8", errors="strict")
            entry = tree.get(path_bytes)
            if entry is None or entry[0] != b"100644" or entry[1] != b"blob":
                raise MilestoneFailure("checkpoint recovery receipt evidence is not an A-tree blob")
            content = self._run(["git", "cat-file", "blob", entry[2].decode("ascii")], 16 * 1024 * 1024)
            evidence.append({"path": evidence_path, "blob_oid": entry[2].decode("ascii"),
                             "sha256": hashlib.sha256(content).hexdigest()})
            receipts.append({"event_sha256": event["event_sha256"],
                             "assessment_sha256": event["data"]["assessment_sha256"],
                             "mechanism": mechanism,
                             "disposition": event["data"]["review"]["disposition"],
                             "change_identity": event["data"]["change_identity"],
                             "evidence": evidence})
        if len(receipts) > 3:
            raise MilestoneFailure("checkpoint recovery receipt inventory exceeded its bound")
        return receipts

    def _validate_checkpoint_envelope(self, envelope: Any, repository: dict[str, str],
                                      issue: int) -> tuple[bytes, str]:
        schema = _read_json(self.root / "schemas/agent-checkpoint-v1.schema.json", 65_536)
        if type(envelope) is not dict or list(Draft202012Validator(schema).iter_errors(envelope)):
            raise MilestoneFailure("checkpoint artifact does not match the closed agent-checkpoint contract")
        if (envelope["protocol"] != CHECKPOINT_PROTOCOL or envelope["schema_version"] != "1"
                or envelope["checkpoint_type"] not in {"design", "review"}
                or envelope["subject"] != {"kind": "issue", "number": issue}
                or envelope["approval"] is not None
                or envelope["delta"]["omitted_path_count"] != 0
                or envelope["repository"] != {
                    "name_with_owner": repository["name_with_owner"],
                    "branch": repository["branch"], "base_sha": repository["base_sha"],
                    "head_sha": repository["head_sha"], "code_dirty": False,
                }):
            raise MilestoneFailure("checkpoint artifact source identity or type is inadmissible")
        raw = _canonical(envelope)
        if len(raw) > CHECKPOINT_MAX_ENVELOPE_BYTES:
            raise MilestoneFailure("checkpoint artifact exceeded its byte bound")
        return raw, hashlib.sha256(raw).hexdigest()

    def register_checkpoint_artifacts(self, milestone_id: str, bundle_path: Path,
                                      summary: str, expected_generation: int,
                                      human_disposition: str, reviewer: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Register exact checkpoint envelopes against a clean REVIEW_READY HEAD."""
        if (MILESTONE.fullmatch(milestone_id) is None or not summary or len(summary) > 512
                or type(expected_generation) is not int or not isinstance(bundle_path, Path)
                or not isinstance(human_disposition, str) or not human_disposition.strip()
                or len(human_disposition) > 240 or any(ord(char) < 32 or ord(char) == 127 for char in human_disposition)
                or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 80
                or any(ord(char) < 32 or ord(char) == 127 for char in reviewer)):
            raise MilestoneFailure("checkpoint artifact registration is invalid")
        try:
            bundle_real = bundle_path.resolve(strict=True)
            bundle_real.relative_to(self.root)
        except (OSError, ValueError):
            bundle_real = None
        if bundle_real is not None:
            raise MilestoneFailure("checkpoint artifact bundle must be outside the repository")
        try:
            bundle_raw = bundle_path.read_bytes()
            if len(bundle_raw) > CHECKPOINT_MAX_BUNDLE_BYTES:
                raise MilestoneFailure("checkpoint artifact bundle exceeded its byte bound")
            candidate_values = json.loads(bundle_raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MilestoneFailure("checkpoint artifact bundle is malformed") from exc
        if (type(candidate_values) is not list or not 1 <= len(candidate_values) <= CHECKPOINT_MAX_ARTIFACTS):
            raise MilestoneFailure("checkpoint artifact bundle cardinality is invalid")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            stored = _read_json(state_path)
            repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            if _digest(stored) != _digest(self._materialized(milestone_id, events, stored["repository"])):
                raise MilestoneFailure("milestone state identity recovery conflict")
            if (stored["status"] != "REVIEW_READY"
                    or stored["scope"]["issue"] != 160
                    or stored["next"] != {"action": "request_merge", "human_boundary": True}
                    or stored["repository"]["head_sha"] != repository["head_sha"]
                    or stored["repository"]["branch"] != repository["branch"]
                    or stored["repository"]["base_sha"] != repository["base_sha"]
                    or stored["repository"]["change_identity"] != repository["change_identity"]):
                raise MilestoneFailure("checkpoint artifact registration requires REVIEW_READY at unchanged A")
            self._require_clean_worktree("checkpoint artifact registration")
            if events[-1]["event_type"] == "checkpoint_artifacts_registered":
                raise MilestoneFailure("checkpoint artifact registration is already pending")
            envelopes = [self._validate_checkpoint_envelope(value, repository, stored["scope"]["issue"])
                         for value in candidate_values]
            if len({digest for _, digest in envelopes}) != len(envelopes):
                raise MilestoneFailure("checkpoint artifact bundle contains duplicate content")
            manifest_path = self._checkpoint_manifest_path(milestone_id)
            if manifest_path.encode("utf-8") in self._tree_entries(repository["head_sha"]):
                raise MilestoneFailure("checkpoint artifact manifest path already exists at A")
            receipts = self._checkpoint_receipts(events, stored, repository["head_sha"])
            receipt_snapshot_sha = _digest(receipts)
            artifacts = []
            for value, (raw, digest) in zip(candidate_values, envelopes):
                path = self._checkpoint_artifact_path(milestone_id, digest)
                if len(path.encode("utf-8")) > 240 or path.encode("utf-8") in self._tree_entries(repository["head_sha"]):
                    raise MilestoneFailure("checkpoint artifact path is invalid or already exists at A")
                artifacts.append({"path": path, "checkpoint_type": value["checkpoint_type"],
                                  "mode": CHECKPOINT_MANIFEST_MODE, "sha256": digest})
            manifest = {"schema_version": "1", "protocol": CHECKPOINT_MANIFEST_PROTOCOL,
                        "milestone_id": milestone_id, "issue": stored["scope"]["issue"],
                        "repository": repository, "artifacts": artifacts,
                        "receipt_snapshot_sha256": receipt_snapshot_sha, "receipts": receipts}
            manifest_schema = _read_json(self.root / CHECKPOINT_MANIFEST_SCHEMA, 65_536)
            if list(Draft202012Validator(manifest_schema).iter_errors(manifest)):
                raise MilestoneFailure("checkpoint artifact manifest is malformed")
            manifest_raw = _canonical(manifest)
            if len(manifest_raw) > CHECKPOINT_MAX_MANIFEST_BYTES:
                raise MilestoneFailure("checkpoint artifact manifest exceeded its byte bound")
            manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
            data = {"manifest_path": manifest_path, "manifest_sha256": manifest_sha,
                    "source_change_identity": stored["repository"]["change_identity"],
                    "assessment_sha256": stored["mission_gate"]["assessment_sha256"],
                    "receipt_snapshot_sha256": receipt_snapshot_sha,
                    "human_disposition": human_disposition, "reviewer": reviewer,
                    "expected_generation": expected_generation,
                    "prior_history_tail_sha256": events[-1]["event_sha256"],
                    "base_sha": repository["base_sha"], "branch": repository["branch"],
                    "issue": stored["scope"]["issue"], "name_with_owner": repository["name_with_owner"],
                    "change_identity": repository["change_identity"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "checkpoint_artifacts_registered",
                     "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary,
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event)
            self._validate(event)
            if len(events) > self.policy["limits"]["max_events"] - 2 or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("checkpoint artifact registration exceeds history bounds")
            current_events = self._read_events(milestone_id)
            current_repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(current_events))
            current_state = _read_json(state_path)
            self._require_clean_worktree("checkpoint artifact registration")
            if (len(current_events) != len(events)
                    or current_events[-1]["event_sha256"] != events[-1]["event_sha256"]
                    or _digest(current_state) != _digest(stored)
                    or current_repository != repository):
                raise MilestoneFailure("checkpoint artifact registration identity changed during verification")
            state = self._project(events + [event], repository)
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            self._atomic_json(state_path, state); self._write_pointer(state)
            return state, manifest

    def _require_clean_worktree(self, operation: str) -> None:
        status = self._run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], 1_048_576)
        entries = [entry for entry in status.split(b"\0") if entry]
        if any(len(entry) < 4 or entry[2:3] != b" " or entry[3:].decode("utf-8") != PROTECTED_RESIDUE
               for entry in entries):
            raise MilestoneFailure(f"{operation} requires a clean worktree")

    def _checkpoint_delta(self, old_head: str, new_head: str,
                          expected_paths: set[bytes]) -> None:
        raw = self._run(["git", "diff-tree", "--raw", "-r", "-z", "--no-abbrev", "--no-renames",
                         old_head, new_head, "--"], 1_048_576)
        parts = raw.split(b"\0")
        changed: dict[bytes, tuple[bytes, bytes, bytes, bytes, bytes]] = {}
        i = 0
        while i < len(parts) and parts[i]:
            header = parts[i]; i += 1
            if not header.startswith(b":") or i >= len(parts) or not parts[i]:
                raise MilestoneFailure("checkpoint artifact tree delta is malformed")
            try:
                old_mode, new_mode, old_oid, new_oid, status = header[1:].split(b" ")
            except ValueError as exc:
                raise MilestoneFailure("checkpoint artifact tree delta is malformed") from exc
            path = parts[i]; i += 1
            if path in changed:
                raise MilestoneFailure("checkpoint artifact tree delta has ambiguous paths")
            changed[path] = (old_mode, new_mode, old_oid, new_oid, status)
        if set(changed) != expected_paths:
            raise MilestoneFailure("checkpoint artifact tree delta contains unregistered or missing paths")
        for path, (old_mode, new_mode, old_oid, _new_oid, status) in changed.items():
            if status != b"A" or old_mode != b"000000" or old_oid != b"0" * 40 or new_mode != b"100644":
                raise MilestoneFailure("checkpoint artifact tree delta contains a modification or unsupported mode")

    def _verify_checkpoint_recovery(self, events: list[dict[str, Any]], index: int,
                                    bound_head: str, bound_identity: str,
                                    data: dict[str, Any]) -> None:
        event = events[index]
        if index == 0 or events[index - 1]["event_type"] != "checkpoint_artifacts_registered":
            raise MilestoneFailure("checkpoint recovery registration is missing or stale")
        registration = events[index - 1]
        reg = registration["data"]
        if (data.get("registration_event_sha256") != registration["event_sha256"]
                or registration["subject_head_sha"] != bound_head
                or reg["source_change_identity"] != bound_identity
                or data["rebound_from_head"] != bound_head
                or data["old_change_identity"] != bound_identity
                or data["new_head"] != event["subject_head_sha"]
                or data["manifest_path"] != reg["manifest_path"]
                or data["manifest_sha256"] != reg["manifest_sha256"]
                or data["receipt_snapshot_sha256"] != reg["receipt_snapshot_sha256"]
                or data["expected_generation"] != event["sequence"] - 2
                or data["prior_history_tail_sha256"] != event["prior_event_sha256"]
                or data["base_sha"] != reg["base_sha"]
                or data["branch"] != reg["branch"]
                or reg["manifest_path"] != self._checkpoint_manifest_path(event["milestone_id"])
                or reg["expected_generation"] != registration["sequence"] - 2
                or reg["prior_history_tail_sha256"] != registration["prior_event_sha256"]
                or reg["issue"] != events[0]["data"]["issue"]
                or reg["issue"] != 160
                or data["resulting_state"] != {"status": "CI_PENDING", "next_action": "ingest_ci",
                                                "ci_status": "not_observed", "ci_head_sha": None}):
            raise MilestoneFailure("checkpoint recovery provenance is inconsistent")
        if not data["human_disposition"].strip() or not data["reviewer"].strip():
            raise MilestoneFailure("checkpoint recovery human disposition is inconsistent")
        old_head = bound_head
        new_head = event["subject_head_sha"]
        parents = self._line(["git", "rev-list", "--parents", "-n", "1", new_head]).split()
        if parents != [new_head, old_head]:
            raise MilestoneFailure("checkpoint recovery requires a direct child descendant HEAD")
        try:
            manifest_entry = self._tree_entries(new_head).get(data["manifest_path"].encode("utf-8"))
        except (UnicodeError, KeyError) as exc:
            raise MilestoneFailure("checkpoint recovery manifest path is invalid") from exc
        if manifest_entry is None or manifest_entry[:2] != (b"100644", b"blob"):
            raise MilestoneFailure("checkpoint recovery manifest blob is missing")
        manifest_raw = self._run(["git", "cat-file", "blob", manifest_entry[2].decode("ascii")], CHECKPOINT_MAX_MANIFEST_BYTES)
        if hashlib.sha256(manifest_raw).hexdigest() != data["manifest_sha256"]:
            raise MilestoneFailure("checkpoint recovery manifest digest does not match registration")
        try:
            manifest = json.loads(manifest_raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise MilestoneFailure("checkpoint recovery manifest is malformed") from exc
        manifest_schema = _read_json(self.root / CHECKPOINT_MANIFEST_SCHEMA, 65_536)
        if (manifest_raw != _canonical(manifest)
                or list(Draft202012Validator(manifest_schema).iter_errors(manifest))
                or manifest["milestone_id"] != event["milestone_id"]
                or manifest["issue"] != reg["issue"]
                or manifest["repository"] != {"name_with_owner": reg["name_with_owner"],
                                                "branch": reg["branch"], "base_sha": reg["base_sha"],
                                                "head_sha": old_head, "change_identity": bound_identity}
                or manifest["repository"]["change_identity"] != reg["source_change_identity"]
                or manifest["receipt_snapshot_sha256"] != reg["receipt_snapshot_sha256"]
                or _digest(manifest["receipts"]) != reg["receipt_snapshot_sha256"]):
            raise MilestoneFailure("checkpoint recovery manifest contract or source binding is invalid")
        prior_events = events[:index - 1]
        prior_repository = {"name_with_owner": reg["name_with_owner"], "branch": reg["branch"],
                            "base_sha": reg["base_sha"], "head_sha": old_head,
                            "change_identity": bound_identity}
        prior_state = self._project(prior_events, prior_repository)
        if (prior_state["status"] != "REVIEW_READY"
                or prior_state["mission_gate"]["assessment_sha256"] != reg["assessment_sha256"]
                or self._checkpoint_receipts(prior_events, prior_state, old_head) != manifest["receipts"]):
            raise MilestoneFailure("checkpoint recovery receipt inventory is incomplete or changed")
        artifact_paths: set[bytes] = set()
        artifact_files: dict[bytes, dict[str, Any]] = {}
        checkpoint_schema = _read_json(self.root / "schemas/agent-checkpoint-v1.schema.json", 65_536)
        new_tree = self._tree_entries(new_head)
        old_tree = self._tree_entries(old_head)
        for artifact in manifest["artifacts"]:
            path_bytes = artifact["path"].encode("utf-8")
            expected_path = self._checkpoint_artifact_path(event["milestone_id"], artifact["sha256"])
            if (artifact["path"] != expected_path or path_bytes in old_tree or path_bytes in artifact_paths
                    or artifact["mode"] != CHECKPOINT_MANIFEST_MODE):
                raise MilestoneFailure("checkpoint recovery artifact path is substituted")
            entry = new_tree.get(path_bytes)
            if entry is None or entry[:2] != (b"100644", b"blob"):
                raise MilestoneFailure("checkpoint recovery artifact blob is missing or unsupported")
            raw = self._run(["git", "cat-file", "blob", entry[2].decode("ascii")], CHECKPOINT_MAX_ENVELOPE_BYTES)
            if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
                raise MilestoneFailure("checkpoint recovery artifact digest is substituted")
            try:
                envelope = json.loads(raw)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise MilestoneFailure("checkpoint recovery artifact is malformed") from exc
            if (raw != _canonical(envelope) or list(Draft202012Validator(checkpoint_schema).iter_errors(envelope))
                    or envelope["checkpoint_type"] != artifact["checkpoint_type"]
                    or envelope["subject"] != {"kind": "issue", "number": reg["issue"]}
                    or envelope["repository"] != {"name_with_owner": manifest["repository"]["name_with_owner"],
                                                   "branch": reg["branch"], "base_sha": reg["base_sha"],
                                                   "head_sha": old_head, "code_dirty": False}
                    or envelope["approval"] is not None or envelope["delta"]["omitted_path_count"] != 0):
                raise MilestoneFailure("checkpoint recovery artifact contract or source binding is invalid")
            artifact_paths.add(path_bytes); artifact_files[path_bytes] = artifact
        manifest_path_bytes = data["manifest_path"].encode("utf-8")
        if manifest_path_bytes in old_tree:
            raise MilestoneFailure("checkpoint recovery manifest was not absent at A")
        self._checkpoint_delta(old_head, new_head, artifact_paths | {manifest_path_bytes})
        for receipt in manifest["receipts"]:
            found = next((item for item in events[:index - 1]
                          if item["event_sha256"] == receipt["event_sha256"]), None)
            if (found is None or found["event_type"] != "mission_reviewed"
                    or found["subject_head_sha"] != old_head
                    or found["data"].get("assessment_sha256") != receipt["assessment_sha256"]
                    or found["data"].get("change_identity") != receipt["change_identity"]
                    or found["data"]["review"]["mechanism"] != receipt["mechanism"]
                    or found["data"]["review"]["disposition"] != receipt["disposition"]
                    or receipt["change_identity"] != bound_identity
                    or len(receipt["evidence"]) != 1
                    or found["data"]["review"]["evidence"] != receipt["evidence"][0]["path"]):
                raise MilestoneFailure("checkpoint recovery retained receipt is misbound")
            for evidence in receipt["evidence"]:
                path_bytes = evidence["path"].encode("utf-8")
                old_blob = old_tree.get(path_bytes); new_blob = new_tree.get(path_bytes)
                if (old_blob is None or new_blob is None or old_blob[:2] != (b"100644", b"blob")
                        or new_blob != old_blob or old_blob[2].decode("ascii") != evidence["blob_oid"]):
                    raise MilestoneFailure("checkpoint recovery retained receipt evidence changed")
                content = self._run(["git", "cat-file", "blob", old_blob[2].decode("ascii")], 16 * 1024 * 1024)
                if hashlib.sha256(content).hexdigest() != evidence["sha256"]:
                    raise MilestoneFailure("checkpoint recovery retained receipt evidence digest changed")
        excluded = tuple([data["manifest_path"], *(artifact["path"] for artifact in manifest["artifacts"])])
        if self._committed_change_identity(reg["base_sha"], old_head) != bound_identity:
            raise MilestoneFailure("checkpoint recovery old source identity is inconsistent")
        if self._committed_change_identity(reg["base_sha"], new_head, excluded) != bound_identity:
            raise MilestoneFailure("checkpoint recovery includes unrelated source changes")
        if self._committed_change_identity(reg["base_sha"], new_head) != data["change_identity"]:
            raise MilestoneFailure("checkpoint recovery new source identity is inconsistent")

    def _controller_identity(self, head: str, paths: tuple[str, ...], diff_sha256: str) -> str:
        return _digest({"head_sha": head, "paths": list(paths), "diff_sha256": diff_sha256})

    def _paths(self, milestone_id: str) -> tuple[Path, Path, Path]:
        if MILESTONE.fullmatch(milestone_id) is None:
            raise MilestoneFailure("milestone ID is invalid")
        directory = self.state_root / milestone_id
        return directory, directory / "state.json", directory / "history.ndjson"

    def _repair_paths(self, state: dict[str, Any]) -> None:
        base = state["repository"]["base_sha"]
        names = [value.decode("utf-8") for value in self._run(["git", "diff", "--name-only", "-z", base, "--"], 1_048_576).split(b"\0") if value]
        status = self._run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], 1_048_576).split(b"\0")
        for entry in status:
            if entry:
                if len(entry) < 4 or entry[2:3] != b" ": raise MilestoneFailure("repository status is malformed")
                names.append(entry[3:].decode("utf-8"))
        names = sorted(set(path for path in names if path != PROTECTED_RESIDUE and not path.startswith(".vss/milestones/")))
        if len(names) > self.policy["limits"]["max_repair_files"]:
            raise MilestoneFailure("repair file budget exhausted")
        def matches(pattern: str, path: str) -> bool:
            return path.startswith(pattern[:-3]) if pattern.endswith("/**") else path == pattern
        if any(any(matches(pattern, path) for pattern in self.policy["protected_patterns"]) for path in names):
            raise MilestoneFailure("repair crosses a protected boundary")
        allowed = state["scope"]["paths"]
        if allowed and any(not any(path.startswith(prefix.rstrip("/")) for prefix in allowed) for path in names):
            raise MilestoneFailure("repair exceeds milestone scope")
        additions = deletions = 0
        for row in self._run(["git", "diff", "--numstat", base, "--"], 1_048_576).splitlines():
            fields = row.split(b"\t", 2)
            if len(fields) != 3: raise MilestoneFailure("repository diff statistics are malformed")
            additions += int(fields[0]) if fields[0].isdigit() else 0; deletions += int(fields[1]) if fields[1].isdigit() else 0
        if additions + deletions > self.policy["limits"]["max_repair_line_delta"]:
            raise MilestoneFailure("repair line budget exhausted")

    @contextmanager
    def _locked(self, directory: Path) -> Iterator[None]:
        directory.mkdir(parents=True, exist_ok=True)
        lock = directory / ".lock"
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _atomic_json(self, path: Path, value: dict[str, Any]) -> None:
        raw = _canonical(value) + b"\n"
        if len(raw) > self.policy["limits"]["max_state_bytes"]:
            raise MilestoneFailure("milestone state exceeded its bound")
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".state-", delete=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno()); temporary = Path(stream.name)
        os.replace(temporary, path)

    def _validate(self, value: dict[str, Any]) -> None:
        if list(Draft202012Validator(self.record_schema).iter_errors(value)):
            raise MilestoneFailure("milestone record is malformed")
        if value.get("authority") != AUTHORITY:
            raise MilestoneFailure("milestone record grants authority")

    def _active_decisions(self) -> tuple[set[str], str]:
        """Load the small Git-native index; its records remain the authority."""
        index = _read_json(self.root / DECISION_INDEX, 8192)
        if (set(index) != {"schema_version", "protocol", "decisions"}
                or index["schema_version"] != "1"
                or index["protocol"] != "vss.active-decision-index"
                or type(index["decisions"]) is not list or not index["decisions"]
                or len(index["decisions"]) > 8):
            raise MilestoneFailure("active decision index is malformed")
        active: set[str] = set()
        for entry in index["decisions"]:
            if (type(entry) is not dict or set(entry) != {"id", "status", "record"}
                    or type(entry["id"]) is not str or not re.fullmatch(r"DEC-[0-9]{4}", entry["id"])
                    or entry["status"] != "ACTIVE"):
                raise MilestoneFailure("active decision index is malformed")
            record_path = self._packet_reference(entry["record"])
            record = _read_json(self.root / record_path, 8192)
            required = {"id", "status", "scope", "decision", "rationale", "constraints",
                        "supersedes", "superseded_by", "references"}
            if (set(record) != required or record["id"] != entry["id"]
                    or record["status"] != "ACTIVE"
                    or any(type(record[key]) is not str or not record[key].strip()
                           for key in ("scope", "decision", "rationale", "constraints"))
                    or record["supersedes"] is not None or record["superseded_by"] is not None
                    or type(record["references"]) is not list or not record["references"]
                    or any(self._packet_reference(reference) != reference for reference in record["references"])
                    or entry["id"] in active):
                raise MilestoneFailure("active decision record is malformed")
            active.add(entry["id"])
        return active, _digest(index)

    def _mission_gate(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Replay declared evidence; review receipts are coordination, never authority."""
        assessment = None
        assessment_sha = None
        required: set[str] = set()
        reviews: dict[str, str] = {}
        stalled = 0
        decision_ids: list[str] = []
        active_decisions, _ = self._active_decisions()
        for event in events:
            data = event["data"]
            kind = event["event_type"]
            if "mission" in data:
                if kind not in {"initialized", "mission_assessed"}:
                    raise MilestoneFailure("mission evidence is misplaced")
                assessment = data["mission"]
                assessment_sha = event["event_sha256"]
                reviews = {}
                heartbeat = assessment["heartbeat"]
                if len({item["milestone_id"] for item in heartbeat}) != len(heartbeat):
                    raise MilestoneFailure("mission heartbeat repeats a milestone")
                stalled = 0
                for item in reversed(heartbeat):
                    if item["advanced"]:
                        break
                    stalled += 1
                for trigger in assessment["triggers"]:
                    required.update(MISSION_REVIEWS[trigger])
                decision_ids = [item["id"] for item in assessment["active_decisions"]]
                if (len(set(decision_ids)) != len(decision_ids)
                        or set(decision_ids) != active_decisions):
                    raise MilestoneFailure("mission assessment does not exactly cover active decisions")
                decision_ids.sort()
                if any(item["disposition"] == "CHALLENGE" for item in assessment["active_decisions"]):
                    required.update({"strategic", "constitutional"})
                if stalled >= 3:
                    required.add("strategic")
                # Required reviews remain latched: a replacement declaration cannot
                # erase a concern. Reassessment invalidates all earlier receipts.
            elif kind == "mission_assessed":
                raise MilestoneFailure("mission assessment is missing")
            if kind == "mission_reviewed":
                if (assessment is None or data["assessment_sha256"] != assessment_sha
                        or data["review"]["mechanism"] not in required):
                    raise MilestoneFailure("mission review does not match the current assessment")
                review = data["review"]
                mechanism = review["mechanism"]
                allowed = ({"CONTINUE", "CONTINUE_WITH_GUARDRAIL", "REMEDIATE_FIRST", "STRATEGIC_REASSESSMENT"}
                           if mechanism == "strategic" else {"ACCEPT", "REVISE", "REJECT"})
                if review["disposition"] not in allowed:
                    raise MilestoneFailure("mission review disposition is incompatible")
                self._packet_reference(review["evidence"])
                reviews[mechanism] = review["disposition"]
        outcome = "PROCEED"
        if assessment is None or assessment["authority_alignment"] != "aligned":
            outcome = "STRATEGIC_REVIEW_REQUIRED"
        elif any(value in {"REMEDIATE_FIRST", "REVISE", "REJECT"} for value in reviews.values()):
            outcome = "REVISE"
        elif (required - reviews.keys() or "STRATEGIC_REASSESSMENT" in reviews.values()):
            outcome = "STRATEGIC_REVIEW_REQUIRED"
        return {"outcome": outcome, "assessment_sha256": assessment_sha,
                "required_reviews": sorted(required), "consecutive_no_advance": stalled,
                "active_decision_ids": decision_ids}

    def _apply_mission_gate(self, state: dict[str, Any]) -> dict[str, Any]:
        if state["mission_gate"]["outcome"] != "PROCEED" and state["status"] != "CONFLICT":
            state["status"] = "DESIGN_REVIEW_REQUIRED"
            state["next"] = {"action": "request_design_review", "human_boundary": True}
            state["routing"] = {"model": self.policy["model_routing"]["architecture_security"], "advisory": True}
        return state

    def _command_json(self, argv: list[str], limit: int = 65536) -> dict[str, Any]:
        try:
            value = json.loads(self._run(argv, limit))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise MilestoneFailure("repository routing output is malformed") from exc
        if type(value) is not dict:
            raise MilestoneFailure("repository routing output is malformed")
        return value

    @staticmethod
    def _packet_reference(path: Any) -> str:
        if (type(path) is not str or not 1 <= len(path) <= 240 or path.startswith("/")
                or "//" in path or any(part in {"", ".", ".."} for part in path.split("/"))
                or any(ord(char) < 32 or ord(char) == 127 for char in path)
                or path == ".local" or path.startswith(".local/")
                or re.search(r"(?i)(secret|credential|token|api[_-]?key|private[_-]?key)", path)):
            raise MilestoneFailure("execution packet repository reference is invalid")
        return path

    def execution_packet(self, milestone_id: str | None = None) -> dict[str, Any]:
        """Project one strict, references-only handoff for the selected next action."""
        state = self.load(milestone_id)
        if state["status"] == "CONFLICT":
            raise MilestoneFailure("execution packet repository identity is stale")
        for path in state["scope"]["paths"]:
            self._packet_reference(path)

        impact = self._command_json([
            "scripts/vss-agent", "impact", "--base", state["repository"]["base_sha"],
        ])
        impact_keys = {"schema_version", "map_sha256", "changed_paths", "domains", "minimum_level",
                       "risk", "profiles", "human_gate_required", "unknown_paths", "authority"}
        harness_authority = {"runtime_execution": False, "provider_execution": False,
                             "merge": False, "push": False}
        if (set(impact) != impact_keys or impact.get("schema_version") != "2"
                or type(impact.get("map_sha256")) is not str
                or SHA256.fullmatch(impact["map_sha256"]) is None
                or impact.get("authority") != harness_authority
                or any(type(impact.get(key)) is not list for key in (
                    "changed_paths", "domains", "profiles", "unknown_paths"))
                or impact.get("minimum_level") not in {"L0", "L1", "L2", "L3"}
                or impact.get("risk") not in {"docs", "isolated", "shared", "external-effect", "paid-authority"}
                or type(impact.get("human_gate_required")) is not bool):
            raise MilestoneFailure("repository impact routing is malformed")
        if impact["unknown_paths"]:
            raise MilestoneFailure("execution packet has unclassified repository impact")

        requested_domains = sorted(set(["agent-coordination", *state["scope"]["domains"],
                                        *impact.get("domains", [])]))
        context_argv = ["scripts/vss-agent", "context"]
        for domain in requested_domains:
            context_argv.extend(["--domain", domain])
        routed = self._command_json(context_argv)
        if (set(routed) != {"schema_version", "map_sha256", "domains", "paths"}
                or routed.get("schema_version") != "2"
                or routed.get("map_sha256") != impact["map_sha256"]
                or routed.get("domains") != requested_domains
                or type(routed.get("paths")) is not dict
                or set(routed["paths"]) != {"docs", "code", "tests"}):
            raise MilestoneFailure("repository context routing is malformed")
        for category in ("docs", "code", "tests"):
            paths = routed["paths"][category]
            if (type(paths) is not list or paths != sorted(set(paths))
                    or any(self._packet_reference(path) != path for path in paths)):
                raise MilestoneFailure("repository context routing is malformed")
        code = routed["paths"]["code"]
        contract_prefixes = ("config/", "schemas/")

        def is_contract(path: str) -> bool:
            return path in {"config", "schemas"} or path.startswith(contract_prefixes)

        context = {
            "domains": requested_domains,
            "guidance_docs": routed["paths"]["docs"],
            "implementation": [path for path in code if not is_contract(path)],
            "tests": routed["paths"]["tests"],
            "validation_config_contracts": [path for path in code if is_contract(path)],
        }
        reference_count = sum(len(context[key]) for key in (
            "guidance_docs", "implementation", "tests", "validation_config_contracts"))
        if reference_count > MAX_PACKET_PATHS:
            raise MilestoneFailure("execution packet repository context exceeded its bound")
        context["reference_count"] = reference_count
        context["content_included"] = False

        tier_by_action = {"run_affected_validation": ("affected", "L1"),
                          "run_subsystem_validation": ("subsystem", "L2"),
                          "run_canonical_validation": ("canonical", "L3")}
        required_tier: str | None = None
        required_level: str | None = None
        if state["next"]["action"] in tier_by_action:
            required_tier, requested_level = tier_by_action[state["next"]["action"]]
            required_level = (requested_level
                              if LEVELS[requested_level] >= LEVELS[impact["minimum_level"]]
                              else impact["minimum_level"])

        packet = {
            "schema_version": "1", "protocol": PACKET_PROTOCOL,
            "milestone": {"id": state["milestone_id"], "generation": state["generation"],
                          "status": state["status"]},
            "work_issue": {"kind": "issue", "number": state["scope"]["issue"]},
            "repository": state["repository"],
            "scope": {"domains": state["scope"]["domains"], "paths": state["scope"]["paths"]},
            "controller": {
                "next": state["next"], "routing": state["routing"],
                "history_tail": state["history_tail"], "state_sha256": _digest(state),
                "policy_sha256": state["policy_sha256"],
                "harness": {"schema_version": "2", "sha256": impact["map_sha256"]},
            },
            "validation": {
                "current_level": state["validation"]["level"],
                "evidence_sha256": state["validation"]["evidence_sha256"],
                "impact_minimum_level": impact["minimum_level"],
                "impact_human_gate_required": impact["human_gate_required"],
                "required_tier": required_tier, "required_level": required_level,
                "profiles": impact["profiles"], "risk": impact["risk"],
            },
            "ci": state["ci"],
            "repair": {"attempts": state["repair"]["attempts"],
                       "maximum_attempts": self.policy["limits"]["max_repair_attempts"],
                       "remaining_attempts": self.policy["limits"]["max_repair_attempts"] - state["repair"]["attempts"],
                       "stop_reason": state["repair"]["stop_reason"]},
            "context": context,
            "mission_gate": state["mission_gate"],
            "active_decisions": {"index_sha256": self._active_decisions()[1],
                                 "ids": state["mission_gate"]["active_decision_ids"]},
            "stop_and_challenge": True,
            "authority": dict(AUTHORITY),
        }
        if list(Draft202012Validator(self.packet_schema).iter_errors(packet)):
            raise MilestoneFailure("execution packet is malformed")
        if len(_canonical(packet)) > MAX_PACKET_BYTES:
            raise MilestoneFailure("execution packet exceeded its bound")
        events = self._read_events(state["milestone_id"])
        if self._repository(state["repository"]["base_sha"], self._residue_from_events(events)) != state["repository"]:
            raise MilestoneFailure("repository changed during execution packet generation")
        return packet

    def _read_events(self, milestone_id: str) -> list[dict[str, Any]]:
        _, _, history = self._paths(milestone_id)
        if not history.exists():
            raise MilestoneFailure("milestone history is missing")
        try:
            lines = history.read_bytes().splitlines()
        except OSError as exc:
            raise MilestoneFailure("milestone history is missing") from exc
        if not 1 <= len(lines) <= self.policy["limits"]["max_events"]:
            raise MilestoneFailure("milestone history is invalid")
        prior = "0" * 64; events: list[dict[str, Any]] = []
        for sequence, raw in enumerate(lines, 1):
            if len(raw) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("milestone event exceeded its bound")
            try: event = json.loads(raw)
            except json.JSONDecodeError as exc: raise MilestoneFailure("milestone history is malformed") from exc
            self._validate(event)
            claimed = event.pop("event_sha256")
            actual = _digest(event)
            event["event_sha256"] = claimed
            if claimed != actual or event["sequence"] != sequence or event["prior_event_sha256"] != prior:
                raise MilestoneFailure("milestone history conflict")
            prior = claimed; events.append(event)
        return events

    def _project(self, events: list[dict[str, Any]], repository: dict[str, str],
                 legacy: bool = False) -> dict[str, Any]:
        first = events[0]
        scope = first["data"]
        if (first["event_type"] != "initialized"
                or (set(scope) - {"mission"}) not in ({"issue", "domains", "paths"},
                                      {"issue", "domains", "paths", "initial_branch", "base_sha",
                                       "change_identity"},
                                      {"issue", "domains", "paths", "initial_branch", "base_sha",
                                       "change_identity", "residue_provenance",
                                       "residue_provenance_sha256"})
                or type(scope["issue"]) is not int or scope["issue"] < 1
                or type(scope["domains"]) is not list or type(scope["paths"]) is not list):
            raise MilestoneFailure("milestone initialization history is malformed")
        validation = {"evidence_sha256": None, "level": "none"}
        ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
        ci_subject_head: str | None = None
        ci_change_identity: str | None = None
        ci_evidence_version: int | None = None
        bound_head = first["subject_head_sha"]
        bound_change_identity = scope.get("change_identity", repository["change_identity"])
        residue_digest = scope.get("residue_provenance_sha256", self._residue_digest(None))
        modern_binding = "residue_provenance_sha256" in scope
        repair = {"attempts": 0, "stop_reason": None}
        status = "READY_FOR_IMPLEMENTATION"; action = "start_bounded_work"; human = False
        for event in events[1:]:
            data = event["data"]
            if event["event_type"] == "validation_completed":
                if data.get("evidence_binding_version") == 1:
                    if (type(data.get("governed_change_identity")) is not str
                            or not SHA256.fullmatch(data["governed_change_identity"])
                            or data.get("residue_provenance_sha256") != residue_digest
                            or data.get("controller_policy_sha256") != self.policy_digest
                            or type(data.get("validation_subject_head_sha")) is not str
                            or not SHA1.fullmatch(data["validation_subject_head_sha"])
                            or type(data.get("validation_map_sha256")) is not str
                            or not SHA256.fullmatch(data["validation_map_sha256"])):
                        raise MilestoneFailure("validation evidence binding is malformed")
                    modern_binding = True
                    bound_head = event["subject_head_sha"]
                    bound_change_identity = data["change_identity"]
                    if ci_evidence_version != 1:
                        ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                        ci_subject_head = None; ci_change_identity = None; ci_evidence_version = None
                validation = {"evidence_sha256": data.get("evidence_sha256"), "level": data.get("validation_level", "none")}
                if (ci["status"] == "passed" and ci["head_sha"] == event["subject_head_sha"]
                        and ci_subject_head == event["subject_head_sha"]
                        and ci_change_identity == data.get("change_identity")):
                    status, action, human = "REVIEW_READY", "request_merge", True
                else:
                    status, action = "CI_PENDING", "ingest_ci"
            elif event["event_type"] == "ci_observed":
                if data.get("ci_evidence_version") == 1:
                    evidence = data.get("ci_evidence")
                    if (data.get("governed_change_identity") != bound_change_identity
                            or data.get("residue_provenance_sha256") != residue_digest
                            or data.get("source_head_sha") != bound_head
                            or event["subject_head_sha"] != bound_head
                            or data.get("ci_head_sha") != bound_head
                            or type(evidence) is not dict
                            or evidence.get("workflow_blob") != CI_WORKFLOW_BLOB
                            or evidence.get("inventory_sha256") != CI_CHECK_INVENTORY_SHA256
                            or evidence.get("head_sha") != bound_head
                            or evidence.get("workflow_path") != CI_WORKFLOW_PATH
                            or type(evidence.get("observation_sha256")) is not str
                            or not SHA256.fullmatch(evidence["observation_sha256"])
                            or evidence.get("repository") != repository["name_with_owner"]
                            or type(evidence.get("workflow_id")) is not int
                            or type(evidence.get("run_id")) is not int
                            or evidence.get("run_status") not in {"completed", "in_progress", "queued", "requested"}
                            or evidence.get("run_conclusion") not in {"success", "failure", "cancelled", "timed_out", "action_required", ""}
                            or type(evidence.get("jobs")) is not list
                            or len(evidence["jobs"]) != len(CI_REQUIRED_CHECKS)
                            or any(type(item) is not dict or type(item.get("name")) is not str
                                   for item in evidence["jobs"])
                            or sorted(item.get("name") for item in evidence["jobs"] if type(item) is dict)
                            != sorted(CI_REQUIRED_CHECKS)
                            or any(type(item) is not dict or set(item) != {"name", "status", "conclusion", "head_sha"}
                                   or item.get("head_sha") != bound_head for item in evidence["jobs"])
                            or len({item["name"] for item in evidence["jobs"]}) != len(CI_REQUIRED_CHECKS)
                            or (data.get("ci_status") == "passed" and (
                                evidence.get("run_status") != "completed"
                                or evidence.get("run_conclusion") != "success"
                                or any(item.get("status") != "completed" or item.get("conclusion") != "success"
                                       for item in evidence["jobs"])))
                            or type(evidence.get("run_attempt")) is not int
                            or evidence.get("run_attempt", 0) < 1
                            or evidence.get("observation_sha256") != _digest({
                                key: evidence.get(key) for key in (
                                    "repository", "head_sha", "workflow_id", "workflow_path", "workflow_blob",
                                    "run_id", "run_attempt", "run_status", "run_conclusion", "jobs")})
                            or data.get("ci_status") != (
                                "pending" if evidence.get("run_status") != "completed"
                                or any(item.get("status") != "completed" for item in evidence["jobs"])
                                else "passed" if evidence.get("run_conclusion") == "success"
                                and all(item.get("conclusion") == "success" for item in evidence["jobs"])
                                else "failed")
                            or data.get("ci_classification") != (
                                "none" if data.get("ci_status") == "pending"
                                else "none" if data.get("ci_status") == "passed"
                                else "security" if any(item.get("name") == "Scan for secrets"
                                                         and item.get("conclusion") not in {"success", ""}
                                                         for item in evidence["jobs"])
                                else "code")):
                        raise MilestoneFailure("CI observation is not bound to current source identity")
                    modern_binding = True
                    ci_evidence_version = 1
                elif modern_binding:
                    # Historical CI remains replayable but cannot satisfy a modern source binding.
                    ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                    ci_subject_head = None; ci_change_identity = None; ci_evidence_version = None
                    continue
                ci = {"head_sha": data.get("ci_head_sha"), "status": data.get("ci_status", "not_observed"), "classification": data.get("ci_classification", "none")}
                ci_subject_head = event["subject_head_sha"]
                ci_change_identity = data.get("governed_change_identity", data.get("change_identity"))
                if ci["status"] == "failed":
                    mapping = {"code": "repair_code", "fixture": "repair_fixture", "flaky/unknown": "reproduce_flaky"}
                    action = mapping.get(ci["classification"], "request_security_review" if ci["classification"] == "security" else "recover_state")
                    human = ci["classification"] in {"security", "infrastructure", "flaky/unknown"}
                    status = "REPAIRING" if not human else "BLOCKED"
                    repair["stop_reason"] = None if not human else ci["classification"]
                elif ci["status"] == "passed": status, action, human = "CANONICAL_VALIDATION_REQUIRED", "run_canonical_validation", False
                elif ci["status"] == "stale": status, action, human = "CONFLICT", "recover_state", True
            elif event["event_type"] == "repair_started":
                repair["attempts"] = data.get("repair_attempts", repair["attempts"] + 1)
                status, action = "LOCAL_VALIDATION_REQUIRED", "run_affected_validation"
            elif event["event_type"] == "validation_invalidated":
                validation = {"evidence_sha256": None, "level": "none"}
                ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                status, action, human = "LOCAL_VALIDATION_REQUIRED", "run_affected_validation", False
            elif event["event_type"] == "issue160_legacy_state_recovered":
                validation = {"evidence_sha256": None, "level": "none"}
                ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                ci_subject_head = None; ci_change_identity = None; ci_evidence_version = None
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                modern_binding = True
                status, action, human = "CANONICAL_VALIDATION_REQUIRED", "run_canonical_validation", False
            elif event["event_type"] == "identity_rebound":
                ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                ci_subject_head = None; ci_change_identity = None
                if data.get("validation_invalidated"):
                    validation = {"evidence_sha256": None, "level": "none"}
                    status, action, human = "LOCAL_VALIDATION_REQUIRED", "run_affected_validation", False
                else:
                    status, action, human = "CI_PENDING", "ingest_ci", False
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
            elif event["event_type"] == "identity_reconciled":
                validation = {"evidence_sha256": data["validation_evidence_sha256"], "level": "L3"}
                ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                ci_subject_head = None; ci_change_identity = None
                status, action, human = "CI_PENDING", "ingest_ci", False
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
            elif event["event_type"] == "controller_bootstrap":
                ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
                ci_subject_head = None; ci_change_identity = None
                status, action, human = "CI_PENDING", "ingest_ci", False
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
            elif event["event_type"] == "blocked": status, action, human, repair["stop_reason"] = "BLOCKED", "request_architecture_review", True, data.get("stop_reason")
            elif event["event_type"] == "completed": status, action, human = "COMPLETE", "none", True
        tail = events[-1]
        model = self.policy["model_routing"]["maintenance"]
        if human:
            model = self.policy["model_routing"]["architecture_security"]
        elif action in {"repair_code", "repair_fixture", "run_affected_validation", "run_subsystem_validation"}:
            model = self.policy["model_routing"]["bounded_implementation"]
        state = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "state", "milestone_id": first["milestone_id"],
                 "generation": len(events) - 1, "status": status, "repository": repository,
                 "scope": {"issue": scope["issue"], "domains": scope.get("domains", []), "paths": scope.get("paths", [])},
                 "validation": validation, "ci": ci, "repair": repair, "routing": {"model": model, "advisory": True}, "next": {"action": action, "human_boundary": human},
                 "history_tail": {"sequence": tail["sequence"], "sha256": tail["event_sha256"]}, "policy_sha256": self.policy_digest,
                 "authority": dict(AUTHORITY)}
        if not legacy:
            state["mission_gate"] = self._mission_gate(events)
            self._apply_mission_gate(state)
        self._validate(state); return state

    def _write_pointer(self, state: dict[str, Any]) -> None:
        pointer = {"schema_version": "1", "milestone_id": state["milestone_id"], "state_sha256": _digest(state),
                   "history_tail_sha256": state["history_tail"]["sha256"]}
        self._atomic_json(self.state_root / "current.json", pointer)

    def initialize(self, milestone_id: str, base: str, issue: int, domains: list[str], paths: list[str], summary: str,
                   mission: dict[str, Any] | None = None) -> dict[str, Any]:
        directory, state_path, history = self._paths(milestone_id)
        if issue < 1 or not summary or len(summary) > 512 or len(domains) > 16 or len(paths) > 64:
            raise MilestoneFailure("milestone initialization is invalid")
        residue_provenance = self._capture_residue(base)
        repository = self._repository(base, residue_provenance)
        with self._locked(directory):
            if state_path.exists() or history.exists(): raise MilestoneFailure("milestone already exists")
            data = {"issue": issue, "domains": sorted(set(domains)), "paths": sorted(set(paths)),
                    "initial_branch": repository["branch"], "base_sha": repository["base_sha"],
                    "change_identity": repository["change_identity"],
                    "residue_provenance": residue_provenance,
                    "residue_provenance_sha256": self._residue_digest(residue_provenance)}
            if mission is not None:
                data["mission"] = mission
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event", "milestone_id": milestone_id,
                     "sequence": 1, "event_type": "initialized", "prior_event_sha256": "0" * 64,
                     "subject_head_sha": repository["head_sha"], "summary": summary, "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            state = self._project([event], repository)
            if len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("milestone event exceeded its bound")
            history.write_bytes(_canonical(event) + b"\n")
            self._atomic_json(state_path, state); self._write_pointer(state)
            return state

    def _materialized(self, milestone_id: str, events: list[dict[str, Any]],
                      repository: dict[str, str]) -> dict[str, Any]:
        _, state_path, _ = self._paths(milestone_id)
        stored = _read_json(state_path)
        self._validate(stored)
        first = events[0]
        initialization = first["data"]
        if ("residue_provenance_sha256" in initialization
                and initialization["residue_provenance_sha256"]
                != self._residue_digest(initialization.get("residue_provenance"))):
            raise MilestoneFailure("milestone residue provenance digest conflicts")
        transitions = [event for event in events if event["event_type"] == "branch_transitioned"]
        if len(transitions) > 1:
            raise MilestoneFailure("milestone branch transition conflict")
        transition_data = transitions[0]["data"] if transitions else {}
        initial_branch = initialization.get(
            "initial_branch", transition_data.get("from_branch", stored["repository"]["branch"]))
        base_sha = initialization.get("base_sha", first["subject_head_sha"])
        modern_protocol = "residue_provenance_sha256" in initialization
        residue_digest = initialization.get("residue_provenance_sha256", self._residue_digest(None))
        baseline_change_identity = initialization.get(
            "change_identity", transition_data.get(
                "change_identity", stored["repository"]["change_identity"]))
        bound_branch = initial_branch
        bound_head = first["subject_head_sha"]
        bound_change_identity = baseline_change_identity
        if transitions:
            transition = transitions[0]
            data = transition["data"]
            if (data.get("from_branch") != initial_branch
                    or data.get("to_branch") != f"feature/{milestone_id}"
                    or data.get("base_sha") != base_sha
                    or data.get("change_identity") != baseline_change_identity
                    or transition["subject_head_sha"] != first["subject_head_sha"]):
                raise MilestoneFailure("milestone branch transition conflict")
            bound_branch = data["to_branch"]
        for index, event in enumerate(events[1:], 1):
            data = event["data"]
            if event["event_type"] == "validation_invalidated":
                if data.get("legacy_quarantine") is True:
                    prior_validation = next((prior for prior in reversed(events[:index])
                                             if prior["event_type"] == "validation_completed"), None)
                    if (prior_validation is None
                            or prior_validation["data"].get("evidence_binding_version") == 1
                            or data.get("recovered_event_sha256") != prior_validation["event_sha256"]
                            or data.get("prior_history_tail_sha256") != events[index - 1]["event_sha256"]
                            or data.get("change_identity") != bound_change_identity
                            or data.get("residue_provenance_sha256") != residue_digest
                            or data.get("expected_generation") != index - 1
                            or event["subject_head_sha"] != bound_head):
                        raise MilestoneFailure("legacy validation quarantine conflicts with source identity")
                elif (data.get("recovered_event_sha256") != events[index - 1]["event_sha256"]
                      or "change_identity" in events[index - 1]["data"]):
                    raise MilestoneFailure("milestone state identity recovery conflict")
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
            if event["event_type"] == "identity_rebound":
                if (data.get("rebound_from_head") != bound_head
                        or event["subject_head_sha"] == bound_head):
                    raise MilestoneFailure("milestone state identity recovery conflict")
                if data.get("recovery_kind") == "review_ready_checkpoint_artifacts":
                    self._verify_checkpoint_recovery(events, index, bound_head,
                                                    bound_change_identity, data)
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                modern_protocol = True
            elif event["event_type"] == "issue160_legacy_state_recovered":
                self._verify_issue160_legacy_recovery(events, index, data)
                bound_head = data["new_head"]
                bound_change_identity = data["change_identity"]
                bound_branch = data["branch"]
                modern_protocol = True
            elif event["event_type"] == "controller_bootstrap":
                if (data.get("old_head") != bound_head
                        or data.get("new_head") != event["subject_head_sha"]
                        or event["subject_head_sha"] == bound_head):
                    raise MilestoneFailure("milestone state identity recovery conflict")
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                modern_protocol = True
            elif (event["event_type"] == "validation_completed"
                  and data.get("evidence_binding_version") == 1):
                equivalent_recovery = next((prior for prior in reversed(events[:index])
                                            if prior["event_type"] == "identity_rebound"), None)
                if (data.get("residue_provenance_sha256") != self._residue_digest(self._residue_from_events(events))
                        or (data.get("change_identity") != data.get("governed_change_identity")
                            and (equivalent_recovery is None
                                 or equivalent_recovery["data"].get("recovery_kind") != "review_ready_checkpoint_artifacts"
                                 or equivalent_recovery["data"].get("old_change_identity")
                                 != data.get("governed_change_identity")))):
                    raise MilestoneFailure("validation evidence binding conflicts with source identity")
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                modern_protocol = True
            elif (event["event_type"] in {"mission_assessed", "mission_reviewed"}
                  and "change_identity" in data):
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                modern_protocol = True
            elif event["event_type"] == "identity_reconciled":
                # This narrowly scoped, human-authorized legacy reconciliation
                # carries fresh exact-HEAD canonical evidence. It advances the
                # replayed source binding, while _validation_current still
                # refuses to reuse older validation receipts across it.
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                if data.get("human_authorization") in {
                        POST_MERGE_RECONCILIATION_AUTHORIZATION,
                        POST_REPAIR_RECONCILIATION_AUTHORIZATION}:
                    bound_branch = repository["branch"]
                modern_protocol = True
            elif event["event_type"] == "ci_observed" and data.get("ci_evidence_version") == 1:
                modern_protocol = True
            elif (not modern_protocol and event["event_type"] != "branch_transitioned"
                  and "change_identity" in data):
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
                if (event["event_type"] == "identity_reconciled"
                        and data.get("human_authorization") in {
                            POST_MERGE_RECONCILIATION_AUTHORIZATION,
                            POST_REPAIR_RECONCILIATION_AUTHORIZATION,
                        }):
                        bound_branch = repository["branch"]
        historical_repository = {
            "name_with_owner": repository["name_with_owner"], "branch": bound_branch,
            "base_sha": base_sha, "head_sha": bound_head,
            "change_identity": bound_change_identity,
        }
        expected = self._project(events, historical_repository)
        legacy_ungated = None
        if "mission_gate" not in stored and not any("mission" in event["data"] or
                event["event_type"].startswith("mission_") for event in events):
            legacy_ungated = self._project(events, historical_repository, legacy=True)
        legacy_cycle_state = None
        cycle_source = legacy_ungated or expected
        if cycle_source["status"] == "REVIEW_READY" and cycle_source["next"] == {"action": "request_merge", "human_boundary": True}:
            legacy_cycle_state = {**cycle_source, "status": "CI_PENDING",
                                  "routing": {"model": self.policy["model_routing"]["maintenance"], "advisory": True},
                                  "next": {"action": "ingest_ci", "human_boundary": False}}
        if ((_digest(stored) != _digest(expected)
             and (legacy_ungated is None or _digest(stored) != _digest(legacy_ungated))
             and (legacy_cycle_state is None or _digest(stored) != _digest(legacy_cycle_state)))
                or stored["policy_sha256"] != self.policy_digest
                or stored["repository"]["name_with_owner"] != repository["name_with_owner"]):
            raise MilestoneFailure("milestone state conflict")
        return expected

    def load(self, milestone_id: str | None = None) -> dict[str, Any]:
        used_current_pointer = milestone_id is None
        if milestone_id is None:
            pointer = _read_json(self.state_root / "current.json", 2048); milestone_id = pointer.get("milestone_id")
            if (set(pointer) != {"schema_version", "milestone_id", "state_sha256", "history_tail_sha256"}
                    or pointer.get("schema_version") != "1" or type(milestone_id) is not str
                    or MILESTONE.fullmatch(milestone_id) is None
                    or any(type(pointer[key]) is not str or SHA256.fullmatch(pointer[key]) is None
                           for key in ("state_sha256", "history_tail_sha256"))):
                raise MilestoneFailure("milestone pointer is malformed")
        events = self._read_events(milestone_id)
        repository = self._repository(events[0]["subject_head_sha"], self._residue_from_events(events))
        stored = self._materialized(milestone_id, events, repository)
        if used_current_pointer:
            pointer = _read_json(self.state_root / "current.json", 2048)
            persisted = _read_json(self._paths(milestone_id)[1])
            if (pointer["state_sha256"] not in {_digest(stored), _digest(persisted)}
                    or pointer["history_tail_sha256"] != stored["history_tail"]["sha256"]):
                raise MilestoneFailure("milestone pointer conflict")
        latest_ci = next((event for event in reversed(events)
                          if event["event_type"] == "ci_observed"), None)
        ci_change_identity = (latest_ci["data"].get("governed_change_identity",
                                                    latest_ci["data"].get("change_identity"))
                              if latest_ci is not None else None)
        if (repository["branch"] != stored["repository"]["branch"]
                or repository["head_sha"] != stored["repository"]["head_sha"]):
            conflict = self._project(events, repository)
            if self._validation_current(events, repository) is None:
                conflict["validation"] = {"evidence_sha256": None, "level": "none"}
            if (conflict["ci"].get("head_sha") != repository["head_sha"]
                    or ci_change_identity != repository["change_identity"]):
                conflict["ci"] = {"head_sha": None, "status": "not_observed", "classification": "none"}
            conflict["status"] = "CONFLICT"; conflict["next"] = {"action": "recover_state", "human_boundary": True}
            return conflict
        if repository["change_identity"] != stored["repository"]["change_identity"]:
            partial = self._project(events, repository)
            if self._validation_current(events, repository) is None:
                partial["validation"] = {"evidence_sha256": None, "level": "none"}
            if ci_change_identity != repository["change_identity"]:
                partial["ci"] = {"head_sha": None, "status": "not_observed", "classification": "none"}
            partial["status"] = "WORKING"; partial["next"] = {"action": "run_affected_validation", "human_boundary": False}
            return self._apply_mission_gate(partial)
        return stored

    def transition_branch(self, milestone_id: str, from_branch: str, to_branch: str,
                          summary: str, expected_generation: int) -> dict[str, Any]:
        if (MILESTONE.fullmatch(milestone_id) is None or BRANCH.fullmatch(from_branch) is None
                or BRANCH.fullmatch(to_branch) is None or not summary or len(summary) > 512
                or type(expected_generation) is not int):
            raise MilestoneFailure("milestone branch transition is invalid")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            repository = self._repository(events[0]["subject_head_sha"], self._residue_from_events(events))
            stored = self._materialized(milestone_id, events, repository)
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            if any(event["event_type"] == "branch_transitioned" for event in events):
                raise MilestoneFailure("milestone branch transition already recorded")
            initialization = events[0]["data"]
            initial_branch = initialization.get("initial_branch", stored["repository"]["branch"])
            base_sha = initialization.get("base_sha", events[0]["subject_head_sha"])
            baseline_change_identity = initialization.get(
                "change_identity", stored["repository"]["change_identity"])
            try:
                source_head = self._line(["git", "rev-parse", "--verify", f"refs/heads/{from_branch}"])
            except MilestoneFailure as exc:
                raise MilestoneFailure("milestone branch transition source is invalid") from exc
            if (from_branch != initial_branch or to_branch != f"feature/{milestone_id}"
                    or repository["branch"] != to_branch or repository["base_sha"] != base_sha
                    or repository["head_sha"] != stored["repository"]["head_sha"]
                    or source_head != repository["head_sha"]):
                raise MilestoneFailure("milestone branch transition is unauthorized")
            data = {"from_branch": from_branch, "to_branch": to_branch, "base_sha": base_sha,
                    "change_identity": baseline_change_identity}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "branch_transitioned", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary, "data": data,
                     "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            historical_repository = dict(stored["repository"]); historical_repository["branch"] = to_branch
            state = self._project(events + [event], historical_repository)
            self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def historical_evidence_snapshot(self, milestone_id: str) -> dict[str, Any]:
        """Return bounded digests of persisted execution evidence, never its payloads."""
        if milestone_id != "m11-0-veo-shot":
            raise MilestoneFailure("historical evidence snapshot is not registered")
        root = self.root / ".local" / "movie" / "m11-0-moving-shot"
        files = []
        for path in sorted(root.rglob("*")) if root.is_dir() else []:
            if path.is_file() and (path.name == "attempt.json" or path.name.endswith(".attempt.json")):
                relative = path.relative_to(self.root).as_posix()
                files.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if not 1 <= len(files) <= 32:
            raise MilestoneFailure("historical evidence snapshot is invalid")
        return {"files": files, "sha256": _digest(files)}

    def _verify_issue160_legacy_history(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Recognize only the exact pre-provenance issue #160 event chain."""
        expected_types = (["initialized", "branch_transitioned", "mission_assessed"]
                          + ["mission_reviewed"] * 6 + ["validation_completed"] * 2)
        if (len(events) != 11
                or events[-1]["event_sha256"] != ISSUE160_LEGACY_HISTORY_TAIL
                or [event["event_type"] for event in events] != expected_types
                or any(event["milestone_id"] != ISSUE160_LEGACY_MILESTONE for event in events)):
            raise MilestoneFailure("issue 160 legacy history is not registered for recovery")
        initialization = events[0]["data"]
        if (events[0]["subject_head_sha"] != ISSUE160_LEGACY_BASE_HEAD
                or set(initialization) != {"issue", "domains", "paths", "initial_branch", "base_sha", "change_identity"}
                or initialization["issue"] != 160
                or initialization["initial_branch"] != "main"
                or initialization["base_sha"] != ISSUE160_LEGACY_BASE_HEAD
                or "residue_provenance" in initialization
                or "residue_provenance_sha256" in initialization):
            raise MilestoneFailure("issue 160 legacy initialization is not admissible")
        transition = events[1]
        if (transition["subject_head_sha"] != ISSUE160_LEGACY_BASE_HEAD
                or transition["data"].get("from_branch") != "main"
                or transition["data"].get("to_branch") != "feature/review-ready-source-identity-recovery"
                or transition["data"].get("base_sha") != ISSUE160_LEGACY_BASE_HEAD):
            raise MilestoneFailure("issue 160 legacy branch history is not admissible")
        if (events[2]["data"].get("mission") is None
                or events[2]["data"]["mission"].get("authority_alignment") != "aligned"
                or events[2]["data"]["mission"].get("triggers") != ["architecture_boundary"]
                or events[2]["event_sha256"] != ISSUE160_LEGACY_ASSESSMENT_EVENT):
            raise MilestoneFailure("issue 160 legacy mission assessment is not admissible")
        accepted = [event for event in events[3:9]
                    if event["data"].get("review", {}).get("disposition") == "ACCEPT"]
        validations = events[9:]
        if (len(accepted) != 2
                or {event["data"].get("review", {}).get("mechanism") for event in accepted}
                != {"constitutional", "unknown_unknown"}
                or any("evidence_binding_version" in event["data"] for event in validations)
                or any(event["data"].get("validation_level") != "L3"
                       or not SHA256.fullmatch(event["data"].get("evidence_sha256", ""))
                       for event in validations)
                or any(event["event_type"] == "ci_observed" for event in events)):
            raise MilestoneFailure("issue 160 legacy validation or review history is not admissible")
        return initialization

    def _verify_issue160_legacy_recovery(self, events: list[dict[str, Any]], index: int,
                                         data: dict[str, Any]) -> None:
        if index != 11:
            raise MilestoneFailure("issue 160 legacy recovery is not in its registered position")
        prefix = events[:index]
        initialization = self._verify_issue160_legacy_history(prefix)
        old_head = prefix[-1]["subject_head_sha"]
        old_identity = prefix[-1]["data"]["change_identity"]
        validation_event_sha256s = [event["event_sha256"] for event in prefix
                                    if event["event_type"] == "validation_completed"]
        event = events[index]
        if (data.get("migration_kind") != "issue160_legacy_source_identity"
                or data.get("prior_generation") != 10
                or data.get("prior_history_tail_sha256") != ISSUE160_LEGACY_HISTORY_TAIL
                or data.get("prior_bound_head") != old_head
                or data.get("prior_change_identity") != old_identity
                or data.get("base_sha") != initialization["base_sha"]
                or data.get("new_head") != event["subject_head_sha"]
                or data.get("branch") != ISSUE160_RECOVERY_BRANCH
                or data.get("validation_invalidated") is not True
                or data.get("ci_invalidated") is not True
                or data.get("prior_validation_event_sha256s") != validation_event_sha256s
                or data.get("prior_ci_event_sha256s") != []
                or data.get("residue_provenance_disposition") != "not_recorded_not_inferred"
                or data.get("resulting_state") != {
                    "status": "CANONICAL_VALIDATION_REQUIRED",
                    "next_action": "run_canonical_validation",
                    "validation_level": "none",
                    "ci_status": "not_observed",
                    "ci_head_sha": None}):
            raise MilestoneFailure("issue 160 legacy recovery event is malformed")
        self._run(["git", "cat-file", "-e", f"{data['new_head']}^{{commit}}"])
        if (subprocess.run(["git", "merge-base", "--is-ancestor", old_head, data["new_head"]],
                           cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False).returncode != 0
                or self._committed_change_identity(data["base_sha"], data["new_head"])
                != data["change_identity"]):
            raise MilestoneFailure("issue 160 legacy recovery source identity is invalid")

    def recover_issue160_legacy_state(self, expected_generation: int,
                                      human_disposition: str) -> dict[str, Any]:
        """Append the one registered recovery for the pre-#161/#162 issue #160 history."""
        if (type(expected_generation) is not int or not isinstance(human_disposition, str)
                or human_disposition != ISSUE160_LEGACY_RECOVERY_DISPOSITION or len(human_disposition) > 240
                or any(ord(char) < 32 or ord(char) == 127 for char in human_disposition)):
            raise MilestoneFailure("issue 160 legacy recovery invocation is invalid")
        milestone_id = ISSUE160_LEGACY_MILESTONE
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            initialization = self._verify_issue160_legacy_history(events)
            stored = _read_json(state_path)
            self._validate(stored)
            if expected_generation != 10 or stored.get("generation") != expected_generation:
                raise MilestoneFailure("issue 160 legacy recovery generation conflict")
            base_sha = initialization["base_sha"]
            repository = self._repository(base_sha)
            try:
                self._materialized(milestone_id, events, repository)
            except MilestoneFailure as exc:
                if str(exc) != "milestone state conflict":
                    raise
            else:
                raise MilestoneFailure("issue 160 legacy state does not require recovery")
            legacy_branch = events[1]["data"]["to_branch"]
            legacy_repo = {"name_with_owner": stored["repository"]["name_with_owner"],
                           "branch": legacy_branch, "base_sha": base_sha,
                           "head_sha": events[-1]["subject_head_sha"],
                           "change_identity": events[-1]["data"]["change_identity"]}
            legacy_projection = self._project(events, legacy_repo)
            if (_digest(stored) != _digest(legacy_projection)
                    or stored["status"] != "CI_PENDING"
                    or stored["validation"].get("level") != "L3"
                    or stored["validation"].get("evidence_sha256")
                    != events[-1]["data"]["evidence_sha256"]
                    or stored["authority"] != AUTHORITY
                    or stored["policy_sha256"] != self.policy_digest):
                raise MilestoneFailure("issue 160 legacy materialized state is not intact")
            if (repository["name_with_owner"] != ISSUE160_REPOSITORY_NAME
                    or repository["branch"] != ISSUE160_RECOVERY_BRANCH
                    or repository["base_sha"] != base_sha
                    or repository["head_sha"] == ISSUE160_LEGACY_BASE_HEAD
                    or subprocess.run(["git", "merge-base", "--is-ancestor", ISSUE160_RECOVERY_ANCHOR_HEAD,
                                       repository["head_sha"]], cwd=self.root, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, check=False).returncode != 0
                    or self._committed_change_identity(base_sha, ISSUE160_RECOVERY_ANCHOR_HEAD)
                    != ISSUE160_RECOVERY_ANCHOR_IDENTITY
                    or repository["change_identity"] != self._committed_change_identity(
                        base_sha, repository["head_sha"])):
                raise MilestoneFailure("issue 160 legacy recovery source is not the registered descendant")
            self._require_clean_worktree("issue 160 legacy recovery")
            validation_event_sha256s = [event["event_sha256"] for event in events
                                        if event["event_type"] == "validation_completed"]
            data = {"migration_kind": "issue160_legacy_source_identity",
                    "prior_generation": expected_generation,
                    "prior_history_tail_sha256": events[-1]["event_sha256"],
                    "prior_bound_head": events[-1]["subject_head_sha"],
                    "prior_change_identity": events[-1]["data"]["change_identity"],
                    "base_sha": repository["base_sha"], "branch": repository["branch"],
                    "new_head": repository["head_sha"],
                    "change_identity": repository["change_identity"],
                    "validation_invalidated": True, "ci_invalidated": True,
                    "prior_validation_event_sha256s": validation_event_sha256s,
                    "prior_ci_event_sha256s": [],
                    "residue_provenance_disposition": "not_recorded_not_inferred",
                    "human_disposition": human_disposition,
                    "resulting_state": {"status": "CANONICAL_VALIDATION_REQUIRED",
                                        "next_action": "run_canonical_validation",
                                        "validation_level": "none", "ci_status": "not_observed",
                                        "ci_head_sha": None}}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "issue160_legacy_state_recovered",
                     "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"],
                     "summary": "Invalidate legacy issue 160 validation and bind current source identity.",
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event)
            self._validate(event)
            self._verify_issue160_legacy_recovery(events + [event], len(events), data)
            if (len(events) >= self.policy["limits"]["max_events"]
                    or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]):
                raise MilestoneFailure("issue 160 legacy recovery event exceeded its bound")
            current_events = self._read_events(milestone_id)
            current_repository = self._repository(base_sha)
            current_state = _read_json(state_path)
            self._require_clean_worktree("issue 160 legacy recovery")
            if (len(current_events) != len(events)
                    or current_events[-1]["event_sha256"] != events[-1]["event_sha256"]
                    or _digest(current_state) != _digest(stored)
                    or current_repository != repository):
                raise MilestoneFailure("issue 160 legacy recovery identity changed during verification")
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            state = self._project(events + [event], repository)
            self._atomic_json(state_path, state)
            self._write_pointer(state)
        return self.load(milestone_id)

    def reconcile_source_identity(self, milestone_id: str, summary: str, reason: str,
                                  authorization: str, validation_evidence: Path,
                                  historical_evidence_sha256: str,
                                  expected_generation: int) -> dict[str, Any]:
        """Append an explicit, evidence-backed recovery event for a stale source identity."""
        if (milestone_id != "m11-0-veo-shot" or not summary or len(summary) > 512
                or not reason or len(reason) > 512
                or authorization not in {RECONCILIATION_AUTHORIZATION, POST_MERGE_RECONCILIATION_AUTHORIZATION,
                                         POST_REPAIR_RECONCILIATION_AUTHORIZATION}
                or not isinstance(validation_evidence, Path) or not SHA256.fullmatch(historical_evidence_sha256)
                or type(expected_generation) is not int):
            raise MilestoneFailure("source identity reconciliation is unauthorized")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id); stored = _read_json(state_path); self._validate(stored)
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            if any(event["event_type"] == "identity_reconciled"
                   and event["data"].get("new_head") == repository["head_sha"]
                   for event in events):
                return self.load(milestone_id)
            post_merge = authorization in {POST_MERGE_RECONCILIATION_AUTHORIZATION,
                                           POST_REPAIR_RECONCILIATION_AUTHORIZATION}
            allowed_statuses = {"READY_FOR_IMPLEMENTATION", "REVIEW_READY"} if post_merge else {"READY_FOR_IMPLEMENTATION"}
            if stored["status"] not in allowed_statuses:
                raise MilestoneFailure("source identity reconciliation requires original ready state")
            if ((post_merge and repository["branch"] != "main")
                    or (not post_merge and repository["branch"] != stored["repository"]["branch"])
                    or repository["base_sha"] != stored["repository"]["base_sha"]
                    or repository["head_sha"] == stored["repository"]["head_sha"]):
                raise MilestoneFailure("source identity reconciliation is unauthorized")
            if any(entry for entry in self._run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], 1_048_576).split(b"\0")
                   if entry and (len(entry) < 4 or entry[2:3] != b" " or entry[3:].decode("utf-8") != PROTECTED_RESIDUE)):
                raise MilestoneFailure("source identity reconciliation requires a clean worktree")
            if subprocess.run(["git", "merge-base", "--is-ancestor", stored["repository"]["head_sha"], repository["head_sha"]],
                              cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode != 0:
                raise MilestoneFailure("source identity reconciliation requires descendant HEAD")
            evidence = _read_json(validation_evidence, 65_536)
            if (evidence.get("protocol") != "vss.agent-validation-evidence" or evidence.get("passed") is not True
                    or evidence.get("repository") != {"name_with_owner": repository["name_with_owner"], "branch": repository["branch"],
                                                       "base_sha": repository["base_sha"], "head_sha": repository["head_sha"]}
                    or evidence.get("plan", {}).get("executed_level") != "L3"):
                raise MilestoneFailure("source identity reconciliation requires fresh canonical validation")
            snapshot = self.historical_evidence_snapshot(milestone_id)
            if snapshot["sha256"] != historical_evidence_sha256:
                raise MilestoneFailure("historical execution evidence changed")
            data = {"prior_bound_head": stored["repository"]["head_sha"], "new_head": repository["head_sha"],
                    "ancestry_proof": "prior_bound_head_is_ancestor_of_new_head", "validation_level": "L3",
                    "validation_evidence_sha256": _digest(evidence), "historical_evidence_sha256": snapshot["sha256"],
                    "human_authorization": authorization,
                    "reason": reason, "expected_generation": expected_generation,
                    "change_identity": repository["change_identity"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event", "milestone_id": milestone_id,
                     "sequence": len(events) + 1, "event_type": "identity_reconciled", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary, "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            if len(events) >= self.policy["limits"]["max_events"] or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("milestone event exceeded its bound")
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state = self._project(events + [event], repository); self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def recover_state_identity(self, milestone_id: str, summary: str,
                               expected_generation: int) -> dict[str, Any]:
        """Explicitly invalidate one legacy unbound validation tail without rewriting history."""
        if (MILESTONE.fullmatch(milestone_id) is None or not summary or len(summary) > 512
                or type(expected_generation) is not int):
            raise MilestoneFailure("milestone state identity recovery is invalid")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            repository = self._repository(events[0]["subject_head_sha"], self._residue_from_events(events))
            stored = _read_json(state_path); self._validate(stored)
            tail = events[-1]
            transitions = [event for event in events if event["event_type"] == "branch_transitioned"]
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            stored_repository = dict(repository)
            stored_repository["change_identity"] = stored["repository"]["change_identity"]
            legacy = "mission_gate" not in stored and not any(
                "mission" in event["data"] or event["event_type"].startswith("mission_") for event in events)
            repository_identity = {key: value for key, value in repository.items() if key != "change_identity"}
            stored_identity = {key: value for key, value in stored["repository"].items() if key != "change_identity"}
            if (len(transitions) != 1 or tail["event_type"] != "validation_completed"
                    or "change_identity" in tail["data"]
                    or stored["history_tail"] != {"sequence": tail["sequence"], "sha256": tail["event_sha256"]}
                    or stored_identity != repository_identity
                    or stored["policy_sha256"] != self.policy_digest
                    or _digest(stored) != _digest(self._project(events, stored_repository, legacy=legacy))):
                raise MilestoneFailure("milestone state identity recovery is unauthorized")
            transition = transitions[0]
            if (transition["data"].get("to_branch") != f"feature/{milestone_id}"
                    or transition["data"].get("base_sha") != repository["base_sha"]
                    or repository["branch"] != f"feature/{milestone_id}"):
                raise MilestoneFailure("milestone state identity recovery is unauthorized")
            data = {"change_identity": repository["change_identity"],
                    "recovered_event_sha256": tail["event_sha256"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "validation_invalidated", "prior_event_sha256": tail["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary,
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state = self._project(events + [event], repository)
            self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def rebind_committed_head(self, milestone_id: str, summary: str,
                              expected_generation: int, reviewed_head: str | None = None,
                              validation_evidence: Path | None = None,
                              checkpoint_manifest_sha256: str | None = None,
                              human_disposition: str | None = None,
                              reviewer: str | None = None) -> dict[str, Any]:
        """Explicitly bind a committed modern milestone head without rewriting history."""
        if (MILESTONE.fullmatch(milestone_id) is None or not summary or len(summary) > 512
                or type(expected_generation) is not int):
            raise MilestoneFailure("milestone head rebind is invalid")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            stored = _read_json(state_path); self._validate(stored)
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            try:
                repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            except MilestoneFailure as exc:
                raise MilestoneFailure("milestone head rebind is unauthorized") from exc
            historical = dict(stored["repository"])
            if _digest(stored) != _digest(self._project(events, historical)):
                raise MilestoneFailure("milestone state identity recovery conflict")
            recovery_args = (checkpoint_manifest_sha256, human_disposition, reviewer)
            if any(value is not None for value in recovery_args) and not all(value is not None for value in recovery_args):
                raise MilestoneFailure("checkpoint recovery requires manifest digest and human disposition")
            self._require_clean_worktree("milestone head rebind")
            if all(value is not None for value in recovery_args):
                if (not isinstance(checkpoint_manifest_sha256, str)
                        or SHA256.fullmatch(checkpoint_manifest_sha256) is None
                        or not isinstance(human_disposition, str) or not human_disposition.strip()
                        or len(human_disposition) > 240
                        or any(ord(char) < 32 or ord(char) == 127 for char in human_disposition)
                        or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 80
                        or any(ord(char) < 32 or ord(char) == 127 for char in reviewer)):
                    raise MilestoneFailure("checkpoint recovery invocation is invalid")
                if (stored["status"] != "REVIEW_READY"
                        or stored["next"] != {"action": "request_merge", "human_boundary": True}
                        or repository["branch"] != stored["repository"]["branch"]
                        or repository["base_sha"] != stored["repository"]["base_sha"]
                        or repository["head_sha"] == stored["repository"]["head_sha"]
                        or not events or events[-1]["event_type"] != "checkpoint_artifacts_registered"
                        or events[-1]["data"]["manifest_sha256"] != checkpoint_manifest_sha256):
                    raise MilestoneFailure("checkpoint recovery is unauthorized or registration is stale")
                registration = events[-1]
                old_head = stored["repository"]["head_sha"]
                data = {"recovery_kind": "review_ready_checkpoint_artifacts",
                        "registration_event_sha256": registration["event_sha256"],
                        "rebound_from_head": old_head, "new_head": repository["head_sha"],
                        "old_change_identity": stored["repository"]["change_identity"],
                        "change_identity": repository["change_identity"],
                        "manifest_path": registration["data"]["manifest_path"],
                        "manifest_sha256": checkpoint_manifest_sha256,
                        "receipt_snapshot_sha256": registration["data"]["receipt_snapshot_sha256"],
                        "human_disposition": human_disposition, "reviewer": reviewer,
                        "expected_generation": expected_generation,
                        "prior_history_tail_sha256": events[-1]["event_sha256"],
                        "ancestry_proof": "prior_bound_head_is_ancestor_of_new_head",
                        "base_sha": stored["repository"]["base_sha"],
                        "branch": stored["repository"]["branch"],
                        "resulting_state": {"status": "CI_PENDING", "next_action": "ingest_ci",
                                            "ci_status": "not_observed", "ci_head_sha": None}}
                event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                         "milestone_id": milestone_id, "sequence": len(events) + 1,
                         "event_type": "identity_rebound", "prior_event_sha256": events[-1]["event_sha256"],
                         "subject_head_sha": repository["head_sha"], "summary": summary,
                         "data": data, "authority": dict(AUTHORITY)}
                event["event_sha256"] = _digest(event); self._validate(event)
                self._verify_checkpoint_recovery(events + [event], len(events), old_head,
                                                 stored["repository"]["change_identity"], data)
                if (len(events) >= self.policy["limits"]["max_events"]
                        or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]):
                    raise MilestoneFailure("checkpoint recovery event exceeded its bound")
                # This final identity/worktree/history check is the linearization point.
                current_events = self._read_events(milestone_id)
                current_repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(current_events))
                current_state = _read_json(state_path)
                self._require_clean_worktree("checkpoint recovery")
                if (len(current_events) != len(events)
                        or current_events[-1]["event_sha256"] != events[-1]["event_sha256"]
                        or _digest(current_state) != _digest(stored)
                        or current_repository["branch"] != repository["branch"]
                        or current_repository["base_sha"] != repository["base_sha"]
                        or current_repository["head_sha"] != repository["head_sha"]
                        or current_repository["change_identity"] != repository["change_identity"]):
                    raise MilestoneFailure("checkpoint recovery repository identity changed during verification")
                with history.open("ab") as stream:
                    stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
                state = self._project(events + [event], current_repository)
                self._atomic_json(state_path, state); self._write_pointer(state)
                return self.load(milestone_id)
            if (stored["status"] != "CI_PENDING"
                    or stored["next"]["action"] != "ingest_ci"
                    or repository["branch"] != stored["repository"]["branch"]
                    or repository["base_sha"] != stored["repository"]["base_sha"]
                    or repository["head_sha"] == stored["repository"]["head_sha"]):
                raise MilestoneFailure("milestone head rebind is unauthorized")
            identity_matches = repository["change_identity"] == stored["repository"]["change_identity"]
            if not identity_matches:
                if reviewed_head is None or validation_evidence is None:
                    raise MilestoneFailure("milestone head rebind is unauthorized")
                if SHA1.fullmatch(reviewed_head) is None or not validation_evidence.is_file():
                    raise MilestoneFailure("milestone identity reconciliation is unauthorized")
                evidence = _read_json(validation_evidence, 65_536)
                if (_digest(evidence) != stored["validation"]["evidence_sha256"]
                        or evidence.get("repository", {}).get("base_sha") != stored["repository"]["base_sha"]
                        or evidence.get("repository", {}).get("branch") != stored["repository"]["branch"]
                        or evidence.get("repository", {}).get("head_sha") != stored["repository"]["head_sha"]):
                    raise MilestoneFailure("milestone identity reconciliation is unauthorized")
                old_head = stored["repository"]["head_sha"]
                if any(subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant],
                                      cwd=self.root, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, check=False).returncode != 0
                       for ancestor, descendant in ((old_head, reviewed_head), (reviewed_head, repository["head_sha"]))):
                    raise MilestoneFailure("milestone identity reconciliation is unauthorized")
                repair_paths = [path.decode("utf-8") for path in self._run(
                    ["git", "diff", "--name-only", "-z", reviewed_head, repository["head_sha"], "--"],
                    1_048_576).split(b"\0") if path]
                if sorted(set(repair_paths)) != list(IDENTITY_REPAIR_PATHS):
                    raise MilestoneFailure("milestone identity reconciliation repair boundary is unauthorized")
                committed_paths = self._run(
                    ["git", "diff", "--name-only", "-z", stored["repository"]["base_sha"], reviewed_head, "--"],
                    1_048_576).split(b"\0")
                committed_paths = sorted(set(path.decode("utf-8") for path in committed_paths if path))
                added_paths = set(path.decode("utf-8") for path in self._run(
                    ["git", "diff", "--diff-filter=A", "--name-only", "-z", stored["repository"]["base_sha"], reviewed_head, "--"],
                    1_048_576).split(b"\0") if path)
                tracked_paths = [path for path in committed_paths if path not in added_paths]
                patch = self._run(["git", "diff", "--binary", stored["repository"]["base_sha"], reviewed_head, "--", *tracked_paths], 16 * 1024 * 1024) if tracked_paths else b""
                manifest = []
                for path in sorted(added_paths):
                    content = self._run(["git", "show", f"{reviewed_head}:{path}"], 16 * 1024 * 1024)
                    mode = self._run(["git", "ls-tree", "-r", reviewed_head, "--", path], 4096).decode("utf-8").split(" ", 1)[0]
                    manifest.append({"path": path, "mode": f"{int(mode, 8) & 0o777:04o}",
                                     "sha256": hashlib.sha256(content).hexdigest()})
                legacy_agent_identity = hashlib.sha256(
                    b"vss-agent-change-v1\0" + hashlib.sha256(patch).digest()
                    + _canonical({"untracked": manifest})).hexdigest()
                if evidence.get("change_identity") != legacy_agent_identity:
                    raise MilestoneFailure("milestone identity reconciliation is unauthorized")
                legacy_controller_identity = _digest({
                    "base": stored["repository"]["base_sha"], "paths": committed_paths,
                    "diff_sha256": hashlib.sha256(patch).hexdigest()})
                if legacy_controller_identity != stored["repository"]["change_identity"]:
                    raise MilestoneFailure("milestone identity reconciliation is unauthorized")
            if subprocess.run(["git", "merge-base", "--is-ancestor", stored["repository"]["head_sha"], repository["head_sha"]],
                              cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode != 0:
                raise MilestoneFailure("milestone head rebind is unauthorized")
            data = {"rebound_from_head": stored["repository"]["head_sha"],
                    "change_identity": repository["change_identity"],
                    "validation_invalidated": not identity_matches}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "identity_rebound", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary,
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            if len(events) >= self.policy["limits"]["max_events"] or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("milestone event exceeded its bound")
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state = self._project(events + [event], repository)
            self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def bootstrap_controller_upgrade(self, milestone_id: str, base_head: str, old_head: str, reviewed_head: str,
                                     target_head: str,
                                     reason: str, expected_generation: int) -> dict[str, Any]:
        """Perform the one-time exact controller-upgrade transition for the accepted milestone."""
        if (milestone_id != BOOTSTRAP_MILESTONE or SHA1.fullmatch(base_head) is None
                or SHA1.fullmatch(old_head) is None
                or SHA1.fullmatch(reviewed_head) is None
                or SHA1.fullmatch(target_head) is None or not reason or len(reason) > 512
                or type(expected_generation) is not int):
            raise MilestoneFailure("controller bootstrap is invalid")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            stored = _read_json(state_path); self._validate(stored)
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            if any(event["event_type"] == "controller_bootstrap" for event in events):
                raise MilestoneFailure("controller bootstrap already recorded")
            if stored["repository"]["base_sha"] != base_head or stored["repository"]["head_sha"] != old_head or stored["status"] != "CI_PENDING" \
                    or stored["next"]["action"] != "ingest_ci":
                raise MilestoneFailure("controller bootstrap is unauthorized")
            try:
                repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            except MilestoneFailure as exc:
                raise MilestoneFailure("controller bootstrap is unauthorized") from exc
            if (repository["branch"] != f"feature/{BOOTSTRAP_MILESTONE}"
                    or repository["base_sha"] != stored["repository"]["base_sha"]
                    or repository["head_sha"] != target_head
                    or target_head == old_head):
                raise MilestoneFailure("controller bootstrap is unauthorized")
            status = self._run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], 1_048_576)
            entries = [entry for entry in status.split(b"\0") if entry]
            if any(len(entry) < 4 or entry[2:3] != b" " or entry[3:].decode("utf-8") != PROTECTED_RESIDUE
                   for entry in entries):
                raise MilestoneFailure("controller bootstrap requires a clean worktree")
            if any(subprocess.run(["git", "merge-base", "--is-ancestor", source, target],
                                  cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode != 0
                   for source, target in ((old_head, target_head), (old_head, reviewed_head), (reviewed_head, target_head))):
                raise MilestoneFailure("controller bootstrap is unauthorized")
            names = [path.decode("utf-8") for path in self._run(
                ["git", "diff", "--name-only", "-z", reviewed_head, target_head, "--"], 1_048_576).split(b"\0") if path]
            if sorted(set(names)) != list(BOOTSTRAP_REPAIR_PATHS):
                raise MilestoneFailure("controller bootstrap repair boundary is unauthorized")
            repair_diff = self._run(["git", "diff", "--binary", reviewed_head, target_head, "--", *BOOTSTRAP_REPAIR_PATHS], 16 * 1024 * 1024)
            if not repair_diff:
                raise MilestoneFailure("controller bootstrap repair is empty")
            repair_digest = hashlib.sha256(repair_diff).hexdigest()
            reviewed_identity = self._committed_change_identity(
                stored["repository"]["base_sha"], reviewed_head)
            if reviewed_identity != stored["repository"]["change_identity"]:
                raise MilestoneFailure("controller bootstrap reviewed identity changed")
            previous_controller_identity = self._controller_identity(reviewed_head, BOOTSTRAP_REPAIR_PATHS, hashlib.sha256(b"").hexdigest())
            new_controller_identity = self._controller_identity(target_head, BOOTSTRAP_REPAIR_PATHS, repair_digest)
            resulting_state = {"status": "CI_PENDING", "next_action": "ingest_ci",
                               "ci_status": "not_observed", "ci_head_sha": None}
            data = {"previous_controller_identity": previous_controller_identity,
                    "new_controller_identity": new_controller_identity, "old_head": old_head,
                    "reviewed_head": reviewed_head,
                    "new_head": target_head, "repair_paths": list(BOOTSTRAP_REPAIR_PATHS),
                    "repair_change_sha256": repair_digest, "reviewed_change_identity": reviewed_identity,
                    "change_identity": repository["change_identity"],
                    "reason": reason, "expected_generation": expected_generation,
                    "resulting_state": resulting_state}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "controller_bootstrap", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": target_head, "summary": reason, "data": data,
                     "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            if len(events) >= self.policy["limits"]["max_events"] or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("milestone event exceeded its bound")
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state_repository = dict(repository)
            state = self._project(events + [event], state_repository)
            self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def checkpoint(self, milestone_id: str | None, event_type: str, summary: str, data: dict[str, Any] | None = None,
                   expected_generation: int | None = None) -> dict[str, Any]:
        state = self.load(milestone_id); milestone_id = state["milestone_id"]
        if event_type not in {"mission_assessed", "mission_reviewed", "checkpointed", "repair_started", "repair_completed", "blocked", "completed"} or not summary or len(summary) > 512:
            raise MilestoneFailure("milestone checkpoint is invalid")
        if (state["mission_gate"]["outcome"] != "PROCEED"
                and event_type in {"repair_started", "repair_completed", "completed"}):
            raise MilestoneFailure("mission review is required before implementation or completion")
        if event_type in {"mission_assessed", "mission_reviewed"}:
            if expected_generation is None or state["status"] == "CONFLICT":
                raise MilestoneFailure("mission checkpoint requires current generation and repository identity")
        if expected_generation is not None and expected_generation != state["generation"]:
            raise MilestoneFailure("milestone writer conflict")
        if event_type == "repair_started":
            attempts = state["repair"]["attempts"] + 1
            if attempts > self.policy["limits"]["max_repair_attempts"]: raise MilestoneFailure("repair budget exhausted")
            self._repair_paths(state)
            data = {"repair_attempts": attempts}
        elif event_type == "blocked":
            data = {"stop_reason": (data or {}).get("stop_reason", "manual-review")}
        else: data = data or {}
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            if len(events) - 1 != state["generation"]: raise MilestoneFailure("milestone writer conflict")
            repository = self._repository(events[0]["subject_head_sha"], self._residue_from_events(events))
            if state["status"] == "CONFLICT" or repository["head_sha"] != state["repository"]["head_sha"]:
                raise MilestoneFailure("milestone source identity conflict")
            stored = _read_json(state_path)
            if expected_generation is not None and stored["generation"] != expected_generation:
                raise MilestoneFailure("milestone writer conflict")
            if (event_type not in {"mission_assessed", "mission_reviewed"}
                    and repository["change_identity"] != stored["repository"]["change_identity"]):
                raise MilestoneFailure("governed source identity requires validation")
            if event_type in {"mission_assessed", "mission_reviewed"} and repository != state["repository"]:
                raise MilestoneFailure("mission checkpoint repository identity changed")
            data = {**data, "change_identity": repository["change_identity"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event", "milestone_id": milestone_id,
                     "sequence": len(events) + 1, "event_type": event_type, "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary, "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            state = self._project(events + [event], repository)
            if (len(events) >= self.policy["limits"]["max_events"]
                    or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]):
                raise MilestoneFailure("milestone event exceeded its bound")
            with history.open("ab") as stream: stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            self._atomic_json(state_path, state); self._write_pointer(state)
            return state

    def _validation_current(self, events: list[dict[str, Any]], repository: dict[str, str],
                            map_sha256: str | None = None) -> dict[str, Any] | None:
        index = next((i for i in range(len(events) - 1, 0, -1)
                      if events[i]["event_type"] == "validation_completed"), None)
        if index is None:
            return None
        event = events[index]
        data = event["data"]
        if (data.get("evidence_binding_version") != 1
                or data.get("residue_provenance_sha256") != self._residue_digest(self._residue_from_events(events))
                or data.get("controller_policy_sha256") != self.policy_digest
                or (map_sha256 is not None and data.get("validation_map_sha256") != map_sha256)):
            return None
        identity = data["governed_change_identity"]
        equivalent = identity == repository["change_identity"]
        if not equivalent:
            prior_recovery = next((later for later in reversed(events[:index])
                                   if later["event_type"] == "identity_rebound"), None)
            equivalent = bool(prior_recovery
                              and prior_recovery["data"].get("recovery_kind") == "review_ready_checkpoint_artifacts"
                              and prior_recovery["data"].get("old_change_identity") == identity)
        for later in events[index + 1:]:
            if later["event_type"] == "validation_invalidated":
                return None
            if later["event_type"] == "identity_rebound":
                rebound = later["data"]
                if (rebound.get("recovery_kind") == "review_ready_checkpoint_artifacts"
                        and rebound.get("old_change_identity") == identity
                        and rebound.get("residue_provenance_sha256", data["residue_provenance_sha256"])
                        == data["residue_provenance_sha256"]
                        and rebound.get("change_identity") == repository["change_identity"]):
                    equivalent = True
                elif (rebound.get("change_identity") == identity
                      and identity == repository["change_identity"]):
                    equivalent = True
                else:
                    return None
            elif later["event_type"] in {"controller_bootstrap", "identity_reconciled"}:
                if later["data"].get("change_identity") != identity:
                    return None
        if not equivalent:
            return None
        return data

    def _append_validation(self, milestone_id: str, summary: str, expected_generation: int,
                           repository_snapshot: dict[str, str], evidence: dict[str, Any],
                           evidence_sha256: str, level: str) -> dict[str, Any]:
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            stored = _read_json(state_path); self._validate(stored)
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            if (repository != repository_snapshot or repository["branch"] != stored["repository"]["branch"]
                    or repository["base_sha"] != stored["repository"]["base_sha"]
                    or stored["status"] == "CONFLICT"):
                raise MilestoneFailure("validation source identity changed during validation")
            residue_digest = self._residue_digest(self._residue_from_events(events))
            binding = evidence.get("milestone_binding")
            if (type(binding) is not dict or binding.get("version") != 1
                    or binding.get("governed_change_identity") != repository["change_identity"]
                    or binding.get("residue_provenance_sha256") != residue_digest
                    or evidence.get("repository") != {
                        "name_with_owner": repository["name_with_owner"], "branch": repository["branch"],
                        "base_sha": repository["base_sha"], "head_sha": evidence.get("repository", {}).get("head_sha")}
                    or evidence.get("repository", {}).get("head_sha") != repository["head_sha"]
                    or evidence.get("passed") is not True or evidence.get("plan", {}).get("executed_level") != level
                    or not SHA256.fullmatch(evidence_sha256)):
                raise MilestoneFailure("validation evidence does not match governed source identity")
            data = {"validation_level": level, "evidence_sha256": evidence_sha256,
                    "change_identity": repository["change_identity"],
                    "evidence_binding_version": 1,
                    "governed_change_identity": repository["change_identity"],
                    "residue_provenance_sha256": residue_digest,
                    "validation_subject_head_sha": evidence["repository"]["head_sha"],
                    "validation_map_sha256": evidence["map"]["sha256"],
                    "controller_policy_sha256": self.policy_digest}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "validation_completed", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary,
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            if len(events) >= self.policy["limits"]["max_events"] or len(_canonical(event)) > self.policy["limits"]["max_event_bytes"]:
                raise MilestoneFailure("validation evidence event exceeded its bound")
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state = self._project(events + [event], repository)
            self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def _append_legacy_validation_quarantine(self, state: dict[str, Any],
                                             validation_event: dict[str, Any]) -> dict[str, Any]:
        directory, state_path, history = self._paths(state["milestone_id"])
        with self._locked(directory):
            events = self._read_events(state["milestone_id"])
            stored = _read_json(state_path); self._validate(stored)
            repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            if (state["generation"] != stored["generation"]
                    or _digest(repository) != _digest(state["repository"])
                    or stored["status"] == "CONFLICT"
                    or not events or events[-1]["event_sha256"] != state["history_tail"]["sha256"]
                    or validation_event not in events
                    or validation_event["data"].get("evidence_binding_version") == 1):
                raise MilestoneFailure("legacy validation quarantine is stale")
            if any(event["event_type"] == "validation_invalidated"
                   and event["data"].get("recovered_event_sha256") == validation_event["event_sha256"]
                   for event in events):
                return self.load(state["milestone_id"])
            data = {"legacy_quarantine": True,
                    "recovered_event_sha256": validation_event["event_sha256"],
                    "prior_history_tail_sha256": events[-1]["event_sha256"],
                    "change_identity": repository["change_identity"],
                    "residue_provenance_sha256": self._residue_digest(self._residue_from_events(events)),
                    "expected_generation": stored["generation"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": state["milestone_id"], "sequence": len(events) + 1,
                     "event_type": "validation_invalidated", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"],
                     "summary": "Unbound legacy validation evidence quarantined before current validation.",
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            current_events = self._read_events(state["milestone_id"])
            current_state = _read_json(state_path)
            current_repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(current_events))
            if (len(current_events) != len(events)
                    or current_events[-1]["event_sha256"] != events[-1]["event_sha256"]
                    or _digest(current_state) != _digest(stored)
                    or current_repository != repository):
                raise MilestoneFailure("legacy validation quarantine changed during verification")
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            projected = self._project(events + [event], repository)
            self._atomic_json(state_path, projected); self._write_pointer(projected)
        return self.load(state["milestone_id"])

    def _append_validation_reuse(self, milestone_id: str, expected_generation: int,
                                 repository_snapshot: dict[str, str], binding: dict[str, Any]) -> dict[str, Any]:
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id); stored = _read_json(state_path)
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            impact = json.loads(self._run(["scripts/vss-agent", "impact", "--base",
                                           stored["repository"]["base_sha"]], 65536))
            current = self._validation_current(events, repository, impact.get("map_sha256"))
            if (repository != repository_snapshot or current != binding
                    or stored["status"] == "CONFLICT"):
                raise MilestoneFailure("validation receipt is stale")
            data = {"validation_level": binding["validation_level"],
                    "evidence_sha256": binding["evidence_sha256"],
                    "change_identity": repository["change_identity"],
                    "evidence_binding_version": 1,
                    "governed_change_identity": binding["governed_change_identity"],
                    "residue_provenance_sha256": binding["residue_provenance_sha256"],
                    "validation_subject_head_sha": binding["validation_subject_head_sha"],
                    "validation_map_sha256": binding["validation_map_sha256"],
                    "controller_policy_sha256": binding["controller_policy_sha256"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": milestone_id, "sequence": len(events) + 1,
                     "event_type": "validation_completed", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": "canonical validation evidence reused.",
                     "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state = self._project(events + [event], repository)
            self._atomic_json(state_path, state); self._write_pointer(state)
        return self.load(milestone_id)

    def validate(self, tier: str, milestone_id: str | None = None) -> dict[str, Any]:
        state = self.load(milestone_id)
        if tier not in {"affected", "subsystem", "canonical"}: raise MilestoneFailure("validation tier is invalid")
        if state["status"] == "CONFLICT":
            raise MilestoneFailure("validation source identity conflict")
        requested = {"affected": "L1", "subsystem": "L2", "canonical": "L3"}[tier]
        impact = json.loads(self._run(["scripts/vss-agent", "impact", "--base", state["repository"]["base_sha"]], 65536))
        required = impact["minimum_level"]
        level = requested if LEVELS[requested] >= LEVELS[required] else required
        events = self._read_events(state["milestone_id"])
        last_validation = next(((index, event) for index, event in reversed(list(enumerate(events)))
                                if event["event_type"] == "validation_completed"), None)
        if last_validation is not None:
            validation_index, validation_event = last_validation
            if (validation_event["data"].get("evidence_binding_version") != 1
                    and not any(event["event_type"] == "validation_invalidated"
                                and event["data"].get("recovered_event_sha256") == validation_event["event_sha256"]
                                for event in events[validation_index + 1:])
                    and not any(event["event_type"] == "issue160_legacy_state_recovered"
                                for event in events[validation_index + 1:])):
                state = self._append_legacy_validation_quarantine(state, validation_event)
                events = self._read_events(state["milestone_id"])
        prior_binding = self._validation_current(events, state["repository"], impact.get("map_sha256"))
        if (prior_binding is not None
                and LEVELS.get(prior_binding.get("validation_level", "none"), -1) >= LEVELS[level]
                and prior_binding.get("evidence_sha256")):
            if tier == "canonical" and state["next"]["action"] == "run_canonical_validation":
                self._append_validation_reuse(state["milestone_id"], state["generation"],
                                               state["repository"], prior_binding)
            return {"status": "reused", "level": prior_binding["validation_level"],
                    "evidence_sha256": prior_binding["evidence_sha256"]}
        evidence = Path(tempfile.gettempdir()) / f"vss-dev-{state['milestone_id']}-evidence.json"
        residue_digest = self._residue_digest(self._residue_from_events(events))
        with tempfile.TemporaryDirectory(prefix="vss-milestone-baseline-") as directory:
            baseline = Path(directory) / "base-secrets.baseline"
            try:
                baseline.write_bytes(self._run(["git", "show", f"{state['repository']['base_sha']}:{BASELINE_RESIDUE}"], 4 * 1024 * 1024))
            except MilestoneFailure as exc:
                raise MilestoneFailure("bound base-HEAD secrets baseline is unavailable") from exc
            environment = os.environ.copy()
            environment["VSS_VALIDATION_SECRETS_BASELINE"] = str(baseline)
            environment["VSS_VALIDATION_BASE_SHA"] = state["repository"]["base_sha"]
            command = ["scripts/vss-agent", "validate-change", "--base", state["repository"]["base_sha"],
                       "--level", level, "--output", str(evidence),
                       "--governed-change-identity", state["repository"]["change_identity"],
                       "--residue-provenance-sha256", residue_digest]
            self._run(command, 65536, environment)
        proof = _read_json(evidence, 16384); evidence_digest = _digest(proof)
        result = self._append_validation(state["milestone_id"], f"{tier} validation passed.",
                                         state["generation"], state["repository"], proof,
                                         evidence_digest, level)
        return {"status": "passed", "level": level, "evidence_sha256": evidence_digest,
                "milestone_status": result["status"]}

    def ingest_ci(self, document: dict[str, Any], milestone_id: str | None = None) -> dict[str, Any]:
        raise MilestoneFailure("caller-supplied CI observations are not admissible; use API refresh")

    def _ci_api(self, endpoint: str) -> dict[str, Any]:
        return _read_external_json(self._run(["gh", "api", endpoint], 1_048_576))

    def _fetch_ci_observation(self, state: dict[str, Any]) -> dict[str, Any]:
        repository = state["repository"]
        head = repository["head_sha"]
        local_blob = self._line(["git", "rev-parse", f"{head}:{CI_WORKFLOW_PATH}"])
        if local_blob != CI_WORKFLOW_BLOB:
            raise MilestoneFailure("CI workflow differs from the admitted workflow identity")
        workflow = self._ci_api(f"repos/{repository['name_with_owner']}/actions/workflows/ci.yml")
        workflow_id = workflow.get("id")
        if (type(workflow_id) is not int or workflow_id < 1
                or workflow.get("path") != CI_WORKFLOW_PATH or workflow.get("state") != "active"):
            raise MilestoneFailure("GitHub CI workflow identity is unavailable or ambiguous")
        runs_value = self._ci_api(
            f"repos/{repository['name_with_owner']}/actions/workflows/{workflow_id}/runs?head_sha={head}"
            f"&branch={repository['branch']}&event=pull_request&per_page=100")
        runs = runs_value.get("workflow_runs")
        if (type(runs) is not list or type(runs_value.get("total_count")) is not int
                or runs_value["total_count"] != len(runs)):
            raise MilestoneFailure("GitHub CI workflow run inventory is malformed or incomplete")
        matching = [run for run in runs if type(run) is dict and run.get("head_sha") == head
                    and run.get("workflow_id") == workflow_id
                    and run.get("head_branch") == repository["branch"]
                    and run.get("event") == "pull_request"]
        if len(matching) != 1:
            raise MilestoneFailure("GitHub CI run for exact HEAD is missing or ambiguous")
        run = matching[0]
        run_id = run.get("id"); attempt = run.get("run_attempt")
        if (type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1
                or run.get("path") != CI_WORKFLOW_PATH):
            raise MilestoneFailure("GitHub CI run identity is malformed")
        jobs_value = self._ci_api(
            f"repos/{repository['name_with_owner']}/actions/runs/{run_id}/jobs?filter=latest&per_page=100")
        jobs = jobs_value.get("jobs")
        if type(jobs) is not list or jobs_value.get("total_count") != len(jobs):
            raise MilestoneFailure("GitHub CI job inventory is incomplete")
        normalized_jobs = []
        for job in jobs:
            if type(job) is not dict:
                raise MilestoneFailure("GitHub CI job is malformed")
            normalized_jobs.append({"name": job.get("name"), "status": job.get("status"),
                                    "conclusion": job.get("conclusion") or "", "head_sha": job.get("head_sha")})
        return {"repository": repository["name_with_owner"], "head_sha": head,
                "workflow_id": workflow_id, "workflow_path": CI_WORKFLOW_PATH,
                "workflow_blob": local_blob, "run_id": run_id, "run_attempt": attempt,
                "run_status": run.get("status"), "run_conclusion": run.get("conclusion") or "",
                "jobs": normalized_jobs}

    def _append_ci_observation(self, state: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        repository_snapshot = state["repository"]
        evidence = {key: observation[key] for key in (
            "repository", "head_sha", "workflow_id", "workflow_path", "workflow_blob",
            "run_id", "run_attempt", "run_status", "run_conclusion", "jobs")}
        if (evidence["repository"] != repository_snapshot["name_with_owner"]
                or evidence["head_sha"] != repository_snapshot["head_sha"]
                or evidence["workflow_path"] != CI_WORKFLOW_PATH
                or evidence["workflow_blob"] != CI_WORKFLOW_BLOB
                or type(evidence["workflow_id"]) is not int or evidence["workflow_id"] < 1
                or type(evidence["run_id"]) is not int or evidence["run_id"] < 1
                or type(evidence["run_attempt"]) is not int or evidence["run_attempt"] < 1
                or evidence["run_status"] not in {"completed", "in_progress", "queued", "requested"}
                or evidence["run_conclusion"] not in {"success", "failure", "cancelled", "timed_out", "action_required", ""}):
            raise MilestoneFailure("CI observation is not for the exact admitted source")
        jobs = evidence["jobs"]
        if (type(jobs) is not list or len(jobs) != len(CI_REQUIRED_CHECKS)
                or any(type(item) is not dict or set(item) != {"name", "status", "conclusion", "head_sha"}
                       for item in jobs)
                or any(type(item["name"]) is not str for item in jobs)
                or sorted(item["name"] for item in jobs) != sorted(CI_REQUIRED_CHECKS)
                or len({item["name"] for item in jobs}) != len(CI_REQUIRED_CHECKS)
                or any(item["head_sha"] != repository_snapshot["head_sha"] for item in jobs)):
            raise MilestoneFailure("CI check set is empty, partial, duplicate, or bound to another SHA")
        pending = evidence["run_status"] != "completed" or any(item["status"] != "completed" for item in jobs)
        passed = (not pending and evidence["run_conclusion"] == "success"
                  and all(item["conclusion"] == "success" for item in jobs))
        if pending:
            ci_status = "pending"
        elif passed:
            ci_status = "passed"
        else:
            ci_status = "failed"
        failed_names = [item["name"] for item in jobs if item["conclusion"] not in {"success", ""}]
        classification = "none"
        if ci_status == "failed":
            classification = "security" if "Scan for secrets" in failed_names else "code"
        evidence_digest = _digest(evidence)
        data = {"ci_status": ci_status, "ci_classification": classification,
                "ci_head_sha": repository_snapshot["head_sha"], "ci_evidence_version": 1,
                "governed_change_identity": repository_snapshot["change_identity"],
                "residue_provenance_sha256": self._residue_digest(
                    self._residue_from_events(self._read_events(state["milestone_id"]))),
                "source_head_sha": repository_snapshot["head_sha"],
                "ci_evidence": {"head_sha": evidence["head_sha"], "workflow_path": evidence["workflow_path"],
                                "repository": evidence["repository"], "workflow_id": evidence["workflow_id"],
                                "workflow_blob": evidence["workflow_blob"],
                                "inventory_sha256": CI_CHECK_INVENTORY_SHA256,
                                "run_id": evidence["run_id"], "run_attempt": evidence["run_attempt"],
                                "run_status": evidence["run_status"], "run_conclusion": evidence["run_conclusion"],
                                "jobs": evidence["jobs"], "observation_sha256": evidence_digest}}
        directory, state_path, history = self._paths(state["milestone_id"])
        with self._locked(directory):
            events = self._read_events(state["milestone_id"])
            stored = _read_json(state_path); self._validate(stored)
            if state["generation"] != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            self._require_clean_worktree("CI observation")
            repository = self._repository(stored["repository"]["base_sha"], self._residue_from_events(events))
            if (stored["status"] != "CI_PENDING" or stored["next"].get("action") != "ingest_ci"
                    or repository != repository_snapshot
                    or repository["head_sha"] != evidence["head_sha"]):
                raise MilestoneFailure("CI observation source identity or state changed")
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event",
                     "milestone_id": state["milestone_id"], "sequence": len(events) + 1,
                     "event_type": "ci_observed", "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": "Exact-HEAD CI API observation recorded.",
                     "data": {**data, "change_identity": repository["change_identity"]},
                     "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            with history.open("ab") as stream:
                stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            projected = self._project(events + [event], repository)
            self._atomic_json(state_path, projected); self._write_pointer(projected)
        return {"status": ci_status, "classification": classification, "head_sha": repository_snapshot["head_sha"],
                "observation_sha256": evidence_digest}

    def ci_refresh(self, milestone_id: str | None = None) -> dict[str, Any]:
        state = self.load(milestone_id)
        if state["status"] == "CONFLICT":
            raise MilestoneFailure("CI cannot reconcile a source identity conflict")
        if state["status"] != "CI_PENDING" or state["next"].get("action") != "ingest_ci":
            raise MilestoneFailure("CI observation is not legal in the current milestone state")
        self._require_clean_worktree("CI observation")
        current = self._repository(state["repository"]["base_sha"],
                                   self._residue_from_events(self._read_events(state["milestone_id"])))
        if current != state["repository"]:
            raise MilestoneFailure("CI observation requires exact bound HEAD and change identity")
        observation = self._fetch_ci_observation(state)
        return self._append_ci_observation(state, observation)

    def analyze(self, milestone_id: str | None = None) -> dict[str, Any]:
        """Derive bounded, advisory findings from the existing milestone history."""
        state = self.load(milestone_id)
        events = self._read_events(state["milestone_id"])
        counts = {kind: sum(event["event_type"] == kind for event in events)
                  for kind in ("validation_completed", "ci_observed", "repair_started", "checkpointed")}
        ci_failures = sum(event["data"].get("ci_status") == "failed" for event in events if event["event_type"] == "ci_observed")
        findings: list[dict[str, str]] = []
        if ci_failures and counts["validation_completed"]:
            findings.append({"finding": "local-green-ci-failure-loop", "recommendation": "run-affected-validation"})
        if counts["repair_started"] > 1:
            findings.append({"finding": "human-relay", "recommendation": "inspect-environment"})
        findings.sort(key=lambda item: item["finding"])
        return {"schema_version": "1", "protocol": "vss.dev-analysis", "milestone_id": state["milestone_id"],
                "counts": counts, "findings": findings,
                "unknown_opportunities": [], "authority": dict(AUTHORITY)}

    def backlog_admit(self, milestone_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
        """Materialize one existing checkpoint observation as an advisory candidate."""
        state = self.load(milestone_id)
        observation_id = candidate.get("source_observation_id")
        if type(observation_id) is not str:
            raise MilestoneFailure("candidate source observation is required")
        observation = None
        for event in self._read_events(state["milestone_id"]):
            value = event["data"].get("observation")
            if value and value.get("id") == observation_id:
                observation = value
        if observation is None:
            raise MilestoneFailure("candidate source observation is not in milestone history")
        finding = candidate.get("finding")
        if finding != observation["finding"]:
            raise MilestoneFailure("candidate finding does not match source observation")
        payload = {key: value for key, value in candidate.items()
                   if key not in {"source_observation_id", "finding"}}
        payload["source"] = {"milestone_id": state["milestone_id"],
                              "observation_id": observation_id, "finding": finding}
        payload["evidence"] = [{"reference": f"milestone:{state['milestone_id']}:observation:{observation_id}",
                                 "digest": observation["evidence_sha256"]}]
        try:
            return ImprovementBacklog(self.root).admit(payload)
        except ImprovementBacklogFailure as exc:
            raise MilestoneFailure(str(exc)) from exc

    def backlog_report(self, milestone_id: str | None = None) -> dict[str, Any]:
        state = self.load(milestone_id)
        try:
            return ImprovementBacklog(self.root).due(state["milestone_id"])
        except ImprovementBacklogFailure as exc:
            raise MilestoneFailure(str(exc)) from exc


def _read_external_json(raw: bytes) -> dict[str, Any]:
    try: value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc: raise MilestoneFailure("GitHub CI response is malformed") from exc
    if type(value) is not dict: raise MilestoneFailure("GitHub CI response is malformed")
    return value
