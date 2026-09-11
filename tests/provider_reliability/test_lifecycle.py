import unittest
import hashlib
from pathlib import Path

from vss_provider_reliability import (
    ApprovedShotPackage,
    DigitalTwinScenario,
    LifecycleFailure,
    LifecycleState,
    OfflineProductionLifecycle,
    ProviderDigitalTwin,
    kpis,
)
from vss_movie_moving_shot import admit_moving_shot


class OfflineProductionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.package = ApprovedShotPackage.build("shot-adjacent", "scene-1", "A character crosses the room")
        self.lifecycle = OfflineProductionLifecycle()

    def test_golden_path_is_generic_for_a_new_adjacent_shot(self):
        result = self.lifecycle.run(self.package)
        self.assertEqual(result.state, LifecycleState.CREATIVELY_REVIEWED)
        self.assertEqual(result.provider_call_count, 1)
        self.assertTrue(result.recovery_used_same_operation)
        self.assertTrue(result.duplicate_submission_prevented)
        self.assertEqual(result.states, tuple(state.value for state in LifecycleState))
        self.assertNotIn("Shot 1", str(result.to_json()))
        self.assertNotIn("Shot 2", str(result.to_json()))

    def test_real_moving_shot_admission_binds_into_offline_lifecycle(self):
        image = b"offline-admitted-png"
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "basis.png"
            image_path.write_bytes(image)
            admission = admit_moving_shot(
                shot_id="shot-0123456789abcdef01234567", scene_id="scene-0123456789abcdef01234567",
                visual_basis_path=image_path, visual_basis_sha256=hashlib.sha256(image).hexdigest(),
                prompt="A new adjacent shot", source_lineage={"storyboard": "a" * 64}, production_id="film1",
            )
        package = ApprovedShotPackage.from_moving_shot_request(admission.request)
        result = self.lifecycle.run(package)
        self.assertEqual(package.request_digest, admission.request_sha256)
        self.assertEqual(package.execution_namespace, "film1/shot-0123456789abcdef01234567")
        self.assertEqual(result.request_digest, admission.request_sha256)
        self.assertEqual(result.state, LifecycleState.CREATIVELY_REVIEWED)

    def test_identity_and_namespace_fail_before_provider_call(self):
        stale = self.lifecycle.run(self.package, supplied_request_digest="0" * 64)
        wrong_namespace = self.lifecycle.run(self.package, supplied_namespace="other/execution")
        for result, reason in ((stale, "request_identity"), (wrong_namespace, "execution_namespace")):
            self.assertEqual(result.provider_call_count, 0)
            self.assertEqual(result.state, LifecycleState.REHEARSED)
            self.assertEqual(result.failure, reason)

    def test_pre_provider_failures_are_distinct_from_accepted_operations(self):
        pre = self.lifecycle.run(self.package, failure=LifecycleFailure.PRE_PROVIDER)
        accepted_then_polling = self.lifecycle.run(self.package, failure=LifecycleFailure.POLLING)
        self.assertEqual(pre.provider_call_count, 0)
        self.assertEqual(pre.failure, "pre_provider")
        self.assertEqual(accepted_then_polling.provider_call_count, 1)
        self.assertIn("provider_accepted", accepted_then_polling.states)
        self.assertEqual(accepted_then_polling.operation_name, self.lifecycle.run(self.package).operation_name)

    def test_recovery_from_accepted_operation_does_not_submit_again(self):
        interrupted = self.lifecycle.run(self.package, failure=LifecycleFailure.POLLING)
        recovered = self.lifecycle.recover_accepted(self.package, interrupted.operation_name or "")
        self.assertEqual(recovered.state, LifecycleState.CREATIVELY_REVIEWED)
        self.assertEqual(recovered.provider_call_count, 0)
        self.assertEqual(recovered.operation_name, interrupted.operation_name)
        self.assertTrue(recovered.recovery_used_same_operation)

    def test_every_required_failure_scenario_is_offline_and_bounded(self):
        required = {
            DigitalTwinScenario.EXPIRED_CREDENTIAL,
            DigitalTwinScenario.MISSING_CREDENTIAL,
            DigitalTwinScenario.FAILURE_BEFORE_PROVIDER_ACCEPTANCE,
            DigitalTwinScenario.ACCEPTED_PROCESS_INTERRUPTION,
            DigitalTwinScenario.POLLING_FAILURE,
            DigitalTwinScenario.PROVIDER_TERMINAL_FAILURE,
            DigitalTwinScenario.MALFORMED_TERMINAL_RESPONSE,
            DigitalTwinScenario.VALID_INLINE_MEDIA,
            DigitalTwinScenario.MEDIA_ADMISSION_FAILURE,
            DigitalTwinScenario.DUPLICATE_EXECUTION_INVOCATION,
            DigitalTwinScenario.STALE_REQUEST_DIGEST,
            DigitalTwinScenario.WRONG_EXECUTION_NAMESPACE,
            DigitalTwinScenario.RECOVERY_FROM_ACCEPTED_OPERATION,
        }
        twin = ProviderDigitalTwin()
        for scenario in required:
            with self.subTest(scenario=scenario):
                result = twin.rehearse(scenario)
                self.assertEqual(result["provider_call_count"], 0 if scenario.value in {
                    "expired_credential", "missing_credential", "failure_before_provider_acceptance",
                    "duplicate_execution_invocation", "stale_request_digest", "wrong_execution_namespace",
                    "recovery_from_accepted_operation",
                } else 1)
                self.assertNotIn("https://", str(result))
                self.assertNotIn("secret", str(result).lower())

    def test_kpis_are_small_and_derived_from_results(self):
        results = [self.lifecycle.run(self.package), self.lifecycle.run(self.package, failure=LifecycleFailure.PRE_PROVIDER)]
        metrics = kpis(results, source_changes=0, handoffs=0, prs=0)
        self.assertEqual(metrics["accepted_provider_submissions"], 1)
        self.assertEqual(metrics["pre_provider_failures"], 1)
        self.assertEqual(metrics["recovery_events"], 1)
        self.assertEqual(metrics["provider_cost_usd"], "0.000000")


if __name__ == "__main__":
    unittest.main()
