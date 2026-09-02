import copy
import unittest

from vss_movie_storyboard.visual_production_set import (
    GroundedStoryboardShotBinding, create_scene_visual_production_set,
)
from vss_movie_storyboard.shot_binding import _KEY
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json
from vss_resource_contracts import ResourceContractError


def _binding(shot_id, card_digest, *, project="project-alpha", scene="scene-alpha"):
    lineage = {key: canonical_digest({"lineage": key}) for key in (
        "story_fragment", "scene_breakdown", "production_option_set", "review_packet",
        "review_decision", "creative_decision_revision", "canon_snapshot",
        "production_canon_binding", "shot_plan_draft", "storyboard_specification",
        "storyboard_frame")}
    value = {
        "schema_version": "1", "contract_identity": "grounded_storyboard_shot_binding",
        "contract_version": "1", "binding_status": "sealed_visual_basis_reference_only",
        "asset_id": "asset-" + "a" * 32, "asset_sha256": "b" * 64,
        "admission_sha256": "c" * 64, "project_id": project, "scene_id": scene,
        "shot_id": shot_id, "shot_plan_digest": "d" * 64,
        "shot_plan_complete_digest": "e" * 64, "shot_card_digest": card_digest,
        "frame_id": "frame-" + shot_id[-24:], "frame_grounding_sha256": "f" * 64,
        "source_repository_lineage": lineage, "approver_accountability_id": "reviewer",
        "rationale": "Bind this exact visual basis for scene review.",
        "authority": {key: False for key in (
            "binding_approval", "production_use", "production_approval", "final_shot_selection",
            "provider_execution", "runtime_execution", "generation", "regeneration", "publication",
            "export", "scheduling", "workflow_activation", "canon_decision", "rights_decision")},
        "limitations": ["single_shot_visual_basis_reference_only", "no_media_copying_or_storage",
                        "not_production_or_generation_authority", "not_provider_or_runtime_authority",
                        "not_publication_export_scheduling_or_workflow_authority", "not_canon_or_rights_authority"],
        "binding_sha256": "0" * 64,
    }
    value["binding_sha256"] = canonical_digest(value)
    return GroundedStoryboardShotBinding(_KEY, value)


class M107VisualProductionSetTests(unittest.TestCase):
    def setUp(self):
        cards = [canonical_digest({"card": ordinal}) for ordinal in (1, 2)]
        self.plan = {
            "schema_version": "1", "result_family": "scene_shot_plan_draft", "result_version": "1",
            "project_id": "project-alpha", "scene_id": "scene-alpha",
            "payload": {"ordered_shots": [{"shot_id": "shot-" + str(ordinal).zfill(24), "shot_card_digest": card}
                                           for ordinal, card in enumerate(cards, 1)], "shot_plan_digest": None},
            "integrity": {"payload_sha256": "0" * 64, "complete_result_sha256": "0" * 64},
        }
        self.plan["payload"]["shot_plan_digest"] = canonical_digest({**self.plan["payload"], "shot_plan_digest": None})
        self.plan["integrity"]["payload_sha256"] = canonical_digest(self.plan["payload"])
        self.plan["integrity"]["complete_result_sha256"] = canonical_digest({
            **self.plan, "integrity": {"payload_sha256": self.plan["integrity"]["payload_sha256"]},
        })
        self.bindings = [_binding(item["shot_id"], item["shot_card_digest"]) for item in self.plan["payload"]["ordered_shots"]]
        for binding in self.bindings:
            raw = binding.to_json_value()
            raw["shot_plan_digest"] = canonical_digest(self.plan)
            raw["shot_plan_complete_digest"] = self.plan["integrity"]["complete_result_sha256"]
            raw["binding_sha256"] = canonical_digest({**raw, "binding_sha256": "0" * 64})
            object.__setattr__(binding, "_value", freeze_json(raw))

    def test_deterministic_ordered_reference_set(self):
        first = create_scene_visual_production_set(self.bindings, self.plan,
            approver_accountability_id="reviewer", rationale="Approve this exact ordered scene visual basis set.")
        second = create_scene_visual_production_set(self.bindings, copy.deepcopy(self.plan),
            approver_accountability_id="reviewer", rationale="Approve this exact ordered scene visual basis set.")
        self.assertEqual(first.to_json_value(), second.to_json_value())
        self.assertTrue(all(not value for value in first.to_json_value()["authority"].values()))

    def test_reordered_and_resealed_card_substitution_fail_closed(self):
        with self.assertRaisesRegex(ResourceContractError, "missing, duplicated, stale, or reordered"):
            create_scene_visual_production_set(list(reversed(self.bindings)), self.plan,
                approver_accountability_id="reviewer", rationale="Order must remain authoritative.")
        forged = copy.deepcopy(self.bindings[0].to_json_value())
        forged["shot_card_digest"] = canonical_digest({"forged": True})
        forged["binding_sha256"] = canonical_digest({**forged, "binding_sha256": "0" * 64})
        forged_binding = GroundedStoryboardShotBinding(_KEY, forged)
        with self.assertRaisesRegex(ResourceContractError, "authoritative shot card"):
            create_scene_visual_production_set([forged_binding, self.bindings[1]], self.plan,
                approver_accountability_id="reviewer", rationale="Resealed substitution must fail closed.")


if __name__ == "__main__":
    unittest.main()
