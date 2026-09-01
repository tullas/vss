from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator


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
LEVELS = {"none": -1, "L0": 0, "L1": 1, "L2": 2, "L3": 3}
MAX_PACKET_BYTES = 16_384
MAX_PACKET_PATHS = 64


class MilestoneFailure(Exception):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


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

    def _run(self, argv: list[str], maximum: int = 1_048_576) -> bytes:
        try:
            result = subprocess.run(argv, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
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

    def _repository(self, base: str | None = None) -> dict[str, str]:
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
                "change_identity": self._change_identity(base_value)}

    def _change_identity(self, base: str) -> str:
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
            if path.startswith(".local/") or re.search(r"(?i)(secret|credential|token|api[_-]?key|private[_-]?key)", path):
                raise MilestoneFailure("unexpected sensitive changed path")
            paths.append(path)
        diff = self._run(["git", "diff", "--binary", base, "--"], 16 * 1024 * 1024)
        return hashlib.sha256(_canonical({"base": base, "paths": sorted(set(paths)), "diff_sha256": hashlib.sha256(diff).hexdigest()})).hexdigest()

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
            "authority": dict(AUTHORITY),
        }
        if list(Draft202012Validator(self.packet_schema).iter_errors(packet)):
            raise MilestoneFailure("execution packet is malformed")
        if len(_canonical(packet)) > MAX_PACKET_BYTES:
            raise MilestoneFailure("execution packet exceeded its bound")
        if self._repository(state["repository"]["base_sha"]) != state["repository"]:
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

    def _project(self, events: list[dict[str, Any]], repository: dict[str, str]) -> dict[str, Any]:
        first = events[0]
        scope = first["data"]
        if (first["event_type"] != "initialized"
                or set(scope) not in ({"issue", "domains", "paths"},
                                      {"issue", "domains", "paths", "initial_branch", "base_sha",
                                       "change_identity"})
                or type(scope["issue"]) is not int or scope["issue"] < 1
                or type(scope["domains"]) is not list or type(scope["paths"]) is not list):
            raise MilestoneFailure("milestone initialization history is malformed")
        validation = {"evidence_sha256": None, "level": "none"}
        ci = {"head_sha": None, "status": "not_observed", "classification": "none"}
        ci_subject_head: str | None = None
        ci_change_identity: str | None = None
        repair = {"attempts": 0, "stop_reason": None}
        status = "READY_FOR_IMPLEMENTATION"; action = "start_bounded_work"; human = False
        for event in events[1:]:
            data = event["data"]
            if event["event_type"] == "validation_completed":
                validation = {"evidence_sha256": data.get("evidence_sha256"), "level": data.get("validation_level", "none")}
                if (ci["status"] == "passed" and ci["head_sha"] == event["subject_head_sha"]
                        and ci_subject_head == event["subject_head_sha"]
                        and ci_change_identity == data.get("change_identity")):
                    status, action, human = "REVIEW_READY", "request_merge", True
                else:
                    status, action = "CI_PENDING", "ingest_ci"
            elif event["event_type"] == "ci_observed":
                ci = {"head_sha": data.get("ci_head_sha"), "status": data.get("ci_status", "not_observed"), "classification": data.get("ci_classification", "none")}
                ci_subject_head = event["subject_head_sha"]
                ci_change_identity = data.get("change_identity")
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
        self._validate(state); return state

    def _write_pointer(self, state: dict[str, Any]) -> None:
        pointer = {"schema_version": "1", "milestone_id": state["milestone_id"], "state_sha256": _digest(state),
                   "history_tail_sha256": state["history_tail"]["sha256"]}
        self._atomic_json(self.state_root / "current.json", pointer)

    def initialize(self, milestone_id: str, base: str, issue: int, domains: list[str], paths: list[str], summary: str) -> dict[str, Any]:
        directory, state_path, history = self._paths(milestone_id)
        if issue < 1 or not summary or len(summary) > 512 or len(domains) > 16 or len(paths) > 64:
            raise MilestoneFailure("milestone initialization is invalid")
        repository = self._repository(base)
        with self._locked(directory):
            if state_path.exists() or history.exists(): raise MilestoneFailure("milestone already exists")
            data = {"issue": issue, "domains": sorted(set(domains)), "paths": sorted(set(paths)),
                    "initial_branch": repository["branch"], "base_sha": repository["base_sha"],
                    "change_identity": repository["change_identity"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event", "milestone_id": milestone_id,
                     "sequence": 1, "event_type": "initialized", "prior_event_sha256": "0" * 64,
                     "subject_head_sha": repository["head_sha"], "summary": summary, "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            history.write_bytes(_canonical(event) + b"\n")
            state = self._project([event], repository); self._atomic_json(state_path, state); self._write_pointer(state)
            return state

    def _materialized(self, milestone_id: str, events: list[dict[str, Any]],
                      repository: dict[str, str]) -> dict[str, Any]:
        _, state_path, _ = self._paths(milestone_id)
        stored = _read_json(state_path)
        self._validate(stored)
        first = events[0]
        initialization = first["data"]
        transitions = [event for event in events if event["event_type"] == "branch_transitioned"]
        if len(transitions) > 1:
            raise MilestoneFailure("milestone branch transition conflict")
        transition_data = transitions[0]["data"] if transitions else {}
        initial_branch = initialization.get(
            "initial_branch", transition_data.get("from_branch", stored["repository"]["branch"]))
        base_sha = initialization.get("base_sha", first["subject_head_sha"])
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
                if (data.get("recovered_event_sha256") != events[index - 1]["event_sha256"]
                        or "change_identity" in events[index - 1]["data"]):
                    raise MilestoneFailure("milestone state identity recovery conflict")
            if event["event_type"] != "branch_transitioned" and "change_identity" in data:
                bound_head = event["subject_head_sha"]
                bound_change_identity = data["change_identity"]
        historical_repository = {
            "name_with_owner": repository["name_with_owner"], "branch": bound_branch,
            "base_sha": base_sha, "head_sha": bound_head,
            "change_identity": bound_change_identity,
        }
        expected = self._project(events, historical_repository)
        legacy_cycle_state = None
        if expected["status"] == "REVIEW_READY" and expected["next"] == {"action": "request_merge", "human_boundary": True}:
            legacy_cycle_state = {**expected, "status": "CI_PENDING",
                                  "routing": {"model": self.policy["model_routing"]["maintenance"], "advisory": True},
                                  "next": {"action": "ingest_ci", "human_boundary": False}}
        if ((_digest(stored) != _digest(expected)
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
        events = self._read_events(milestone_id); repository = self._repository(events[0]["subject_head_sha"])
        stored = self._materialized(milestone_id, events, repository)
        if used_current_pointer:
            pointer = _read_json(self.state_root / "current.json", 2048)
            persisted = _read_json(self._paths(milestone_id)[1])
            if (pointer["state_sha256"] not in {_digest(stored), _digest(persisted)}
                    or pointer["history_tail_sha256"] != stored["history_tail"]["sha256"]):
                raise MilestoneFailure("milestone pointer conflict")
        if (repository["branch"] != stored["repository"]["branch"]
                or repository["head_sha"] != stored["repository"]["head_sha"]):
            conflict = self._project(events, repository)
            conflict["status"] = "CONFLICT"; conflict["next"] = {"action": "recover_state", "human_boundary": True}
            return conflict
        if repository["change_identity"] != stored["repository"]["change_identity"]:
            partial = self._project(events, repository)
            partial["status"] = "WORKING"; partial["next"] = {"action": "run_affected_validation", "human_boundary": False}
            return partial
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
            repository = self._repository(events[0]["subject_head_sha"])
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

    def recover_state_identity(self, milestone_id: str, summary: str,
                               expected_generation: int) -> dict[str, Any]:
        """Explicitly invalidate one legacy unbound validation tail without rewriting history."""
        if (MILESTONE.fullmatch(milestone_id) is None or not summary or len(summary) > 512
                or type(expected_generation) is not int):
            raise MilestoneFailure("milestone state identity recovery is invalid")
        directory, state_path, history = self._paths(milestone_id)
        with self._locked(directory):
            events = self._read_events(milestone_id)
            repository = self._repository(events[0]["subject_head_sha"])
            stored = _read_json(state_path); self._validate(stored)
            tail = events[-1]
            transitions = [event for event in events if event["event_type"] == "branch_transitioned"]
            if expected_generation != stored["generation"]:
                raise MilestoneFailure("milestone writer conflict")
            stored_repository = dict(repository)
            stored_repository["change_identity"] = stored["repository"]["change_identity"]
            repository_identity = {key: value for key, value in repository.items() if key != "change_identity"}
            stored_identity = {key: value for key, value in stored["repository"].items() if key != "change_identity"}
            if (len(transitions) != 1 or tail["event_type"] != "validation_completed"
                    or "change_identity" in tail["data"]
                    or stored["history_tail"] != {"sequence": tail["sequence"], "sha256": tail["event_sha256"]}
                    or stored_identity != repository_identity
                    or stored["policy_sha256"] != self.policy_digest
                    or _digest(stored) != _digest(self._project(events, stored_repository))):
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

    def checkpoint(self, milestone_id: str | None, event_type: str, summary: str, data: dict[str, Any] | None = None,
                   expected_generation: int | None = None) -> dict[str, Any]:
        state = self.load(milestone_id); milestone_id = state["milestone_id"]
        if event_type not in {"checkpointed", "validation_completed", "ci_observed", "repair_started", "repair_completed", "blocked", "completed"} or not summary or len(summary) > 512:
            raise MilestoneFailure("milestone checkpoint is invalid")
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
            repository = self._repository(events[0]["subject_head_sha"])
            data = {**data, "change_identity": repository["change_identity"]}
            event = {"schema_version": "1", "protocol": PROTOCOL, "record_kind": "event", "milestone_id": milestone_id,
                     "sequence": len(events) + 1, "event_type": event_type, "prior_event_sha256": events[-1]["event_sha256"],
                     "subject_head_sha": repository["head_sha"], "summary": summary, "data": data, "authority": dict(AUTHORITY)}
            event["event_sha256"] = _digest(event); self._validate(event)
            with history.open("ab") as stream: stream.write(_canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            state = self._project(events + [event], repository); self._atomic_json(state_path, state); self._write_pointer(state)
            return state

    def validate(self, tier: str, milestone_id: str | None = None) -> dict[str, Any]:
        state = self.load(milestone_id)
        if tier not in {"affected", "subsystem", "canonical"}: raise MilestoneFailure("validation tier is invalid")
        if state["status"] == "CONFLICT":
            raise MilestoneFailure("validation source identity conflict")
        requested = {"affected": "L1", "subsystem": "L2", "canonical": "L3"}[tier]
        impact = json.loads(self._run(["scripts/vss-agent", "impact", "--base", state["repository"]["base_sha"]], 65536))
        required = impact["minimum_level"]
        level = requested if LEVELS[requested] >= LEVELS[required] else required
        if (state["status"] not in {"WORKING", "LOCAL_VALIDATION_REQUIRED"}
                and LEVELS.get(state["validation"]["level"], -1) >= LEVELS[level]
                and state["validation"]["evidence_sha256"]):
            if tier == "canonical" and state["next"]["action"] == "run_canonical_validation":
                self.checkpoint(
                    state["milestone_id"], "validation_completed",
                    "canonical validation evidence reused.",
                    {"validation_level": state["validation"]["level"],
                     "evidence_sha256": state["validation"]["evidence_sha256"]},
                    state["generation"])
            return {"status": "reused", "level": state["validation"]["level"], "evidence_sha256": state["validation"]["evidence_sha256"]}
        evidence = Path(tempfile.gettempdir()) / f"vss-dev-{state['milestone_id']}-evidence.json"
        self._run(["scripts/vss-agent", "validate-change", "--base", state["repository"]["base_sha"], "--level", level, "--output", str(evidence)], 65536)
        proof = _read_json(evidence, 16384); evidence_digest = _digest(proof)
        self.checkpoint(state["milestone_id"], "validation_completed", f"{tier} validation passed.", {"validation_level": level, "evidence_sha256": evidence_digest}, state["generation"])
        return {"status": "passed", "level": level, "evidence_sha256": evidence_digest}

    def ingest_ci(self, document: dict[str, Any], milestone_id: str | None = None) -> dict[str, Any]:
        state = self.load(milestone_id)
        if state["status"] in {"CANONICAL_VALIDATION_REQUIRED", "REVIEW_READY", "COMPLETE"}:
            raise MilestoneFailure("CI observation is not required")
        if set(document) != {"head_sha", "checks"} or type(document["checks"]) is not list or len(document["checks"]) > 64:
            raise MilestoneFailure("CI observation is malformed")
        head = document["head_sha"]
        if type(head) is not str or SHA1.fullmatch(head) is None: raise MilestoneFailure("CI observation is malformed")
        if head != state["repository"]["head_sha"]:
            result = {"status": "stale", "classification": "none", "head_sha": head}
        else:
            text: list[str] = []; pending = False; failed = False
            for check in document["checks"]:
                if type(check) is not dict or set(check) != {"name", "status", "conclusion", "summary"}:
                    raise MilestoneFailure("CI observation is malformed")
                if not all(type(check[key]) is str and len(check[key]) <= 512 for key in check): raise MilestoneFailure("CI observation is malformed")
                pending = pending or check["status"] != "completed"; failed = failed or check["conclusion"] not in {"success", "skipped", "neutral"}
                text.append((check["name"] + " " + check["summary"]).lower())
            joined = " ".join(text)
            terms = self.policy["classification"]
            def contains(name: str) -> bool: return any(term in joined for term in terms[name])
            if pending: result = {"status": "pending", "classification": "none", "head_sha": head}
            elif not failed: result = {"status": "passed", "classification": "none", "head_sha": head}
            elif contains("security_terms"): result = {"status": "failed", "classification": "security", "head_sha": head}
            elif contains("infrastructure_terms"): result = {"status": "failed", "classification": "infrastructure", "head_sha": head}
            elif contains("fixture_terms"): result = {"status": "failed", "classification": "fixture", "head_sha": head}
            elif contains("flaky_terms"): result = {"status": "failed", "classification": "flaky/unknown", "head_sha": head}
            else: result = {"status": "failed", "classification": "code", "head_sha": head}
        data = {"ci_status": result["status"], "ci_classification": result["classification"], "ci_head_sha": result["head_sha"]}
        self.checkpoint(state["milestone_id"], "ci_observed", "CI observation ingested.", data, state["generation"])
        return result

    def ci_refresh(self, milestone_id: str | None = None) -> dict[str, Any]:
        state = self.load(milestone_id); repo = state["repository"]["name_with_owner"]; head = state["repository"]["head_sha"]
        raw = self._run(["gh", "api", f"repos/{repo}/commits/{head}/check-runs"], 1_048_576)
        value = _read_external_json(raw)
        checks = [{"name": item.get("name", ""), "status": item.get("status", ""), "conclusion": item.get("conclusion") or "",
                   "summary": ((item.get("output") or {}).get("summary") or "")[:512]} for item in value.get("check_runs", [])]
        return self.ingest_ci({"head_sha": head, "checks": checks}, state["milestone_id"])


def _read_external_json(raw: bytes) -> dict[str, Any]:
    try: value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc: raise MilestoneFailure("GitHub CI response is malformed") from exc
    if type(value) is not dict: raise MilestoneFailure("GitHub CI response is malformed")
    return value
