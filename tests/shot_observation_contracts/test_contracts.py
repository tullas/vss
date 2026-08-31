import copy
import json
import unittest
from pathlib import Path
from math import inf, nan

from jsonschema import Draft202012Validator
from vss_movie_contracts import MovieContractRegistry, validate_shot_cinematography_observation
from vss_movie_contracts.errors import MovieContractError
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "shot_observation"

def fixture(name):
    return json.loads((FIXTURES / name).read_text())

def redigest(value):
    value["observation_content_digest"] = canonical_digest({k: v for k, v in value.items() if k != "observation_content_digest"})
    return value

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
                reordered = dict(reversed(list(value.items())))
                self.assertEqual(first.digest, validate_shot_cinematography_observation(reordered).digest)

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
        uncertain = validate_shot_cinematography_observation(fixture("low-angle-close-shot-valid.json"))
        self.assertEqual(dict(uncertain.value["attributes"]["composition"]), {"status": "uncertain", "value": "rule_of_thirds"})

    def test_provenance_pairing_is_strict(self):
        value = fixture("static-medium-shot-valid.json")
        value["provenance"]["method_identity"] = "synthetic_fixture"
        redigest(value)
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)
        schema = thaw_json(MovieContractRegistry.built_in().schemas["shot_cinematography_observation/1"]["schema"])
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))

    def test_integrity_is_rejected(self):
        value = fixture("static-medium-shot-valid.json")
        value["attributes"]["subject_count"]["value"] = 2
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(value)

    def test_narrow_vocabulary_and_single_subject_direction_are_enforced(self):
        for field, rejected in (("camera_angle", "overhead"), ("camera_movement", "handheld"),
                                ("camera_movement", "stabilized"), ("composition", "balanced"),
                                ("composition", "unbalanced")):
            with self.subTest(field=field, value=rejected):
                value = fixture("static-medium-shot-valid.json")
                value["attributes"][field] = {"status": "observed", "value": rejected}
                with self.assertRaises(MovieContractError):
                    validate_shot_cinematography_observation(redigest(value))
        value = fixture("low-angle-close-shot-valid.json")
        value["attributes"]["subject_count"] = {"status": "observed", "value": 2}
        with self.assertRaises(MovieContractError):
            validate_shot_cinematography_observation(redigest(value))

    def test_numeric_bounds_non_finite_values_and_boolean_count_are_rejected(self):
        cases = (("subject_count", -1), ("subject_count", 129), ("subject_count", True),
                 ("focal_length_mm", 0), ("focal_length_mm", 2001),
                 ("focal_length_mm", nan), ("focal_length_mm", inf))
        for field, candidate in cases:
            with self.subTest(field=field, candidate=candidate):
                value = fixture("static-medium-shot-valid.json")
                value["attributes"][field] = {"status": "observed", "value": candidate}
                with self.assertRaises(MovieContractError):
                    validate_shot_cinematography_observation(value if candidate != candidate or candidate == inf else redigest(value))

    def test_zero_subject_count_is_explicit_and_requires_no_direction(self):
        value = fixture("static-medium-shot-valid.json")
        value["attributes"]["subject_count"] = {"status": "observed", "value": 0}
        value["attributes"]["screen_direction"] = {"status": "not_applicable"}
        artifact = validate_shot_cinematography_observation(redigest(value))
        self.assertEqual(artifact.value["attributes"]["subject_count"]["value"], 0)

    def test_registry_digest_is_deterministic_and_only_new_registration_is_added(self):
        first = MovieContractRegistry.built_in()
        second = MovieContractRegistry.built_in()
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.digest, "011c1bcfcbd5442c8f6fe452b7858e043ac18d6c9a18ddc28c4f8dd2175da34b")  # pragma: allowlist secret
        self.assertEqual(sum(r.identity == "shot_cinematography_observation/1" for r in first.registrations), 1)

if __name__ == "__main__":
    unittest.main()
