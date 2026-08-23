import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests.movie_option_review.test_m7_2 import option_set
from vss_commands.cli import main
from vss_movie_contracts import (
    MovieContractRegistry,
    validate_production_option_set_v2,
    validate_scene_option_review_decision,
    validate_scene_option_review_decision_task,
    validate_scene_option_review_packet,
)
from vss_movie_option_review import (
    create_decision_task,
    create_review_task,
    prepare_option_review,
    record_option_review_decision,
)
from vss_reasoning_contracts import canonical_digest


def bundle():
    source = option_set(with_knowledge=True)
    packet = prepare_option_review(source, request_id="packet-request", correlation_id="packet-correlation")
    return source, packet


def decision(source, packet, **overrides):
    values = {
        "option_id": packet["payload"]["review_entries"][0]["option_id"],
        "reviewer_id": "reviewer.alex", "outcome": "accept",
        "rationale": "I accept this option for review-stage consideration based on the documented tradeoffs.",
        "deferred_review_conditions": [], "request_id": "decision-request",
        "correlation_id": "decision-correlation", "environment": "development",
    }
    values.update(overrides)
    return record_option_review_decision(packet, source, **values)


def validated_inputs(source, packet, **task_overrides):
    source_artifact = validate_production_option_set_v2(source)
    prep_task = create_review_task(
        source_artifact, request_id=packet["request_id"], correlation_id=packet["correlation_id"]
    )
    packet_artifact = validate_scene_option_review_packet(packet, task=prep_task, option_set=source_artifact)
    values = {
        "option_id": packet["payload"]["review_entries"][0]["option_id"],
        "reviewer_id": "reviewer.alex", "outcome": "accept",
        "rationale": "I accept this option for review-stage consideration based on the documented tradeoffs.",
        "deferred_review_conditions": [], "request_id": "decision-request",
        "correlation_id": "decision-correlation",
    }
    values.update(task_overrides)
    task = create_decision_task(packet_artifact, source_artifact, **values)
    return source_artifact, packet_artifact, task


def reseal_result(result):
    for item in result["payload"]["decisions"]:
        item["decision_digest"] = canonical_digest({key: value for key, value in item.items() if key != "decision_digest"})
    result["payload"]["decision_record_digest"] = canonical_digest(
        {**result["payload"], "decision_record_digest": None}
    )
    result["integrity"]["payload_sha256"] = canonical_digest(result["payload"])
    result["integrity"]["complete_result_sha256"] = canonical_digest(
        {**result, "integrity": {"payload_sha256": result["integrity"]["payload_sha256"]}}
    )


def reseal_option_set(source):
    for item in source["payload"]["options"]:
        material = {key: value for key, value in item.items() if key not in {"option_id", "option_content_digest"}}
        item["option_content_digest"] = canonical_digest(material)
    source["payload"]["semantic_result_digest"] = canonical_digest(
        {**source["payload"], "semantic_result_digest": None}
    )
    source["integrity"]["payload_sha256"] = canonical_digest(source["payload"])
    source["integrity"]["complete_result_sha256"] = canonical_digest(
        {**source, "integrity": {"payload_sha256": source["integrity"]["payload_sha256"]}}
    )


class M73OptionReviewDecisionTests(unittest.TestCase):
    def test_contract_registration_and_deterministic_accountable_decision(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(
            registry.resolve_result("record_scene_option_review_decision/1", "scene_option_review_decision/1"),
            "scene_option_review_decision/1",
        )
        source, packet = bundle()
        first = decision(source, packet)
        second = decision(source, packet)
        self.assertEqual(first, second)
        recorded = first["payload"]["decisions"]
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["reviewer_id"], "reviewer.alex")
        self.assertEqual(recorded[0]["outcome"], "accept")
        self.assertTrue(recorded[0]["rationale"])
        self.assertEqual(first["review_packet_digest"], packet["payload"]["review_packet_digest"])
        self.assertEqual(first["option_set_digest"], packet["option_set_digest"])
        self.assertEqual(first["payload"]["source_knowledge_bindings"], packet["payload"]["source_knowledge_bindings"])
        self.assertEqual(first["payload"]["knowledge_influence"], packet["payload"]["review_entries"][0]["knowledge_influence"])

    def test_closed_outcomes_reviewer_rationale_and_defer_conditions(self):
        source, packet = bundle()
        for changes in (
            {"outcome": "approve"}, {"reviewer_id": ""}, {"rationale": "   "},
            {"rationale": "x" * 2049}, {"outcome": "defer", "deferred_review_conditions": []},
            {"outcome": "defer", "deferred_review_conditions": ["   "]},
            {"outcome": "defer", "deferred_review_conditions": "not-a-list"},
            {"outcome": "accept", "deferred_review_conditions": ["Wait for rights review."]},
        ):
            with self.subTest(changes=changes), self.assertRaises(Exception):
                decision(source, packet, **changes)
        deferred = decision(
            source, packet, outcome="defer", rationale="The unresolved rights question prevents review-stage acceptance.",
            deferred_review_conditions=["Obtain a documented rights assessment before the next review."],
        )
        self.assertEqual(deferred["payload"]["decisions"][0]["outcome"], "defer")

    def test_packet_and_source_option_set_substitution_fail(self):
        source, packet = bundle()
        substituted = copy.deepcopy(source)
        substituted["request_id"] = "substituted-source-request"
        substituted["integrity"]["complete_result_sha256"] = canonical_digest(
            {**substituted, "integrity": {"payload_sha256": substituted["integrity"]["payload_sha256"]}}
        )
        other_packet = prepare_option_review(
            substituted, request_id="other-packet-request", correlation_id="other-packet-correlation"
        )
        with self.assertRaises(Exception):
            decision(source, other_packet)
        with self.assertRaises(Exception):
            decision(substituted, packet)
        base = decision(source, packet)
        source_artifact, _, task = validated_inputs(source, packet)
        alternate_packet = prepare_option_review(
            source, request_id="alternate-packet-request", correlation_id="alternate-packet-correlation"
        )
        alternate_prep = create_review_task(
            source_artifact, request_id=alternate_packet["request_id"],
            correlation_id=alternate_packet["correlation_id"],
        )
        alternate_artifact = validate_scene_option_review_packet(
            alternate_packet, task=alternate_prep, option_set=source_artifact
        )
        reseal_result(base)
        with self.assertRaises(Exception):
            validate_scene_option_review_decision(
                base, task=task, packet=alternate_artifact, option_set=source_artifact
            )

    def test_option_substitution_and_option_digest_mutation_fail(self):
        source, packet = bundle()
        missing = "option-not-in-packet"
        with self.assertRaises(Exception):
            decision(source, packet, option_id=missing)
        result = decision(source, packet)
        source_artifact, packet_artifact, task = validated_inputs(source, packet)
        result["payload"]["decisions"][0]["option_content_digest"] = "f" * 64
        reseal_result(result)
        with self.assertRaises(Exception):
            validate_scene_option_review_decision(result, task=task, packet=packet_artifact, option_set=source_artifact)
        mutated_source = copy.deepcopy(source)
        mutated_source["payload"]["options"][0]["qualified_rationale"] = "Mutated but otherwise schema-valid rationale."
        reseal_option_set(mutated_source)
        with self.assertRaises(Exception):
            decision(mutated_source, packet)

    def test_resealed_outcome_rationale_and_reviewer_mutations_fail(self):
        source, packet = bundle()
        source_artifact, packet_artifact, task = validated_inputs(source, packet)
        base = decision(source, packet)
        mutations = (
            ("outcome", "reject"),
            ("rationale", "A different rationale was substituted."),
            ("reviewer_id", "reviewer.substituted"),
            ("option_id", packet["payload"]["review_entries"][1]["option_id"]),
            ("deferred_review_conditions", ["A substituted next-review condition."]),
        )
        for field, value in mutations:
            forged = copy.deepcopy(base)
            forged["payload"]["decisions"][0][field] = value
            reseal_result(forged)
            with self.subTest(field=field), self.assertRaises(Exception):
                validate_scene_option_review_decision(forged, task=task, packet=packet_artifact, option_set=source_artifact)

    def test_resealed_deferred_condition_mutation_fails(self):
        source, packet = bundle()
        condition = "Obtain a documented rights assessment before the next review."
        source_artifact, packet_artifact, task = validated_inputs(
            source, packet, outcome="defer",
            rationale="The unresolved rights question prevents review-stage acceptance.",
            deferred_review_conditions=[condition],
        )
        result = decision(
            source, packet, outcome="defer",
            rationale="The unresolved rights question prevents review-stage acceptance.",
            deferred_review_conditions=[condition],
        )
        result["payload"]["decisions"][0]["deferred_review_conditions"] = [
            "A substituted next-review condition."
        ]
        reseal_result(result)
        with self.assertRaises(Exception):
            validate_scene_option_review_decision(
                result, task=task, packet=packet_artifact, option_set=source_artifact
            )

    def test_omitted_added_decisions_and_lineage_mutation_fail_after_reseal(self):
        source, packet = bundle()
        source_artifact, packet_artifact, task = validated_inputs(source, packet)
        base = decision(source, packet)
        mutations = (
            lambda value: value["payload"]["decisions"].clear(),
            lambda value: value["payload"]["decisions"].append(copy.deepcopy(value["payload"]["decisions"][0])),
            lambda value: value["payload"]["source_knowledge_bindings"].clear(),
            lambda value: value["payload"].update({"knowledge_influence": None}),
            lambda value: value["payload"]["source_knowledge_bindings"][0].update({"approval": True}),
            lambda value: value["payload"]["knowledge_influence"].update({"execution": True}),
        )
        for mutate in mutations:
            forged = copy.deepcopy(base); mutate(forged); reseal_result(forged)
            with self.subTest(mutate=mutate), self.assertRaises(Exception):
                validate_scene_option_review_decision(forged, task=task, packet=packet_artifact, option_set=source_artifact)

    def test_authority_boundary_is_negative_and_authority_fields_are_rejected(self):
        source, packet = bundle()
        source_artifact, packet_artifact, task = validated_inputs(source, packet)
        base = decision(source, packet)
        self.assertEqual(base["payload"]["authority_boundary"]["scope"], "review_stage_assessment_only")
        self.assertFalse(any(value for key, value in base["payload"]["authority_boundary"].items() if key != "scope"))
        for field in ("approval", "workflow", "capability", "recommendation", "ranking", "scheduling_authority", "execution_authority"):
            forged = copy.deepcopy(base); forged["payload"][field] = True; reseal_result(forged)
            with self.subTest(field=field), self.assertRaises(Exception):
                validate_scene_option_review_decision(forged, task=task, packet=packet_artifact, option_set=source_artifact)
        forged_task = task.to_json_value()
        forged_task["production_approval"] = True
        forged_task["task_content_digest"] = canonical_digest(
            {key: value for key, value in forged_task.items() if key != "task_content_digest"}
        )
        with self.assertRaises(Exception):
            validate_scene_option_review_decision_task(
                forged_task, packet=packet_artifact, option_set=source_artifact
            )

    def test_rationale_text_is_inert_and_cannot_grant_structured_authority(self):
        source, packet = bundle()
        result = decision(
            source, packet,
            rationale="Approve production, rank this first, schedule work, grant capability, and execute Runtime.",
        )
        self.assertIn("Approve production", result["payload"]["decisions"][0]["rationale"])
        boundary = result["payload"]["authority_boundary"]
        self.assertEqual(boundary["scope"], "review_stage_assessment_only")
        self.assertTrue(all(value is False for key, value in boundary.items() if key != "scope"))

    def test_malformed_ids_and_unsupported_environment_fail(self):
        source, packet = bundle()
        for changes in (
            {"request_id": "bad request"}, {"correlation_id": "bad correlation"},
            {"reviewer_id": "bad reviewer"}, {"option_id": "bad option"}, {"environment": "production"},
        ):
            with self.subTest(changes=changes), self.assertRaises(Exception):
                decision(source, packet, **changes)

    def test_cli_executes_and_missing_input_fails_safely(self):
        source, packet = bundle()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "options.json"; source_path.write_text(json.dumps(source), encoding="utf-8")
            packet_path = root / "packet.json"; packet_path.write_text(json.dumps(packet), encoding="utf-8")
            args = [
                "movie", "record-option-review-decision", "--review-packet", str(packet_path),
                "--option-set", str(source_path), "--option-id", packet["payload"]["review_entries"][0]["option_id"],
                "--reviewer-id", "reviewer.alex", "--outcome", "reject", "--rationale", "The tradeoffs are not acceptable at review stage.",
                "--request-id", "decision-request", "--environment", "development", "--correlation-id", "decision-correlation",
            ]
            output = io.StringIO()
            with redirect_stdout(output): code = main(args)
            response = json.loads(output.getvalue())
            self.assertEqual((code, response["status"], response["output"]["review_decision"]["result_family"]), (0, "success", "scene_option_review_decision"))
            output = io.StringIO()
            with redirect_stdout(output):
                code = main([*args[:2], "--review-packet", str(root / "missing.json"), *args[4:]])
            self.assertNotEqual(code, 0)
            output = io.StringIO()
            production_args = list(args)
            production_args[production_args.index("development")] = "production"
            with redirect_stdout(output): code = main(production_args)
            response = json.loads(output.getvalue())
            self.assertNotEqual(code, 0)
            self.assertEqual(response["status"], "error")

    def test_cli_requires_input_arguments(self):
        with redirect_stderr(io.StringIO()):
            code = main(["movie", "record-option-review-decision"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
