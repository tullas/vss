from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from vss_assurance.service import (
    AssuranceAssessmentError,
    BASE_OBLIGATIONS,
    RESULT_SCHEMA,
    assess_registered_shot_plan,
)
from vss_movie_canon import (
    bind_production_input_to_canon,
    create_canon_snapshot,
    create_creative_decision_revision,
)
from vss_movie_demo import prepare_demo
from vss_movie_option_review import record_option_review_decision
from vss_reasoning_contracts import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
STORY = ROOT / "tests/fixtures/movie/story-fragment-valid.json"
REQUEST = {
    "schema_version": "1",
    "protocol": "vss.assurance-assessment-request",
    "task_identity": "create_scene_shot_plan_draft/1",
    "result_identity": "scene_shot_plan_draft/1",
}


def reviewed(option_index: int, request_id: str):
    prepared = prepare_demo(json.loads(STORY.read_text(encoding="utf-8")),
                            correlation_id="assurance-integration")
    option = prepared.option_set["payload"]["options"][option_index]
    decision = record_option_review_decision(
        prepared.review_packet, prepared.option_set, option_id=option["option_id"],
        reviewer_id="local.reviewer", outcome="accept", rationale="Assurance path review.",
        request_id=request_id, correlation_id="assurance-integration", environment="development")
    return prepared, decision


class FakeController:
    policy_digest = "1" * 64

    def __init__(self, state):
        self.state = state

    def load(self, milestone_id=None):
        return self.state

    def _active_decisions(self):
        return {"DEC-0001"}, "2" * 64


class AssuranceFitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior_prepared, cls.prior_decision = reviewed(0, "assurance-prior")
        cls.prior_revision = create_creative_decision_revision(
            cls.prior_decision, cls.prior_prepared.review_packet, cls.prior_prepared.option_set,
            cls.prior_prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one")
        cls.prior_canon = create_canon_snapshot(decisions=[cls.prior_revision], snapshot_version=1)
        cls.prior_binding = bind_production_input_to_canon(
            cls.prior_decision, cls.prior_prepared.review_packet, cls.prior_prepared.option_set,
            cls.prior_prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one",
            decisions=[cls.prior_revision], canon_snapshot=cls.prior_canon)
        cls.changed_prepared, cls.changed_decision = reviewed(1, "assurance-candidate")
        cls.changed_revision = create_creative_decision_revision(
            cls.changed_decision, cls.changed_prepared.review_packet, cls.changed_prepared.option_set,
            cls.changed_prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one",
            revision=2, previous_revision=cls.prior_revision)
        cls.changed_canon = create_canon_snapshot(
            decisions=[cls.changed_revision], snapshot_version=2)

    def setUp(self):
        self.head = "a" * 40
        self.base = "b" * 40
        self.change_identity = "c" * 64
        self.repository = {
            "name_with_owner": "tullas/vss", "base_sha": self.base,
            "head_sha": self.head, "branch": "feature/assurance-fixture",
            "change_identity": self.change_identity,
        }
        self.state = {
            "status": "WORKING", "repository": self.repository,
            "history_tail": {"sha256": "d" * 64},
            "mission_gate": {"outcome": "PROCEED", "assessment_sha256": "3" * 64},
            "validation": {"level": "L0"},
            "ci": {"status": "passed", "head_sha": self.head},
        }
        self.obligations = sorted(BASE_OBLIGATIONS | {"resource.canon_decisions"})

    def dependency_arguments(self, changed=False):
        candidate_prepared = self.changed_prepared if changed else self.prior_prepared
        candidate_decision = self.changed_decision if changed else self.prior_decision
        candidate_revision = self.changed_revision if changed else self.prior_revision
        candidate_canon = self.changed_canon if changed else self.prior_canon
        return {
            "prior_decision_data": self.prior_decision,
            "prior_packet_data": self.prior_prepared.review_packet,
            "prior_option_set_data": self.prior_prepared.option_set,
            "prior_breakdown_data": self.prior_prepared.scene_breakdown,
            "prior_decision_revision": self.prior_revision,
            "prior_canon_snapshot": self.prior_canon,
            "prior_binding": self.prior_binding,
            "candidate_decision_data": candidate_decision,
            "candidate_packet_data": candidate_prepared.review_packet,
            "candidate_option_set_data": candidate_prepared.option_set,
            "candidate_breakdown_data": candidate_prepared.scene_breakdown,
            "candidate_decision_revision": candidate_revision,
            "candidate_canon_snapshot": candidate_canon,
            "prior_previous_revision": None,
            "candidate_previous_revision": self.prior_revision if changed else None,
        }

    def plan(self, *, scope="exact_registered_subject", unknown=(), missing=()):
        return {
            "schema_version": "2", "map_sha256": "e" * 64,
            "changed_paths": ["docs/movie-scene-breakdown.md"], "domains": ["architecture"],
            "minimum_level": "L0", "risk": "docs", "profiles": ["harness-l0"],
            "human_gate_required": False, "unknown_paths": list(unknown),
            "coverage": {"rule_patterns": ["docs/**"], "obligations": self.obligations,
                         "effect_scope": scope, "missing_rules": list(missing)},
            "authority": {"runtime_execution": False, "provider_execution": False,
                          "merge": False, "push": False},
        }

    def invoke(self, *, changed=False, state=None, candidate_plan=None, base_plan=None,
               dependency_arguments=None):
        controller = FakeController(state or self.state)
        with patch("vss_assurance.service.MilestoneController", return_value=controller), \
             patch("vss_assurance.service._impact", side_effect=[candidate_plan or self.plan(),
                                                                  base_plan or self.plan()]):
            return assess_registered_shot_plan(
                REQUEST, dependency_arguments=dependency_arguments or self.dependency_arguments(changed),
                repository_root=ROOT, milestone_id="assurance-fitness-change-impact-v1")

    def test_real_story_review_to_shot_plan_chain_avoids_duplicate_reassurance(self):
        historical_binding = self.prior_binding.to_json_value()
        result = self.invoke()
        self.assertEqual("fit", result["assurance_fitness"])
        self.assertEqual("unaffected", result["change_impact"])
        self.assertIn("exact_dependencies_unchanged", result["reason_codes"])
        self.assertEqual(historical_binding, self.prior_binding.to_json_value())

    def test_changed_accepted_decision_forces_reassessment_of_old_binding(self):
        historical_binding = self.prior_binding.to_json_value()
        result = self.invoke(changed=True)
        self.assertEqual("additional_assurance_required", result["assurance_fitness"])
        self.assertEqual("affected_reassessment_required", result["change_impact"])
        self.assertIn("selected_dependency_changed", result["reason_codes"])
        self.assertEqual(historical_binding, self.prior_binding.to_json_value())

    def test_substituted_valid_revision_is_reconstructed_and_fails_closed(self):
        arguments = self.dependency_arguments()
        arguments["candidate_decision_revision"] = self.changed_revision
        result = self.invoke(dependency_arguments=arguments)
        self.assertEqual("incomplete_fail_closed", result["assurance_fitness"])
        self.assertEqual("incomplete_fail_closed", result["change_impact"])
        self.assertIn("authoritative_chain_incomplete", result["reason_codes"])

    def test_caller_cannot_supply_scope_action_or_dependency_subset(self):
        request = {**REQUEST, "impact_scope": "repository_only"}
        with patch("vss_assurance.service.MilestoneController",
                   return_value=FakeController(self.state)):
            with self.assertRaises(AssuranceAssessmentError):
                assess_registered_shot_plan(request, dependency_arguments=self.dependency_arguments(),
                                            repository_root=ROOT)
        incomplete = self.dependency_arguments()
        del incomplete["candidate_canon_snapshot"]
        result = self.invoke(dependency_arguments=incomplete)
        self.assertEqual("incomplete_fail_closed", result["assurance_fitness"])
        self.assertEqual("incomplete_fail_closed", result["change_impact"])

    def test_unknown_authority_alignment_and_missing_coverage_fail_closed(self):
        unknown_state = {**self.state,
                         "mission_gate": {"outcome": "REVISE", "assessment_sha256": "3" * 64}}
        result = self.invoke(state=unknown_state)
        self.assertEqual("incomplete_fail_closed", result["assurance_fitness"])
        missing = self.plan(missing=("docs/**",))
        result = self.invoke(candidate_plan=missing)
        self.assertEqual("incomplete_fail_closed", result["change_impact"])
        self.assertIn("coverage_rule_missing", result["reason_codes"])

    def test_shared_impact_and_rights_obligations_never_claim_unaffected(self):
        shared = self.plan(scope="all_affected_subjects")
        result = self.invoke(candidate_plan=shared)
        self.assertEqual("incomplete_fail_closed", result["change_impact"])
        rights = self.plan()
        rights["coverage"]["obligations"] = sorted(
            set(rights["coverage"]["obligations"]) | {"resource.rights_eligibility"})
        result = self.invoke(candidate_plan=rights)
        self.assertEqual("incomplete_fail_closed", result["change_impact"])

    def test_stale_validation_or_ci_cannot_yield_fit(self):
        state = {**self.state, "validation": {"level": "none"},
                 "ci": {"status": "passed", "head_sha": "f" * 40}}
        result = self.invoke(state=state)
        self.assertEqual("additional_assurance_required", result["assurance_fitness"])
        self.assertEqual("unaffected", result["change_impact"])
        self.assertIn("validation_level_insufficient", result["reason_codes"])
        self.assertIn("ci_required", result["reason_codes"])

    def test_result_is_closed_and_authority_is_constant_false(self):
        result = self.invoke()
        schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(result)))
        self.assertEqual({key: False for key in result["authority"]}, result["authority"])
        altered = {**result, "runtime_execution": True}
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(altered)))
        self.assertEqual(result, self.invoke())

    def test_harness_coverage_is_closed_for_every_supported_impact_rule(self):
        mapping = json.loads((ROOT / "config/agent-harness-v2.json").read_text(encoding="utf-8"))
        allowed = {
            "repo.impact_union", "milestone.validation", "mission.alignment",
            "mission.review_receipts", "ci.exact_head", "resource.canon_decisions",
            "resource.rights_eligibility", "schema.consumer_closure",
            "dependency.subject_enumeration", "security.l3_review",
            "policy.controller_self_change", "workflow.exact_ci",
        }
        self.assertLessEqual(len(mapping["impact_rules"]), 64)
        self.assertEqual(sorted(rule["pattern"] for rule in mapping["impact_rules"]),
                         sorted(set(rule["pattern"] for rule in mapping["impact_rules"])))
        for rule in mapping["impact_rules"]:
            with self.subTest(pattern=rule["pattern"]):
                self.assertEqual({"pattern", "domain", "minimum_level", "risk", "profiles",
                                  "obligations", "effect_scope"}, set(rule))
                self.assertTrue(BASE_OBLIGATIONS.issubset(set(rule["obligations"])))
                self.assertLessEqual(set(rule["obligations"]), allowed)
                self.assertLessEqual(len(rule["obligations"]), 16)
                self.assertIn(rule["effect_scope"],
                              {"exact_registered_subject", "all_affected_subjects"})
        by_pattern = {rule["pattern"]: set(rule["obligations"])
                      for rule in mapping["impact_rules"]}
        self.assertIn("resource.rights_eligibility", by_pattern["src/vss_resource_admission/**"])
        self.assertIn("resource.canon_decisions", by_pattern["src/vss_movie_canon/**"])
        self.assertIn("security.l3_review", by_pattern["security/**"])
        self.assertIn("policy.controller_self_change", by_pattern["src/vss_dev/**"])
        self.assertIn("workflow.exact_ci", by_pattern[".github/**"])
        self.assertIn("schema.consumer_closure", by_pattern["schemas/**"])


if __name__ == "__main__":
    unittest.main()
