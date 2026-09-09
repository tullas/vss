import copy
import hashlib
import json
import unittest
from pathlib import Path

from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_storyboard import (
    bind_existing_media_to_current_shot, complete_existing_media_revalidation,
    prepare_existing_media_revalidation,
)
from vss_resource_contracts import ResourceContractError, validate_existing_media_revalidation_evidence
from vss_movie_contracts import validate_existing_media_current_shot_binding
from vss_reasoning_contracts import canonical_digest

ROOT = Path(__file__).resolve().parents[2]
STORY = json.loads((ROOT / "tests/fixtures/movie/vikramaditya-opening-story-fragment.json").read_text())
DURABLE_REVIEW = json.loads((ROOT / "docs/reviews/m11-0-existing-media-revalidation.json").read_text())
DURABLE_CURRENT_REVIEW = json.loads((ROOT / "docs/reviews/m11-0-existing-media-revalidation-current.json").read_text())
DURABLE_BINDING = json.loads((ROOT / "docs/reviews/m11-0-existing-media-current-shot-binding.json").read_text())
# The contract boundary accepts bytes and verifies their digest.  Keep this
# test independent of host-local Runtime output; the retained production SHA
# is asserted from the durable review artifact above.
MEDIA = b"deterministic existing-media revalidation test bytes\n"
SCENE, SHOT, FRAME, OPTION = "scene-91f5c8634519d8264e2dd5f8", "shot-024b0d6352149eabb74df543", "frame-fb0d79ba59d7781b0bad3e7e", "option-b5d2461f4ec95dc0377938ba"

def lineage(result, story_digest):
    return {"story_fragment": story_digest,
            "scene_breakdown": result["scene_breakdown"]["integrity"]["payload_sha256"],
            "production_option_set": result["scene_production_option_set"]["integrity"]["complete_result_sha256"],
            "review_packet": result["review_packet"]["integrity"]["complete_result_sha256"],
            "review_decision": result["review_decision"]["integrity"]["complete_result_sha256"],
            "creative_decision_revision": result["creative_decision_revision"]["decision_sha256"],
            "canon_snapshot": result["canon_snapshot"]["canon_sha256"],
            "production_canon_binding": result["production_canon_binding"]["result_sha256"],
            "shot_plan_draft": result["scene_shot_plan_draft"]["integrity"]["complete_result_sha256"],
            "storyboard_specification": result["scene_storyboard_specification"]["integrity"]["complete_result_sha256"],
            "storyboard_frame": result["scene_storyboard_specification"]["payload"]["ordered_frames"][1]["frame_specification_digest"]}

class ExistingMediaRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepared = prepare_demo(STORY, correlation_id="m11-revalidation")
        cls.result = finish_demo(prepared, option_id=OPTION, reviewer_id="source.preparation", rationale="accepted source", correlation_id="m11-revalidation", include_storyboard=True)
        target = {"project_id":"vikramaditya-local", "scene_id":SCENE, "shot_id":SHOT, "frame_id":FRAME, "option_id":OPTION,
                  "shot_card_digest":"8dd0e25e170f90776b406ffafea95f5e10179bd131072cf79ecb283bd1a3635b", "frame_specification_digest":"4ff516866b0123661613c2d47aec059ee802822fcf22776314cca7a1ad5f12d6", "storyboard_specification_digest":"e5f9a09e9bb0744d9587975fa40012483dbf94d370aa7e639cc0285ce4c5f75c", "lineage":lineage(cls.result, canonical_digest(prepared.story))}
        hist = {"candidate_sha256":"525ee34d08f175d562672fd53b8ee4d0c2a119fcabde338da7c1c49c84e0771c", "grounding_review_sha256":"5f01af93619f7410f6525df8502497e48b234df9eabc37e087787f05abf51f04", "promotion_sha256":"0"*64, "admission_sha256":"0"*64, "catalog_asset_sha256":"0"*64, "lineage":dict(target["lineage"])}
        cls.target, cls.hist = target, hist
        cls.pending = prepare_existing_media_revalidation(media=MEDIA, media_reference="local-review/candidate-1/image.png", historical_only=hist, current_target=target)

    def test_pending_artifact_verifies_bytes_and_requires_new_review(self):
        self.assertEqual("2d23736bce6f76def26416841b81806262c0a172e29b6d994f140e4a39eb55aa",  # pragma: allowlist secret -- durable immutable media SHA
                         DURABLE_REVIEW["media"]["media_sha256"])
        self.assertEqual(hashlib.sha256(MEDIA).hexdigest(), self.pending.to_json_value()["media"]["media_sha256"])
        with self.assertRaisesRegex(ResourceContractError, "digest mismatch"):
            validate_existing_media_revalidation_evidence(self.pending.to_json_value(), media=b"tampered")
        with self.assertRaisesRegex(ResourceContractError, "requires completed new human review"):
            bind_existing_media_to_current_shot(self.pending, media=MEDIA, current_target=self.target)

    def test_tampering_and_resealed_wrong_current_lineage_fail(self):
        bad = copy.deepcopy(self.pending.to_json_value()); bad["media"]["media_sha256"] = "0"*64
        with self.assertRaisesRegex(ResourceContractError, "identity mismatch|seal mismatch"):
            validate_existing_media_revalidation_evidence(bad, media=MEDIA)
        bad = copy.deepcopy(self.pending.to_json_value()); bad["current_authoritative_target"]["scene_id"] = "scene-wrong"
        bad["revalidation_sha256"] = hashlib.sha256(json.dumps({**bad, "revalidation_sha256":"0"*64}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaisesRegex(ResourceContractError, "current shot binding requires completed new human review|current authoritative lineage mismatch|seal mismatch"):
            bind_existing_media_to_current_shot(self.pending, media=MEDIA, current_target=self.target)

    def test_historical_review_cannot_be_reused_and_authority_is_closed(self):
        old = self.pending.to_json_value()["historical_only"]["candidate_sha256"]
        review = {"review_sha256":"0"*64, "candidate_sha256":old, "scene_id":SCENE, "shot_id":SHOT, "frame_id":FRAME, "option_id":OPTION, "disposition":"USE", "reviewer_accountability_id":"human"}
        review["review_sha256"] = hashlib.sha256(json.dumps({**review, "review_sha256":"0"*64}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.assertRaisesRegex(ResourceContractError, "historical"):
            complete_existing_media_revalidation(self.pending, review=review)
        self.assertTrue(all(value is False for value in self.pending.to_json_value()["authority"].values()))

    def test_wrong_scene_shot_frame_option_and_missing_review_are_closed(self):
        review = {"review_sha256":"0"*64, "candidate_sha256":"6"*64, "scene_id":SCENE, "shot_id":SHOT, "frame_id":FRAME, "option_id":OPTION, "disposition":"USE", "reviewer_accountability_id":"human"}
        review["review_sha256"] = hashlib.sha256(json.dumps({**review, "review_sha256":"0"*64}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        completed = complete_existing_media_revalidation(self.pending, review=review)
        for key, value in (("scene_id", "scene-aaaaaaaaaaaaaaaaaaaaaaaa"), ("shot_id", "shot-aaaaaaaaaaaaaaaaaaaaaaaa"), ("frame_id", "frame-aaaaaaaaaaaaaaaaaaaaaaaa"), ("option_id", "option-aaaaaaaaaaaaaaaaaaaaaaaa")):
            target = copy.deepcopy(self.target); target[key] = value
            with self.assertRaisesRegex(ResourceContractError, "lineage mismatch"):
                bind_existing_media_to_current_shot(completed, media=MEDIA, current_target=target)

    def test_completed_use_review_admits_separate_current_shot_binding(self):
        review = {"review_sha256":"0"*64, "candidate_sha256":"6"*64, "scene_id":SCENE, "shot_id":SHOT, "frame_id":FRAME, "option_id":OPTION, "disposition":"USE", "reviewer_accountability_id":"human"}
        review["review_sha256"] = hashlib.sha256(json.dumps({**review, "review_sha256":"0"*64}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        completed = complete_existing_media_revalidation(self.pending, review=review)
        binding = bind_existing_media_to_current_shot(completed, media=MEDIA, current_target=self.target).to_json_value()
        self.assertEqual("existing_media_current_shot_binding", binding["contract_identity"])
        self.assertEqual("sealed_current_visual_basis_reference_only", binding["binding_status"])
        self.assertEqual(review["review_sha256"], binding["human_review_sha256"])
        self.assertTrue(all(value is False for value in binding["authority"].values()))

    def test_durable_current_review_and_binding_are_admitted_and_distinct(self):
        checked = validate_existing_media_revalidation_evidence(DURABLE_CURRENT_REVIEW)
        binding = validate_existing_media_current_shot_binding(DURABLE_BINDING)
        self.assertEqual("revalidated_review_only", checked.value["status"])
        self.assertEqual("USE", checked.value["human_grounding_review"]["disposition"])
        self.assertNotEqual(DURABLE_CURRENT_REVIEW["human_grounding_review"]["candidate_sha256"],
                            DURABLE_CURRENT_REVIEW["historical_only"]["candidate_sha256"])
        self.assertEqual(checked.value["revalidation_sha256"], binding.value["revalidation_sha256"])
        self.assertEqual(checked.value["human_grounding_review"]["review_sha256"], binding.value["human_review_sha256"])
        self.assertTrue(all(value is False for value in checked.value["authority"].values()))
        self.assertTrue(all(value is False for value in binding.value["authority"].values()))

if __name__ == "__main__": unittest.main()
