import copy
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tests.shot_observation_context.test_context import observation, seal
from vss_movie_cinematic_observation import assemble_shot_cinematography_context, create_shot_cinematography_observation_set
from vss_movie_cinematic_patterns import ShotCinematographyPatternRuleCatalogue, create_pattern_task
from vss_movie_contracts import MovieContractRegistry, validate_shot_cinematography_pattern_set, validate_shot_cinematography_pattern_task
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning.registry import ReasoningImplementationRegistry
from vss_reasoning.errors import CandidateGenerationFailure, InvalidReasoningRequest
from vss_reasoning_contracts import canonical_digest

ROOT = Path(__file__).resolve().parents[2]


class Audit:
    def __init__(self): self.records = []
    def append(self, record): self.records.append(record)


def context_for(raw):
    observation_set = create_shot_cinematography_observation_set(raw)
    return assemble_shot_cinematography_context(observation_set, raw).context


def gateway(audit=None):
    return ReasoningGateway._for_testing(implementations=ReasoningImplementationRegistry.built_in(), audit=audit or Audit())


class ShotCinematographyPatternTests(unittest.TestCase):
    def execute(self, raw, *, dry_run=False):
        context = context_for(raw)
        task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        return gateway().execute_shot_cinematography_patterns(task, context, environment="development", correlation_id="correlation-m6-3", dry_run=dry_run)

    def test_repeated_values_and_variation_are_explicit(self):
        raw = [observation(1), observation(2), observation(3)]
        raw[0]["attributes"]["camera_angle"] = {"status":"observed", "value":"level"}
        raw[1]["attributes"]["camera_angle"] = {"status":"observed", "value":"level"}
        raw[2]["attributes"]["camera_angle"] = {"status":"observed", "value":"low_angle"}
        raw = [seal(item, "observation_content_digest") for item in raw]
        payload = self.execute(raw)["shot_cinematography_pattern_set"]["payload"]
        angle = [item for item in payload["patterns"] if item["attribute"] == "camera_angle"]
        self.assertEqual({item["pattern_type"] for item in angle}, {"repeated_value", "variation"})
        repeat = next(item for item in angle if item["pattern_type"] == "repeated_value")
        self.assertEqual((repeat["values"], repeat["occurrence_count"], repeat["eligible_observation_count"]), (["level"], 2, 3))

    def test_qualification_is_preserved_and_only_observed_participates(self):
        raw = [observation(index) for index in range(5)]
        states = ({"status":"observed","value":"wide"}, {"status":"uncertain","value":"wide"}, {"status":"unknown"}, {"status":"not_observed"}, {"status":"not_applicable"})
        for item, state in zip(raw, states):
            item["attributes"]["shot_scale"] = state; seal(item, "observation_content_digest")
        payload = self.execute(raw)["shot_cinematography_pattern_set"]["payload"]
        summary = next(item for item in payload["attribute_summaries"] if item["attribute"] == "shot_scale")
        self.assertEqual(summary["eligible_observation_count"], 1)
        self.assertEqual([item["qualification"] for item in summary["excluded_observations"]], ["uncertain", "unknown", "not_observed", "not_applicable"])
        self.assertEqual(summary["determination"], "insufficient_comparable")
        self.assertFalse(any(item["attribute"] == "shot_scale" for item in payload["patterns"]))

    def test_no_absence_inference_and_no_combination_patterns(self):
        payload = self.execute([observation(1), observation(2)])["shot_cinematography_pattern_set"]["payload"]
        self.assertEqual({item["pattern_type"] for item in payload["patterns"]} - {"repeated_value", "variation"}, set())
        self.assertNotIn("combination", str(payload).lower())
        def keys(node):
            if isinstance(node, dict):
                yield from node
                for value in node.values(): yield from keys(value)
            elif isinstance(node, list):
                for value in node: yield from keys(value)
        self.assertNotIn("confidence", set(keys(payload)))

    def test_two_and_eight_observation_bounds_execute(self):
        for count in (2, 8):
            with self.subTest(count=count):
                output = self.execute([observation(index) for index in range(count)])
                self.assertEqual(len(output["shot_cinematography_pattern_set"]["payload"]["observation_bindings"]), count)

    def test_dry_run_invokes_zero_providers_and_normal_invokes_once(self):
        raw = [observation(1), observation(2)]
        with patch("vss_reasoning_providers.deterministic_shot_cinematography_patterns.DeterministicShotCinematographyPatternProvider.analyze", autospec=True) as analyze:
            ready = self.execute(raw, dry_run=True)
            analyze.assert_not_called()
            self.assertEqual(ready["readiness"]["provider_call_count"], 0)
        normal = self.execute(raw)
        self.assertEqual(normal["provider_call_count"], 1)

    def test_exact_dispatch_and_context_binding_fail_closed(self):
        context = context_for([observation(1), observation(2)])
        task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        for replacement in ("2", "latest", "*", ">=1"):
            raw = task.to_json_value(); raw["task_version"] = replacement; seal(raw, "task_content_digest")
            with self.subTest(version=replacement), self.assertRaises(Exception):
                validate_shot_cinematography_pattern_task(raw, context)
        malformed = context.to_json_value(); malformed["context_family_version"] = "latest"
        with self.assertRaises(InvalidReasoningRequest):
            gateway().execute_shot_cinematography_patterns(task, malformed, environment="development", correlation_id="correlation-m6-3")

    def test_pre_provider_failure_invokes_zero_calls(self):
        context = context_for([observation(1), observation(2)])
        task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        with patch("vss_reasoning_providers.deterministic_shot_cinematography_patterns.DeterministicShotCinematographyPatternProvider.analyze", autospec=True) as analyze:
            with self.assertRaises(InvalidReasoningRequest):
                gateway().execute_shot_cinematography_patterns(task, context, environment="production", correlation_id="correlation-m6-3")
            analyze.assert_not_called()

    def test_forged_result_and_incomplete_evidence_are_rejected(self):
        raw = [observation(1), observation(2)]
        context = context_for(raw); task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        output = gateway().execute_shot_cinematography_patterns(task, context, environment="development", correlation_id="correlation-m6-3")
        value = output["shot_cinematography_pattern_set"]
        forged = copy.deepcopy(value); forged["payload"]["observation_bindings"].pop()
        forged["payload"]["semantic_result_digest"] = canonical_digest({**forged["payload"], "semantic_result_digest": None})
        forged["integrity"]["payload_sha256"] = canonical_digest(forged["payload"])
        forged["integrity"]["complete_result_sha256"] = canonical_digest({**forged, "integrity":{"payload_sha256":forged["integrity"]["payload_sha256"]}})
        with self.assertRaises(Exception):
            validate_shot_cinematography_pattern_set(forged, task=task, context=context, invocation_binding_digest=output["invocation_binding_digest"])

    def test_forged_provider_analysis_is_rejected(self):
        raw = [observation(1), observation(2)]
        context = context_for(raw); task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        with patch("vss_reasoning_providers.deterministic_shot_cinematography_patterns.DeterministicShotCinematographyPatternProvider.analyze", return_value={"attribute_summaries": [], "patterns": []}):
            with self.assertRaises(CandidateGenerationFailure):
                gateway().execute_shot_cinematography_patterns(task, context, environment="development", correlation_id="correlation-m6-3")

    def test_resealed_context_projection_is_rejected_before_provider(self):
        context = context_for([observation(1), observation(2)])
        task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        forged = context.to_json_value(); forged["payload"]["observations"][0]["attributes"]["shot_scale"]["value"] = "wide"
        forged["context_content_digest"] = canonical_digest(forged["payload"])
        forged["context_id"] = "shot-context-" + forged["context_content_digest"][:32]
        forged["integrity"]["complete_context_sha256"] = canonical_digest({**forged, "integrity":{}})
        with self.assertRaises(InvalidReasoningRequest):
            gateway().execute_shot_cinematography_patterns(task, forged, environment="development", correlation_id="correlation-m6-3")

    def test_input_order_key_order_and_repeated_execution_are_deterministic(self):
        raw = [observation(3), observation(1), observation(2)]
        first = self.execute(raw); second = self.execute([dict(reversed(list(item.items()))) for item in reversed(raw)])
        self.assertEqual(first["semantic_result_digest"], second["semantic_result_digest"])
        self.assertEqual(first["complete_result_digest"], second["complete_result_digest"])

    def test_hash_seed_working_directory_and_concurrency_are_deterministic(self):
        script = """
from tests.shot_observation_context.test_context import observation
from tests.shot_cinematography_patterns.test_patterns_m6_3 import context_for, gateway
from vss_movie_cinematic_patterns import create_pattern_task
c=context_for([observation(1),observation(2),observation(3)])
t=create_pattern_task(c,request_id='request-m6-3',correlation_id='correlation-m6-3')
print(gateway().execute_shot_cinematography_patterns(t,c,environment='development',correlation_id='correlation-m6-3')['semantic_result_digest'])
"""
        outputs = []
        for seed, cwd in (("7", ROOT), ("991", ROOT / "tests")):
            env = dict(os.environ); env["PYTHONHASHSEED"] = seed; env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
            outputs.append(subprocess.run([sys.executable, "-c", script], cwd=cwd, env=env, check=True, text=True, capture_output=True).stdout.strip())
        self.assertEqual(len(set(outputs)), 1)
        raw = [observation(1), observation(2), observation(3)]
        context = context_for(raw)
        task = create_pattern_task(context, request_id="request-m6-3", correlation_id="correlation-m6-3")
        shared = gateway()
        with ThreadPoolExecutor(max_workers=4) as pool:
            digests = list(pool.map(lambda _: shared.execute_shot_cinematography_patterns(task, context, environment="development", correlation_id="correlation-m6-3")["semantic_result_digest"], range(8)))
        self.assertEqual(len(set(digests)), 1)

    def test_registry_catalogue_and_schema_are_exact(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(registry.resolve_result("analyze_shot_cinematography_patterns/1", "shot_cinematography_pattern_set/1"), "shot_cinematography_pattern_set/1")
        self.assertEqual(ShotCinematographyPatternRuleCatalogue.built_in().recurrence_threshold, 2)
        for version in ("2", "latest", "*", ">=1"):
            with self.subTest(version=version), self.assertRaises(Exception): registry.resolve("analyze_shot_cinematography_patterns", version)


if __name__ == "__main__":
    unittest.main()
