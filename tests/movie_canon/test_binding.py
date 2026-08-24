import json
import unittest
from pathlib import Path

from vss_movie_canon import (
    bind_production_input_to_canon,
    create_canon_snapshot,
    create_creative_decision_revision,
)
from vss_movie_demo import prepare_demo
from vss_movie_option_review import record_option_review_decision
from vss_reasoning_contracts import canonical_digest
from vss_resource_contracts import (
    ResourceContractError,
    canon_snapshot_identity_material,
    canon_snapshot_seal_material,
    creative_decision_seal_material,
    validate_canon_snapshot,
    validate_creative_decision_revision,
)


STORY = Path(__file__).resolve().parents[1] / "fixtures/movie/story-fragment-valid.json"


def inputs(*, outcome="accept", option_index=0):
    prepared = prepare_demo(json.loads(STORY.read_text(encoding="utf-8")),
                            correlation_id="canon-test")
    option = prepared.option_set["payload"]["options"][option_index]
    decision = record_option_review_decision(
        prepared.review_packet, prepared.option_set, option_id=option["option_id"],
        reviewer_id="local.reviewer", outcome=outcome, rationale="Bounded review decision.",
        request_id="canon-test-decision", correlation_id="canon-test",
        environment="development",
    )
    return prepared, decision


def revision(prepared, decision, **overrides):
    values = dict(tenant_id="tenant-one", universe_id="universe-one")
    values.update(overrides)
    return create_creative_decision_revision(
        decision, prepared.review_packet, prepared.option_set, prepared.scene_breakdown,
        **values,
    )


class MovieCanonBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared, cls.decision = inputs()

    def test_deterministic_happy_path_preserves_exact_lineage_and_is_inert(self):
        first_decision = revision(self.prepared, self.decision)
        second_decision = revision(self.prepared, self.decision)
        first_canon = create_canon_snapshot(decisions=[first_decision], snapshot_version=1)
        second_canon = create_canon_snapshot(decisions=[second_decision], snapshot_version=1)
        first = bind_production_input_to_canon(
            self.decision, self.prepared.review_packet, self.prepared.option_set,
            self.prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one",
            decisions=[first_decision], canon_snapshot=first_canon)
        second = bind_production_input_to_canon(
            self.decision, self.prepared.review_packet, self.prepared.option_set,
            self.prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one",
            decisions=[second_decision], canon_snapshot=second_canon)
        self.assertEqual(first_decision, second_decision)
        self.assertEqual(first_canon, second_canon)
        self.assertEqual(first, second)
        self.assertEqual(first.value["decisions"], first_canon.value["decisions"])
        self.assertEqual(first.value["scope"]["production_id"],
                         self.prepared.option_set["project_id"])
        self.assertIn("not_runtime_authority", first.value["limitations"])
        self.assertIn("not_provider_authority", first.value["limitations"])
        self.assertNotIn("latest", json.dumps(first.to_json_value()))

    def test_scope_is_exact_and_cross_tenant_or_universe_fails(self):
        item = revision(self.prepared, self.decision)
        snapshot = create_canon_snapshot(decisions=[item], snapshot_version=1)
        for tenant, universe in (("tenant-two", "universe-one"),
                                 ("tenant-one", "universe-two")):
            with self.subTest(tenant=tenant, universe=universe), self.assertRaisesRegex(
                    ResourceContractError, "reconstruction mismatch"):
                bind_production_input_to_canon(
                    self.decision, self.prepared.review_packet, self.prepared.option_set,
                    self.prepared.scene_breakdown, tenant_id=tenant, universe_id=universe,
                    decisions=[item], canon_snapshot=snapshot)

    def test_new_revision_and_snapshot_leave_historical_values_unchanged(self):
        old = revision(self.prepared, self.decision)
        old_json = old.to_json_value()
        old_canon = create_canon_snapshot(decisions=[old], snapshot_version=1)
        old_canon_json = old_canon.to_json_value()
        changed_prepared, changed_review = inputs(option_index=1)
        newer = revision(changed_prepared, changed_review, revision=2, previous_revision=old)
        newer_canon = create_canon_snapshot(decisions=[newer], snapshot_version=2)
        binding = bind_production_input_to_canon(
            changed_review, changed_prepared.review_packet, changed_prepared.option_set,
            changed_prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one",
            decisions=[newer], canon_snapshot=newer_canon, previous_revision=old)
        self.assertEqual(newer.value["decision_id"], old.value["decision_id"])
        self.assertNotEqual(newer.value["decision_sha256"], old.value["decision_sha256"])
        self.assertNotEqual(newer_canon.value["canon_snapshot_id"], old_canon.value["canon_snapshot_id"])
        self.assertEqual(old.to_json_value(), old_json)
        self.assertEqual(old_canon.to_json_value(), old_canon_json)
        self.assertEqual(binding.value["decisions"][0]["revision"], 2)

    def test_nonaccepted_lifecycle_states_fail_closed(self):
        rejected_prepared, rejected_review = inputs(outcome="reject")
        rejected = revision(rejected_prepared, rejected_review)
        with self.assertRaises(ResourceContractError):
            create_canon_snapshot(decisions=[rejected], snapshot_version=1)
        accepted = revision(self.prepared, self.decision)
        for state in ("deprecated", "superseded"):
            candidate = revision(self.prepared, self.decision, revision=2, status=state,
                                 previous_revision=accepted)
            with self.subTest(state=state), self.assertRaises(ResourceContractError):
                create_canon_snapshot(decisions=[candidate], snapshot_version=2)

    def test_validly_resealed_decision_and_canon_substitutions_fail(self):
        authoritative = revision(self.prepared, self.decision)
        snapshot = create_canon_snapshot(decisions=[authoritative], snapshot_version=1)
        other_prepared, other_review = inputs(option_index=1)
        substituted = revision(other_prepared, other_review)
        with self.assertRaisesRegex(ResourceContractError, "reconstruction mismatch"):
            bind_production_input_to_canon(
                self.decision, self.prepared.review_packet, self.prepared.option_set,
                self.prepared.scene_breakdown, tenant_id="tenant-one", universe_id="universe-one",
                decisions=[substituted], canon_snapshot=snapshot)
        forged = snapshot.to_json_value()
        forged["decisions"] = [{
            "decision_id": substituted.value["decision_id"],
            "revision": substituted.value["revision"],
            "decision_sha256": substituted.value["decision_sha256"],
            "status": "accepted", "scene_id": substituted.value["scope"]["scene_id"],
        }]
        forged["canon_snapshot_id"] = "canon-" + canonical_digest(
            canon_snapshot_identity_material(forged))[:32]
        forged["canon_sha256"] = canonical_digest(canon_snapshot_seal_material(forged))
        with self.assertRaisesRegex(ResourceContractError, "authoritative binding mismatch"):
            validate_canon_snapshot(forged, decisions=[authoritative])

        resealed = authoritative.to_json_value()
        resealed["evidence_references"] = ["forged-evidence"]
        resealed["decision_sha256"] = canonical_digest(creative_decision_seal_material(resealed))
        seal_only = validate_creative_decision_revision(resealed)
        with self.assertRaisesRegex(ResourceContractError, "authoritative"):
            create_canon_snapshot(decisions=[seal_only], snapshot_version=1)

    def test_missing_duplicate_or_altered_bindings_fail(self):
        item = revision(self.prepared, self.decision)
        with self.assertRaisesRegex(ResourceContractError, "requires a decision"):
            create_canon_snapshot(decisions=[], snapshot_version=1)
        with self.assertRaises(ResourceContractError):
            create_canon_snapshot(decisions=[item, item], snapshot_version=1)
        newer = revision(self.prepared, self.decision, revision=2, previous_revision=item)
        with self.assertRaisesRegex(ResourceContractError, "one revision"):
            create_canon_snapshot(decisions=[item, newer], snapshot_version=2)
        value = item.to_json_value()
        value["semantic_payload"]["option_content_digest"] = "f" * 64
        with self.assertRaisesRegex(ResourceContractError, "seal mismatch"):
            validate_creative_decision_revision(value)


if __name__ == "__main__":
    unittest.main()
