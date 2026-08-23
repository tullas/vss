import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.movie_option_review.test_m7_2 import option_set
from tests.movie_option_review.test_m7_3 import bundle as knowledge_bundle, reseal_option_set
from vss_commands.cli import main
from vss_context import ContextAssembler
from vss_movie_contracts import (
    MovieContractRegistry, validate_production_option_set_v2,
    validate_scene_breakdown, validate_scene_option_review_decision,
    validate_scene_option_review_packet, validate_scene_shot_plan_draft,
)
from vss_movie_option_review import (
    create_decision_task, create_review_task, prepare_option_review,
    record_option_review_decision,
)
from vss_movie_shot_plan import admit_shot_plan_inputs
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning_contracts import canonical_digest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/movie"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def inputs(outcome="accept", knowledge=False):
    source = knowledge_bundle()[0] if knowledge else option_set()
    if knowledge:
        source["project_id"] = "movie-local"
        source["integrity"]["complete_result_sha256"] = canonical_digest(
            {**source, "integrity": {"payload_sha256": source["integrity"]["payload_sha256"]}}
        )
    packet = prepare_option_review(source, request_id="packet-request", correlation_id="packet-correlation")
    decision = record_option_review_decision(
        packet, source, option_id=packet["payload"]["review_entries"][0]["option_id"],
        reviewer_id="reviewer.alex", outcome=outcome,
        rationale="This is an accountable review-stage assessment only.",
        deferred_review_conditions=["Obtain more evidence before another review."] if outcome == "defer" else [],
        request_id="decision-request", correlation_id="decision-correlation",
    )
    breakdown = load("scene-breakdown-valid.json")
    return decision, packet, source, breakdown


def execute(values=None, **kwargs):
    d, p, o, b = values or inputs()
    return ReasoningGateway.built_in().execute_scene_shot_plan_draft(
        d, p, o, b, request_id=kwargs.pop("request_id", "shot-request"),
        environment=kwargs.pop("environment", "development"),
        correlation_id=kwargs.pop("correlation_id", "shot-correlation"), **kwargs,
    )


def validated(values):
    d, p, o, b = values
    task, decision, packet, source, breakdown, _ = admit_shot_plan_inputs(
        d, p, o, b, request_id="shot-request", correlation_id="shot-correlation"
    )
    return task, decision, packet, source, breakdown


def reseal_result(value):
    for card in value["payload"]["ordered_shots"]:
        raw = dict(card); raw.pop("shot_card_digest", None)
        card["shot_card_digest"] = canonical_digest(raw)
    value["payload"]["shot_plan_digest"] = canonical_digest({**value["payload"], "shot_plan_digest": None})
    value["integrity"]["payload_sha256"] = canonical_digest(value["payload"])
    value["integrity"]["complete_result_sha256"] = canonical_digest(
        {**value, "integrity": {"payload_sha256": value["integrity"]["payload_sha256"]}}
    )


class M74ShotPlanTests(unittest.TestCase):
    def test_registry_and_accepted_deterministic_draft(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(registry.resolve_result("create_scene_shot_plan_draft/1", "scene_shot_plan_draft/1"), "scene_shot_plan_draft/1")
        first = execute(); second = execute()
        self.assertEqual(first["scene_shot_plan_draft"], second["scene_shot_plan_draft"])
        result = first["scene_shot_plan_draft"]
        self.assertEqual(result["payload"]["draft_status"], "draft_only")
        self.assertEqual([x["source_ordinal"] for x in result["payload"]["ordered_shots"]], [1, 2, 3])
        self.assertTrue(result["payload"]["stable_order_is_not_ranking"])
        self.assertFalse(any(v for k, v in result["payload"]["authority_boundary"].items() if k != "scope"))
        shots = result["payload"]["ordered_shots"]
        self.assertIn("courtyard", shots[0]["narrative_focus"])
        self.assertIn("lantern", shots[1]["narrative_focus"])
        self.assertIn("significance of the lantern", shots[2]["narrative_focus"])
        self.assertIn("minimal_stage", shots[0]["option_application"])

    def test_reject_defer_environment_and_malformed_ids_fail(self):
        for outcome in ("reject", "defer"):
            with self.subTest(outcome=outcome), self.assertRaises(Exception): execute(inputs(outcome))
        with self.assertRaises(Exception): execute(environment="production")
        with self.assertRaises(Exception): execute(request_id="bad id")
        with self.assertRaises(Exception): execute(correlation_id="bad id")

    def test_exact_upstream_substitution_and_content_mutation_fail(self):
        base = inputs()
        mutations = []
        other_packet = prepare_option_review(base[2], request_id="other-packet", correlation_id="other-packet")
        mutations.append(("packet", (base[0], other_packet, base[2], base[3])))
        other_source = copy.deepcopy(base[2]); other_source["request_id"] = "other-request"
        other_source["integrity"]["complete_result_sha256"] = canonical_digest({**other_source, "integrity": {"payload_sha256": other_source["integrity"]["payload_sha256"]}})
        mutations.append(("option-set", (base[0], base[1], other_source, base[3])))
        scene = copy.deepcopy(base[3]); scene["payload"]["ordered_scenes"][0]["events"][0]["text"] = "Mutated scene content."
        scene["integrity"]["payload_sha256"] = canonical_digest(scene["payload"])
        mutations.append(("scene", (base[0], base[1], base[2], scene)))
        for name, values in mutations:
            with self.subTest(name=name), self.assertRaises(Exception): execute(values)

    def test_decision_and_selected_option_binding_fail(self):
        d, p, o, b = inputs()
        forged = copy.deepcopy(d); forged["payload"]["decisions"][0]["option_id"] = p["payload"]["review_entries"][1]["option_id"]
        with self.assertRaises(Exception): execute((forged, p, o, b))
        forged = copy.deepcopy(d); forged["payload"]["decisions"][0]["option_content_digest"] = "f" * 64
        with self.assertRaises(Exception): execute((forged, p, o, b))
        forged_option = copy.deepcopy(o); forged_option["payload"]["options"][0]["qualified_rationale"] = "Mutated content."
        with self.assertRaises(Exception): execute((d, p, forged_option, b))
        resealed_option = copy.deepcopy(o)
        resealed_option["payload"]["options"][0]["qualified_rationale"] = "Resealed substituted content."
        reseal_option_set(resealed_option)
        with self.assertRaises(Exception): execute((d, p, resealed_option, b))

    def test_resealed_omitted_added_reordered_and_mutated_shots_fail(self):
        values = inputs(); result = execute(values)["scene_shot_plan_draft"]
        task, decision, packet, source, breakdown = validated(values)
        mutations = (
            lambda p: p["ordered_shots"].pop(),
            lambda p: p["ordered_shots"].append(copy.deepcopy(p["ordered_shots"][-1])),
            lambda p: p["ordered_shots"].reverse(),
            lambda p: p["ordered_shots"][0].update({"shot_scale_qualification": "Forged qualification."}),
        )
        for mutate in mutations:
            forged = copy.deepcopy(result); mutate(forged["payload"]); reseal_result(forged)
            with self.assertRaises(Exception):
                validate_scene_shot_plan_draft(forged, task=task, decision=decision, packet=packet,
                                               option_set=source, breakdown=breakdown)

    def test_resealed_authority_and_binding_mutations_fail(self):
        values = inputs(); result = execute(values)["scene_shot_plan_draft"]
        task, decision, packet, source, breakdown = validated(values)
        for field in ("production_approval", "scheduling", "workflow", "capability", "provider_execution", "runtime_authority"):
            forged = copy.deepcopy(result); forged["payload"][field] = True; reseal_result(forged)
            with self.subTest(field=field), self.assertRaises(Exception):
                validate_scene_shot_plan_draft(forged, task=task, decision=decision, packet=packet,
                                               option_set=source, breakdown=breakdown)
        for field in ("decision_digest", "review_packet_digest", "option_set_digest", "scene_breakdown_digest"):
            forged = copy.deepcopy(result); forged[field] = "f" * 64; reseal_result(forged)
            with self.subTest(field=field), self.assertRaises(Exception):
                validate_scene_shot_plan_draft(forged, task=task, decision=decision, packet=packet,
                                               option_set=source, breakdown=breakdown)

    def test_valid_resealed_decision_and_selected_option_substitutions_cannot_rebind_result(self):
        values = inputs(); original = execute(values)["scene_shot_plan_draft"]
        task, _, packet, source, breakdown = validated(values)
        alternate_decision_data = record_option_review_decision(
            values[1], values[2], option_id=values[1]["payload"]["review_entries"][0]["option_id"],
            reviewer_id="reviewer.alex", outcome="accept",
            rationale="A different, fully sealed accountable rationale.",
            request_id="other-decision", correlation_id="other-decision",
        )
        _, alternate_decision, _, _, _, _ = admit_shot_plan_inputs(
            alternate_decision_data, values[1], values[2], values[3],
            request_id="other-shot", correlation_id="other-shot",
        )
        with self.assertRaises(Exception):
            validate_scene_shot_plan_draft(original, task=task, decision=alternate_decision,
                                           packet=packet, option_set=source, breakdown=breakdown)
        alternate_decision_data = record_option_review_decision(
            values[1], values[2], option_id=values[1]["payload"]["review_entries"][1]["option_id"],
            reviewer_id="reviewer.alex", outcome="accept",
            rationale="A different exact option was accepted at review stage.",
            request_id="other-option-decision", correlation_id="other-option-decision",
        )
        _, alternate_decision, _, _, _, _ = admit_shot_plan_inputs(
            alternate_decision_data, values[1], values[2], values[3],
            request_id="other-option-shot", correlation_id="other-option-shot",
        )
        with self.assertRaises(Exception):
            validate_scene_shot_plan_draft(original, task=task, decision=alternate_decision,
                                           packet=packet, option_set=source, breakdown=breakdown)
    def test_knowledge_lineage_and_influence_are_exact(self):
        values = inputs(knowledge=True); result = execute(values)["scene_shot_plan_draft"]
        self.assertEqual(result["payload"]["source_knowledge_bindings"], values[1]["payload"]["source_knowledge_bindings"])
        self.assertEqual(result["payload"]["knowledge_influence"], values[0]["payload"]["knowledge_influence"])
        task, decision, packet, source, breakdown = validated(values)
        for mutate in (lambda p: p["source_knowledge_bindings"].clear(), lambda p: p.update({"knowledge_influence": None})):
            forged = copy.deepcopy(result); mutate(forged["payload"]); reseal_result(forged)
            with self.assertRaises(Exception):
                validate_scene_shot_plan_draft(forged, task=task, decision=decision, packet=packet,
                                               option_set=source, breakdown=breakdown)
        mutated_lineage = copy.deepcopy(values[2])
        mutated_lineage["knowledge_bindings"][0]["admission_decision_id"] = "admission-substituted"
        mutated_lineage["integrity"]["complete_result_sha256"] = canonical_digest(
            {**mutated_lineage, "integrity": {"payload_sha256": mutated_lineage["integrity"]["payload_sha256"]}}
        )
        with self.assertRaises(Exception):
            execute((values[0], values[1], mutated_lineage, values[3]))
        mutated_influence = copy.deepcopy(values[2])
        mutated_influence["payload"]["options"][0]["knowledge_influence"]["knowledge_values"] = ["substituted"]
        reseal_option_set(mutated_influence)
        with self.assertRaises(Exception):
            execute((values[0], values[1], mutated_influence, values[3]))

    def test_dry_run_calls_no_provider(self):
        with patch("vss_reasoning_providers.deterministic_scene_shot_plan.DeterministicSceneShotPlanProvider.generate") as generate:
            readiness = execute(dry_run=True)["readiness"]
        generate.assert_not_called(); self.assertFalse(readiness["provider_invoked"])
        self.assertEqual(readiness["provider_call_count"], 0)

    def test_complete_executable_path_from_committed_story_fixture(self):
        story = load("story-fragment-valid.json")
        scene_context = ContextAssembler().assemble_scene_breakdown(
            story, request_id="m4-2-request-001", correlation_id="m4-2-local-run",
            project_id=story["project_id"], environment="development",
            validation_time="2026-08-02T00:00:00Z",
        )
        breakdown = ReasoningGateway.built_in().execute_scene_breakdown(
            load("break-down-scenes-request-runtime-valid.json"), scene_context.to_json_value(),
            environment="development", correlation_id="m4-2-local-run",
        )["scene_breakdown"]
        scene = breakdown["payload"]["ordered_scenes"][0]
        prod_task = load("generate-scene-production-options-request-valid.json")
        prod_task.update(scene_breakdown_digest=validate_scene_breakdown(breakdown).digest,
                         scene_id=scene["scene_id"], scene_content_digest=scene["scene_content_digest"],
                         schema_version="2", task_version="2",
                         purpose="scene_production_options_local_analysis",
                         expected_context_version="2", expected_result_version="2")
        assembled = ContextAssembler().assemble_scene_production_options(
            prod_task, breakdown, correlation_id=prod_task["correlation_id"], environment="development",
            validation_time="2026-08-17T00:00:00Z",
        ).context.to_json_value()
        self.assertEqual(assembled["context_family_version"], "2")
        source = ReasoningGateway.built_in().execute_scene_production_options(
            prod_task, assembled, environment="development",
            correlation_id=prod_task["correlation_id"],
        )["scene_production_option_set"]
        packet = prepare_option_review(source, request_id="poc-packet", correlation_id="poc-packet")
        decision = record_option_review_decision(
            packet, source, option_id=packet["payload"]["review_entries"][0]["option_id"],
            reviewer_id="poc.reviewer", outcome="accept", rationale="Accepted at review stage for a draft POC.",
            request_id="poc-decision", correlation_id="poc-decision",
        )
        result = execute((decision, packet, source, breakdown))["scene_shot_plan_draft"]
        self.assertEqual(result["result_family"], "scene_shot_plan_draft")
        self.assertEqual(len(result["payload"]["ordered_shots"]), 3)

    def test_cli_missing_inputs_and_success(self):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertNotEqual(main(["movie", "create-shot-plan-draft"]), 0)
        d, p, o, b = inputs()
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name, value in zip(("d", "p", "o", "b"), (d, p, o, b)):
                path = Path(directory) / f"{name}.json"; path.write_text(json.dumps(value)); paths.append(path)
            args = ["movie", "create-shot-plan-draft", "--decision", str(paths[0]),
                    "--review-packet", str(paths[1]), "--option-set", str(paths[2]),
                    "--scene-breakdown", str(paths[3]), "--request-id", "cli-shot",
                    "--environment", "development", "--correlation-id", "cli-shot"]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args + ["--dry-run"]), 0)
                malformed_id = list(args); malformed_id[malformed_id.index("cli-shot", malformed_id.index("--request-id"))] = "bad id"
                self.assertNotEqual(main(malformed_id), 0)
                missing = list(args); missing[missing.index(str(paths[0]))] = str(Path(directory) / "missing.json")
                self.assertNotEqual(main(missing), 0)
                malformed_file = Path(directory) / "malformed.json"; malformed_file.write_text("{")
                malformed = list(args); malformed[malformed.index(str(paths[0]))] = str(malformed_file)
                self.assertNotEqual(main(malformed), 0)
                unsupported = list(args); unsupported[unsupported.index("development")] = "production"
                self.assertNotEqual(main(unsupported), 0)
                for outcome in ("reject", "defer"):
                    invalid_decision = inputs(outcome)[0]
                    paths[0].write_text(json.dumps(invalid_decision))
                    self.assertNotEqual(main(args), 0)


if __name__ == "__main__":
    unittest.main()
