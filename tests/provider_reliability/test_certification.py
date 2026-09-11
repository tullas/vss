import copy
import json
import tempfile
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

from vss_provider_reliability import (
    ExpertiseDisposition,
    assess_certification_readiness,
    assert_request_matches_certification,
    assert_production_eligible,
    classify_expertise,
    durable_moving_shot_package,
    reconstruct_durable_moving_shot_request,
    validate_provider_certification,
)
from vss_movie_moving_shot import admit_moving_shot


ROOT = Path(__file__).resolve().parents[2]
CERTIFICATION = ROOT / "docs/provider-certifications/google-vertex-ai-veo-3.1-generate-001.json"


class CertificationTests(unittest.TestCase):
    def _request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "basis.png"
            path.write_bytes(b"authoritative-png")
            import hashlib
            return admit_moving_shot(
                shot_id="shot-0123456789abcdef01234567", scene_id="scene-0123456789abcdef01234567",
                visual_basis_path=path, visual_basis_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                prompt="A bounded adjacent shot", source_lineage={"storyboard_sha256": "a" * 64},
                production_id="vikramaditya-local",
            ).request

    def test_domain_inventory_requires_specialist_contract_for_external_domains(self):
        result = classify_expertise({"generative_video": "external", "deterministic_hashing": "local"})
        self.assertEqual(result["generative_video"], ExpertiseDisposition.SPECIALIST_CONTRACT)
        self.assertEqual(result["deterministic_hashing"], ExpertiseDisposition.SPECIALIST_REVIEW)

    def test_provider_certification_document_matches_strict_schema(self):
        schema = json.loads((ROOT / "schemas/provider-certification-v1.schema.json").read_text())
        value = json.loads(CERTIFICATION.read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(value)), [])

    def test_unknown_or_stale_certification_cannot_be_production_eligible(self):
        value = json.loads(CERTIFICATION.read_text())
        for status in ("UNKNOWN", "STALE"):
            candidate = copy.deepcopy(value)
            candidate["live_certification"]["status"] = status
            validate_provider_certification(candidate)
            with self.assertRaises(ValueError):
                assert_production_eligible(candidate)

    def test_certification_is_provider_specific_and_metadata_probe_is_explicitly_unsupported(self):
        value = json.loads(CERTIFICATION.read_text())
        self.assertTrue(any(item.startswith("GET publisher model metadata is not a supported readiness assumption") for item in value["unsupported_probes"]))
        self.assertFalse(value["authority"]["provider_execution"])
        readiness = assess_certification_readiness(value, credential_present=True, quota_evidence_valid=True, configuration_valid=True)
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["provider_call_count"], 0)
        self.assertFalse(readiness["checks"]["metadata_lookup_required"])

    def test_provider_contract_mismatch_and_uncertified_provider_fail_closed(self):
        value = json.loads(CERTIFICATION.read_text())
        request = self._request()
        assert_request_matches_certification(request, value)
        wrong = copy.deepcopy(request)
        wrong["provider"]["model_snapshot"] = "unknown-model"
        with self.assertRaises(ValueError):
            assert_request_matches_certification(wrong, value)

    def test_serialized_package_reconstructs_request_and_namespace(self):
        request = self._request()
        package = durable_moving_shot_package(request, {"storyboard": "a" * 64})
        reloaded = json.loads(json.dumps(package))
        reconstructed, digest, namespace = reconstruct_durable_moving_shot_request(reloaded)
        self.assertEqual(reconstructed, request)
        self.assertEqual(digest, request["request_sha256"])
        self.assertEqual(namespace, "vikramaditya-local/shot-0123456789abcdef01234567")

    def test_missing_lineage_and_resealed_substitution_fail_closed(self):
        request = self._request()
        package = durable_moving_shot_package(request, {"storyboard": "a" * 64})
        missing = copy.deepcopy(package)
        del missing["canonical_request"]["source_lineage"]
        with self.assertRaises(ValueError):
            reconstruct_durable_moving_shot_request(missing)
        forged = copy.deepcopy(package)
        forged["canonical_request"]["prompt"] = "substituted"
        with self.assertRaises(ValueError):
            reconstruct_durable_moving_shot_request(forged)


if __name__ == "__main__":
    unittest.main()
