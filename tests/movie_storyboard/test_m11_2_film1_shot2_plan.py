"""Offline-only checks for the Film #1 adjacent Shot 2 planning package."""

import hashlib
import json
from pathlib import Path
import unittest
import tempfile
import time

from vss_movie_moving_shot import AttemptLedger, AttemptLedgerError, admit_moving_shot, build_moving_shot_request, record_existing_authorization, validate_moving_shot_admission
from vss_runtime import RuntimeController
from vss_runtime.audit import AuditLogger


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/experiments/m11-2-film1-shot2-continuity-plan.json"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class Film1Shot2PlanTests(unittest.TestCase):
    def test_shot_one_attempt_five_state_remains_historical(self):
        namespace = ROOT / ".local/movie/m11-0-moving-shot/attempt-5"
        self.assertEqual(
            (namespace / "9a7fb8229afabd087db5128efc4a1cb788a0a1fe4d8e34aec09185854320e76b.attempt.json").read_text(),
            '{"attempts":1,"maximum_cost_usd":"5.000000","request_sha256":"9a7fb8229afabd087db5128efc4a1cb788a0a1fe4d8e34aec09185854320e76b","status":"failed"}',
        )
        self.assertEqual(
            (namespace / "authorization.json").read_text(),
            '{"attempts":0,"maximum_provider_attempts":1,"request_sha256":"9a7fb8229afabd087db5128efc4a1cb788a0a1fe4d8e34aec09185854320e76b","source":"preexisting_human_authorization","status":"authorized"}',
        )

    def test_shot_scoped_execution_identity_is_independent_and_not_attempt_six(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        shot_1_namespace = "m11-0-moving-shot/attempt-5"
        shot_2_namespace = f"m11-0-moving-shot/{plan['shot_2']['shot_id']}"
        self.assertNotEqual(shot_1_namespace, shot_2_namespace)
        self.assertNotIn("attempt-6", shot_2_namespace)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            shot_1 = root / shot_1_namespace
            shot_2 = root / shot_2_namespace
            shot_1.mkdir(parents=True)
            historical = {"attempts": 1, "maximum_cost_usd": "5.000000",
                          "request_sha256": "a" * 64, "status": "completed"}
            historical_path = shot_1 / "historical.attempt.json"
            historical_path.write_text(json.dumps(historical, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            historical_bytes = historical_path.read_bytes()
            record_existing_authorization(shot_2 / "authorization.json", "b" * 64)
            ledger = AttemptLedger(shot_2 / "b.attempt.json", "b" * 64)
            ledger.reserve_execution()
            self.assertEqual(historical_path.read_bytes(), historical_bytes)
            self.assertEqual(json.loads((shot_2 / "authorization.json").read_text())["request_sha256"], "b" * 64)
            self.assertEqual(json.loads(ledger.path.read_text())["status"], "reserved")
            ledger.release_execution()
            self.assertEqual(json.loads(ledger.path.read_text())["attempts"], 0)
            ledger.reserve_execution()
            self.assertEqual(json.loads(ledger.path.read_text())["status"], "reserved")

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
        admission = self._admission(plan)
        validate_moving_shot_admission(admission)
        self.assertEqual(admission.request_sha256, plan["deterministic_binding"]["provider_request_sha256"])

    def _admission(self, plan):
        image = ROOT / plan["source_visual_reference"]["primary_image_reference"]
        return admit_moving_shot(
            shot_id=plan["shot_2"]["shot_id"], scene_id=plan["shot_2"]["scene_id"],
            visual_basis_path=image,
            visual_basis_sha256=plan["source_visual_reference"]["primary_image_sha256"],
            prompt=plan["provider_request"]["prompt"],
            source_lineage={key: value for key, value in plan["shot_2"]["source_context"].items()
                            if key.endswith("_sha256")},
            production_id=plan["shot_2"]["project_id"],
        )

    def test_plan_authorization_and_runtime_share_one_binding(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        admission = self._admission(plan)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            authorization = Path(directory) / "authorization.json"
            record_existing_authorization(authorization, admission.request_sha256)
            recorded = json.loads(authorization.read_text(encoding="utf-8"))
            self.assertEqual(recorded["request_sha256"], plan["deterministic_binding"]["provider_request_sha256"])
            rebuilt = build_moving_shot_request(
                shot_id=admission.request["scope"]["shot_id"],
                scene_id=admission.request["scope"]["scene_id"],
                visual_basis_sha256=admission.request["production_input"]["content_sha256"],
                visual_basis_byte_count=admission.request["production_input"]["byte_count"],
                prompt=admission.request["prompt"],
                source_lineage=admission.request["source_lineage"],
                production_id=admission.request["scope"]["production_id"],
            )
            rebuilt["request_sha256"] = hashlib.sha256(canonical(rebuilt)).hexdigest()
            self.assertEqual(rebuilt["request_sha256"], admission.request_sha256)

    def test_runtime_preflight_admits_the_authorized_plan_binding_without_effects(self):
        plan = json.loads(PACKAGE.read_text(encoding="utf-8"))
        admission = self._admission(plan)

        class OfflinePreflight:
            def run(self, spec):
                self.spec = spec
                return object()

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            controller = RuntimeController(
                root=ROOT,
                audit_logger=AuditLogger(Path(directory) / "audit", trusted_root=ROOT),
                external_execution_preflight=OfflinePreflight(),
            )
            response, code = controller.run(
                "movie.moving-shot-generate", "development", {},
                {"admission_id": admission.request_sha256, "mode": "preflight"},
                "film-1-shot-2-offline-rehearsal", "2026-09-11T00:00:00.000Z", time.monotonic(),
                dry_run=True, admitted_request=admission,
            )
        self.assertEqual(code, 0)
        self.assertEqual(response["output"]["request_sha256"], plan["deterministic_binding"]["provider_request_sha256"])
        self.assertEqual(response["output"]["provider_call_count"], 0)

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
