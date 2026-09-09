"""Real deterministic source reconstruction for the Issue #132 prerequisite."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vss_movie_contracts import validate_story_fragment
from vss_movie_controlled_generation import (
    admit_controlled_generation, issue_approval, load_sealed_grounded_admission, verify_approval,
)
from vss_movie_controlled_generation import admit_grounded_controlled_generation
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_visual_grounding import create_grounded_movie_route, create_production_visual_grounding_profile
from vss_movie_storyboard_render import admit_storyboard_render
from vss_commands.runner import CommandRunner
from vss_runtime import RuntimeController
from vss_runtime.audit import AuditLogger
from vss_runtime.external_preflight import ExternalExecutionPreflight
from vss_resource_contracts import ResourceContractError
from vss_resource_contracts.validation import validate_production_visual_grounding_profile


ROOT = Path(__file__).resolve().parents[2]
STORY = ROOT / "tests/fixtures/movie/vikramaditya-opening-story-fragment.json"
OPTION_ID = "option-b5d2461f4ec95dc0377938ba"
SCENE_ID = "scene-91f5c8634519d8264e2dd5f8"
SHOT_ID = "shot-024b0d6352149eabb74df543"
SHOT_CARD_DIGEST = "8dd0e25e170f90776b406ffafea95f5e10179bd131072cf79ecb283bd1a3635b"  # pragma: allowlist secret
FRAME_ID = "frame-fb0d79ba59d7781b0bad3e7e"
FRAME_DIGEST = "4ff516866b0123661613c2d47aec059ee802822fcf22776314cca7a1ad5f12d6"  # pragma: allowlist secret
STORYBOARD_DIGEST = "e5f9a09e9bb0744d9587975fa40012483dbf94d370aa7e639cc0285ce4c5f75c"  # pragma: allowlist secret
PROFILE_PATH = ROOT / "docs/reviews/m11-0-authoritative-visual-grounding-profile.json"
SEALED_CANDIDATE_2_PATH = ROOT / "docs/reviews/m11-0-candidate-2-sealed-admission.json"
SEALED_CANDIDATE_1_PATH = ROOT / "docs/reviews/m11-0-candidate-1-sealed-admission.json"
PROFILE_SHA = "51e785c899f7331e51c7583edc4558f779864236dfa1501e826ace994a71b903"  # pragma: allowlist secret


class M110VikramadityaSourceTests(unittest.TestCase):
    def _load_authoritative_profile(self):
        value = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return create_production_visual_grounding_profile(
            profile_id=value["profile_id"], revision=value["revision"],
            tenant_id=value["scope"]["tenant_id"], universe_id=value["scope"]["universe_id"],
            production_id=value["scope"]["production_id"], mode=value["mode"],
            scene_ids=value["applicability"]["scene_ids"],
            character_ids=value["applicability"]["character_ids"], groups=value["groups"],
            uncertainty=value["uncertainty"], conflicts=value["conflicts"],
            limitations=value["limitations"], evidence_references=value["evidence_references"],
            lifecycle=value["lifecycle"],
            reviewer_accountability_id=value["reviewer_accountability_id"],
        ).to_json_value()

    def test_persisted_authoritative_profile_seals_and_binds_candidate_one(self):
        profile = self._load_authoritative_profile()
        self.assertEqual(profile["profile_sha256"], PROFILE_SHA)
        mutated = copy.deepcopy(profile)
        mutated["groups"][0]["positive_constraints"][0] += " changed"
        mutated["profile_sha256"] = "0" * 64
        with self.assertRaisesRegex(ResourceContractError, "seal mismatch"):
            validate_production_visual_grounding_profile(mutated)
        story = json.loads(STORY.read_text(encoding="utf-8"))
        _prepared, result = self._run_real_path(story)
        route = create_grounded_movie_route(
            result["review_decision"], result["review_packet"],
            result["scene_production_option_set"], result["scene_breakdown"],
            result["creative_decision_revision"], result["canon_snapshot"],
            result["production_canon_binding"], result["scene_shot_plan_draft"],
            result["scene_storyboard_specification"], profile_data=profile,
        )
        admitted = admit_grounded_controlled_generation(
            story, result["review_decision"], result["review_packet"],
            result["scene_production_option_set"], result["scene_breakdown"],
            result["creative_decision_revision"], result["canon_snapshot"],
            result["production_canon_binding"], result["scene_shot_plan_draft"],
            result["scene_storyboard_specification"], profile_data=profile,
            grounded_creative_decision_data=route.creative_decision.to_json_value(),
            grounded_canon_snapshot_data=route.canon_snapshot.to_json_value(),
            grounded_canon_binding_data=route.canon_binding.to_json_value(),
            grounded_shot_plan_data=route.shot_plan.to_json_value(),
            grounded_storyboard_data=route.storyboard.to_json_value(),
            frame_id=FRAME_ID, environment="development",
        )
        request = admitted.request_json()
        self.assertEqual(request["contract_version"], "3")
        self.assertEqual(request["projection"]["visual_grounding_profile_sha256"], PROFILE_SHA)

    def test_sealed_candidate_two_handoff_is_exact_and_mutation_safe(self):
        material = json.loads(SEALED_CANDIDATE_2_PATH.read_text(encoding="utf-8"))
        kwargs = dict(
            expected_request_sha256="a471323eec0b3d3c69897447a5bb6d1922023cf09825a4910eed687514108d54",
            expected_provider_request_sha256="de2dfa6860117de59be5cb0202764b4e930f88187694d386415fc91dad7759a3",
            expected_profile_sha256=PROFILE_SHA, expected_variation_identity="comparison-candidate-2",
            expected_variation_ordinal=2, expected_option_id=OPTION_ID, expected_scene_id=SCENE_ID,
            expected_shot_id=SHOT_ID, expected_frame_id=FRAME_ID,
        )
        admitted = load_sealed_grounded_admission(material, **kwargs)
        self.assertEqual(admitted.request_json()["request_sha256"], kwargs["expected_request_sha256"])
        mutated = copy.deepcopy(material)
        mutated["binding"]["shot_id"] = "shot-other"
        with self.assertRaisesRegex(Exception, "binding mismatch"):
            load_sealed_grounded_admission(mutated, **kwargs)
        mutated = copy.deepcopy(material)
        mutated["request"]["candidate_variation"]["ordinal"] = 1
        with self.assertRaisesRegex(Exception, "seal mismatch|binding mismatch|does not match its contract"):
            load_sealed_grounded_admission(mutated, **kwargs)

    def test_sealed_candidate_one_host_binding_is_exact(self):
        material = json.loads(SEALED_CANDIDATE_1_PATH.read_text(encoding="utf-8"))
        kwargs = dict(
            expected_request_sha256="3ebdeced6133e558f26f4c6174580174ed7a070b31cd5749f5dd7800692691e6",  # pragma: allowlist secret
            expected_provider_request_sha256="dd30b2dd121ed50d58fc7fa057cf8f0fc6ab75ae310e6c76e8030f4ff85d0f84",  # pragma: allowlist secret
            expected_profile_sha256=PROFILE_SHA, expected_variation_identity="comparison-candidate-1",
            expected_variation_ordinal=1, expected_option_id=OPTION_ID, expected_scene_id=SCENE_ID,
            expected_shot_id=SHOT_ID, expected_frame_id=FRAME_ID,
        )
        admitted = load_sealed_grounded_admission(material, **kwargs)
        self.assertEqual(admitted.request_json()["contract_version"], "3")
        self.assertEqual(admitted.request_json()["bounds"]["maximum_provider_attempts"], 1)
        self.assertEqual(admitted.request_json()["bounds"]["maximum_cost_usd"], "0.100000")
        mutated = copy.deepcopy(material)
        mutated["request"]["candidate_variation"]["ordinal"] = 2
        with self.assertRaisesRegex(Exception, "seal mismatch|binding mismatch|does not match its contract"):
            load_sealed_grounded_admission(mutated, **kwargs)

    def test_host_handoff_never_uses_base_consumed_candidate(self):
        material = json.loads(SEALED_CANDIDATE_2_PATH.read_text(encoding="utf-8"))
        material["request"]["request_sha256"] = "030d0851a453eb9552981e575cc4664b264391e479a24dc6d5b7c80d6c71d4a3"
        with self.assertRaises(Exception):
            load_sealed_grounded_admission(
                material, expected_request_sha256="a471323eec0b3d3c69897447a5bb6d1922023cf09825a4910eed687514108d54",
                expected_provider_request_sha256="de2dfa6860117de59be5cb0202764b4e930f88187694d386415fc91dad7759a3",
                expected_profile_sha256=PROFILE_SHA, expected_variation_identity="comparison-candidate-2",
                expected_variation_ordinal=2, expected_option_id=OPTION_ID, expected_scene_id=SCENE_ID,
                expected_shot_id=SHOT_ID, expected_frame_id=FRAME_ID,
            )

    def _run_real_path(self, story: dict, *, option_id: str | None = OPTION_ID):
        prepared = prepare_demo(story, correlation_id="vikramaditya-source")
        if option_id is None:
            option_id = prepared.review_packet["payload"]["review_entries"][0]["option_id"]
        return prepared, finish_demo(
            prepared, option_id=option_id, reviewer_id="source.preparation",
            rationale="Accepted at human review for a local shot-plan draft demo.",
            correlation_id="vikramaditya-source", include_storyboard=True,
        )

    def _admit_primary_request(self, *, option_id: str = OPTION_ID):
        story = json.loads(STORY.read_text(encoding="utf-8"))
        _prepared, result = self._run_real_path(story, option_id=option_id)
        frame = result["scene_storyboard_specification"]["payload"]["ordered_frames"][1]
        return admit_controlled_generation(
            story, result["review_decision"], result["review_packet"],
            result["scene_production_option_set"], result["scene_breakdown"],
            result["creative_decision_revision"], result["canon_snapshot"],
            result["production_canon_binding"], result["scene_shot_plan_draft"],
            result["scene_storyboard_specification"], frame_id=frame["frame_id"],
            environment="development",
        )

    def test_exact_vikramaditya_scene_and_selected_shot_reconstruct_from_source(self):
        story = json.loads(STORY.read_text(encoding="utf-8"))
        validated = validate_story_fragment(story).to_json_value()
        prepared, result = self._run_real_path(story)

        self.assertEqual(validated["fragment_id"], "fragment-vikramaditya-opening-001")
        self.assertEqual(validated["project_id"], "vikramaditya-local")
        self.assertEqual(validated["payload"]["rights_qualification"], "original")
        self.assertEqual(validated["payload"]["cultural_qualification"], "legendary")
        scene = result["scene_breakdown"]["payload"]["ordered_scenes"]
        self.assertEqual([item["scene_id"] for item in scene], [SCENE_ID])
        shots = result["scene_shot_plan_draft"]["payload"]["ordered_shots"]
        selected = [item for item in shots if item["shot_id"] == SHOT_ID]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["shot_card_digest"], SHOT_CARD_DIGEST)
        frames = result["scene_storyboard_specification"]["payload"]["ordered_frames"]
        self.assertEqual(
            (frames[0]["source_shot_id"], frames[0]["frame_id"]),
            ("shot-5ba90f12605541ae415b4acc", "frame-79a74a8ea66c64a41508ca76"),
        )
        self.assertEqual(
            (frames[1]["source_shot_id"], frames[1]["frame_id"]),
            (SHOT_ID, FRAME_ID),
        )
        selected_frames = [item for item in frames if item["frame_id"] == FRAME_ID]
        self.assertEqual(len(selected_frames), 1)
        self.assertEqual(selected_frames[0]["source_shot_id"], SHOT_ID)
        self.assertEqual(selected_frames[0]["source_shot_card_digest"], SHOT_CARD_DIGEST)
        self.assertEqual(selected_frames[0]["frame_specification_digest"], FRAME_DIGEST)
        self.assertEqual(
            result["scene_storyboard_specification"]["payload"]["storyboard_specification_digest"],
            STORYBOARD_DIGEST,
        )
        admitted = admit_storyboard_render(
            result["review_decision"], result["review_packet"],
            result["scene_production_option_set"], result["scene_breakdown"],
            result["scene_shot_plan_draft"], result["scene_storyboard_specification"],
            environment="development",
        )
        self.assertEqual(admitted.scene_id, SCENE_ID)
        self.assertEqual(admitted.storyboard_specification_digest, STORYBOARD_DIGEST)
        self.assertEqual(prepared.story, validated)

    def test_resealed_source_substitution_cannot_match_the_recorded_scene_or_shot(self):
        substituted = json.loads(STORY.read_text(encoding="utf-8"))
        substituted["payload"]["fragment_text"] = (
            "SCENE: At dusk, Vikramaditya turns away from the banyan tree."
        )
        _prepared, result = self._run_real_path(copy.deepcopy(substituted), option_id=None)
        scene = result["scene_breakdown"]["payload"]["ordered_scenes"][0]
        self.assertNotEqual(scene["scene_id"], SCENE_ID)
        self.assertNotEqual(
            result["scene_shot_plan_draft"]["payload"]["ordered_shots"][1]["shot_id"],
            SHOT_ID,
        )

    def test_authoritative_controlled_request_is_byte_deterministic_across_independent_runs(self):
        story = json.loads(STORY.read_text(encoding="utf-8"))
        requests = []
        for _ in range(2):
            prepared, result = self._run_real_path(story)
            frame = result["scene_storyboard_specification"]["payload"]["ordered_frames"][0]
            admitted = admit_controlled_generation(
                story, result["review_decision"], result["review_packet"],
                result["scene_production_option_set"], result["scene_breakdown"],
                result["creative_decision_revision"], result["canon_snapshot"],
                result["production_canon_binding"], result["scene_shot_plan_draft"],
                result["scene_storyboard_specification"], frame_id=frame["frame_id"],
                environment="development",
            )
            requests.append(admitted.request_json())
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(
            requests[0]["provider"]["provider_request_sha256"],
            requests[1]["provider"]["provider_request_sha256"],
        )

    def test_authoritative_request_is_identical_in_a_fresh_process(self):
        probe = """
import json
from pathlib import Path
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_controlled_generation import admit_controlled_generation
story = json.loads(Path("tests/fixtures/movie/vikramaditya-opening-story-fragment.json").read_text())
prepared = prepare_demo(story, correlation_id="vikramaditya-source")
result = finish_demo(
    prepared, option_id="option-b5d2461f4ec95dc0377938ba",
    reviewer_id="source.preparation",
    rationale="Accepted at human review for a local shot-plan draft demo.",
    correlation_id="vikramaditya-source", include_storyboard=True,
)
frame = result["scene_storyboard_specification"]["payload"]["ordered_frames"][1]
admitted = admit_controlled_generation(
    story, result["review_decision"], result["review_packet"],
    result["scene_production_option_set"], result["scene_breakdown"],
    result["creative_decision_revision"], result["canon_snapshot"],
    result["production_canon_binding"], result["scene_shot_plan_draft"],
    result["scene_storyboard_specification"], frame_id=frame["frame_id"],
    environment="development",
)
print(admitted.request["request_sha256"])
"""
        first = self._admit_primary_request().request["request_sha256"]
        child_environment = os.environ.copy()
        child_environment.pop("VSS_CONTROLLED_MEDIA_APPROVER_HMAC_KEY", None)
        child_environment.pop("VSS_CONTROLLED_MEDIA_OPENAI_API_KEY", None)
        with subprocess.Popen(
            [sys.executable, "-c", probe], cwd=ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=child_environment,
        ) as process:
            stdout, stderr = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), first)

    def test_actual_prepaid_command_path_reuses_identical_request(self):
        admitted = self._admit_primary_request()
        request = admitted.request_json()
        payload = {
            "story": json.loads(STORY.read_text(encoding="utf-8")),
            "decision": None,
            "review_packet": None,
            "option_set": None,
            "scene_breakdown": None,
            "creative_decision": None,
            "canon_snapshot": None,
            "canon_binding": None,
            "shot_plan": None,
            "storyboard": None,
            "frame_id": request["scope"]["frame_id"],
            "mode": "preflight",
        }
        _prepared, result = self._run_real_path(payload["story"])
        payload.update({
            "decision": result["review_decision"], "review_packet": result["review_packet"],
            "option_set": result["scene_production_option_set"],
            "scene_breakdown": result["scene_breakdown"],
            "creative_decision": result["creative_decision_revision"],
            "canon_snapshot": result["canon_snapshot"],
            "canon_binding": result["production_canon_binding"],
            "shot_plan": result["scene_shot_plan_draft"],
            "storyboard": result["scene_storyboard_specification"],
        })
        with tempfile.TemporaryDirectory() as directory:
            controller = RuntimeController(
                root=ROOT,
                audit_logger=AuditLogger(Path(directory) / "audit", trusted_root=Path(directory)),
                external_execution_preflight=ExternalExecutionPreflight(
                    environment_contains=lambda name: name == "VSS_CONTROLLED_MEDIA_OPENAI_API_KEY",
                    resolver=lambda hostname, port: [(hostname, port)],
                ),
            )
            response, code = CommandRunner(runtime_controller=controller).run(
                "movie.controlled-review-frame", "development", payload,
                correlation_id="vikramaditya-source-preflight",
            )
        self.assertEqual(code, 0, response)
        self.assertEqual(response["output"]["request"]["request_sha256"], admitted.request["request_sha256"])
        self.assertEqual(response["output"]["provider_call_count"], 0)
        self.assertFalse(response["output"]["attempt_reserved"])

    def test_location_approval_cannot_be_consumed_by_different_option_shot_or_frame(self):
        location = self._admit_primary_request()
        minimal = self._admit_primary_request(option_id="option-5b5dcf7ac126caf590e666ca")
        self.assertNotEqual(location.request["request_sha256"], minimal.request["request_sha256"])
        approval = issue_approval(
            location.request_json(), recorded_by="location-selection-reviewer",
            secret="r" * 32, issued_at="2030-01-02T03:00:00Z",
            expires_at="2030-01-02T03:15:00Z",
        )
        with self.assertRaises(Exception):
            verify_approval(
                approval, minimal.request_json(), secret="r" * 32,
                now="2030-01-02T03:05:00Z",
            )


if __name__ == "__main__":
    unittest.main()
