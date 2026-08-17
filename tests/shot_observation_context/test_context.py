import copy
import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vss_context_contracts import ContextContractRegistry
from vss_context_contracts.errors import ContextRegistryError, InvalidContextInput
from vss_context_contracts.validation import validate_context
from vss_movie_cinematic_observation import (
    MAX_OBSERVATIONS,
    assemble_shot_cinematography_context,
    create_shot_cinematography_observation_set,
    validate_shot_cinematography_context,
)
from vss_movie_contracts import MovieContractRegistry, validate_shot_cinematography_observation_set
from vss_movie_contracts.errors import MovieContractError
from vss_reasoning_contracts import canonical_digest

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "tests/fixtures/shot_observation/static-medium-shot-valid.json").read_text())


def seal(value, field):
    value[field] = canonical_digest({key: item for key, item in value.items() if key != field})
    return value


def observation(index, *, project="project-m6-synthetic", scene="scene-courtyard-001", classification="internal"):
    value = copy.deepcopy(BASE)
    value["observation_id"] = f"shot-observation-context-{index:02d}"
    value["project_id"] = project
    value["scene_id"] = scene
    value["shot_id"] = f"shot-courtyard-context-{index:02d}"
    value["evidence_reference"] = f"evidence-synthetic-context-{index:02d}"
    value["classification"] = classification
    if index % 3 == 1:
        value["attributes"]["composition"] = {"status": "uncertain", "value": "rule_of_thirds"}
    elif index % 3 == 2:
        value["attributes"]["composition"] = {"status": "unknown"}
    return seal(value, "observation_content_digest")


def context_material(value):
    value["context_content_digest"] = canonical_digest(value["payload"])
    value["context_id"] = "shot-context-" + value["context_content_digest"][:32]
    value["integrity"]["complete_context_sha256"] = canonical_digest({**value, "integrity": {}})
    return value


class ShotObservationContextTests(unittest.TestCase):
    def test_two_observations_build_an_immutable_non_reasoning_context(self):
        raw = [observation(1), observation(2)]
        observation_set = create_shot_cinematography_observation_set(raw)
        result = assemble_shot_cinematography_context(observation_set, raw)
        self.assertEqual(result.context.value["context_family"], "shot_cinematography_context")
        self.assertEqual(result.context.value["purpose"], "shot_cinematography_local_analysis")
        self.assertEqual(result.context.value["payload"]["set_semantics"], "unordered_exact")
        self.assertEqual([item["attributes"]["composition"]["status"] for item in result.context.value["payload"]["observations"]], ["uncertain", "unknown"])
        self.assertNotIn("semantic_task", result.context.value)
        with self.assertRaises(TypeError):
            result.context.value["purpose"] = "changed"

    def test_maximum_bound_is_admitted_and_pairwise_growth_is_explicit(self):
        raw = [observation(index) for index in range(MAX_OBSERVATIONS)]
        result = assemble_shot_cinematography_context(create_shot_cinematography_observation_set(raw), raw)
        self.assertEqual(len(result.context.value["payload"]["observations"]), 8)
        self.assertEqual(result.context.value["payload"]["budget_summary"]["maximum_future_pairwise_comparisons"], 28)

    def test_minimum_and_maximum_bounds_fail_closed(self):
        for raw in ([observation(1)], [observation(index) for index in range(9)]):
            with self.subTest(count=len(raw)), self.assertRaises(ValueError):
                create_shot_cinematography_observation_set(raw)

    def test_unordered_input_has_one_canonical_set_and_context(self):
        raw = [observation(3), observation(1), observation(2)]
        first_set = create_shot_cinematography_observation_set(raw)
        second_set = create_shot_cinematography_observation_set(list(reversed(raw)))
        self.assertEqual(first_set.digest, second_set.digest)
        first = assemble_shot_cinematography_context(first_set, raw)
        second = assemble_shot_cinematography_context(second_set, list(reversed(raw)))
        self.assertEqual(first.context.digest, second.context.digest)
        self.assertEqual(first.report, second.report)

    def test_duplicate_observation_and_shot_identities_are_rejected(self):
        one = observation(1)
        with self.assertRaises(ValueError):
            create_shot_cinematography_observation_set([one, copy.deepcopy(one)])
        two = observation(2)
        two["shot_id"] = one["shot_id"]
        seal(two, "observation_content_digest")
        with self.assertRaises(ValueError):
            create_shot_cinematography_observation_set([one, two])

    def test_digest_mutation_and_wrong_observation_contract_fail(self):
        raw = [observation(1), observation(2)]
        observation_set = create_shot_cinematography_observation_set(raw)
        mutated = copy.deepcopy(raw)
        mutated[0]["attributes"]["shot_scale"]["value"] = "wide"
        with self.assertRaises(MovieContractError):
            assemble_shot_cinematography_context(observation_set, mutated)
        for replacement in ("2", "latest", "*", ">=1"):
            wrong = copy.deepcopy(raw)
            wrong[0]["contract_version"] = replacement
            with self.subTest(version=replacement), self.assertRaises(MovieContractError):
                create_shot_cinematography_observation_set(wrong)

    def test_mixed_scope_and_classification_downgrade_fail_closed(self):
        cases = (
            [observation(1), observation(2, project="project-other")],
            [observation(1), observation(2, scene="scene-other")],
            [observation(1), observation(2, classification="public")],
        )
        for raw in cases:
            with self.subTest(), self.assertRaises(ValueError):
                create_shot_cinematography_observation_set(raw)
        raw = [observation(1), observation(2)]
        value = create_shot_cinematography_observation_set(raw).to_json_value()
        value["classification"] = "public"
        seal(value, "content_digest")
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation_set(value, raw)

    def test_set_purpose_version_binding_and_bool_bound_are_exact(self):
        raw = [observation(1), observation(2)]
        original = create_shot_cinematography_observation_set(raw).to_json_value()
        mutations = (("purpose", "cinematic_observation_local_validation"), ("contract_version", "latest"))
        for field, replacement in mutations:
            value = copy.deepcopy(original)
            value[field] = replacement
            seal(value, "content_digest")
            with self.subTest(field=field), self.assertRaises(MovieContractError):
                validate_shot_cinematography_observation_set(value, raw)
        value = copy.deepcopy(original)
        value["bounds"]["maximum_observations"] = True
        seal(value, "content_digest")
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation_set(value, raw)

    def test_context_projection_cannot_be_resealed_by_caller(self):
        raw = [observation(1), observation(2)]
        observation_set = create_shot_cinematography_observation_set(raw)
        context = assemble_shot_cinematography_context(observation_set, raw).context.to_json_value()
        context["payload"]["observations"][0]["attributes"]["shot_scale"] = {"status": "observed", "value": "wide"}
        context_material(context)
        with self.assertRaises(ValueError):
            validate_shot_cinematography_context(context, observation_set=observation_set, observations=raw)
        with self.assertRaises(InvalidContextInput):
            validate_context(context, ContextContractRegistry.built_in())
        malformed = assemble_shot_cinematography_context(observation_set, raw).context.to_json_value()
        del malformed["payload"]["observations"][0]["provenance"]
        context_material(malformed)
        with self.assertRaises(ValueError):
            validate_shot_cinematography_context(malformed, observation_set=observation_set, observations=raw)

    def test_context_scope_and_classification_cannot_be_resealed(self):
        raw = [observation(1), observation(2)]
        observation_set = create_shot_cinematography_observation_set(raw)
        original = assemble_shot_cinematography_context(observation_set, raw).context.to_json_value()
        for field, replacement in (
            ("project_id", "project-other"),
            ("scene_id", "scene-other"),
            ("classification", "public"),
        ):
            value = copy.deepcopy(original)
            value[field] = replacement
            context_material(value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_shot_cinematography_context(
                    value,
                    observation_set=observation_set,
                    observations=raw,
                )

    def test_context_registry_is_exact(self):
        registry = ContextContractRegistry.built_in()
        self.assertEqual(registry.resolve("shot_cinematography_context", "1").schema_identity, "vss.shot_cinematography_context/1")
        self.assertEqual(registry.digest, "91db620f1c7b6c657171d2be509a806db2f9f1e319313822ab1180913b5504b5")  # pragma: allowlist secret
        for version in ("2", "latest", "*", ">=1"):
            with self.subTest(version=version), self.assertRaises(ContextRegistryError):
                registry.resolve("shot_cinematography_context", version)

    def test_observation_set_registry_is_exact(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(
            registry.resolve("shot_cinematography_observation_set", "1").schema_identity,
            "vss.movie.shot_cinematography_observation_set/1/1",
        )
        for version in ("2", "latest", "*", ">=1"):
            with self.subTest(version=version), self.assertRaises(MovieContractError):
                registry.resolve("shot_cinematography_observation_set", version)

    def test_repeated_concurrent_construction_is_deterministic(self):
        raw = [observation(1), observation(2), observation(3)]
        observation_set = create_shot_cinematography_observation_set(raw)
        with ThreadPoolExecutor(max_workers=8) as pool:
            digests = list(pool.map(lambda _: assemble_shot_cinematography_context(observation_set, raw).context.digest, range(32)))
        self.assertEqual(len(set(digests)), 1)

    def test_key_order_and_caller_aliases_do_not_change_sealed_artifacts(self):
        raw = [observation(1), observation(2)]
        reordered = [dict(reversed(list(item.items()))) for item in raw]
        first_set = create_shot_cinematography_observation_set(raw)
        second_set = create_shot_cinematography_observation_set(reordered)
        first = assemble_shot_cinematography_context(first_set, raw)
        second = assemble_shot_cinematography_context(second_set, reordered)
        self.assertEqual(first_set.digest, second_set.digest)
        self.assertEqual(first.context.digest, second.context.digest)
        sealed_scale = dict(first.context.value["payload"]["observations"][0]["attributes"]["shot_scale"])
        raw[0]["attributes"]["shot_scale"] = {"status": "observed", "value": "wide"}
        self.assertEqual(
            dict(first.context.value["payload"]["observations"][0]["attributes"]["shot_scale"]),
            sealed_scale,
        )

    def test_process_hash_seed_and_working_directory_do_not_change_digest(self):
        script = """
from tests.shot_observation_context.test_context import observation
from vss_movie_cinematic_observation import create_shot_cinematography_observation_set, assemble_shot_cinematography_context
raw=[observation(1),observation(2),observation(3)]
print(assemble_shot_cinematography_context(create_shot_cinematography_observation_set(raw),raw).context.digest)
"""
        outputs = []
        for seed, cwd in (("1", ROOT), ("773", ROOT / "tests")):
            environment = dict(os.environ)
            environment["PYTHONHASHSEED"] = seed
            environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
            outputs.append(subprocess.run([sys.executable, "-c", script], cwd=cwd, env=environment, check=True, text=True, capture_output=True).stdout.strip())
        self.assertEqual(len(set(outputs)), 1)


if __name__ == "__main__":
    unittest.main()
