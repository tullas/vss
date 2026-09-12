from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / "docs/reviews/m11-3-film1-shot3-creative-acceptance.json"


class Film1Shot3AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))

    def test_acceptance_is_sealed_to_authoritative_shot3_media(self):
        review = self.review
        self.assertEqual(review["film_id"], "film-1")
        self.assertEqual(review["shot_id"], "shot-471187bad6ae782a5ef83800")
        self.assertEqual(review["request_sha256"], "6f482e960dc12faa5f9bfc51599a423cb6364374ebc8bb58d919ca6212095d86")
        self.assertEqual(review["decision"], "ACCEPT")
        self.assertEqual(review["disposition"], "USE")
        self.assertEqual(review["provider"]["operation_name"], "projects/vss-film-poc/locations/us-central1/publishers/google/models/veo-3.1-generate-001/operations/f9615177-e991-4bf3-ab67-b89b2ad6b2d8")
        self.assertEqual(review["provider"]["actual_cost_usd"], "UNKNOWN")
        self.assertEqual(review["artifact"]["sha256"], "9a957db8712d00361d49174f15152197504055b347615b43ff128f9423eb838a")
        self.assertEqual(review["artifact"]["duration_seconds"], 8.0)
        self.assertEqual(review["artifact"]["resolution"], "1280x720")
        self.assertEqual(review["artifact"]["frame_rate"], "24/1")
        self.assertIs(review["artifact"]["audio"], False)
        material = {**review, "review_sha256": "0" * 64}
        canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(review["review_sha256"], hashlib.sha256(canonical).hexdigest())

    def test_use_binds_only_immediate_shot4_continuity_not_story_canon(self):
        review = self.review
        continuity = review["continuity_authority"]
        self.assertEqual(continuity["for_shot_number"], 4)
        self.assertEqual(continuity["source_shot_id"], review["shot_id"])
        self.assertEqual(continuity["source_artifact_sha256"], review["artifact"]["sha256"])
        self.assertEqual(continuity["scope"], "primary_immediate_visual_continuity_only")
        self.assertIs(continuity["incidental_generated_details_are_permanent_story_canon"], False)
        self.assertTrue(all(value is False for value in review["authority"].values()))
        self.assertIn("does_not_authorize_shot_4_generation", review["limitations"])


if __name__ == "__main__":
    unittest.main()
