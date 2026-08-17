import json
import unittest
from pathlib import Path

from vss_reasoning_contracts import canonical_digest
from vss_reasoning.gateway import ReasoningGateway
from vss_movie_production_options import validate_production_options_context_v2

ROOT = Path(__file__).resolve().parents[2]


def _v2_context():
    value = json.loads((ROOT / "tests/fixtures/movie/scene-production-options-context-valid.json").read_text())
    value.update(schema_version="2", context_family_version="2", result_version="2", semantic_task_version="2",
                 purpose="scene_production_options_local_analysis", policy_version="2",
                 constructed_at="2026-08-17T00:00:00Z", expires_at="2026-08-17T00:05:00Z")
    value["payload"]["knowledge_bindings"] = []
    value["context_content_digest"] = canonical_digest(value["payload"])
    value["integrity"] = {"complete_context_sha256": "0" * 64}
    value["integrity"]["complete_context_sha256"] = canonical_digest({**value, "integrity": {}})
    return value


def _v2_task():
    value = json.loads((ROOT / "tests/fixtures/movie/generate-scene-production-options-request-valid.json").read_text())
    value.update(schema_version="2", task_version="2", purpose="scene_production_options_local_analysis",
                 expected_context_version="2", expected_result_version="2")
    return value


class M71ProductionOptionsTests(unittest.TestCase):
    def test_v2_without_knowledge_is_deterministic_and_non_ranking(self):
        task, context = _v2_task(), _v2_context()
        first = ReasoningGateway.built_in().execute_scene_production_options(task, context, environment="development", correlation_id=task["correlation_id"])
        second = ReasoningGateway.built_in().execute_scene_production_options(task, context, environment="development", correlation_id=task["correlation_id"])
        self.assertEqual(first["scene_production_option_set"], second["scene_production_option_set"])
        result = first["scene_production_option_set"]
        self.assertEqual(result["knowledge_bindings"], [])
        self.assertTrue(result["payload"]["stable_order_is_not_ranking"])
        self.assertTrue(all("knowledge_influence" not in option for option in result["payload"]["options"]))

    def test_v2_context_rejects_untrusted_binding_shape(self):
        context = _v2_context()
        context["payload"]["knowledge_bindings"] = [{"knowledge": {"knowledge_id": "forged"}, "lifecycle_events": [], "replacements": []}]
        context["context_content_digest"] = canonical_digest(context["payload"])
        context["integrity"] = {"complete_context_sha256": "0" * 64}
        context["integrity"]["complete_context_sha256"] = canonical_digest({**context, "integrity": {}})
        with self.assertRaises(ValueError):
            validate_production_options_context_v2(context, validation_time="2026-08-17T00:00:01Z")

    def test_dry_run_does_not_invoke_provider(self):
        outcome = ReasoningGateway.built_in().execute_scene_production_options(_v2_task(), _v2_context(), environment="development", correlation_id="m4-3-local-run", dry_run=True)
        self.assertFalse(outcome["readiness"]["provider_invoked"])
        self.assertEqual(outcome["readiness"]["provider_call_count"], 0)


if __name__ == "__main__":
    unittest.main()
