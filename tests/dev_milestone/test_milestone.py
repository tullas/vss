from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from vss_dev import MilestoneController, MilestoneFailure


ROOT = Path(__file__).resolve().parents[2]


class MilestoneControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for path in ("config/dev-milestone-policy-v1.json", "schemas/dev-milestone-policy-v1.schema.json",
                     "schemas/dev-milestone-record-v1.schema.json", "config/agent-harness-v2.json",
                     "schemas/dev-milestone-execution-packet-v1.schema.json",
                     "schemas/agent-harness-v2.schema.json", "schemas/agent-validation-evidence-v1.schema.json"):
            destination = self.root / path; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / path, destination)
        (self.root / "scripts").mkdir(); shutil.copy2(ROOT / "scripts/vss-agent", self.root / "scripts/vss-agent")
        (self.root / "scripts/vss-agent").chmod(0o755)
        (self.root / "scripts/validate-change.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        (self.root / "scripts/validate-change.sh").chmod(0o755)
        self.git("init", "-q", "-b", "main"); self.git("config", "user.name", "test"); self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/example/vss.git")
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(".vss/\n", encoding="utf-8")
        self.git("add", "."); self.git("commit", "-qm", "fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        residue = self.root / ".local/secrets/development.auto.tfvars.example"; residue.parent.mkdir(parents=True); residue.write_text("protected\n", encoding="utf-8")
        self.controller = MilestoneController(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True)

    def initialize(self) -> dict:
        return self.controller.initialize("dev-wf-1", self.base, 114, ["agent-coordination"], ["src/demo"], "Approved bounded development milestone.")

    def legacy_initialize(self) -> dict:
        state = self.initialize()
        directory = self.root / ".vss/milestones/dev-wf-1"
        history = directory / "history.ndjson"
        event = json.loads(history.read_text())
        event["data"] = {key: event["data"][key] for key in ("issue", "domains", "paths")}
        unsigned = {key: value for key, value in event.items() if key != "event_sha256"}
        event["event_sha256"] = hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        history.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        repository = dict(state["repository"])
        legacy_state = self.controller._project([event], repository)
        self.controller._atomic_json(directory / "state.json", legacy_state)
        self.controller._write_pointer(legacy_state)
        return legacy_state

    def test_strict_contracts_initialize_replay_and_protected_residue(self) -> None:
        state = self.initialize()
        schema = json.loads((ROOT / "schemas/dev-milestone-record-v1.schema.json").read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(state)), [])
        self.assertEqual(state["status"], "READY_FOR_IMPLEMENTATION")
        self.assertEqual(state["routing"], {"model": "gpt-5.6-terra-low", "advisory": True})
        self.assertEqual(state["authority"], {key: False for key in state["authority"]})
        replayed = self.controller.load("dev-wf-1")
        self.assertEqual(state, replayed)
        self.assertFalse((self.root / ".vss/milestones/current.json").read_text().find(".local") >= 0)

    def test_execution_packet_is_strict_deterministic_bounded_and_references_only(self) -> None:
        state = self.initialize()
        first = self.controller.execution_packet("dev-wf-1")
        second = self.controller.execution_packet("dev-wf-1")
        schema = json.loads((ROOT / "schemas/dev-milestone-execution-packet-v1.schema.json").read_text())
        self.assertEqual(first, second)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(first)), [])
        self.assertEqual(first["milestone"], {"id": "dev-wf-1", "generation": 0,
                                               "status": "READY_FOR_IMPLEMENTATION"})
        self.assertEqual(first["repository"], state["repository"])
        self.assertEqual(first["work_issue"], {"kind": "issue", "number": 114})
        self.assertEqual(first["controller"]["next"], state["next"])
        self.assertEqual(first["controller"]["policy_sha256"], state["policy_sha256"])
        self.assertEqual(first["controller"]["harness"]["schema_version"], "2")
        self.assertTrue(all(value is False for value in first["authority"].values()))
        self.assertLessEqual(len(json.dumps(first, sort_keys=True, separators=(",", ":")).encode()), 16_384)
        context_paths = [path for category in ("guidance_docs", "implementation", "tests",
                                                "validation_config_contracts")
                         for path in first["context"][category]]
        self.assertLessEqual(len(context_paths), 64)
        self.assertTrue(all(type(path) is str for path in context_paths))
        self.assertNotIn("fixture\n", json.dumps(first))
        self.assertNotIn("argv", json.dumps(first))

    def test_packet_tracks_generation_and_exact_worktree_identity_then_rejects_changed_head(self) -> None:
        initialized = self.initialize()
        first = self.controller.execution_packet("dev-wf-1")
        current = self.controller.checkpoint(
            "dev-wf-1", "checkpointed", "Durable handoff.",
            expected_generation=initialized["generation"])
        second = self.controller.execution_packet("dev-wf-1")
        self.assertEqual(second["milestone"]["generation"], current["generation"])
        self.assertNotEqual(first["controller"]["state_sha256"], second["controller"]["state_sha256"])
        path = self.root / "src/vss_dev/change.py"; path.parent.mkdir(parents=True); path.write_text("value = 1\n")
        changed = self.controller.execution_packet("dev-wf-1")
        self.assertNotEqual(changed["repository"]["change_identity"], second["repository"]["change_identity"])
        self.assertEqual(changed["controller"]["next"]["action"], "run_affected_validation")
        self.git("add", "src/vss_dev/change.py"); self.git("commit", "-qm", "advance head")
        with self.assertRaisesRegex(MilestoneFailure, "identity is stale"):
            self.controller.execution_packet("dev-wf-1")

    def test_validation_ci_canonical_and_repair_packets_select_exact_next_requirements(self) -> None:
        initialized = self.initialize()
        changed = self.root / "src/vss_dev/change.py"; changed.parent.mkdir(parents=True); changed.write_text("value = 1\n")
        validation = self.controller.execution_packet("dev-wf-1")
        self.assertEqual(validation["controller"]["next"]["action"], "run_affected_validation")
        self.assertEqual(validation["validation"]["required_tier"], "affected")
        self.assertEqual(validation["validation"]["required_level"], "L1")
        self.assertIn("dev-milestone-tests", validation["validation"]["profiles"])

        changed.unlink()
        state = self.controller.checkpoint(
            "dev-wf-1", "validation_completed", "Affected validation passed.",
            {"validation_level": "L1", "evidence_sha256": "a" * 64}, initialized["generation"])
        pending = self.controller.ingest_ci({
            "head_sha": state["repository"]["head_sha"],
            "checks": [{"name": "tests", "status": "queued", "conclusion": "", "summary": ""}],
        }, "dev-wf-1")
        self.assertEqual(pending["status"], "pending")
        ci_packet = self.controller.execution_packet("dev-wf-1")
        self.assertEqual(ci_packet["controller"]["next"]["action"], "ingest_ci")
        self.assertEqual(ci_packet["ci"]["status"], "pending")
        self.assertEqual(ci_packet["validation"]["evidence_sha256"], "a" * 64)

        canonical_state = self.controller.initialize("canonical", self.base, 115, [], [], "Canonical route.")
        canonical_state = self.controller.checkpoint(
            "canonical", "validation_completed", "Affected validation passed.",
            {"validation_level": "L1", "evidence_sha256": "b" * 64}, canonical_state["generation"])
        self.controller.ingest_ci({"head_sha": canonical_state["repository"]["head_sha"], "checks": []}, "canonical")
        canonical = self.controller.execution_packet("canonical")
        self.assertEqual(canonical["controller"]["next"]["action"], "run_canonical_validation")
        self.assertEqual(canonical["validation"]["required_tier"], "canonical")
        self.assertEqual(canonical["validation"]["required_level"], "L3")

        repair_state = self.controller.initialize("repair", self.base, 116, [], [], "Repair route.")
        repair_state = self.controller.checkpoint(
            "repair", "validation_completed", "Affected validation passed.",
            {"validation_level": "L1", "evidence_sha256": "c" * 64}, repair_state["generation"])
        self.controller.ingest_ci({
            "head_sha": repair_state["repository"]["head_sha"],
            "checks": [{"name": "tests", "status": "completed", "conclusion": "failure",
                        "summary": "assertion failed"}],
        }, "repair")
        repair = self.controller.execution_packet("repair")
        self.assertEqual(repair["controller"]["next"]["action"], "repair_code")
        self.assertEqual(repair["repair"], {"attempts": 0, "maximum_attempts": 3,
                                             "remaining_attempts": 3, "stop_reason": None})

    def test_human_architecture_security_and_review_boundaries_remain_non_authoritative(self) -> None:
        security = self.initialize()
        security = self.controller.checkpoint(
            "dev-wf-1", "validation_completed", "Validation passed.",
            {"validation_level": "L1", "evidence_sha256": "a" * 64}, security["generation"])
        self.controller.ingest_ci({
            "head_sha": security["repository"]["head_sha"],
            "checks": [{"name": "security", "status": "completed", "conclusion": "failure",
                        "summary": "security policy failure"}],
        }, "dev-wf-1")
        security_packet = self.controller.execution_packet("dev-wf-1")
        self.assertEqual(security_packet["controller"]["next"],
                         {"action": "request_security_review", "human_boundary": True})

        architecture = self.controller.initialize("architecture-stop", self.base, 115, [], [], "Architecture stop.")
        self.controller.checkpoint("architecture-stop", "blocked", "Architecture decision required.",
                                   {"stop_reason": "architecture"}, architecture["generation"])
        architecture_packet = self.controller.execution_packet("architecture-stop")
        self.assertEqual(architecture_packet["controller"]["next"],
                         {"action": "request_architecture_review", "human_boundary": True})

        review = self.controller.initialize("review", self.base, 116, [], [], "Review route.")
        review = self.controller.checkpoint(
            "review", "validation_completed", "Validation passed.",
            {"validation_level": "L3", "evidence_sha256": "d" * 64}, review["generation"])
        self.controller.ingest_ci({"head_sha": review["repository"]["head_sha"], "checks": []}, "review")
        review = self.controller.load("review")
        self.controller.checkpoint(
            "review", "validation_completed", "Canonical validation passed.",
            {"validation_level": "L3", "evidence_sha256": "d" * 64}, review["generation"])
        review_packet = self.controller.execution_packet("review")
        self.assertEqual(review_packet["controller"]["next"],
                         {"action": "request_merge", "human_boundary": True})
        for packet in (security_packet, architecture_packet, review_packet):
            self.assertTrue(all(value is False for value in packet["authority"].values()))

    def test_external_effect_impact_preserves_harness_human_gate_without_execution_authority(self) -> None:
        self.initialize()
        path = self.root / "src/vss_runtime/change.py"
        path.parent.mkdir(parents=True); path.write_text("value = 1\n")
        packet = self.controller.execution_packet("dev-wf-1")
        self.assertEqual(packet["validation"]["risk"], "external-effect")
        self.assertTrue(packet["validation"]["impact_human_gate_required"])
        self.assertIn("runtime", packet["context"]["domains"])
        self.assertTrue(all(value is False for value in packet["authority"].values()))

    def test_packet_corruption_sensitive_paths_unknown_impact_and_context_overflow_fail_closed(self) -> None:
        self.initialize()
        state_path = self.root / ".vss/milestones/dev-wf-1/state.json"
        original = state_path.read_text()
        state_path.write_text("{}\n")
        with self.assertRaisesRegex(MilestoneFailure, "record is malformed"):
            self.controller.execution_packet("dev-wf-1")
        state_path.write_text(original)

        unknown = self.root / "unclassified.bin"; unknown.write_bytes(b"unknown")
        with self.assertRaisesRegex(MilestoneFailure, "unclassified repository impact"):
            self.controller.execution_packet("dev-wf-1")
        unknown.unlink()
        sensitive = self.root / ".local/unexpected-token.txt"; sensitive.write_text("redacted\n")
        with self.assertRaisesRegex(MilestoneFailure, "unexpected sensitive changed path"):
            self.controller.execution_packet("dev-wf-1")
        sensitive.unlink()

        mapping_path = self.root / "config/agent-harness-v2.json"
        mapping = json.loads(mapping_path.read_text())
        domain = next(item for item in mapping["domains"] if item["id"] == "agent-coordination")
        domain["docs"] = [f"docs/reference-{index:02d}" for index in range(33)]
        domain["code"] = [f"src/reference-{index:02d}" for index in range(33)]
        mapping_path.write_text(json.dumps(mapping))
        with self.assertRaisesRegex(MilestoneFailure, "context exceeded its bound"):
            self.controller.execution_packet("dev-wf-1")

    def test_partial_worktree_and_head_advance_recover_without_erasure(self) -> None:
        self.initialize()
        (self.root / "work.py").write_text("pass\n", encoding="utf-8")
        partial = self.controller.load("dev-wf-1")
        self.assertEqual(partial["status"], "WORKING")
        self.assertEqual(partial["next"]["action"], "run_affected_validation")
        self.assertTrue((self.root / "work.py").exists())
        self.git("add", "work.py"); self.git("commit", "-qm", "work")
        advanced = self.controller.load("dev-wf-1")
        self.assertEqual(advanced["status"], "CONFLICT")
        self.assertTrue(advanced["next"]["human_boundary"])

    def test_explicit_feature_branch_transition_preserves_delta_and_history(self) -> None:
        initialized = self.initialize()
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        initial_event = history.read_text().splitlines()[0]
        self.git("switch", "-c", "feature/dev-wf-1")
        path = self.root / "src/demo/change.py"; path.parent.mkdir(parents=True); path.write_text("value = 1\n", encoding="utf-8")
        conflict = self.controller.load("dev-wf-1")
        self.assertEqual(conflict["status"], "CONFLICT")
        recovered = self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized milestone branch.",
            initialized["generation"],
        )
        self.assertEqual(recovered["repository"]["base_sha"], self.base)
        self.assertEqual(recovered["repository"]["branch"], "feature/dev-wf-1")
        self.assertEqual(recovered["status"], "WORKING")
        self.assertEqual(recovered["next"]["action"], "run_affected_validation")
        self.assertEqual(history.read_text().splitlines()[0], initial_event)
        event = json.loads(history.read_text().splitlines()[-1])
        self.assertEqual(event["event_type"], "branch_transitioned")
        self.assertEqual(event["data"]["from_branch"], "main")
        self.assertEqual(event["data"]["to_branch"], "feature/dev-wf-1")
        self.assertEqual(event["data"]["base_sha"], self.base)
        self.assertEqual(event["data"]["change_identity"], initialized["repository"]["change_identity"])
        self.assertTrue(all(value is False for value in event["authority"].values()))

    def test_legacy_initialization_recovers_through_sealed_transition(self) -> None:
        initialized = self.legacy_initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        path = self.root / "src/demo/change.py"; path.parent.mkdir(parents=True); path.write_text("value = 1\n", encoding="utf-8")
        recovered = self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized legacy recovery.",
            initialized["generation"])
        self.assertEqual(recovered["status"], "WORKING")
        self.assertEqual(recovered["repository"]["branch"], "feature/dev-wf-1")
        self.assertEqual(recovered["repository"]["change_identity"], self.controller._repository(self.base)["change_identity"])

    def test_arbitrary_branch_substitution_and_post_transition_switch_fail_closed(self) -> None:
        initialized = self.initialize()
        self.git("switch", "-c", "feature/arbitrary")
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.transition_branch(
                "dev-wf-1", "main", "feature/arbitrary", "Substituted branch.", initialized["generation"])
        self.git("switch", "-c", "feature/dev-wf-1", self.base)
        recovered = self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized milestone branch.",
            initialized["generation"])
        self.assertEqual(recovered["repository"]["branch"], "feature/dev-wf-1")
        self.git("switch", "feature/arbitrary")
        conflict = self.controller.load("dev-wf-1")
        self.assertEqual(conflict["status"], "CONFLICT")
        self.assertEqual(conflict["next"], {"action": "recover_state", "human_boundary": True})

    def test_branch_transition_replay_two_writer_and_event_substitution_fail_closed(self) -> None:
        initialized = self.initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        first_writer = MilestoneController(self.root)
        second_writer = MilestoneController(self.root)
        first_writer.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized milestone branch.",
            initialized["generation"])
        with self.assertRaisesRegex(MilestoneFailure, "writer conflict"):
            second_writer.transition_branch(
                "dev-wf-1", "main", "feature/dev-wf-1", "Stale writer.",
                initialized["generation"])
        current = first_writer.load("dev-wf-1")
        with self.assertRaisesRegex(MilestoneFailure, "already recorded"):
            first_writer.transition_branch(
                "dev-wf-1", "main", "feature/dev-wf-1", "Replay.", current["generation"])
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        lines = history.read_text().splitlines(); transition = json.loads(lines[-1])
        transition["data"]["to_branch"] = "feature/substituted"
        lines[-1] = json.dumps(transition, sort_keys=True, separators=(",", ":"))
        history.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "history conflict"):
            first_writer.load("dev-wf-1")

    def test_materialized_state_reseal_cannot_hide_transition_delta(self) -> None:
        initialized = self.initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized milestone branch.",
            initialized["generation"])
        state_path = self.root / ".vss/milestones/dev-wf-1/state.json"
        state = json.loads(state_path.read_text())
        state["repository"]["change_identity"] = "f" * 64
        state_path.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "state conflict"):
            self.controller.load("dev-wf-1")

    def test_explicit_legacy_validation_identity_recovery_is_append_only(self) -> None:
        initialized = self.initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        path = self.root / "src/demo/change.py"; path.parent.mkdir(parents=True); path.write_text("value = 1\n", encoding="utf-8")
        self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized milestone branch.",
            initialized["generation"])
        directory = self.root / ".vss/milestones/dev-wf-1"
        history = directory / "history.ndjson"
        events = [json.loads(line) for line in history.read_text().splitlines()]
        tail = {
            "schema_version": "1", "protocol": "vss.dev-milestone", "record_kind": "event",
            "milestone_id": "dev-wf-1", "sequence": 3, "event_type": "validation_completed",
            "prior_event_sha256": events[-1]["event_sha256"], "subject_head_sha": self.base,
            "summary": "Legacy validation.",
            "data": {"validation_level": "L3", "evidence_sha256": "a" * 64},
            "authority": initialized["authority"],
        }
        tail["event_sha256"] = hashlib.sha256(json.dumps(
            tail, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        events.append(tail)
        history.write_text("\n".join(json.dumps(
            event, sort_keys=True, separators=(",", ":")) for event in events) + "\n", encoding="utf-8")
        repository = self.controller._repository(self.base)
        legacy_state = self.controller._project(events, repository)
        self.controller._atomic_json(directory / "state.json", legacy_state)
        self.controller._write_pointer(legacy_state)
        with self.assertRaisesRegex(MilestoneFailure, "state conflict"):
            self.controller.load("dev-wf-1")
        recovered = self.controller.recover_state_identity(
            "dev-wf-1", "Bind legacy validated worktree identity.", legacy_state["generation"])
        self.assertEqual(recovered["status"], "LOCAL_VALIDATION_REQUIRED")
        self.assertEqual(recovered["next"]["action"], "run_affected_validation")
        bound = json.loads(history.read_text().splitlines()[-1])
        self.assertEqual(bound["event_type"], "validation_invalidated")
        self.assertEqual(bound["data"]["recovered_event_sha256"], tail["event_sha256"])
        self.assertEqual(bound["data"]["change_identity"], repository["change_identity"])
        self.assertTrue(all(value is False for value in bound["authority"].values()))
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.recover_state_identity(
                "dev-wf-1", "Replay.", recovered["generation"])
        continued = self.controller.checkpoint(
            "dev-wf-1", "checkpointed", "Continue after explicit invalidation.",
            expected_generation=recovered["generation"])
        self.assertEqual(continued["status"], "LOCAL_VALIDATION_REQUIRED")
        self.assertEqual(continued["next"]["action"], "run_affected_validation")

    def test_event_substitution_and_two_writer_conflicts_fail_closed(self) -> None:
        state = self.initialize()
        self.controller.checkpoint("dev-wf-1", "checkpointed", "First checkpoint.", expected_generation=state["generation"])
        with self.assertRaisesRegex(MilestoneFailure, "writer conflict"):
            self.controller.checkpoint("dev-wf-1", "checkpointed", "Stale writer.", expected_generation=state["generation"])
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        lines = history.read_text().splitlines(); history.write_text(lines[1] + "\n" + lines[0] + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "history conflict"):
            self.controller.load("dev-wf-1")

    def test_ci_exact_head_precedence_and_stop_boundaries(self) -> None:
        self.initialize()
        stale = self.controller.ingest_ci({"head_sha": "f" * 40, "checks": []}, "dev-wf-1")
        self.assertEqual(stale["status"], "stale")
        # Start a fresh state for each independent classifier because observations are append-only.
        for suffix, summary, expected in (("code", "assertion failed", "code"), ("fixture", "fixture digest mismatch", "fixture"),
                                          ("security", "security policy failure", "security"), ("infra", "runner network timeout", "infrastructure"),
                                          ("flaky", "intermittent retry", "flaky/unknown")):
            identifier = f"ci-{suffix}"
            self.controller.initialize(identifier, self.base, 114, [], [], "CI classification.")
            head = self.controller.load(identifier)["repository"]["head_sha"]
            result = self.controller.ingest_ci({"head_sha": head, "checks": [{"name": "check", "status": "completed", "conclusion": "failure", "summary": summary}]}, identifier)
            self.assertEqual(result["classification"], expected)
        security_state = self.controller.load("ci-security")
        self.assertEqual(security_state["status"], "BLOCKED")
        self.assertTrue(security_state["next"]["human_boundary"])
        self.assertEqual(security_state["routing"]["model"], "gpt-5.6-sol-high")

    def test_repair_budget_and_malformed_ci_are_closed(self) -> None:
        self.initialize()
        for attempt in range(3):
            current = self.controller.load("dev-wf-1")
            self.controller.checkpoint("dev-wf-1", "repair_started", "Bounded repair.", expected_generation=current["generation"])
        current = self.controller.load("dev-wf-1")
        with self.assertRaisesRegex(MilestoneFailure, "repair budget"):
            self.controller.checkpoint("dev-wf-1", "repair_started", "Over budget.", expected_generation=current["generation"])
        with self.assertRaisesRegex(MilestoneFailure, "CI observation is malformed"):
            self.controller.ingest_ci({"head_sha": self.base, "checks": [{"name": "x"}]}, "dev-wf-1")

    def test_repair_cannot_cross_scope_or_protected_boundary(self) -> None:
        self.initialize()
        protected = self.root / ".github/workflows/unsafe.yml"; protected.parent.mkdir(parents=True); protected.write_text("name: unsafe\n", encoding="utf-8")
        state = self.controller.load("dev-wf-1")
        with self.assertRaisesRegex(MilestoneFailure, "protected boundary"):
            self.controller.checkpoint("dev-wf-1", "repair_started", "Unsafe repair.", expected_generation=state["generation"])

    def test_cli_surface_stays_outside_runtime(self) -> None:
        init = subprocess.run(["vss", "dev", "milestone", "init", "--milestone-id", "cli-state", "--base", self.base,
                               "--issue", "114", "--summary", "CLI state."], cwd=self.root, text=True, capture_output=True, check=False)
        self.assertEqual(init.returncode, 0, init.stderr)
        status = subprocess.run(["vss", "dev", "milestone", "next", "--milestone-id", "cli-state"], cwd=self.root,
                                text=True, capture_output=True, check=False)
        self.assertEqual(status.returncode, 0, status.stderr)
        value = json.loads(status.stdout)
        self.assertEqual(value["next"]["action"], "start_bounded_work")
        self.assertTrue(all(result is False for result in value["authority"].values()))
        packet_result = subprocess.run([
            "vss", "dev", "milestone", "next", "--packet", "--milestone-id", "cli-state",
        ], cwd=self.root, text=True, capture_output=True, check=False)
        self.assertEqual(packet_result.returncode, 0, packet_result.stderr)
        packet = json.loads(packet_result.stdout)
        self.assertEqual(packet["protocol"], "vss.dev-milestone-execution-packet")
        self.assertEqual(packet["controller"]["next"]["action"], "start_bounded_work")
        self.assertTrue(all(result is False for result in packet["authority"].values()))
        self.git("switch", "-c", "feature/cli-state")
        transition = subprocess.run([
            "vss", "dev", "milestone", "transition-branch", "--milestone-id", "cli-state",
            "--from-branch", "main", "--to-branch", "feature/cli-state",
            "--summary", "Authorized CLI transition.", "--expected-generation", "0",
        ], cwd=self.root, text=True, capture_output=True, check=False)
        self.assertEqual(transition.returncode, 0, transition.stderr)
        transitioned = json.loads(transition.stdout)
        self.assertEqual(transitioned["repository"]["branch"], "feature/cli-state")
        self.assertTrue(all(result is False for result in transitioned["authority"].values()))

    def test_validation_evidence_is_reused_for_an_unchanged_source_change(self) -> None:
        self.initialize()
        first = self.controller.validate("affected", "dev-wf-1")
        second = self.controller.validate("affected", "dev-wf-1")
        self.assertEqual(first["status"], "passed")
        self.assertEqual(second["status"], "reused")
        self.assertEqual(first["evidence_sha256"], second["evidence_sha256"])

    def test_fresh_canonical_success_after_exact_ci_progresses_to_review(self) -> None:
        initialized = self.initialize()
        self.controller.checkpoint(
            "dev-wf-1", "validation_completed", "Sealed lower-level validation.",
            {"validation_level": "L1", "evidence_sha256": "a" * 64},
            initialized["generation"])
        head = self.controller.load("dev-wf-1")["repository"]["head_sha"]
        self.controller.ingest_ci({"head_sha": head, "checks": []}, "dev-wf-1")
        fresh = self.controller.validate("canonical", "dev-wf-1")
        state = self.controller.load("dev-wf-1")
        self.assertEqual(fresh["status"], "passed")
        self.assertEqual(fresh["level"], "L3")
        self.assertEqual(state["status"], "REVIEW_READY")
        self.assertEqual(state["next"], {"action": "request_merge", "human_boundary": True})

    def test_reused_canonical_success_after_exact_ci_progresses_to_review(self) -> None:
        self.initialize()
        canonical = self.controller.validate("canonical", "dev-wf-1")
        head = self.controller.load("dev-wf-1")["repository"]["head_sha"]
        self.controller.ingest_ci({"head_sha": head, "checks": []}, "dev-wf-1")
        reused = self.controller.validate("canonical", "dev-wf-1")
        state = self.controller.load("dev-wf-1")
        self.assertEqual(reused, {"status": "reused", "level": "L3",
                                  "evidence_sha256": canonical["evidence_sha256"]})
        self.assertEqual(state["status"], "REVIEW_READY")
        self.assertEqual(state["next"], {"action": "request_merge", "human_boundary": True})

    def test_prior_ci_pending_materialization_recovers_only_the_exact_review_projection(self) -> None:
        self.initialize()
        self.controller.validate("canonical", "dev-wf-1")
        head = self.controller.load("dev-wf-1")["repository"]["head_sha"]
        self.controller.ingest_ci({"head_sha": head, "checks": []}, "dev-wf-1")
        self.controller.validate("canonical", "dev-wf-1")
        expected = self.controller.load("dev-wf-1")
        legacy = {**expected, "status": "CI_PENDING",
                  "routing": {"model": self.controller.policy["model_routing"]["maintenance"], "advisory": True},
                  "next": {"action": "ingest_ci", "human_boundary": False}}
        state_path = self.root / ".vss/milestones/dev-wf-1/state.json"
        self.controller._atomic_json(state_path, legacy)
        self.controller._write_pointer(legacy)
        recovered = self.controller.load("dev-wf-1")
        self.assertEqual(recovered["status"], "REVIEW_READY")
        self.assertEqual(recovered["next"], {"action": "request_merge", "human_boundary": True})

    def test_exact_ci_and_canonical_validation_cannot_cycle_or_duplicate(self) -> None:
        self.initialize()
        self.controller.validate("canonical", "dev-wf-1")
        head = self.controller.load("dev-wf-1")["repository"]["head_sha"]
        self.controller.ingest_ci({"head_sha": head, "checks": []}, "dev-wf-1")
        self.controller.validate("canonical", "dev-wf-1")
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        before = history.read_text(encoding="utf-8")
        repeated = self.controller.validate("canonical", "dev-wf-1")
        self.assertEqual(repeated["status"], "reused")
        self.assertEqual(history.read_text(encoding="utf-8"), before)
        with self.assertRaisesRegex(MilestoneFailure, "not required"):
            self.controller.ingest_ci({"head_sha": head, "checks": []}, "dev-wf-1")

    def test_stale_or_changed_source_never_reuses_canonical_evidence(self) -> None:
        self.initialize()
        self.controller.validate("canonical", "dev-wf-1")
        (self.root / "work.py").write_text("pass\n", encoding="utf-8")
        changed = self.controller.validate("canonical", "dev-wf-1")
        self.assertEqual(changed["status"], "passed")
        self.git("add", "work.py"); self.git("commit", "-qm", "advanced")
        with self.assertRaisesRegex(MilestoneFailure, "source identity conflict"):
            self.controller.validate("canonical", "dev-wf-1")

    def test_controller_has_no_runtime_provider_or_mutating_github_path(self) -> None:
        source = (ROOT / "src/vss_dev/milestone.py").read_text(encoding="utf-8")
        for forbidden in ("vss_runtime", "vss_providers", "git push", "git merge", "gh pr create", "shell=True", "--method"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
