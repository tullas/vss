"""Offline-only checks for the Film #1 adjacent Shot 2 planning package."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/experiments/m11-2-film1-shot2-continuity-plan.json"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class Film1Shot2PlanTests(unittest.TestCase):
    def test_plan_is_one_inert_adjacent_shot_with_fixed_bound(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(plan["status"], "offline_provider_execution_plan")
        self.assertEqual(plan["shot_2"]["shot_order"], 3)
        self.assertEqual(plan["shot_2"]["relationship_to_shot_1"], "adjacent_consecutive")
        self.assertEqual(plan["cost"]["expected_cost_usd"], "1.600000")
        self.assertEqual(plan["cost"]["hard_ceiling_usd"], "5.000000")
        self.assertEqual(plan["provider_request"]["maximum_provider_attempts"], 1)
        self.assertEqual(plan["provider_request"]["duration_seconds"], 8)
        self.assertFalse(plan["provider_request"]["generate_audio"])
        self.assertFalse(plan["authority"]["provider_execution"])
        self.assertIsNone(plan["offline_rehearsal"]["attempt_number"])
        self.assertEqual(plan["creative_decision"]["decision"], "APPROVE")

    def test_source_digests_and_request_seal_are_deterministic(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        image = ROOT / plan["source_visual_reference"]["primary_image_reference"]
        self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), plan["source_visual_reference"]["primary_image_sha256"])
        request = dict(plan["provider_request"])
        request["source_visual_reference_sha256"] = plan["source_visual_reference"]["primary_image_sha256"]
        request["shot_1_accepted_artifact_sha256"] = plan["shot_1_anchor"]["accepted_artifact_sha256"]
        request["scene_id"] = plan["shot_2"]["scene_id"]
        request["shot_id"] = plan["shot_2"]["shot_id"]
        request["request_sha256"] = "0" * 64
        digest = hashlib.sha256(canonical(request)).hexdigest()
        self.assertEqual(digest, plan["deterministic_binding"]["provider_request_sha256"])

    def test_package_seal_includes_approved_pricing(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        package["deterministic_binding"]["package_sha256"] = "0" * 64
        digest = hashlib.sha256(canonical(package)).hexdigest()
        self.assertEqual(digest, plan["deterministic_binding"]["package_sha256"])

    def test_rehearsal_proves_no_provider_or_attempt(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        rehearsal = plan["offline_rehearsal"]
        self.assertEqual(rehearsal["result"], "passed")
        self.assertFalse(rehearsal["provider_invoked"])
        self.assertEqual(rehearsal["provider_call_count"], 0)
        self.assertFalse(rehearsal["paid_attempt"])
        self.assertIn("no Runtime invocation", rehearsal["no_provider_call_evidence"])


if __name__ == "__main__":
    unittest.main()
