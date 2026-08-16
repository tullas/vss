import copy
import json
import unittest
from pathlib import Path

from vss_movie_contracts import MovieContractRegistry, validate_shot_cinematography_observation
from vss_movie_contracts.errors import MovieContractError
from vss_reasoning_contracts import canonical_digest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "shot_observation"

def fixture(name):
    return json.loads((FIXTURES / name).read_text())

class ShotObservationContractTests(unittest.TestCase):
    valid_names = (
        "static-medium-shot-valid.json", "low-angle-close-shot-valid.json",
        "moving-wide-shot-valid.json", "unknown-attribute-valid.json",
    )

    def test_representative_manual_and_synthetic_fixtures_are_valid(self):
        for name in self.valid_names:
            with self.subTest(name=name):
                value = fixture(name)
                first = validate_shot_cinematography_observation(value)
                second = validate_shot_cinematography_observation(copy.deepcopy(value))
                self.assertEqual(first.digest, second.digest)

    def test_exact_version_dispatch_has_no_fallback(self):
        registry = MovieContractRegistry.built_in()
        self.assertEqual(registry.resolve("shot_cinematography_observation", "1").identity, "shot_cinematography_observation/1")
        for version in ("2", "latest", "*"):
            with self.subTest(version=version), self.assertRaises(MovieContractError):
                registry.resolve("shot_cinematography_observation", version)
        value = fixture("static-medium-shot-valid.json")
        value["contract_version"] = "2"
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)

    def test_closed_schema_rejects_invalid_fixtures(self):
        for name in ("invalid-enum.json", "malformed-identity.json", "unsupported-field.json"):
            with self.subTest(name=name), self.assertRaises(MovieContractError):
                validate_shot_cinematography_observation(fixture(name))

    def test_required_fields_and_qualified_value_combinations_are_exact(self):
        value = fixture("static-medium-shot-valid.json")
        del value["shot_id"]
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)
        value = fixture("static-medium-shot-valid.json")
        value["attributes"]["camera_angle"] = {"status": "unknown", "value": "level"}
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)
        value = fixture("static-medium-shot-valid.json")
        value["attributes"]["camera_angle"] = {"status": "observed"}
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)

    def test_unknown_states_remain_distinct_and_are_not_inferred(self):
        value = fixture("unknown-attribute-valid.json")
        artifact = validate_shot_cinematography_observation(value)
        self.assertEqual(artifact.value["attributes"]["camera_angle"]["status"], "unknown")
        self.assertEqual(artifact.value["attributes"]["camera_elevation"]["status"], "not_observed")
        self.assertEqual(artifact.value["attributes"]["screen_direction"]["status"], "not_applicable")

    def test_provenance_pairing_is_strict(self):
        value = fixture("static-medium-shot-valid.json")
        value["provenance"]["method_identity"] = "synthetic_fixture"
        value["observation_content_digest"] = canonical_digest({k: v for k, v in value.items() if k != "observation_content_digest"})
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)

    def test_integrity_is_rejected(self):
        value = fixture("static-medium-shot-valid.json")
        value["attributes"]["subject_count"]["value"] = 2
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)

    def test_registry_digest_is_deterministic_and_only_new_registration_is_added(self):
        first = MovieContractRegistry.built_in()
        second = MovieContractRegistry.built_in()
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.digest, "fc2441d82cbc7d8b899b69904ca6a5d1a3a795b573a28a6158d80bee347a5e94")  # pragma: allowlist secret
        self.assertEqual(sum(r.identity == "shot_cinematography_observation/1" for r in first.registrations), 1)

if __name__ == "__main__":
    unittest.main()
