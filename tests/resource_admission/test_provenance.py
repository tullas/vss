import copy
import json
import unittest
from pathlib import Path

from vss_movie_canon import (
    bind_production_input_to_canon, create_canon_snapshot,
    create_creative_decision_revision,
)
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_pictorial import admit_pictorial_frame
from vss_reasoning_contracts import canonical_digest
from vss_resource_admission import (
    create_media_provenance_request, create_production_artifact,
    create_storyboard_review_frame_provenance,
)
from vss_resource_contracts import (
    ResourceContractError, media_provenance_request_seal_material,
    validate_media_provenance_view,
)
from tests.resource_test_support import pictorial_png


STORY = Path(__file__).resolve().parents[1] / "fixtures/movie/story-fragment-valid.json"


def authoritative_chain(*, tenant_id="tenant-one", universe_id="universe-one",
                        option_index=0, rights_reference="rights-reference-one"):
    prepared = prepare_demo(json.loads(STORY.read_text(encoding="utf-8")),
                            correlation_id=f"m95-{tenant_id}-{option_index}")
    option_id = prepared.review_packet["payload"]["review_entries"][option_index]["option_id"]
    finished = finish_demo(
        prepared, option_id=option_id, reviewer_id="m95.reviewer",
        rationale="Accepted for deterministic provenance testing.",
        correlation_id=f"m95-{tenant_id}-{option_index}", include_storyboard=True)
    decision = create_creative_decision_revision(
        finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"],
        tenant_id=tenant_id, universe_id=universe_id)
    canon = create_canon_snapshot(decisions=[decision], snapshot_version=1)
    binding = bind_production_input_to_canon(
        finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"],
        tenant_id=tenant_id, universe_id=universe_id, decisions=[decision],
        canon_snapshot=canon)
    storyboard = finished["scene_storyboard_specification"]
    frame_id = storyboard["payload"]["ordered_frames"][0]["frame_id"]
    pictorial = admit_pictorial_frame(
        finished["review_decision"], finished["review_packet"],
        finished["scene_production_option_set"], finished["scene_breakdown"],
        finished["scene_shot_plan_draft"], storyboard, frame_id=frame_id,
        environment="development")
    artifact = create_production_artifact(
        pictorial_frame=pictorial, resource_revision=1, tenant_id=tenant_id,
        universe_id=universe_id, content=pictorial_png(),
        ownership_class="customer_owned", rights_status="confirmed",
        permissions=["use_in_source_production", "reuse_as_universe_visual_reference"],
        restrictions=["no_training", "no_redistribution", "no_publication"],
        rights_reference=rights_reference)
    return finished, decision, canon, binding, pictorial, artifact


def arguments(chain):
    finished, decision, canon, binding, pictorial, artifact = chain
    request = create_media_provenance_request(
        production_artifact=artifact, decision_revision=decision,
        canon_snapshot=canon, production_canon_binding=binding,
        pictorial_frame=pictorial)
    return request, {
        "decision_data": finished["review_decision"],
        "review_packet_data": finished["review_packet"],
        "option_set_data": finished["scene_production_option_set"],
        "scene_breakdown_data": finished["scene_breakdown"],
        "decision_revision": decision, "canon_snapshot": canon,
        "production_canon_binding": binding,
        "shot_plan_data": finished["scene_shot_plan_draft"],
        "storyboard_data": finished["scene_storyboard_specification"],
        "admitted_pictorial_frame": pictorial, "production_artifact": artifact,
        "content": pictorial_png(),
    }


class MediaProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chain = authoritative_chain()

    def test_real_path_is_deterministic_inert_and_evidence_qualified(self):
        request, kwargs = arguments(self.chain)
        historical = [json.dumps(item.to_json_value(), sort_keys=True)
                      for item in self.chain[1:4] + self.chain[5:6]]
        first = create_storyboard_review_frame_provenance(
            request.to_json_value(), **kwargs)
        second = create_storyboard_review_frame_provenance(
            request.to_json_value(), **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(9, len(first.value["lineage"]))
        self.assertEqual("identity_and_provenance",
                         first.value["reproducibility"]["level"])
        self.assertFalse(first.value["reproducibility"]["exact_byte_replay_claimed"])
        self.assertEqual("caller_supplied_not_persisted",
                         first.value["preservation"]["payload_availability"])
        self.assertIn("provider_identity", first.value["unavailable_evidence"])
        serialized = json.dumps(first.to_json_value())
        for forbidden in ("latest", "timestamp", "storage_path"):
            self.assertNotIn(forbidden, serialized)
        for limitation in ("not_runtime_authority", "not_regeneration_authority",
                           "not_export_or_publication_authority",
                           "not_storage_or_deletion_authority", "not_rights_authority"):
            self.assertIn(limitation, first.value["limitations"])
        self.assertEqual(historical, [json.dumps(item.to_json_value(), sort_keys=True)
                                     for item in self.chain[1:4] + self.chain[5:6]])

    def test_scope_and_resealed_request_substitution_fail_closed(self):
        request, kwargs = arguments(self.chain)
        for field, replacement in (("tenant_id", "tenant-two"),
                                   ("universe_id", "universe-two"),
                                   ("production_id", "production-two"),
                                   ("scene_id", "scene-two")):
            with self.subTest(field=field):
                changed = request.to_json_value()
                changed["scope"][field] = replacement
                changed["request_sha256"] = canonical_digest(
                    media_provenance_request_seal_material(changed))
                with self.assertRaisesRegex(ResourceContractError,
                                            "reconstruction|authoritative"):
                    create_storyboard_review_frame_provenance(changed, **kwargs)

    def test_validly_resealed_artifact_and_rights_substitution_are_rejected(self):
        request, kwargs = arguments(self.chain)
        alternate = authoritative_chain(rights_reference="alternate-rights")[-1]
        changed = dict(kwargs)
        changed["production_artifact"] = alternate
        with self.assertRaisesRegex(ResourceContractError, "reconstruction|binding"):
            create_storyboard_review_frame_provenance(request.to_json_value(), **changed)

    def test_alternate_movie_chain_and_changed_content_are_rejected(self):
        request, kwargs = arguments(self.chain)
        _, alternate_kwargs = arguments(authoritative_chain(option_index=1))
        with self.assertRaises(ResourceContractError):
            create_storyboard_review_frame_provenance(
                request.to_json_value(), **alternate_kwargs)
        changed = dict(kwargs)
        changed["content"] = b"changed"
        with self.assertRaises(ResourceContractError):
            create_storyboard_review_frame_provenance(
                request.to_json_value(), **changed)

    def test_missing_authority_and_tampered_view_are_rejected(self):
        request, kwargs = arguments(self.chain)
        missing = dict(kwargs)
        missing["production_canon_binding"] = None
        with self.assertRaisesRegex(ResourceContractError, "incomplete"):
            create_storyboard_review_frame_provenance(request.to_json_value(), **missing)
        view = create_storyboard_review_frame_provenance(
            request.to_json_value(), **kwargs).to_json_value()
        view["reproducibility"]["exact_byte_replay_claimed"] = True
        with self.assertRaises(ResourceContractError):
            validate_media_provenance_view(view)

    def test_contract_is_closed(self):
        request, kwargs = arguments(self.chain)
        view = create_storyboard_review_frame_provenance(
            request.to_json_value(), **kwargs).to_json_value()
        view["output"]["storage_key"] = "frames/one.png"
        with self.assertRaises(ResourceContractError):
            validate_media_provenance_view(view)


if __name__ == "__main__":
    unittest.main()
