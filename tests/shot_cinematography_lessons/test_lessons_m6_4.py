import copy
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tests.shot_cinematography_patterns.test_patterns_m6_3 import Audit, context_for, gateway
from tests.shot_observation_context.test_context import observation, seal
from vss_movie_cinematic_lessons import ShotCinematographyLessonRuleCatalogue, create_lesson_candidate_task
from vss_movie_cinematic_patterns import create_pattern_task
from vss_movie_contracts import (
    MovieContractRegistry, validate_shot_cinematography_lesson_candidate_set,
    validate_shot_cinematography_lesson_candidate_task, validate_shot_cinematography_pattern_set,
)
from vss_reasoning.errors import CandidateGenerationFailure, InvalidReasoningRequest
from vss_reasoning_contracts import canonical_digest

ROOT = Path(__file__).resolve().parents[2]


def source_for(raw, *, request_suffix=""):
    context = context_for(raw)
    correlation = "correlation-m6-3" + request_suffix
    pattern_task = create_pattern_task(context, request_id="request-m6-3" + request_suffix, correlation_id=correlation)
    output = gateway().execute_shot_cinematography_patterns(
        pattern_task, context, environment="development", correlation_id=correlation,
    )
    pattern_set = validate_shot_cinematography_pattern_set(
        output["shot_cinematography_pattern_set"], task=pattern_task, context=context,
        invocation_binding_digest=output["invocation_binding_digest"],
    )
    return context, pattern_task, pattern_set, output["invocation_binding_digest"]


def lesson_task(source, *, suffix=""):
    context, pattern_task, pattern_set, pattern_binding = source
    return create_lesson_candidate_task(
        pattern_set, pattern_task=pattern_task, context=context,
        pattern_invocation_binding_digest=pattern_binding,
        request_id="request-m6-4" + suffix, correlation_id="correlation-m6-4" + suffix,
    )


def execute(source, *, suffix="", dry_run=False, shared=None):
    context, pattern_task, pattern_set, pattern_binding = source
    task = lesson_task(source, suffix=suffix)
    return (shared or gateway()).execute_shot_cinematography_lesson_candidates(
        task, pattern_set, pattern_task=pattern_task, context_data=context,
        pattern_invocation_binding_digest=pattern_binding, environment="development",
        correlation_id="correlation-m6-4" + suffix, dry_run=dry_run,
    )


class ShotCinematographyLessonCandidateTests(unittest.TestCase):
    def mixed_source(self):
        raw = [observation(1), observation(2), observation(3)]
        for item, angle in zip(raw, ("level", "level", "low_angle")):
            item["attributes"]["camera_angle"] = {"status": "observed", "value": angle}
            seal(item, "observation_content_digest")
        return source_for(raw)

    def test_recurrence_and_variation_map_one_to_one_with_exact_scope_and_lineage(self):
        source = self.mixed_source()
        output = execute(source)
        payload = output["shot_cinematography_lesson_candidate_set"]["payload"]
        candidates = [item for item in payload["candidates"] if item["proposition"]["attribute"] == "camera_angle"]
        self.assertEqual({item["candidate_type"] for item in candidates},
                         {"recurrence_lesson_candidate", "variation_lesson_candidate"})
        patterns = {item["pattern_id"]: item for item in source[2].value["payload"]["patterns"]}
        for candidate in candidates:
            pattern = patterns[candidate["source_pattern_id"]]
            self.assertEqual(candidate["source_pattern_digest"], pattern["pattern_digest"])
            self.assertEqual(candidate["supporting_evidence_digest"], pattern["supporting_evidence_digest"])
            self.assertEqual(candidate["pattern_set_digest"], source[2].digest)
            self.assertEqual(candidate["pattern_set_complete_digest"], source[2].value["integrity"]["complete_result_sha256"])
            self.assertEqual(candidate["scope"], "exact_source_context")
            self.assertEqual(candidate["context_id"], source[0].value["context_id"])
            self.assertEqual(candidate["complete_context_digest"], source[0].digest)
            self.assertIn("not_admitted_knowledge", candidate["limitations"])

    def test_no_pattern_produces_no_candidate_and_no_cross_pattern_synthesis(self):
        raw = [observation(1), observation(2)]
        raw[1]["attributes"] = {key: {"status": "not_observed"} for key in raw[1]["attributes"]}
        for item in raw: seal(item, "observation_content_digest")
        payload = execute(source_for(raw))["shot_cinematography_lesson_candidate_set"]["payload"]
        self.assertEqual(payload["source_pattern_bindings"], [])
        self.assertEqual(payload["candidates"], [])
        self.assertNotIn("combination", str(payload).lower())

    def test_structured_semantics_have_no_persuasion_causality_truth_or_confidence(self):
        payload = execute(self.mixed_source())["shot_cinematography_lesson_candidate_set"]["payload"]
        text = str(payload).lower()
        for prohibited in ("recommended", "effective", "improve", "preferred", "emotion", "confidence", "is truth", "should use"):
            self.assertNotIn(prohibited, text)
        self.assertIn("no_recommendation", text)
        self.assertIn("no_causal_interpretation", text)

    def test_dry_run_zero_calls_normal_one_call_and_audit_is_terminal(self):
        source = self.mixed_source()
        with patch("vss_reasoning_providers.deterministic_shot_cinematography_lessons.DeterministicShotCinematographyLessonCandidateProvider.derive", autospec=True) as derive:
            ready = execute(source, dry_run=True)
            derive.assert_not_called()
            self.assertEqual(ready["readiness"]["provider_call_count"], 0)
        sink = Audit(); output = execute(source, shared=gateway(sink))
        self.assertEqual(output["provider_call_count"], 1)
        self.assertEqual((len(sink.records), sink.records[0]["provider_call_count"], sink.records[0]["status"]), (1, 1, "success"))
        self.assertNotIn("candidates", sink.records[0])

    def test_pattern_and_task_tampering_fail_before_provider(self):
        source = self.mixed_source(); task = lesson_task(source)
        context, pattern_task, pattern_set, pattern_binding = source
        forged = pattern_set.to_json_value()
        forged["payload"]["patterns"][0]["values"] = ["wide"]
        forged["payload"]["semantic_result_digest"] = canonical_digest({**forged["payload"], "semantic_result_digest": None})
        forged["integrity"]["payload_sha256"] = canonical_digest(forged["payload"])
        forged["integrity"]["complete_result_sha256"] = canonical_digest({**forged, "integrity": {"payload_sha256": forged["integrity"]["payload_sha256"]}})
        with patch("vss_reasoning_providers.deterministic_shot_cinematography_lessons.DeterministicShotCinematographyLessonCandidateProvider.derive", autospec=True) as derive:
            with self.assertRaises(InvalidReasoningRequest):
                gateway().execute_shot_cinematography_lesson_candidates(
                    task, forged, pattern_task=pattern_task, context_data=context,
                    pattern_invocation_binding_digest=pattern_binding, environment="development",
                    correlation_id="correlation-m6-4",
                )
            derive.assert_not_called()
        task_raw = task.to_json_value(); task_raw["rule_catalogue_digest"] = "0" * 64
        task_raw["task_content_digest"] = canonical_digest({key: value for key, value in task_raw.items() if key != "task_content_digest"})
        forged_task = validate_shot_cinematography_lesson_candidate_task(task_raw, pattern_set)
        with self.assertRaises(InvalidReasoningRequest):
            gateway().execute_shot_cinematography_lesson_candidates(
                forged_task, pattern_set, pattern_task=pattern_task, context_data=context,
                pattern_invocation_binding_digest=pattern_binding, environment="development",
                correlation_id="correlation-m6-4",
            )

    def test_result_tampering_duplicate_omission_fabrication_and_outer_reseal_fail(self):
        source = self.mixed_source(); task = lesson_task(source); output = execute(source)
        base = output["shot_cinematography_lesson_candidate_set"]
        for mutate in (
            lambda value: value["payload"]["candidates"][0]["proposition"].update({"occurrence_count": 8}),
            lambda value: value["payload"]["candidates"].append(copy.deepcopy(value["payload"]["candidates"][0])),
            lambda value: value["payload"]["candidates"].pop(),
            lambda value: value["payload"]["candidates"][0].update({"scope": "project_scope"}),
            lambda value: value["payload"]["candidates"][0]["limitations"].pop(),
            lambda value: value["payload"]["candidates"][0].update({"source_pattern_digest": "0" * 64}),
            lambda value: value["payload"]["candidates"][0].update({"pattern_set_digest": "0" * 64}),
            lambda value: value["payload"]["candidates"][0].update({"complete_context_digest": "0" * 64}),
            lambda value: value["payload"]["candidates"][0].update({"recommendation": "use this angle"}),
        ):
            candidate = copy.deepcopy(base); mutate(candidate)
            candidate["payload"]["semantic_result_digest"] = canonical_digest({**candidate["payload"], "semantic_result_digest": None})
            candidate["integrity"]["payload_sha256"] = canonical_digest(candidate["payload"])
            candidate["integrity"]["complete_result_sha256"] = canonical_digest({**candidate, "integrity": {"payload_sha256": candidate["integrity"]["payload_sha256"]}})
            with self.subTest(), self.assertRaises(Exception):
                validate_shot_cinematography_lesson_candidate_set(
                    candidate, task=task, pattern_set=source[2],
                    invocation_binding_digest=output["invocation_binding_digest"],
                )

    def test_arbitrary_recommendation_and_generalization_content_is_structurally_impossible(self):
        source = self.mixed_source(); task = lesson_task(source); output = execute(source)
        for field, content in (("statement", "Use this angle; it is better."),
                               ("generalization", "Directors generally prefer this."),
                               ("effect", "This causes emotion.")):
            candidate = copy.deepcopy(output["shot_cinematography_lesson_candidate_set"])
            candidate["payload"]["candidates"][0][field] = content
            candidate["payload"]["semantic_result_digest"] = canonical_digest({**candidate["payload"], "semantic_result_digest": None})
            candidate["integrity"]["payload_sha256"] = canonical_digest(candidate["payload"])
            candidate["integrity"]["complete_result_sha256"] = canonical_digest({**candidate, "integrity": {"payload_sha256": candidate["integrity"]["payload_sha256"]}})
            with self.subTest(field=field), self.assertRaises(Exception):
                validate_shot_cinematography_lesson_candidate_set(
                    candidate, task=task, pattern_set=source[2],
                    invocation_binding_digest=output["invocation_binding_digest"],
                )

    def test_forged_provider_result_is_rejected_after_one_call(self):
        source = self.mixed_source()
        with patch("vss_reasoning_providers.deterministic_shot_cinematography_lessons.DeterministicShotCinematographyLessonCandidateProvider.derive", return_value=[]):
            with self.assertRaises(CandidateGenerationFailure):
                execute(source)

    def test_exact_dispatch_catalogue_and_registry_fail_closed(self):
        source = self.mixed_source(); registry = MovieContractRegistry.built_in()
        self.assertEqual(registry.resolve_result(
            "derive_shot_cinematography_lesson_candidates/1", "shot_cinematography_lesson_candidate_set/1"),
            "shot_cinematography_lesson_candidate_set/1")
        catalogue = ShotCinematographyLessonRuleCatalogue.built_in()
        self.assertEqual((catalogue.one_candidate_per_pattern, catalogue.knowledge_admission), (True, "off"))
        for version in ("2", "latest", "*", ">=1"):
            with self.subTest(version=version), self.assertRaises(Exception):
                registry.resolve("derive_shot_cinematography_lesson_candidates", version)

    def test_order_key_process_cwd_hash_seed_and_repeated_runs_are_deterministic(self):
        source = self.mixed_source()
        first = execute(source); second = execute(source)
        self.assertEqual(first["semantic_result_digest"], second["semantic_result_digest"])
        self.assertEqual(first["complete_result_digest"], second["complete_result_digest"])
        script = """
from tests.shot_cinematography_lessons.test_lessons_m6_4 import execute, source_for
from tests.shot_observation_context.test_context import observation
print(execute(source_for([observation(1),observation(2)]))['semantic_result_digest'])
"""
        outputs = []
        for seed, cwd in (("11", ROOT), ("733", ROOT / "tests")):
            env = dict(os.environ); env["PYTHONHASHSEED"] = seed; env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
            outputs.append(subprocess.run([sys.executable, "-c", script], cwd=cwd, env=env, check=True, text=True, capture_output=True).stdout.strip())
        self.assertEqual(len(set(outputs)), 1)

    def test_shared_gateway_concurrency_is_isolated(self):
        sources = [source_for([observation(1), observation(2)], request_suffix=f"-{index}") for index in range(2)]
        sink = Audit(); shared = gateway(sink)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda index: execute(sources[index], suffix=f"-{index}", shared=shared), range(2)))
        self.assertEqual(len(outputs), 2)
        self.assertEqual({record["request_id"] for record in sink.records}, {"request-m6-4-0", "request-m6-4-1"})


if __name__ == "__main__":
    unittest.main()
