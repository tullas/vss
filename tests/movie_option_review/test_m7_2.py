import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.movie_production_options.test_m7_1 import _v2_context, _v2_task
import tests.shot_cinematography_knowledge.test_knowledge_m6_5 as knowledge_tests
from vss_commands.cli import main
from vss_movie_contracts import MovieContractRegistry, validate_production_option_set_v2, validate_scene_option_review_packet
from vss_movie_option_review import create_review_task, prepare_option_review
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning_contracts import canonical_digest


def option_set(with_knowledge=False):
    context, task = _v2_context(), _v2_task()
    if with_knowledge:
        _, _, _, admitted = knowledge_tests.ShotCinematographyKnowledgeTests()._admit()
        context.update(project_id=admitted.knowledge.value["project_id"], classification=admitted.knowledge.value["classification"])
        context["payload"]["knowledge_bindings"] = [{"knowledge": admitted.knowledge.to_json_value(), "lifecycle_events": [], "replacements": []}]
        context["context_content_digest"] = canonical_digest(context["payload"])
        context["integrity"] = {"complete_context_sha256": "0" * 64}
        context["integrity"]["complete_context_sha256"] = canonical_digest({**context, "integrity": {}})
        task.update(project_id=context["project_id"], classification=context["classification"])
    return ReasoningGateway.built_in().execute_scene_production_options(task, context, environment="development", correlation_id=task["correlation_id"])["scene_production_option_set"]


def reseal_packet(packet):
    for entry in packet["payload"]["review_entries"]:
        entry["entry_digest"] = canonical_digest({key: value for key, value in entry.items() if key != "entry_digest"})
    packet["payload"]["review_packet_digest"] = canonical_digest({**packet["payload"], "review_packet_digest": None})
    packet["integrity"]["payload_sha256"] = canonical_digest(packet["payload"])
    packet["integrity"]["complete_result_sha256"] = canonical_digest({**packet, "integrity": {"payload_sha256": packet["integrity"]["payload_sha256"]}})


class M72OptionReviewPreparationTests(unittest.TestCase):
    def test_exact_contract_registration_and_compatibility(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(registry.resolve_result("prepare_scene_option_review/1", "scene_option_review_packet/1"), "scene_option_review_packet/1")
        with self.assertRaises(Exception): registry.resolve("prepare_scene_option_review", "latest")

    def test_packet_preserves_every_option_in_source_order_without_ranking(self):
        source = option_set()
        packet = prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2")
        entries = packet["payload"]["review_entries"]
        self.assertEqual([item["option_id"] for item in entries], [item["option_id"] for item in source["payload"]["options"]])
        self.assertEqual([item["source_ordinal"] for item in entries], [1, 2, 3, 4])
        self.assertTrue(packet["payload"]["stable_order_is_not_ranking"])
        self.assertTrue(all(item["unresolved_checks"] for item in entries))
        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items(): yield key; yield from keys(child)
            elif isinstance(value, list):
                for child in value: yield from keys(child)
        prohibited = {"rank", "score", "recommendation", "preference", "selected", "approved", "winner", "workflow", "capability", "execution"}
        self.assertFalse(prohibited & set(keys(packet)))

    def test_knowledge_lineage_and_influence_are_traceable_not_authoritative(self):
        source = option_set(with_knowledge=True)
        packet = prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2")
        self.assertEqual(packet["payload"]["source_knowledge_bindings"], source["knowledge_bindings"])
        for entry, option in zip(packet["payload"]["review_entries"], source["payload"]["options"]):
            self.assertEqual(entry["knowledge_influence"], option["knowledge_influence"])
            self.assertEqual(entry["knowledge_influence"]["mode"], "informational_context_only")
        validated = validate_production_option_set_v2(source)
        task = create_review_task(validated, request_id="request-m7-2", correlation_id="correlation-m7-2")
        packet["payload"]["source_knowledge_bindings"] = []
        reseal_packet(packet)
        with self.assertRaises(Exception):
            validate_scene_option_review_packet(packet, task=task, option_set=validated)

    def test_repeated_execution_is_deterministic_and_source_is_not_mutated(self):
        source = option_set(); before = copy.deepcopy(source)
        first = prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2")
        second = prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2")
        self.assertEqual(first, second); self.assertEqual(source, before)

    def test_source_and_packet_tampering_fail_closed(self):
        source = option_set(); forged = copy.deepcopy(source)
        forged["payload"]["options"][0]["qualified_rationale"] = "This is the winner."
        with self.assertRaises(Exception): prepare_option_review(forged, request_id="request-m7-2", correlation_id="correlation-m7-2")
        validated = validate_production_option_set_v2(source)
        task = create_review_task(validated, request_id="request-m7-2", correlation_id="correlation-m7-2")
        packet = prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2")
        packet["payload"]["review_entries"][0]["profile_identity"] = "substituted"
        reseal_packet(packet)
        with self.assertRaises(Exception): validate_scene_option_review_packet(packet, task=task, option_set=validated)

    def test_omit_add_reorder_mutate_and_fully_reseal_attacks_fail(self):
        source = option_set(); validated = validate_production_option_set_v2(source)
        task = create_review_task(validated, request_id="request-m7-2", correlation_id="correlation-m7-2")
        base = prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2")
        mutations = (
            lambda packet: packet["payload"]["review_entries"].pop(),
            lambda packet: packet["payload"]["review_entries"].append(copy.deepcopy(packet["payload"]["review_entries"][0])),
            lambda packet: packet["payload"]["review_entries"].reverse(),
            lambda packet: packet["payload"]["review_entries"][0]["considerations"].update({"qualified_rationale": "mutated"}),
            lambda packet: packet["payload"]["review_entries"][0]["unresolved_checks"].pop(),
            lambda packet: packet["payload"]["shared_review_prompts"].pop(),
        )
        for mutate in mutations:
            packet = copy.deepcopy(base); mutate(packet); reseal_packet(packet)
            with self.subTest(mutate=mutate), self.assertRaises(Exception):
                validate_scene_option_review_packet(packet, task=task, option_set=validated)

    def test_task_identifiers_environment_and_source_binding_are_strict(self):
        source = option_set(); validated = validate_production_option_set_v2(source)
        for kwargs in (
            {"request_id": "invalid space", "correlation_id": "correlation-m7-2"},
            {"request_id": "request-m7-2", "correlation_id": "invalid space"},
            {"request_id": "request-m7-2", "correlation_id": "correlation-m7-2", "environment": "production"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(Exception): create_review_task(validated, **kwargs)
        other = option_set(); other["request_id"] = "different-source"
        other["integrity"]["complete_result_sha256"] = canonical_digest({**other, "integrity": {"payload_sha256": other["integrity"]["payload_sha256"]}})
        with self.assertRaises(Exception): validate_scene_option_review_packet(
            prepare_option_review(source, request_id="request-m7-2", correlation_id="correlation-m7-2"),
            task=create_review_task(validate_production_option_set_v2(other), request_id="request-m7-2", correlation_id="correlation-m7-2"),
            option_set=validate_production_option_set_v2(other),
        )

    def test_cli_executes_the_vertical_slice(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"; path.write_text(json.dumps(option_set()), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["movie", "prepare-option-review", "--input", str(path), "--request-id", "request-m7-2", "--environment", "development", "--correlation-id", "correlation-m7-2"])
        response = json.loads(output.getvalue())
        self.assertEqual((code, response["status"], response["output"]["review_packet"]["result_family"]), (0, "success", "scene_option_review_packet"))

    def test_cli_invalid_source_and_environment_fail_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"; path.write_text(json.dumps(option_set()), encoding="utf-8")
            cases = (("production", path), ("development", Path(directory) / "missing.json"))
            for environment, candidate in cases:
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(["movie", "prepare-option-review", "--input", str(candidate), "--request-id", "request-m7-2", "--environment", environment, "--correlation-id", "correlation-m7-2"])
                response = json.loads(output.getvalue())
                with self.subTest(environment=environment, candidate=candidate):
                    self.assertNotEqual(code, 0); self.assertEqual(response.get("status", "error"), "error")


if __name__ == "__main__": unittest.main()
