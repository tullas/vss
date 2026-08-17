from datetime import datetime, timedelta, timezone
import unittest

from marketing.src.orchestrator import (
    Claim,
    ContentDraft,
    Evidence,
    EvidenceGate,
    ReviewResult,
    WorkflowState,
)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 31, tzinfo=timezone.utc)
        self.valid_evidence = Evidence(
            source_id="source-1",
            source_url="https://example.invalid/source",
            retrieved_at=self.now,
            excerpt="Direct support for the claim.",
        )
        self.passing_reviews = [
            ReviewResult("fact_checker", True),
            ReviewResult("brand_guardian", True),
        ]

    def test_supported_draft_reaches_approval_queue(self) -> None:
        draft = ContentDraft(
            channel="instagram",
            body="A clear, evidence-backed message.",
            claims=[Claim("Supported fact", ("source-1",))],
        )
        result = EvidenceGate().evaluate(
            draft, [self.valid_evidence], self.passing_reviews, self.now
        )
        self.assertEqual(WorkflowState.READY_FOR_APPROVAL, result.state)
        self.assertEqual([], result.rejection_reasons)

    def test_unsupported_claim_is_rejected(self) -> None:
        draft = ContentDraft(
            channel="website",
            body="An unsupported claim.",
            claims=[Claim("Unverified market leadership")],
        )
        result = EvidenceGate().evaluate(draft, [], self.passing_reviews, self.now)
        self.assertEqual(WorkflowState.REJECTED, result.state)
        self.assertTrue(any("unsupported factual claim" in item for item in result.rejection_reasons))

    def test_expired_time_sensitive_evidence_is_rejected(self) -> None:
        expired = Evidence(
            source_id="trend-1",
            source_url="https://example.invalid/trend",
            retrieved_at=self.now - timedelta(days=10),
            excerpt="A time-sensitive trend signal.",
            time_sensitive=True,
            expires_at=self.now - timedelta(days=1),
        )
        draft = ContentDraft(
            channel="instagram",
            body="A current trend claim.",
            claims=[Claim("This trend is current", ("trend-1",))],
        )
        result = EvidenceGate().evaluate(draft, [expired], self.passing_reviews, self.now)
        self.assertEqual(WorkflowState.REJECTED, result.state)
        self.assertTrue(any("expired evidence" in item for item in result.rejection_reasons))

    def test_missing_required_review_is_rejected(self) -> None:
        draft = ContentDraft(channel="instagram", body="Creative copy", claims=[])
        result = EvidenceGate().evaluate(
            draft,
            [],
            [ReviewResult("fact_checker", True)],
            self.now,
        )
        self.assertEqual(WorkflowState.REJECTED, result.state)
        self.assertIn("missing required review: brand_guardian", result.rejection_reasons)

    def test_guarantee_language_is_rejected(self) -> None:
        draft = ContentDraft(channel="instagram", body="Get guaranteed results today.")
        result = EvidenceGate().evaluate(draft, [], self.passing_reviews, self.now)
        self.assertEqual(WorkflowState.REJECTED, result.state)
        self.assertTrue(any("prohibited unsupported promise" in item for item in result.rejection_reasons))


if __name__ == "__main__":
    unittest.main()
