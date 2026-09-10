from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from vss_dev import ImprovementBacklog, ImprovementBacklogFailure, MilestoneController, MilestoneFailure
from vss_dev.milestone import BOOTSTRAP_REPAIR_PATHS


ROOT = Path(__file__).resolve().parents[2]


def mission_evidence() -> dict:
    return {"gap": "Film #1 needs a moving shot.",
            "observable_result": "A bounded moving-shot review candidate.",
            "authority_alignment": "aligned", "triggers": [],
            "heartbeat": [{"milestone_id": "prior", "capability": "image", "advanced": True,
                           "evidence": "README.md"}],
            "active_decisions": [{"id": "DEC-0001", "disposition": "COMPLY",
                                  "rationale": "The bounded milestone follows Foundation Closure."},
                                 {"id": "DEC-0002", "disposition": "COMPLY",
                                  "rationale": "The bounded milestone preserves existing-media revalidation guardrails."}]}


class MilestoneControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for path in ("config/dev-milestone-policy-v1.json", "schemas/dev-milestone-policy-v1.schema.json",
                     "schemas/dev-milestone-record-v1.schema.json", "config/agent-harness-v2.json",
                     "schemas/dev-milestone-execution-packet-v1.schema.json",
                     "schemas/agent-harness-v2.schema.json", "schemas/agent-validation-evidence-v1.schema.json",
                     "schemas/dev-improvement-candidate-v1.schema.json", "docs/engineering/improvement-backlog-v1.json"):
            destination = self.root / path; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / path, destination)
        for path in ("docs/architecture/decisions/index.json", "docs/architecture/decisions/DEC-0001-foundation-closure.json", "docs/architecture/decisions/DEC-0002-existing-media-revalidation.json"):
            destination = self.root / path; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / path, destination)
        (self.root / "scripts").mkdir(); shutil.copy2(ROOT / "scripts/vss-agent", self.root / "scripts/vss-agent")
        (self.root / "scripts/security").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/security/validate-repository-governance.py",
                     self.root / "scripts/security/validate-repository-governance.py")
        for path in ("config/repository-governance-v1.json", "config/secrets-baseline-scope-v1.json",
                     "config/test-classification-v1.json", ".secrets.baseline"):
            destination = self.root / path; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / path, destination)
        (self.root / "tests/movie_storyboard").mkdir(parents=True)
        (self.root / "tests/performance").mkdir(parents=True)
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
        return self.controller.initialize("dev-wf-1", self.base, 114, ["agent-coordination"], ["src/demo"], "Approved bounded development milestone.", mission_evidence())

    def committed_pending_milestone(self) -> tuple[dict, str, bytes]:
        initialized = self.initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        transitioned = self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized milestone branch.", initialized["generation"])
        changed = self.root / "README.md"
        changed.write_text("accepted implementation\n", encoding="utf-8")
        pending = self.controller.checkpoint(
            "dev-wf-1", "validation_completed", "Canonical validation passed.",
            {"validation_level": "L3", "evidence_sha256": "a" * 64}, transitioned["generation"])
        history_before = (self.root / ".vss/milestones/dev-wf-1/history.ndjson").read_bytes()
        self.git("add", "README.md"); self.git("commit", "-qm", "accepted implementation")
        return pending, self.git("rev-parse", "HEAD").stdout.strip(), history_before

    def committed_controller_upgrade(self) -> tuple[dict, str, str, str, bytes]:
        initialized = self.controller.initialize(
            "dev-wf-2-engineering-observability", self.base, 140,
            ["agent-coordination", "architecture"], ["src/vss_dev"],
            "Controller bootstrap fixture.", mission_evidence())
        self.git("switch", "-c", "feature/dev-wf-2-engineering-observability")
        transitioned = self.controller.transition_branch(
            "dev-wf-2-engineering-observability", "main", "feature/dev-wf-2-engineering-observability",
            "Authorized milestone branch.", initialized["generation"])
        (self.root / "README.md").write_text("accepted implementation\n", encoding="utf-8")
        pending = self.controller.checkpoint(
            "dev-wf-2-engineering-observability", "validation_completed", "Canonical validation passed.",
            {"validation_level": "L3", "evidence_sha256": "a" * 64}, transitioned["generation"])
        old_head = pending["repository"]["head_sha"]
        self.git("add", "README.md"); self.git("commit", "-qm", "accepted implementation")
        reviewed_head = self.git("rev-parse", "HEAD").stdout.strip()
        for path in BOOTSTRAP_REPAIR_PATHS:
            target = self.root / path; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("controller repair fixture\n", encoding="utf-8")
        self.git("add", *BOOTSTRAP_REPAIR_PATHS); self.git("commit", "-qm", "controller repair")
        target_head = self.git("rev-parse", "HEAD").stdout.strip()
        history_before = (self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson").read_bytes()
        return pending, old_head, reviewed_head, target_head, history_before

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
        legacy_state = self.controller._project([event], repository, legacy=True)
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

    def test_governed_baseline_change_is_admitted_and_tampered_baseline_is_rejected(self) -> None:
        baseline = json.loads((self.root / ".secrets.baseline").read_text())
        baseline["generated_at"] = "2026-09-10T00:00:00Z"
        (self.root / ".secrets.baseline").write_text(json.dumps(baseline), encoding="utf-8")
        accepted = self.controller._repository(self.base)
        self.assertEqual(accepted["head_sha"], self.base)

        baseline["results"]["unauthorized.json"] = []
        (self.root / ".secrets.baseline").write_text(json.dumps(baseline), encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "unexpected sensitive changed path"):
            self.controller._repository(self.base)

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
        self.assertEqual(first["active_decisions"]["ids"], ["DEC-0001", "DEC-0002"])
        self.assertRegex(first["active_decisions"]["index_sha256"], r"^[0-9a-f]{64}$")
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

    def test_change_identity_is_stable_when_untracked_files_become_committed(self) -> None:
        self.initialize()
        new_file = self.root / "src/demo/new-contract.json"
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.write_bytes(b'{"stable":true}\n')
        before = self.controller._repository(self.base)["change_identity"]
        self.git("add", "src/demo/new-contract.json")
        self.git("commit", "-qm", "commit intended new file")
        after = self.controller._repository(self.base)["change_identity"]
        self.assertEqual(before, after)

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

        canonical_state = self.controller.initialize("canonical", self.base, 115, [], [], "Canonical route.", mission_evidence())
        canonical_state = self.controller.checkpoint(
            "canonical", "validation_completed", "Affected validation passed.",
            {"validation_level": "L1", "evidence_sha256": "b" * 64}, canonical_state["generation"])
        self.controller.ingest_ci({"head_sha": canonical_state["repository"]["head_sha"], "checks": []}, "canonical")
        canonical = self.controller.execution_packet("canonical")
        self.assertEqual(canonical["controller"]["next"]["action"], "run_canonical_validation")
        self.assertEqual(canonical["validation"]["required_tier"], "canonical")
        self.assertEqual(canonical["validation"]["required_level"], "L3")

        repair_state = self.controller.initialize("repair", self.base, 116, [], [], "Repair route.", mission_evidence())
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

        architecture = self.controller.initialize("architecture-stop", self.base, 115, [], [], "Architecture stop.", mission_evidence())
        self.controller.checkpoint("architecture-stop", "blocked", "Architecture decision required.",
                                   {"stop_reason": "architecture"}, architecture["generation"])
        architecture_packet = self.controller.execution_packet("architecture-stop")
        self.assertEqual(architecture_packet["controller"]["next"],
                         {"action": "request_architecture_review", "human_boundary": True})

        review = self.controller.initialize("review", self.base, 116, [], [], "Review route.", mission_evidence())
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

    def test_durable_backlog_is_deterministic_advisory_and_due_report_only(self) -> None:
        backlog = ImprovementBacklog(self.root)
        candidate = {
            "source": {"milestone_id": "dev-wf-2-engineering-observability",
                       "observation_id": "obs-seeded", "finding": "known finding"},
            "category": "validation", "problem_statement": "A bounded test problem.",
            "evidence": [{"reference": "docs/agent-coordination.md", "digest": "a" * 64}],
            "expected_benefit_dimensions": ["validation-speed"], "risk": "low",
            "architectural_fit": "extend-existing", "disposition": "deferred",
            "trigger": {"kind": "milestone-boundary", "condition": "At a later boundary."},
            "priority": 2, "authority_required": ["human-review"], "status": "queued",
        }
        first = backlog.admit(candidate)
        second = backlog.admit(candidate)
        self.assertEqual(first, second)
        self.assertFalse(first["implementation_authorized"])
        report = backlog.due("dev-wf-1")
        self.assertIn(first["candidate_id"], report["selected_for_review"])
        self.assertFalse(report["implementation_authorized"])
        tampered = json.loads((self.root / "docs/engineering/improvement-backlog-v1.json").read_text())
        tampered["authority"]["merge"] = True
        (self.root / "docs/engineering/improvement-backlog-v1.json").write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaises(ImprovementBacklogFailure):
            backlog.load()

    def test_checkpoint_observation_materializes_only_matching_advisory_candidate(self) -> None:
        state = self.initialize()
        observation = {"id": "obs-context-loss", "kind": "friction", "finding": "human-relay",
                       "metric": "count", "value": 2, "unit": "count", "source": "milestone-controller",
                       "recommendation": "inspect-environment", "evidence_sha256": "b" * 64}
        state = self.controller.checkpoint("dev-wf-1", "checkpointed", "Observed relay friction.",
                                           {"observation": observation}, state["generation"])
        spec = {"source_observation_id": "obs-context-loss", "finding": "human-relay",
                "category": "human-friction", "problem_statement": "Relay work is repeated.",
                "expected_benefit_dimensions": ["human-friction"], "risk": "low",
                "architectural_fit": "extend-existing", "disposition": "deferred",
                "trigger": {"kind": "milestone-boundary", "condition": "At the next boundary."},
                "priority": 2, "authority_required": ["human-review"], "status": "queued"}
        admitted = self.controller.backlog_admit("dev-wf-1", spec)
        self.assertEqual(admitted["source"]["milestone_id"], "dev-wf-1")
        self.assertFalse(admitted["implementation_authorized"])
        with self.assertRaisesRegex(MilestoneFailure, "does not match"):
            self.controller.backlog_admit("dev-wf-1", {**spec, "finding": "slow-validation"})

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

    def test_analysis_is_bounded_and_advisory(self) -> None:
        self.initialize()
        result = self.controller.analyze("dev-wf-1")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["unknown_opportunities"], [])
        self.assertTrue(all(value is False for value in result["authority"].values()))

    def test_legacy_initialization_recovers_through_sealed_transition(self) -> None:
        initialized = self.legacy_initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        path = self.root / "src/demo/change.py"; path.parent.mkdir(parents=True); path.write_text("value = 1\n", encoding="utf-8")
        recovered = self.controller.transition_branch(
            "dev-wf-1", "main", "feature/dev-wf-1", "Authorized legacy recovery.",
            initialized["generation"])
        self.assertEqual(recovered["status"], "DESIGN_REVIEW_REQUIRED")
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

    def test_modern_post_commit_head_rebind_preserves_history_and_invalidates_ci(self) -> None:
        pending, committed_head, history_before = self.committed_pending_milestone()
        rebound = self.controller.rebind_committed_head(
            "dev-wf-1", "Bind accepted committed implementation.", pending["generation"])
        self.assertEqual(rebound["generation"], pending["generation"] + 1)
        self.assertEqual(rebound["repository"]["head_sha"], committed_head)
        self.assertEqual(rebound["status"], "CI_PENDING")
        self.assertEqual(rebound["next"], {"action": "ingest_ci", "human_boundary": False})
        self.assertEqual(rebound["validation"], pending["validation"])
        self.assertEqual(rebound["ci"], {"head_sha": None, "status": "not_observed", "classification": "none"})
        history = (self.root / ".vss/milestones/dev-wf-1/history.ndjson").read_bytes()
        self.assertTrue(history.startswith(history_before))
        event = json.loads(history.splitlines()[-1])
        self.assertEqual(event["event_type"], "identity_rebound")
        self.assertEqual(event["data"]["rebound_from_head"], pending["repository"]["head_sha"])
        self.assertTrue(all(value is False for value in event["authority"].values()))

    def test_modern_post_commit_rebind_rejects_changed_identity_and_dirty_worktree(self) -> None:
        pending, _, history_before = self.committed_pending_milestone()
        changed = self.root / "README.md"; changed.write_text("unauthorized change\n", encoding="utf-8")
        self.git("add", "README.md"); self.git("commit", "-qm", "unauthorized change")
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.rebind_committed_head("dev-wf-1", "Reject changed identity.", pending["generation"])
        self.assertEqual((self.root / ".vss/milestones/dev-wf-1/history.ndjson").read_bytes(), history_before)


    def test_modern_post_commit_rebind_rejects_dirty_worktree(self) -> None:
        pending, _, history_before = self.committed_pending_milestone()
        (self.root / "src/demo").mkdir(parents=True, exist_ok=True)
        (self.root / "src/demo/dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "clean worktree"):
            self.controller.rebind_committed_head("dev-wf-1", "Reject dirty worktree.", pending["generation"])
        self.assertEqual((self.root / ".vss/milestones/dev-wf-1/history.ndjson").read_bytes(), history_before)

    def test_modern_post_commit_rebind_rejects_wrong_branch_stale_generation_and_rewrite(self) -> None:
        pending, _, history_before = self.committed_pending_milestone()
        self.git("switch", "main")
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.rebind_committed_head("dev-wf-1", "Reject wrong branch.", pending["generation"])
        self.assertEqual((self.root / ".vss/milestones/dev-wf-1/history.ndjson").read_bytes(), history_before)

        self.git("switch", "feature/dev-wf-1")
        with self.assertRaisesRegex(MilestoneFailure, "writer conflict"):
            self.controller.rebind_committed_head("dev-wf-1", "Reject stale writer.", pending["generation"] - 1)

        self.git("switch", "main")
        self.git("branch", "-D", "feature/dev-wf-1")
        self.git("switch", "--orphan", "feature/dev-wf-1")
        (self.root / "README.md").write_text("rewritten\n", encoding="utf-8")
        self.git("add", "-A"); self.git("commit", "-qm", "rewritten history")
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.rebind_committed_head("dev-wf-1", "Reject rewrite.", pending["generation"])

    def test_modern_post_commit_rebind_rejects_tampered_identity_event(self) -> None:
        pending, _, _ = self.committed_pending_milestone()
        rebound = self.controller.rebind_committed_head(
            "dev-wf-1", "Bind accepted committed implementation.", pending["generation"])
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        events = history.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(events[-1]); tampered["data"]["rebound_from_head"] = "f" * 40
        events[-1] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        history.write_text("\n".join(events) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "history conflict"):
            self.controller.load("dev-wf-1")
        self.assertEqual(rebound["generation"], pending["generation"] + 1)

    def test_controller_upgrade_bootstrap_succeeds_and_invalidates_ci(self) -> None:
        pending, old_head, reviewed_head, target_head, history_before = self.committed_controller_upgrade()
        bootstrapped = self.controller.bootstrap_controller_upgrade(
            "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head, target_head,
            "Authorize the exact controller upgrade.", pending["generation"])
        self.assertEqual(bootstrapped["generation"], pending["generation"] + 1)
        self.assertEqual(bootstrapped["repository"]["head_sha"], target_head)
        self.assertEqual(bootstrapped["status"], "CI_PENDING")
        self.assertEqual(bootstrapped["next"], {"action": "ingest_ci", "human_boundary": False})
        self.assertEqual(bootstrapped["validation"], pending["validation"])
        self.assertEqual(bootstrapped["ci"]["status"], "not_observed")
        self.assertTrue((self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson").read_bytes().startswith(history_before))

    def test_controller_upgrade_bootstrap_rejects_wrong_heads_base_and_generation(self) -> None:
        pending, old_head, reviewed_head, target_head, history_before = self.committed_controller_upgrade()
        cases = (("base", "f" * 40, old_head, reviewed_head, target_head, pending["generation"]),
                 ("old", self.base, "f" * 40, reviewed_head, target_head, pending["generation"]),
                 ("reviewed-head", self.base, old_head, "f" * 40, target_head, pending["generation"]),
                 ("reviewed-identity", self.base, old_head, old_head, target_head, pending["generation"]),
                 ("target", self.base, old_head, reviewed_head, "f" * 40, pending["generation"]),
                 ("generation", self.base, old_head, reviewed_head, target_head, pending["generation"] - 1))
        for name, base, old, reviewed, target, generation in cases:
            with self.subTest(name=name), self.assertRaises(MilestoneFailure):
                self.controller.bootstrap_controller_upgrade(
                    "dev-wf-2-engineering-observability", base, old, reviewed, target, "Reject.", generation)
        self.assertEqual((self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson").read_bytes(), history_before)

    def test_controller_upgrade_bootstrap_rejects_unrelated_dirty_or_stale_ci(self) -> None:
        pending, old_head, reviewed_head, target_head, history_before = self.committed_controller_upgrade()
        unrelated = self.root / "unrelated.py"; unrelated.write_text("unrelated\n", encoding="utf-8")
        self.git("add", "unrelated.py"); self.git("commit", "-qm", "unrelated")
        with self.assertRaisesRegex(MilestoneFailure, "boundary"):
            self.controller.bootstrap_controller_upgrade(
                "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head,
                self.git("rev-parse", "HEAD").stdout.strip(), "Reject unrelated.", pending["generation"])
        self.assertEqual((self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson").read_bytes(), history_before)

    def test_controller_upgrade_bootstrap_rejects_dirty_worktree(self) -> None:
        pending, old_head, reviewed_head, target_head, history_before = self.committed_controller_upgrade()
        (self.root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "clean worktree"):
            self.controller.bootstrap_controller_upgrade(
                "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head, target_head,
                "Reject dirty.", pending["generation"])
        self.assertEqual((self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson").read_bytes(), history_before)

    def test_controller_upgrade_bootstrap_rejects_stale_ci(self) -> None:
        pending, old_head, reviewed_head, target_head, history_before = self.committed_controller_upgrade()
        self.controller.ingest_ci({"head_sha": old_head, "checks": []}, "dev-wf-2-engineering-observability")
        current_generation = self.controller.load("dev-wf-2-engineering-observability")["generation"]
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.bootstrap_controller_upgrade(
                "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head, target_head,
                "Reject stale CI.", current_generation)
        current = (self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson").read_text(encoding="utf-8")
        self.assertNotIn('"event_type":"controller_bootstrap"', current)
        self.assertTrue(current.encode().startswith(history_before))

    def test_controller_upgrade_bootstrap_rejects_non_descendant_replay_and_tampering(self) -> None:
        pending, old_head, reviewed_head, target_head, history_before = self.committed_controller_upgrade()
        self.git("switch", "main"); self.git("branch", "-D", "feature/dev-wf-2-engineering-observability")
        self.git("switch", "--orphan", "feature/dev-wf-2-engineering-observability")
        (self.root / "README.md").write_text("rewritten\n", encoding="utf-8")
        self.git("add", "-A"); self.git("commit", "-qm", "rewritten")
        with self.assertRaisesRegex(MilestoneFailure, "unauthorized"):
            self.controller.bootstrap_controller_upgrade(
                "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head,
                self.git("rev-parse", "HEAD").stdout.strip(), "Reject rewrite.", pending["generation"])

        self.assertTrue(history_before)

    def test_controller_upgrade_bootstrap_rejects_replay_and_tampered_event(self) -> None:
        pending, old_head, reviewed_head, target_head, _ = self.committed_controller_upgrade()
        bootstrapped = self.controller.bootstrap_controller_upgrade(
            "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head, target_head,
            "Bootstrap once.", pending["generation"])
        with self.assertRaisesRegex(MilestoneFailure, "already recorded"):
            self.controller.bootstrap_controller_upgrade(
                "dev-wf-2-engineering-observability", self.base, old_head, reviewed_head, target_head,
                "Replay.", bootstrapped["generation"])
        history = self.root / ".vss/milestones/dev-wf-2-engineering-observability/history.ndjson"
        lines = history.read_text(encoding="utf-8").splitlines(); event = json.loads(lines[-1])
        event["data"]["new_head"] = "f" * 40
        lines[-1] = json.dumps(event, sort_keys=True, separators=(",", ":")); history.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "history conflict"):
            self.controller.load("dev-wf-2-engineering-observability")

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
            self.controller.initialize(identifier, self.base, 114, [], [], "CI classification.", mission_evidence())
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

    def test_checkpoint_persists_bounded_observation_record(self) -> None:
        self.initialize()
        observation = {"id": "obs-validation-friction", "kind": "friction",
                       "finding": "human-relay", "metric": "count", "value": 2,
                       "unit": "count", "source": "milestone-controller",
                       "recommendation": "run-affected-validation", "evidence_sha256": "a" * 64}
        state = self.controller.load("dev-wf-1")
        updated = self.controller.checkpoint("dev-wf-1", "checkpointed",
                                             "Recorded bounded friction observation.",
                                             {"observation": observation}, state["generation"])
        self.assertEqual(updated["generation"], 1)
        event = json.loads((self.root / ".vss/milestones/dev-wf-1/history.ndjson").read_text().splitlines()[-1])
        self.assertEqual(event["data"]["observation"], observation)
        self.assertTrue(all(value is False for value in event["authority"].values()))

    def test_cli_surface_stays_outside_runtime(self) -> None:
        mission_path = self.root / ".vss/mission-input.json"
        mission_path.parent.mkdir(parents=True, exist_ok=True)
        mission_path.write_text(json.dumps(mission_evidence()))
        init = subprocess.run(["vss", "dev", "milestone", "init", "--milestone-id", "cli-state", "--base", self.base,
                               "--issue", "114", "--summary", "CLI state.", "--mission-input", str(mission_path)], cwd=self.root, text=True, capture_output=True, check=False)
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

    def assess(self, evidence: dict, identifier: str = "dev-wf-1") -> dict:
        state = self.controller.load(identifier)
        return self.controller.checkpoint(identifier, "mission_assessed", "Mission evidence.",
                                         {"mission": evidence}, state["generation"])

    def review(self, state: dict, mechanism: str, disposition: str) -> dict:
        return self.controller.checkpoint(
            state["milestone_id"], "mission_reviewed", "Bounded existing review disposition.",
            {"assessment_sha256": state["mission_gate"]["assessment_sha256"],
             "review": {"mechanism": mechanism, "disposition": disposition,
                        "owner": "project-owner", "evidence": "README.md"}}, state["generation"])

    def test_missing_gate_stops_initialization_legacy_and_worktree_bypasses(self) -> None:
        state = self.controller.initialize("ungated", self.base, 128, [], [], "No assessment yet.")
        self.assertEqual(state["status"], "DESIGN_REVIEW_REQUIRED")
        self.assertEqual(state["mission_gate"]["outcome"], "STRATEGIC_REVIEW_REQUIRED")
        changed = self.root / "src/vss_dev/change.py"
        changed.parent.mkdir(parents=True); changed.write_text("value = 1\n")
        for event, data in (("checkpointed", {}),
                            ("validation_completed", {"validation_level": "L3", "evidence_sha256": "a" * 64}),
                            ("ci_observed", {"ci_head_sha": self.base, "ci_status": "failed", "ci_classification": "code"})):
            with self.subTest(event=event):
                self.controller.checkpoint("ungated", event, "Cannot clear mission gate.", data)
                packet = self.controller.execution_packet("ungated")
                self.assertEqual(packet["controller"]["next"],
                                 {"action": "request_design_review", "human_boundary": True})
                self.assertTrue(packet["stop_and_challenge"])
        self.assertTrue(all(value is False for value in packet["authority"].values()))
        for event in ("repair_started", "repair_completed", "completed"):
            with self.assertRaisesRegex(MilestoneFailure, "mission review is required"):
                self.controller.checkpoint("ungated", event, "Bypass attempt.")
        legacy = self.legacy_initialize()
        self.assertNotIn("mission_gate", legacy)
        self.assertEqual(self.controller.load("dev-wf-1")["status"], "DESIGN_REVIEW_REQUIRED")
        assessed = self.assess(mission_evidence())
        self.assertEqual(assessed["next"]["action"], "start_bounded_work")

    def test_each_trigger_requires_all_applicable_reviews_and_only_then_proceeds(self) -> None:
        cases = {"strategic_concern": ["strategic"],
                 "creative_production_authority": ["constitutional", "strategic", "unknown_unknown"],
                 "provider_media_transition": ["constitutional"],
                 "architecture_boundary": ["constitutional", "unknown_unknown"]}
        for trigger, required in cases.items():
            with self.subTest(trigger=trigger):
                evidence = mission_evidence(); evidence["triggers"] = [trigger]
                identifier = trigger.replace("_", "-")
                state = self.controller.initialize(identifier, self.base, 128, [], [], "Review trigger.", evidence)
                self.assertEqual(state["mission_gate"]["required_reviews"], required)
                for mechanism in required:
                    self.assertEqual(self.controller.execution_packet(identifier)["controller"]["next"]["action"],
                                     "request_design_review")
                    state = self.review(state, mechanism, "CONTINUE" if mechanism == "strategic" else "ACCEPT")
                packet = self.controller.execution_packet(identifier)
                self.assertEqual(packet["mission_gate"]["outcome"], "PROCEED")
                self.assertEqual(packet["controller"]["next"]["action"], "start_bounded_work")

    def test_active_decision_challenge_requires_existing_review_path(self) -> None:
        evidence = mission_evidence()
        evidence["active_decisions"] = [{
            "id": "DEC-0001", "disposition": "CHALLENGE",
            "rationale": "New evidence supports a different Film #1 experiment.",
        }, {"id": "DEC-0002", "disposition": "COMPLY",
            "rationale": "The revalidation guardrails remain applicable."}]
        state = self.controller.initialize("decision-challenge", self.base, 128, [], [],
                                           "Challenge an active decision.", evidence)
        self.assertEqual(state["mission_gate"]["required_reviews"], ["constitutional", "strategic"])
        self.assertEqual(self.controller.execution_packet("decision-challenge")["controller"]["next"],
                         {"action": "request_design_review", "human_boundary": True})
        state = self.review(state, "strategic", "CONTINUE_WITH_GUARDRAIL")
        state = self.review(state, "constitutional", "ACCEPT")
        packet = self.controller.execution_packet("decision-challenge")
        self.assertEqual(packet["mission_gate"]["outcome"], "PROCEED")
        self.assertEqual(packet["controller"]["next"]["action"], "start_bounded_work")

    def test_omitted_indexed_active_decision_fails_closed(self) -> None:
        index_path = self.root / "docs/architecture/decisions/index.json"
        second_record = self.root / "docs/architecture/decisions/DEC-0003-test.json"
        second = json.loads((self.root / "docs/architecture/decisions/DEC-0001-foundation-closure.json").read_text())
        second.update(id="DEC-0003", decision="A third active decision for omission testing.")
        second_record.write_text(json.dumps(second), encoding="utf-8")
        index = json.loads(index_path.read_text())
        index["decisions"].append({"id": "DEC-0003", "status": "ACTIVE",
                                   "record": "docs/architecture/decisions/DEC-0003-test.json"})
        index_path.write_text(json.dumps(index), encoding="utf-8")
        with self.assertRaisesRegex(MilestoneFailure, "exactly cover active decisions"):
            self.controller.initialize("omitted-decision", self.base, 128, [], [],
                                       "Omitted decision.", mission_evidence())
        evidence = mission_evidence()
        evidence["active_decisions"].append({"id": "DEC-0003", "disposition": "NOT_APPLICABLE",
                                             "rationale": "The test decision does not govern this slice."})
        state = self.controller.initialize("covered-decisions", self.base, 128, [], [],
                                           "All decisions covered.", evidence)
        self.assertEqual(state["mission_gate"]["outcome"], "PROCEED")

    def test_declared_consecutive_heartbeat_stalls_require_strategic_review(self) -> None:
        evidence = mission_evidence()
        evidence["heartbeat"] = [{"milestone_id": f"prior-{i}", "capability": "image", "advanced": False,
                                  "evidence": "README.md"} for i in range(3)]
        state = self.controller.initialize("dev-wf-1", self.base, 128, [], [], "Stalled production.", evidence)
        self.assertEqual(state["mission_gate"]["consecutive_no_advance"], 3)
        self.assertEqual(state["mission_gate"]["required_reviews"], ["strategic"])
        cleared = mission_evidence()
        state = self.assess(cleared)
        self.assertEqual(state["mission_gate"]["outcome"], "STRATEGIC_REVIEW_REQUIRED")
        state = self.review(state, "strategic", "CONTINUE_WITH_GUARDRAIL")
        self.assertEqual(state["mission_gate"]["outcome"], "PROCEED")
        # A same-rung observable improvement breaks the consecutive stall signal.
        evidence["heartbeat"][-1]["advanced"] = True
        state = self.controller.initialize("improvement", self.base, 128, [], [], "Image improvement.", evidence)
        self.assertEqual(state["mission_gate"]["consecutive_no_advance"], 0)
        self.assertEqual(state["mission_gate"]["outcome"], "PROCEED")

    def test_negative_dispositions_unknown_authority_and_reassessment_fail_closed(self) -> None:
        self.initialize()
        evidence = mission_evidence(); evidence["triggers"] = ["strategic_concern", "architecture_boundary"]
        state = self.assess(evidence)
        for disposition, expected in (("REMEDIATE_FIRST", "REVISE"),
                                      ("STRATEGIC_REASSESSMENT", "STRATEGIC_REVIEW_REQUIRED")):
            state = self.review(state, "strategic", disposition)
            self.assertEqual(state["mission_gate"]["outcome"], expected)
        state = self.review(state, "strategic", "CONTINUE")
        for disposition in ("REVISE", "REJECT"):
            state = self.review(state, "constitutional", disposition)
            self.assertEqual(state["mission_gate"]["outcome"], "REVISE")
        state = self.review(state, "constitutional", "ACCEPT")
        state = self.review(state, "unknown_unknown", "ACCEPT")
        self.assertEqual(state["mission_gate"]["outcome"], "PROCEED")
        for alignment in ("unknown", "conflicting"):
            evidence["authority_alignment"] = alignment
            state = self.assess(evidence)
            for mechanism in state["mission_gate"]["required_reviews"]:
                state = self.review(state, mechanism, "CONTINUE" if mechanism == "strategic" else "ACCEPT")
            self.assertEqual(state["mission_gate"]["outcome"], "STRATEGIC_REVIEW_REQUIRED")
        state = self.assess(mission_evidence())
        self.assertEqual(state["mission_gate"]["required_reviews"], ["constitutional", "strategic", "unknown_unknown"])
        self.assertEqual(state["mission_gate"]["outcome"], "STRATEGIC_REVIEW_REQUIRED")

    def test_malformed_evidence_wrong_reviews_and_stale_writers_leave_history_intact(self) -> None:
        initial = self.initialize()
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        malformed = []
        for key in mission_evidence():
            value = mission_evidence(); del value[key]; malformed.append(value)
        for key, value in (("triggers", ["unknown"]), ("authority_alignment", "approved"),
                           ("gap", "   "), ("heartbeat", []), ("production", True),
                           ("active_decisions", [{"id": "DEC-9999", "disposition": "COMPLY", "rationale": "Unknown."}])):
            evidence = mission_evidence(); evidence[key] = value; malformed.append(evidence)
        duplicate = mission_evidence(); duplicate["heartbeat"] *= 2; malformed.append(duplicate)
        for evidence in malformed:
            with self.subTest(evidence=evidence):
                before = history.read_bytes()
                with self.assertRaises(MilestoneFailure): self.assess(evidence)
                self.assertEqual(history.read_bytes(), before)
        evidence = mission_evidence(); evidence["triggers"] = ["strategic_concern"]
        state = self.assess(evidence)
        for mechanism, disposition in (("constitutional", "ACCEPT"), ("strategic", "ACCEPT")):
            before = history.read_bytes()
            with self.assertRaises(MilestoneFailure): self.review(state, mechanism, disposition)
            self.assertEqual(history.read_bytes(), before)
        with self.assertRaisesRegex(MilestoneFailure, "writer conflict"):
            self.controller.checkpoint("dev-wf-1", "mission_assessed", "Stale writer.",
                                       {"mission": evidence}, initial["generation"])
        with self.assertRaisesRegex(MilestoneFailure, "requires current generation"):
            self.controller.checkpoint("dev-wf-1", "mission_assessed", "No generation.", {"mission": evidence})
        with self.assertRaisesRegex(MilestoneFailure, "current assessment"):
            self.controller.checkpoint("dev-wf-1", "mission_reviewed", "Wrong assessment.",
                {"assessment_sha256": initial["mission_gate"]["assessment_sha256"],
                 "review": {"mechanism": "strategic", "disposition": "CONTINUE",
                            "owner": "project-owner", "evidence": "README.md"}}, state["generation"])

    def test_resealed_state_and_misbound_review_cannot_substitute_gate_evidence(self) -> None:
        self.initialize()
        evidence = mission_evidence(); evidence["triggers"] = ["strategic_concern"]
        assessed = self.assess(evidence)
        directory = self.root / ".vss/milestones/dev-wf-1"
        forged = json.loads(json.dumps(assessed))
        forged["mission_gate"]["outcome"] = "PROCEED"
        forged["status"] = "READY_FOR_IMPLEMENTATION"
        forged["next"] = {"action": "start_bounded_work", "human_boundary": False}
        self.controller._atomic_json(directory / "state.json", forged)
        self.controller._write_pointer(forged)
        with self.assertRaisesRegex(MilestoneFailure, "state conflict"):
            self.controller.execution_packet()
        self.controller._atomic_json(directory / "state.json", assessed)
        self.controller._write_pointer(assessed)
        reviewed = self.review(assessed, "strategic", "CONTINUE")
        events = self.controller._read_events("dev-wf-1")
        events[-1]["data"]["assessment_sha256"] = events[0]["event_sha256"]
        from vss_dev.milestone import _canonical, _digest
        unsigned = {key: value for key, value in events[-1].items() if key != "event_sha256"}
        events[-1]["event_sha256"] = _digest(unsigned)
        (directory / "history.ndjson").write_bytes(b"\n".join(_canonical(event) for event in events) + b"\n")
        reviewed["history_tail"]["sha256"] = events[-1]["event_sha256"]
        self.controller._atomic_json(directory / "state.json", reviewed)
        self.controller._write_pointer(reviewed)
        with self.assertRaisesRegex(MilestoneFailure, "current assessment"):
            self.controller.execution_packet()

    def test_cli_mission_review_path_uses_real_controller_and_packet(self) -> None:
        def run(*args: str) -> dict:
            result = subprocess.run(["vss", "dev", "milestone", *args], cwd=self.root,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        state = run("init", "--milestone-id", "cli-mission", "--base", self.base,
                    "--issue", "128", "--summary", "Mission gate.")
        self.assertEqual(state["next"]["action"], "request_design_review")
        source = self.root / ".vss/input.json"
        evidence = mission_evidence(); evidence["triggers"] = ["strategic_concern"]
        source.write_text(json.dumps({"mission": evidence}))
        state = run("checkpoint", "--milestone-id", "cli-mission", "--type", "mission_assessed",
                    "--input", str(source), "--summary", "Strategic concern.", "--expected-generation", "0")
        packet = run("next", "--packet", "--milestone-id", "cli-mission")
        self.assertEqual(packet["controller"]["next"]["action"], "request_design_review")
        source.write_text(json.dumps({"assessment_sha256": state["mission_gate"]["assessment_sha256"],
                                     "review": {"mechanism": "strategic", "disposition": "CONTINUE",
                                                "owner": "project-owner", "evidence": "README.md"}}))
        run("checkpoint", "--milestone-id", "cli-mission", "--type", "mission_reviewed",
            "--input", str(source), "--summary", "Review recorded.", "--expected-generation", "1")
        packet = run("next", "--packet", "--milestone-id", "cli-mission")
        self.assertEqual(packet["controller"]["next"]["action"], "start_bounded_work")
        self.assertEqual(packet["mission_gate"]["outcome"], "PROCEED")
        self.assertTrue(packet["stop_and_challenge"])

    def test_oversized_and_misplaced_mission_evidence_cannot_poison_history(self) -> None:
        self.initialize()
        history = self.root / ".vss/milestones/dev-wf-1/history.ndjson"
        before = history.read_bytes()
        evidence = mission_evidence()
        evidence["gap"] = "x" * 240
        evidence["observable_result"] = "x" * 240
        evidence["heartbeat"] = [{"milestone_id": f"prior-{i}", "capability": "image",
                                  "advanced": False, "evidence": "x" * 160} for i in range(5)]
        with self.assertRaisesRegex(MilestoneFailure, "exceeded its bound"):
            self.assess(evidence)
        with self.assertRaisesRegex(MilestoneFailure, "record is malformed"):
            self.controller.checkpoint("dev-wf-1", "checkpointed", "Hidden mission replacement.",
                                       {"mission": mission_evidence()})
        self.assertEqual(history.read_bytes(), before)
        with self.assertRaisesRegex(MilestoneFailure, "exceeded its bound"):
            self.controller.initialize("oversized", self.base, 128, [], [], "Oversized assessment.", evidence)
        self.assertFalse((self.root / ".vss/milestones/oversized/history.ndjson").exists())

    def test_legacy_ci_cycle_and_identity_recovery_preserve_mission_stop(self) -> None:
        from vss_dev.milestone import _canonical, _digest
        self.legacy_initialize()
        self.git("switch", "-c", "feature/dev-wf-1")
        self.controller.transition_branch("dev-wf-1", "main", "feature/dev-wf-1", "Legacy transition.", 0)
        changed = self.root / "src/demo/change.py"
        changed.parent.mkdir(parents=True); changed.write_text("value = 1\n")
        directory = self.root / ".vss/milestones/dev-wf-1"
        events = self.controller._read_events("dev-wf-1")
        tail = {"schema_version": "1", "protocol": "vss.dev-milestone", "record_kind": "event",
                "milestone_id": "dev-wf-1", "sequence": 3, "event_type": "validation_completed",
                "prior_event_sha256": events[-1]["event_sha256"], "subject_head_sha": self.base,
                "summary": "Legacy unbound validation.",
                "data": {"validation_level": "L3", "evidence_sha256": "a" * 64},
                "authority": events[0]["authority"]}
        tail["event_sha256"] = _digest(tail); events.append(tail)
        (directory / "history.ndjson").write_bytes(b"\n".join(_canonical(event) for event in events) + b"\n")
        repository = self.controller._repository(self.base)
        legacy = self.controller._project(events, repository, legacy=True)
        self.controller._atomic_json(directory / "state.json", legacy); self.controller._write_pointer(legacy)
        recovered = self.controller.recover_state_identity("dev-wf-1", "Legacy identity binding.", 2)
        self.assertEqual(recovered["status"], "DESIGN_REVIEW_REQUIRED")
        self.assertIsNone(recovered["validation"]["evidence_sha256"])
        self.controller.validate("canonical", "dev-wf-1")
        self.controller.ingest_ci({"head_sha": self.base, "checks": []}, "dev-wf-1")
        self.controller.checkpoint("dev-wf-1", "validation_completed", "Legacy canonical evidence.",
                                   {"validation_level": "L3", "evidence_sha256": "a" * 64})
        events = self.controller._read_events("dev-wf-1")
        legacy = self.controller._project(events, repository, legacy=True)
        self.assertEqual(legacy["status"], "REVIEW_READY")
        legacy.update(status="CI_PENDING", next={"action": "ingest_ci", "human_boundary": False},
                      routing={"model": self.controller.policy["model_routing"]["maintenance"], "advisory": True})
        self.controller._atomic_json(directory / "state.json", legacy); self.controller._write_pointer(legacy)
        self.assertEqual(self.controller.load()["status"], "DESIGN_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
