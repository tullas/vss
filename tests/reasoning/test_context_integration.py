import json
import unittest
from pathlib import Path

from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning.errors import InvalidReasoningRequest
from vss_knowledge_contracts.revocation import KnowledgeRevocationRegistry, RevocationRecord

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ContextReasoningIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.request = load(ROOT / "tests/fixtures/reasoning/generate-options-runtime-valid.json")
        self.context = load(ROOT / "tests/fixtures/context/context-object-valid.json")

    def test_context_changes_deterministic_result_qualification(self):
        gateway = ReasoningGateway.built_in()
        result = gateway.execute(self.request, environment="development", correlation_id=self.request["correlation_id"], context_data=self.context)
        limitations = result.validated_result.value["payload"]["common_sections"]["limitations"]
        self.assertIn("context_qualification", {item["id"] for item in limitations})

    def test_context_request_binding_fails_before_provider(self):
        context = dict(self.context)
        context["request_id"] = "other-request"
        gateway = ReasoningGateway.built_in()
        with self.assertRaises(InvalidReasoningRequest):
            gateway.execute(self.request, environment="development", correlation_id=self.request["correlation_id"], context_data=context)

    def test_context_dry_run_does_not_return_result(self):
        gateway = ReasoningGateway.built_in()
        outcome = gateway.execute(self.request, environment="development", correlation_id=self.request["correlation_id"], context_data=self.context, dry_run=True)
        self.assertIsNone(outcome.validated_result)
        self.assertFalse(outcome.output["readiness"]["provider_invoked"])

    def test_context_free_path_remains_unchanged_shape(self):
        gateway = ReasoningGateway.built_in()
        outcome = gateway.execute(self.request, environment="development", correlation_id=self.request["correlation_id"])
        self.assertNotIn("context_qualification", {item["id"] for item in outcome.validated_result.value["payload"]["common_sections"]["limitations"]})

    def test_current_revocation_is_checked_before_delivery(self):
        revocations = KnowledgeRevocationRegistry((RevocationRecord(
            target_identity="local-validation-principle", target_type="item",
            reason_category="owner_request", revoked_at="2026-01-01T00:00:00Z"),))
        with self.assertRaises(InvalidReasoningRequest):
            ReasoningGateway.built_in().execute(self.request, environment="development", correlation_id=self.request["correlation_id"], context_data=self.context, revocations=revocations)


if __name__ == "__main__":
    unittest.main()
