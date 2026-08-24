import json
import unittest
from pathlib import Path

from vss_movie_canon import (
    assess_production_binding_impact, bind_production_input_to_canon,
    create_canon_snapshot, create_creative_decision_revision,
    create_dependency_impact_request,
)
from vss_movie_demo import prepare_demo
from vss_movie_option_review import record_option_review_decision
from vss_reasoning_contracts import canonical_digest
from vss_resource_contracts import (
    ResourceContractError, dependency_impact_request_seal_material,
    validate_dependency_impact_request, validate_dependency_impact_result,
)


STORY = Path(__file__).resolve().parents[1] / "fixtures/movie/story-fragment-valid.json"


def reviewed(option_index):
    prepared = prepare_demo(json.loads(STORY.read_text(encoding="utf-8")),
                            correlation_id="impact-test")
    option = prepared.option_set["payload"]["options"][option_index]
    decision = record_option_review_decision(
        prepared.review_packet, prepared.option_set, option_id=option["option_id"],
        reviewer_id="local.reviewer", outcome="accept", rationale="Impact test acceptance.",
        request_id=f"impact-decision-{option_index}", correlation_id="impact-test",
        environment="development")
    return prepared, decision


def movie_arguments(prefix, prepared, decision, revision, canon, binding=None):
    result = {
        f"{prefix}_decision_data": decision, f"{prefix}_packet_data": prepared.review_packet,
        f"{prefix}_option_set_data": prepared.option_set,
        f"{prefix}_breakdown_data": prepared.scene_breakdown,
        f"{prefix}_decision_revision": revision, f"{prefix}_canon_snapshot": canon,
    }
    if binding is not None:
        result["prior_binding"] = binding
    return result


class DependencyImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior_prepared, cls.prior_review = reviewed(0)
        cls.prior_revision = create_creative_decision_revision(
            cls.prior_review, cls.prior_prepared.review_packet, cls.prior_prepared.option_set,
            cls.prior_prepared.scene_breakdown, tenant_id="tenant-one",
            universe_id="universe-one")
        cls.prior_canon = create_canon_snapshot(decisions=[cls.prior_revision], snapshot_version=1)
        cls.prior_binding = bind_production_input_to_canon(
            cls.prior_review, cls.prior_prepared.review_packet, cls.prior_prepared.option_set,
            cls.prior_prepared.scene_breakdown, tenant_id="tenant-one",
            universe_id="universe-one", decisions=[cls.prior_revision],
            canon_snapshot=cls.prior_canon)
        cls.changed_prepared, cls.changed_review = reviewed(1)
        cls.changed_revision = create_creative_decision_revision(
            cls.changed_review, cls.changed_prepared.review_packet,
            cls.changed_prepared.option_set, cls.changed_prepared.scene_breakdown,
            tenant_id="tenant-one", universe_id="universe-one", revision=2,
            previous_revision=cls.prior_revision)
        cls.changed_canon = create_canon_snapshot(
            decisions=[cls.changed_revision], snapshot_version=2)

    def arguments(self, candidate_prepared=None, candidate_review=None,
                  candidate_revision=None, candidate_canon=None):
        result = movie_arguments("prior", self.prior_prepared, self.prior_review,
                                 self.prior_revision, self.prior_canon, self.prior_binding)
        result.update(movie_arguments(
            "candidate", candidate_prepared or self.prior_prepared,
            candidate_review or self.prior_review, candidate_revision or self.prior_revision,
            candidate_canon or self.prior_canon))
        return result

    def request(self, candidate_revision=None, candidate_canon=None):
        return create_dependency_impact_request(
            prior_binding=self.prior_binding, prior_canon_snapshot=self.prior_canon,
            prior_decision_revision=self.prior_revision,
            candidate_canon_snapshot=candidate_canon or self.prior_canon,
            candidate_decision_revision=candidate_revision or self.prior_revision)

    def test_unchanged_is_deterministic_and_inert(self):
        request = self.request()
        first = assess_production_binding_impact(request.to_json_value(), **self.arguments())
        second = assess_production_binding_impact(request.to_json_value(), **self.arguments())
        self.assertEqual(first, second)
        self.assertEqual("unaffected", first.value["classification"])
        self.assertEqual("exact_dependencies_unchanged", first.value["reason_code"])
        self.assertTrue(all(not item["changed"] for item in first.value["evidence"]))
        serialized = json.dumps(first.to_json_value())
        self.assertNotIn("latest", serialized)
        self.assertNotIn("timestamp", serialized)
        self.assertIn("not_runtime_authority", serialized)
        self.assertIn("not_regeneration_authority", serialized)

    def test_genuine_changed_revision_and_canon_affect_old_binding_without_mutation(self):
        historical = tuple(json.dumps(item.to_json_value(), sort_keys=True) for item in (
            self.prior_revision, self.prior_canon, self.prior_binding))
        request = self.request(self.changed_revision, self.changed_canon)
        args = self.arguments(self.changed_prepared, self.changed_review,
                              self.changed_revision, self.changed_canon)
        args["candidate_previous_revision"] = self.prior_revision
        result = assess_production_binding_impact(request.to_json_value(), **args)
        self.assertEqual("affected_reassessment_required", result.value["classification"])
        self.assertTrue(all(item["changed"] for item in result.value["evidence"]))
        self.assertEqual(historical, tuple(json.dumps(item.to_json_value(), sort_keys=True)
                                          for item in (self.prior_revision, self.prior_canon,
                                                       self.prior_binding)))
        self.assertIn("not_historical_invalidation", result.value["limitations"])

    def test_missing_evidence_and_scope_mismatch_fail_closed(self):
        request = self.request()
        missing = self.arguments()
        missing["prior_binding"] = None
        result = assess_production_binding_impact(request.to_json_value(), **missing)
        self.assertEqual("prior_authoritative_chain_incomplete", result.value["reason_code"])
        for field, replacement in (
                ("tenant_id", "tenant-two"), ("universe_id", "universe-two"),
                ("production_id", "production-two"), ("scene_id", "scene-two")):
            with self.subTest(field=field):
                changed_scope = request.to_json_value()
                changed_scope["scope"][field] = replacement
                changed_scope["request_sha256"] = canonical_digest(
                    dependency_impact_request_seal_material(changed_scope))
                scoped = assess_production_binding_impact(changed_scope, **self.arguments())
                self.assertEqual("incomplete_fail_closed", scoped.value["classification"])
                self.assertEqual("scope_mismatch", scoped.value["reason_code"])

    def test_malformed_or_resealed_request_cannot_manufacture_impact(self):
        malformed = self.request().to_json_value()
        malformed["candidate_decision"]["revision"] = 2
        with self.assertRaisesRegex(ResourceContractError, "impact_request_invalid"):
            validate_dependency_impact_request(malformed)
        malformed["request_sha256"] = canonical_digest(
            dependency_impact_request_seal_material(malformed))
        result = assess_production_binding_impact(malformed, **self.arguments())
        self.assertEqual("dependency_identity_ambiguous", result.value["reason_code"])

        tampered_result = assess_production_binding_impact(
            self.request().to_json_value(), **self.arguments()).to_json_value()
        tampered_result["evidence"][0]["changed"] = True
        with self.assertRaisesRegex(ResourceContractError, "impact_result_invalid"):
            validate_dependency_impact_result(tampered_result)

    def test_validly_resealed_alternate_upstream_chain_is_not_authoritative(self):
        alternate_prepared, alternate_review = reviewed(1)
        alternate = create_creative_decision_revision(
            alternate_review, alternate_prepared.review_packet, alternate_prepared.option_set,
            alternate_prepared.scene_breakdown, tenant_id="tenant-one",
            universe_id="universe-one")
        alternate_canon = create_canon_snapshot(decisions=[alternate], snapshot_version=1)
        args = self.arguments()
        args["prior_decision_revision"] = alternate
        args["prior_canon_snapshot"] = alternate_canon
        result = assess_production_binding_impact(self.request().to_json_value(), **args)
        self.assertEqual("incomplete_fail_closed", result.value["classification"])
        self.assertEqual("prior_authoritative_chain_incomplete", result.value["reason_code"])


if __name__ == "__main__":
    unittest.main()
