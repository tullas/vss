from __future__ import annotations

import json
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
                     "schemas/agent-harness-v2.schema.json", "schemas/agent-validation-evidence-v1.schema.json"):
            destination = self.root / path; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / path, destination)
        (self.root / "scripts").mkdir(); shutil.copy2(ROOT / "scripts/vss-agent", self.root / "scripts/vss-agent")
        (self.root / "scripts/vss-agent").chmod(0o755)
        (self.root / "scripts/validate-change.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        (self.root / "scripts/validate-change.sh").chmod(0o755)
        self.git("init", "-q", "-b", "main"); self.git("config", "user.name", "test"); self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/example/vss.git")
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
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

    def test_validation_evidence_is_reused_for_an_unchanged_source_change(self) -> None:
        self.initialize()
        first = self.controller.validate("affected", "dev-wf-1")
        second = self.controller.validate("affected", "dev-wf-1")
        self.assertEqual(first["status"], "passed")
        self.assertEqual(second["status"], "reused")
        self.assertEqual(first["evidence_sha256"], second["evidence_sha256"])

    def test_controller_has_no_runtime_provider_or_mutating_github_path(self) -> None:
        source = (ROOT / "src/vss_dev/milestone.py").read_text(encoding="utf-8")
        for forbidden in ("vss_runtime", "vss_providers", "git push", "git merge", "gh pr create", "shell=True", "--method"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
