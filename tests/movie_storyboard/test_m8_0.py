import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.movie_shot_plan.test_m7_4 import inputs as m74_inputs, execute as execute_shot_plan, reseal_result as reseal_shot_plan
from vss_commands.cli import main
from vss_movie_contracts import MovieContractRegistry, validate_scene_storyboard_specification
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_storyboard import admit_storyboard_inputs
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning_contracts import canonical_digest


STORY = Path(__file__).resolve().parents[1] / "fixtures/movie/story-fragment-valid.json"


def bundle(*, knowledge=False):
    decision, packet, options, breakdown = m74_inputs(knowledge=knowledge)
    shot_plan = execute_shot_plan((decision, packet, options, breakdown))["scene_shot_plan_draft"]
    return decision, packet, options, breakdown, shot_plan


def execute(values=None, **kwargs):
    decision, packet, options, breakdown, shot_plan = values or bundle()
    return ReasoningGateway.built_in().execute_scene_storyboard_specification(
        decision, packet, options, breakdown, shot_plan,
        request_id=kwargs.pop("request_id", "storyboard-request"),
        correlation_id=kwargs.pop("correlation_id", "storyboard-correlation"),
        environment=kwargs.pop("environment", "development"), **kwargs,
    )


def validated(values):
    return admit_storyboard_inputs(
        *values, request_id="storyboard-request", correlation_id="storyboard-correlation"
    )


def reseal_storyboard(value):
    for frame in value["payload"]["ordered_frames"]:
        material = dict(frame); material.pop("frame_specification_digest", None)
        frame["frame_specification_digest"] = canonical_digest(material)
    value["payload"]["storyboard_specification_digest"] = canonical_digest(
        {**value["payload"], "storyboard_specification_digest": None}
    )
    value["integrity"]["payload_sha256"] = canonical_digest(value["payload"])
    value["integrity"]["complete_result_sha256"] = canonical_digest(
        {**value, "integrity": {"payload_sha256": value["integrity"]["payload_sha256"]}}
    )


class M80StoryboardTests(unittest.TestCase):
    def test_contracts_determinism_and_provider_neutral_frames(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(registry.resolve_result(
            "create_scene_storyboard_specification/1", "scene_storyboard_specification/1"
        ), "scene_storyboard_specification/1")
        first, second = execute(), execute()
        self.assertEqual(first["scene_storyboard_specification"], second["scene_storyboard_specification"])
        result = first["scene_storyboard_specification"]
        frames = result["payload"]["ordered_frames"]
        self.assertEqual([f["source_ordinal"] for f in frames], [1, 2, 3])
        self.assertEqual(len(frames), 3)
        self.assertEqual(result["payload"]["specification_status"], "specification_only")
        self.assertIn("courtyard", frames[0]["environment"])
        self.assertIn("dawn", frames[0]["time_and_lighting"])
        self.assertIn("lantern", frames[1]["action"])
        self.assertIn("minimal_stage", frames[0]["visual_style"])
        self.assertTrue(frames[0]["explicit_unknowns"])
        self.assertTrue(frames[0]["negative_constraints"])
        self.assertFalse(any(v for k, v in result["payload"]["authority_boundary"].items() if k != "scope"))
        self.assertEqual(first["external_image_provider_call_count"], 0)

    def test_committed_story_fixture_runs_real_end_to_end_path(self):
        story = json.loads(STORY.read_text(encoding="utf-8"))
        prepared = prepare_demo(story, correlation_id="m8-e2e")
        result = finish_demo(
            prepared, option_id=prepared.review_packet["payload"]["review_entries"][0]["option_id"],
            reviewer_id="m8.reviewer", rationale="Accepted for inert storyboard specification.",
            correlation_id="m8-e2e", include_storyboard=True,
        )
        self.assertIn("scene_storyboard_specification", result)
        self.assertEqual(len(result["scene_storyboard_specification"]["payload"]["ordered_frames"]), 3)

    def test_resealed_omission_addition_reordering_and_content_mutation_fail(self):
        values = bundle(); original = execute(values)["scene_storyboard_specification"]
        task, decision, packet, options, breakdown, _, shot_plan = validated(values)
        mutations = (
            lambda p: p["ordered_frames"].pop(),
            lambda p: p["ordered_frames"].append(copy.deepcopy(p["ordered_frames"][-1])),
            lambda p: p["ordered_frames"].reverse(),
            lambda p: p["ordered_frames"][0].update({"environment": "unsupported palace"}),
        )
        for mutate in mutations:
            forged = copy.deepcopy(original); mutate(forged["payload"]); reseal_storyboard(forged)
            with self.assertRaises(Exception):
                validate_scene_storyboard_specification(
                    forged, task=task, decision=decision, packet=packet, option_set=options,
                    breakdown=breakdown, shot_plan=shot_plan,
                )

    def test_resealed_upstream_substitution_and_shot_plan_mutation_fail(self):
        values = bundle()
        substituted = list(values); substituted[0] = copy.deepcopy(substituted[0])
        substituted[0]["request_id"] = "substituted-decision"
        substituted[0]["integrity"]["complete_result_sha256"] = canonical_digest(
            {**substituted[0], "integrity": {"payload_sha256": substituted[0]["integrity"]["payload_sha256"]}}
        )
        with self.assertRaises(Exception): execute(tuple(substituted))
        mutated = list(values); mutated[4] = copy.deepcopy(mutated[4])
        mutated[4]["payload"]["ordered_shots"][0]["narrative_focus"] = "Unsupported substituted event."
        reseal_shot_plan(mutated[4])
        with self.assertRaises(Exception): execute(tuple(mutated))

    def test_knowledge_mutation_and_authority_injection_fail(self):
        values = bundle(knowledge=True)
        result = execute(values)["scene_storyboard_specification"]
        self.assertEqual(result["payload"]["source_knowledge_bindings"], values[4]["payload"]["source_knowledge_bindings"])
        mutated = list(values); mutated[2] = copy.deepcopy(mutated[2])
        mutated[2]["knowledge_bindings"][0]["admission_decision_id"] = "admission-substituted"
        mutated[2]["integrity"]["complete_result_sha256"] = canonical_digest(
            {**mutated[2], "integrity": {"payload_sha256": mutated[2]["integrity"]["payload_sha256"]}}
        )
        with self.assertRaises(Exception): execute(tuple(mutated))
        task, decision, packet, options, breakdown, _, shot_plan = validated(values)
        forged = copy.deepcopy(result); forged["payload"]["production_approval"] = True
        reseal_storyboard(forged)
        with self.assertRaises(Exception):
            validate_scene_storyboard_specification(
                forged, task=task, decision=decision, packet=packet, option_set=options,
                breakdown=breakdown, shot_plan=shot_plan,
            )

    def test_malformed_environment_dry_run_and_cli(self):
        with self.assertRaises(Exception): execute(environment="production")
        malformed = list(bundle()); malformed[4] = {"result_family": "scene_shot_plan_draft"}
        with self.assertRaises(Exception): execute(tuple(malformed))
        with patch("vss_reasoning_providers.deterministic_scene_storyboard.DeterministicSceneStoryboardProvider.generate") as generate:
            readiness = execute(dry_run=True)["readiness"]
        generate.assert_not_called(); self.assertFalse(readiness["provider_invoked"])
        self.assertFalse(readiness["external_image_provider_invoked"])
        values = bundle()
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name, value in zip(("decision", "packet", "options", "breakdown", "shots"), values):
                path = Path(directory) / f"{name}.json"; path.write_text(json.dumps(value), encoding="utf-8"); paths.append(path)
            args = ["movie", "create-storyboard-specification", "--decision", str(paths[0]),
                    "--review-packet", str(paths[1]), "--option-set", str(paths[2]),
                    "--scene-breakdown", str(paths[3]), "--shot-plan", str(paths[4]),
                    "--request-id", "cli-storyboard", "--environment", "development",
                    "--correlation-id", "cli-storyboard"]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args + ["--dry-run"]), 0)
                unsupported = list(args); unsupported[unsupported.index("development")] = "production"
                self.assertNotEqual(main(unsupported), 0)

    def test_demo_option_continues_without_manual_json(self):
        stdout, stderr = StringIO(), StringIO()
        args = ["movie", "demo", "--story", str(STORY), "--reviewer-id", "local.reviewer",
                "--correlation-id", "m8-demo-cli", "--option-id", "option-802bf5f0a0d8df08c1376b91",
                "--storyboard-specification"]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(args), 0)
        self.assertIn("scene_storyboard_specification", json.loads(stdout.getvalue()))


if __name__ == "__main__":
    unittest.main()
