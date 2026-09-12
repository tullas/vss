# Issue #160 Constitutional Review

**Disposition:** REVISE (initial design review)
**Review basis:** Fresh-context review of the proposed general controller
recovery. Reviewer/owner labels are accountability metadata, not authentication.

## Findings

The narrow recovery is compatible with the Constitution's human-authority,
provenance, and reversibility principles in intent: it is a development
coordination transition, preserves append-only history, clears CI, and cannot
restore `REVIEW_READY` directly. Reusing `identity_rebound` is the smallest
existing projection seam, provided the new path carries enough typed evidence
for replay to reconstruct why the identity change was allowed.

The initial proposal did not specify an authoritative artifact provenance
source, exact content binding, or an operational human decision. A strict
schema and digest alone establish byte consistency, not that a file belongs to
an eligible checkpoint or was reviewed. Caller-supplied paths/digests and
reviewer IDs cannot serve as authorization proof.

## Receipt rule

A receipt remains an append-only fact about the assessment event, source
identity, scope, and evidence content it recorded. It may continue to count
only for that unchanged subject when replay proves those digests and its
disposition are unchanged. It never becomes a review of HEAD B or of artifacts
added at B. Each new artifact requires an exact-content receipt; any changed
assessment, implementation, evidence, scope, or disposition requires fresh
applicable review. CI(A) is invalid regardless of receipt preservation, and
B must pass fresh exact-HEAD CI(B) and the existing canonical-validation path.

The first design therefore required revision of the provenance and receipt
rules before implementation.
