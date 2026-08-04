from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class WorkflowState(str, Enum):
    RESEARCH = "RESEARCH"
    DRAFT = "DRAFT"
    VERIFY = "VERIFY"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Evidence:
    source_id: str
    source_url: str
    retrieved_at: datetime
    excerpt: str
    time_sensitive: bool = False
    expires_at: datetime | None = None

    def is_valid(self, now: datetime) -> bool:
        if not self.source_id.strip() or not self.source_url.strip() or not self.excerpt.strip():
            return False
        if self.time_sensitive and self.expires_at is None:
            return False
        return self.expires_at is None or self.expires_at >= now


@dataclass(frozen=True)
class Claim:
    text: str
    evidence_ids: tuple[str, ...] = ()
    is_factual: bool = True


@dataclass
class ContentDraft:
    channel: str
    body: str
    claims: list[Claim] = field(default_factory=list)
    disclosures: list[str] = field(default_factory=list)
    state: WorkflowState = WorkflowState.DRAFT
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewResult:
    reviewer: str
    passed: bool
    reasons: tuple[str, ...] = ()


class EvidenceGate:
    """Deterministic guardrail that runs before any content can be approved."""

    PROHIBITED_PHRASES = (
        "guaranteed results",
        "100% guaranteed",
        "instant success",
        "everyone is saying",
    )

    def evaluate(
        self,
        draft: ContentDraft,
        evidence: Iterable[Evidence],
        reviews: Iterable[ReviewResult],
        now: datetime | None = None,
    ) -> ContentDraft:
        now = now or datetime.now(timezone.utc)
        evidence_map = {item.source_id: item for item in evidence}
        reasons: list[str] = []

        normalized_body = draft.body.casefold()
        for phrase in self.PROHIBITED_PHRASES:
            if phrase in normalized_body:
                reasons.append(f"prohibited unsupported promise: {phrase}")

        for claim in draft.claims:
            if not claim.is_factual:
                continue
            if not claim.evidence_ids:
                reasons.append(f"unsupported factual claim: {claim.text}")
                continue
            for evidence_id in claim.evidence_ids:
                item = evidence_map.get(evidence_id)
                if item is None:
                    reasons.append(f"missing evidence {evidence_id} for claim: {claim.text}")
                elif not item.is_valid(now):
                    reasons.append(f"invalid or expired evidence {evidence_id} for claim: {claim.text}")

        review_map = {review.reviewer: review for review in reviews}
        for required_reviewer in ("fact_checker", "brand_guardian"):
            review = review_map.get(required_reviewer)
            if review is None:
                reasons.append(f"missing required review: {required_reviewer}")
            elif not review.passed:
                reasons.extend(review.reasons or (f"{required_reviewer} rejected draft",))

        draft.rejection_reasons = sorted(set(reasons))
        draft.state = (
            WorkflowState.REJECTED if draft.rejection_reasons else WorkflowState.READY_FOR_APPROVAL
        )
        return draft


def demo() -> None:
    now = datetime.now(timezone.utc)
    evidence = Evidence(
        source_id="owned-website-001",
        source_url="https://example.invalid/about",
        retrieved_at=now,
        excerpt="Verified description imported from the owner's website.",
    )
    draft = ContentDraft(
        channel="instagram",
        body="Discover our verified story and join the community.",
        claims=[Claim("The description is from our owned website.", (evidence.source_id,))],
    )
    reviews = [
        ReviewResult("fact_checker", True),
        ReviewResult("brand_guardian", True),
    ]
    result = EvidenceGate().evaluate(draft, [evidence], reviews, now)
    print({"state": result.state.value, "reasons": result.rejection_reasons})


if __name__ == "__main__":
    demo()
