import unittest
import json
from pathlib import Path

from vss_provider_reliability import DigitalTwinScenario, EXTERNAL_PROVIDER_ADMISSION_RULE, FailureClass, FlightRecorder, ProviderDigitalTwin, ProviderReliabilityEngineer, assess_readiness


class ProviderReliabilityFoundationTests(unittest.TestCase):
    def test_historical_lessons_index_all_five_consumed_attempts(self):
        value = json.loads((Path(__file__).resolve().parents[2] / "docs/reviews/m11-r-attempt-lessons.json").read_text())
        self.assertEqual([item["attempt"] for item in value["attempts"]], [1, 2, 3, 4, 5])
        self.assertTrue(all(item["status"] == "consumed" and item["regression"] and item["readiness_check"] for item in value["attempts"]))
    def test_taxonomy_and_readiness_are_closed_and_provider_free(self):
        readiness = assess_readiness({name: True for name in (
            "authentication_construction", "network_readiness", "request_contract",
            "submission_observability", "lro_persistence", "poll_observability",
            "terminal_result_observability", "result_parser", "media_admission",
            "historical_regression_coverage")})
        self.assertTrue(readiness.paid_execution_recommended)
        self.assertFalse(readiness.provider_call_required_for_reproduction)
        self.assertEqual(readiness.unresolved_known_risks, ())
        engineer = ProviderReliabilityEngineer()
        self.assertFalse(engineer.provider_execution_authority)
        self.assertEqual(engineer.diagnosis(FailureClass.POLLING, "delayed")["classification"], "polling")
        self.assertTrue(EXTERNAL_PROVIDER_ADMISSION_RULE.startswith("No paid"))

    def test_flight_recorder_is_deterministic_bounded_secret_safe_and_freezable(self):
        def build():
            recorder = FlightRecorder({"request": "r", "access_token": "secret"})
            recorder.record("submission", status="accepted", metadata={"http_status": 200})
            recorder.record_terminal({"field_path": "response.videos[0].bytesBase64Encoded", "kind": "inline_base64"})
            recorder.record_diagnosis(classification=__import__("vss_provider_reliability").FailureClass.RESULT_REPRESENTATION, message="bad")
            return recorder.freeze()
        first, second = build(), build()
        self.assertEqual(first, second)
        self.assertEqual(first["request_summary"]["access_token"], "[redacted]")
        with self.assertRaises(RuntimeError):
            # A new call cannot mutate the frozen recorder.
            recorder = FlightRecorder({})
            recorder.freeze(); recorder.record("late", status="rejected")

    def test_digital_twin_covers_all_named_scenarios_without_external_calls(self):
        twin = ProviderDigitalTwin()
        for scenario in DigitalTwinScenario:
            with self.subTest(scenario=scenario):
                result = twin.rehearse(scenario)
                self.assertIn("flight_recorder", result)
                self.assertNotIn("secret", str(result).lower())
                self.assertNotIn("https://", str(result))

    def test_attempt_5_shape_is_rehearsed_as_malformed_inline_terminal_result(self):
        result = ProviderDigitalTwin().rehearse(DigitalTwinScenario.MALFORMED_INLINE_MEDIA)
        recorder = result["flight_recorder"]
        self.assertEqual(result["provider_call_count"], 1)
        self.assertEqual(result["poll_count"], 1)
        self.assertEqual(recorder["terminal_response"]["done"], True)
        self.assertEqual(recorder["terminal_response"]["video_representation"]["value_preview"], "not-base64")


if __name__ == "__main__":
    unittest.main()
