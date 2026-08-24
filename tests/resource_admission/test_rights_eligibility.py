import copy
import json
import unittest
from pathlib import Path

from vss_movie_canon import bind_production_input_to_canon, create_canon_snapshot, create_creative_decision_revision
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_pictorial import admit_pictorial_frame
from vss_reasoning_contracts import canonical_digest
from vss_resource_admission import (
    admit_storyboard_frame_to_universe, create_media_provenance_request,
    create_production_artifact, create_resource_resolution_request,
    create_rights_eligibility_reassessment_request, create_storyboard_review_frame_provenance,
    create_universe_admission, reassess_storyboard_visual_reference_rights,
    resolve_universe_visual_reference,
)
from vss_resource_contracts import (
    rights_eligibility_request_seal_material, validate_rights_eligibility_reassessment_request,
)
from tests.resource_test_support import pictorial_png


STORY = Path(__file__).resolve().parents[1] / "fixtures/movie/story-fragment-valid.json"
CONTENT = pictorial_png()


def chain():
    prepared = prepare_demo(json.loads(STORY.read_text(encoding="utf-8")), correlation_id="m96")
    option_id = prepared.review_packet["payload"]["review_entries"][0]["option_id"]
    finished = finish_demo(prepared, option_id=option_id, reviewer_id="m96.reviewer",
                           rationale="M9.6 real-path test.", correlation_id="m96", include_storyboard=True)
    decision = create_creative_decision_revision(finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"], tenant_id="tenant-one", universe_id="universe-one")
    canon = create_canon_snapshot(decisions=[decision], snapshot_version=1)
    binding = bind_production_input_to_canon(finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"], tenant_id="tenant-one",
        universe_id="universe-one", decisions=[decision], canon_snapshot=canon)
    storyboard = finished["scene_storyboard_specification"]
    pictorial = admit_pictorial_frame(finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"], finished["scene_shot_plan_draft"],
        storyboard, frame_id=storyboard["payload"]["ordered_frames"][0]["frame_id"], environment="development")
    source = create_production_artifact(pictorial_frame=pictorial, resource_revision=1, tenant_id="tenant-one",
        universe_id="universe-one", content=CONTENT, ownership_class="customer_owned", rights_status="confirmed",
        permissions=["use_in_source_production", "reuse_as_universe_visual_reference"],
        restrictions=["no_training", "no_redistribution", "no_publication"], rights_reference="rights-reference-one")
    admission = create_universe_admission(source_artifact=source, destination_tenant_id="tenant-one", destination_universe_id="universe-one")
    asset = admit_storyboard_frame_to_universe(source, source_content=CONTENT, admission_request=admission).asset
    request = create_resource_resolution_request(source_artifact=source, admission=admission, asset=asset,
        source_content=CONTENT, tenant_id="tenant-one", universe_id="universe-one", production_id="production-two")
    resolution = resolve_universe_visual_reference(source_artifact=source, admission=admission, asset=asset,
        source_content=CONTENT, request=request, tenant_id="tenant-one", universe_id="universe-one", production_id="production-two").resource
    provenance_request = create_media_provenance_request(production_artifact=source, decision_revision=decision,
        canon_snapshot=canon, production_canon_binding=binding, pictorial_frame=pictorial)
    provenance = create_storyboard_review_frame_provenance(provenance_request.to_json_value(), decision_data=finished["review_decision"],
        review_packet_data=finished["review_packet"], option_set_data=finished["scene_production_option_set"], scene_breakdown_data=finished["scene_breakdown"],
        decision_revision=decision, canon_snapshot=canon, production_canon_binding=binding, shot_plan_data=finished["scene_shot_plan_draft"],
        storyboard_data=storyboard, admitted_pictorial_frame=pictorial, production_artifact=source, content=CONTENT)
    return source, admission, asset, request, resolution, provenance


def reassessment(values, **overrides):
    source, admission, asset, request, resolution, _ = values
    data = dict(source_artifact=source, source_content=CONTENT, admission=admission, asset=asset,
        resolution_request=request, resolution_result=resolution, tenant_id="tenant-one", universe_id="universe-one",
        production_id="production-two", candidate_evidence_revision=1, candidate_evidence_reference="rights-evidence-one",
        candidate_status="confirmed", candidate_revocation="active",
        candidate_permissions=["reuse_as_universe_visual_reference", "use_in_source_production"],
        candidate_restrictions=["no_training", "no_redistribution", "no_publication"], candidate_rights_reference="rights-reference-one")
    data.update(overrides)
    return create_rights_eligibility_reassessment_request(**data)


def assess(values, request, **overrides):
    source, admission, asset, resolution_request, resolution, _ = values
    data = dict(source_artifact=source, source_content=CONTENT, admission=admission, asset=asset,
        resolution_request=resolution_request, resolution_result=resolution, tenant_id="tenant-one",
        universe_id="universe-one", production_id="production-two")
    data.update(overrides)
    return reassess_storyboard_visual_reference_rights(request.to_json_value() if hasattr(request, "to_json_value") else request, **data)


class RightsEligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = chain()

    def test_real_path_is_deterministic_and_preserves_history(self):
        request = reassessment(self.values)
        historical = [json.dumps(value.to_json_value(), sort_keys=True) for value in self.values]
        first, second = assess(self.values, request), assess(self.values, request)
        self.assertTrue(first.assessed)
        self.assertEqual("eligible_unchanged", first.result.value["classification"])
        self.assertEqual(first.result, second.result)
        self.assertEqual(historical, [json.dumps(value.to_json_value(), sort_keys=True) for value in self.values])
        self.assertIn("not_runtime_authority", first.result.value["limitations"])

    def test_required_rights_changes_are_ineligible_and_uncertainty_fails_closed(self):
        cases = [
            ({"candidate_permissions": ["use_in_source_production"]}, "required_permission_removed", "ineligible_new_use"),
            ({"candidate_restrictions": ["no_reuse"]}, "applicable_no_reuse_added", "ineligible_new_use"),
            ({"candidate_revocation": "revoked"}, "authoritative_rights_revoked", "ineligible_new_use"),
            ({"candidate_status": "unknown"}, "candidate_rights_unknown", "incomplete_fail_closed"),
            ({"candidate_status": "conflicting"}, "candidate_rights_conflicting", "incomplete_fail_closed"),
        ]
        for overrides, code, classification in cases:
            with self.subTest(code=code):
                result = assess(self.values, reassessment(self.values, **overrides))
                self.assertEqual(code, result.code)
                self.assertEqual(classification, result.result.value["classification"])

    def test_unrelated_candidate_change_does_not_invalidate_and_scope_is_exact(self):
        result = assess(self.values, reassessment(self.values, candidate_restrictions=["no_training"]))
        self.assertEqual("unrelated_rights_change_eligibility_unchanged", result.code)
        wrong = assess(self.values, reassessment(self.values), production_id="production-three")
        self.assertEqual("scope_mismatch", wrong.code)

    def test_resealed_request_and_candidate_substitutions_fail_closed(self):
        request = reassessment(self.values).to_json_value()
        request["source"]["resource_revision"] = 2
        request["request_sha256"] = canonical_digest(rights_eligibility_request_seal_material(request))
        changed = validate_rights_eligibility_reassessment_request(request)
        self.assertEqual("authoritative_chain_incomplete", assess(self.values, changed).code)
        request = reassessment(self.values).to_json_value()
        request["candidate_rights"]["subject"]["artifact_id"] = "artifact-" + "f" * 32
        request["candidate_rights"]["evidence_sha256"] = canonical_digest({**request["candidate_rights"], "evidence_sha256": "0" * 64})
        request["request_sha256"] = canonical_digest(rights_eligibility_request_seal_material(request))
        changed = validate_rights_eligibility_reassessment_request(request)
        self.assertEqual("candidate_subject_mismatch", assess(self.values, changed).code)


if __name__ == "__main__":
    unittest.main()
