from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.movie_storyboard.test_m8_0 import bundle, execute as execute_storyboard, reseal_storyboard
from vss_commands import CommandRunner, ExitCode
from vss_movie_pictorial import admit_pictorial_frame
from vss_movie_pictorial.service import _depiction_projection
from vss_providers import PictorialFrameRequest
from vss_reasoning_contracts.canonicalization import thaw_json
from vss_runtime import RuntimeController


ROOT = Path(__file__).resolve().parents[2]
CREATIVE_FREEDOMS = {
    "composition", "focal_hierarchy", "depth_of_field", "negative_space",
    "time_consistent_lighting_nuance", "atmospheric_treatment", "non_semantic_texture",
    "camera_interpretation_within_shot_scale",
}


class M83DepictionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        self.values = bundle(knowledge=True)
        self.storyboard = execute_storyboard(self.values)["scene_storyboard_specification"]
        self.frame = self.storyboard["payload"]["ordered_frames"][2]
        self.admitted = admit_pictorial_frame(
            *self.values, self.storyboard, frame_id=self.frame["frame_id"], environment="development",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def payload(self):
        value = dict(zip(
            ("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), self.values,
        ))
        value.update(storyboard=self.storyboard, frame_id=self.frame["frame_id"])
        return value

    def provider_request(self, projection):
        return PictorialFrameRequest(
            self.admitted.project_id, self.admitted.scene_id,
            self.admitted.storyboard_specification_digest, self.admitted.frame_id,
            self.admitted.frame_specification_digest, self.admitted.semantic_request_digest,
            self.admitted.provider_visible_digest, projection,
        )

    def test_mira_detail_preserves_relationship_context_and_ambiguity(self):
        projection = self.admitted.projection
        facts = " ".join(projection["depictable_facts"]).casefold()
        emphasis = " ".join(projection["required_narrative_emphasis"]).casefold()
        context = projection["narrative_context"]
        for value in ("mira", "lantern", "locked gate"):
            self.assertIn(value, facts)
            self.assertIn(value, emphasis)
        self.assertEqual(context["characters"], ("mira",))
        self.assertEqual(context["locations"], ("courtyard",))
        self.assertEqual(context["time_indicators"], ("dawn",))
        self.assertEqual(projection["shot"], {"purpose": "detail_or_transition", "scale_constraint": "close_detail"})
        self.assertIn("The significance of the lantern is not established.", projection["deliberate_ambiguities"])
        self.assertNotIn("Hold space for", emphasis)

    def test_control_plane_and_production_unknowns_are_structurally_unreachable(self):
        projection = self.admitted.projection
        self.assertEqual(set(projection), {
            "depictable_facts", "required_narrative_emphasis", "narrative_context",
            "deliberate_ambiguities", "creative_degrees_of_freedom", "shot",
            "prohibited_contradictions", "depiction_instructions", "output",
        })
        serialized = json.dumps(thaw_json(projection)).casefold()
        for text in (
            "review status", "approval state", "human determination", "feasibility", "cost",
            "rights", "provider execution", "workflow state", "specification status", "tbd",
            "validated frame specification", "bounded_minimal_stage", "shot feasibility",
        ):
            self.assertNotIn(text, serialized)
        self.assertNotIn("source fragment may not be complete", serialized)
        self.assertNotIn("production approval", serialized)

    def test_freedoms_are_closed_candidate_only_and_cannot_reclassify_facts(self):
        projection = self.admitted.projection
        self.assertEqual(set(projection["creative_degrees_of_freedom"]), CREATIVE_FREEDOMS)
        self.assertTrue(set(projection["depictable_facts"]).isdisjoint(CREATIVE_FREEDOMS))
        with self.assertRaises(TypeError):
            projection["creative_degrees_of_freedom"] = ("invent_character",)
        with self.assertRaises(TypeError):
            projection["narrative_context"]["characters"] = ()
        injected = {**self.payload(), "creative_degrees_of_freedom": ["invent_character"]}
        response, code = CommandRunner(runtime_controller=RuntimeController(root=self.root)).run(
            "movie.generate-pictorial-frame", "development", injected, "m83-injection",
        )
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)

    def test_digest_is_deterministic_and_resealed_substitution_still_fails(self):
        again = admit_pictorial_frame(
            *self.values, self.storyboard, frame_id=self.frame["frame_id"], environment="development",
        )
        self.assertEqual(self.admitted.provider_visible_digest, again.provider_visible_digest)
        self.assertEqual(self.admitted.semantic_request_digest, again.semantic_request_digest)
        forged = copy.deepcopy(self.storyboard)
        forged["payload"]["ordered_frames"][2]["action"] = "Invent a canonical answer."
        reseal_storyboard(forged)
        value = self.payload(); value["storyboard"] = forged
        response, code = CommandRunner(runtime_controller=RuntimeController(root=self.root)).run(
            "movie.generate-pictorial-frame", "development", value, "m83-forgery",
        )
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)

    def test_real_local_path_remains_offline_and_non_authoritative(self):
        with patch("socket.socket.connect") as connect:
            response, code = CommandRunner(runtime_controller=RuntimeController(root=self.root)).run(
                "movie.generate-pictorial-frame", "development", self.payload(), "m83-local",
            )
        connect.assert_not_called()
        self.assertEqual(code, 0, response)
        output = response["output"]
        self.assertEqual(output["provider_call_count"], 1)
        self.assertTrue(all(value is False for value in output["authority_boundary"].values()))
        self.assertTrue((self.root / output["artifact_path"]).is_file())

    def test_local_provider_rejects_every_malformed_projection_shape(self):
        provider = self.controller_provider()
        media = provider.generate(self.provider_request(self.admitted.projection))
        self.assertEqual((media.width, media.height), (640, 360))

        mutations = {
            "extra_top_level": lambda p: p.update(extra="value"),
            "extra_nested_context": lambda p: p["narrative_context"].update(extra="value"),
            "extra_nested_output": lambda p: p["output"].update(extra="value"),
            "extra_nested_facts": lambda p: p.update(depictable_facts={"items": p["depictable_facts"], "extra": "value"}),
            "extra_nested_shot": lambda p: p["shot"].update(extra="value"),
            "missing_context_field": lambda p: p["narrative_context"].pop("locations"),
            "wrong_nested_type": lambda p: p.update(narrative_context=[]),
            "additional_freedom": lambda p: p.update(creative_degrees_of_freedom=tuple((*p["creative_degrees_of_freedom"], "invent_character"))),
            "malformed_freedom": lambda p: p.update(creative_degrees_of_freedom=tuple((*p["creative_degrees_of_freedom"][:-1], 7))),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                projection = thaw_json(self.admitted.projection)
                mutable = _freeze_for_request(projection)
                mutate(mutable)
                with self.assertRaises(ValueError):
                    provider.generate(self.provider_request(mutable))

    def test_projection_preserves_unicode_without_keyword_classification(self):
        projection = _depiction_projection({
            "source_observations": [{"text": "ミラは夜明けの中庭を横切る。"}],
            "events": [{"text": "ميرا تجد فانوسًا بجانب البوابة المغلقة."}],
            "declared_characters": ["Мира"], "declared_locations": ["中庭"],
            "time_indicators": ["الفجر"], "unknowns": ["灯籠の意味は未確定。"],
        }, {"shot_purpose": "detail_or_transition"})
        self.assertIn("ミラは夜明けの中庭を横切る。", projection["depictable_facts"])
        self.assertEqual(projection["required_narrative_emphasis"],
                         ("ميرا تجد فانوسًا بجانب البوابة المغلقة.",))
        self.assertEqual(projection["narrative_context"]["characters"], ("Мира",))
        self.assertEqual(projection["deliberate_ambiguities"], ("灯籠の意味は未確定。",))

    def controller_provider(self):
        controller = RuntimeController(root=self.root)
        registration = controller.provider_registry.resolve("movie.storyboard-image.local")
        return controller.provider_registry.initialize(registration)


def _freeze_for_request(value):
    if isinstance(value, dict):
        return {key: _freeze_for_request(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_freeze_for_request(item) for item in value)
    return value


if __name__ == "__main__":
    unittest.main()
