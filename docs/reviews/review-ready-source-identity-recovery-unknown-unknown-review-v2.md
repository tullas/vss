# Issue #160 UNKNOWN_UNKNOWN_REVIEW — Revised Design

**Disposition:** REVISE
**Review basis:** Fresh-context adversarial re-review. Reviewer and owner
labels are accountability metadata, not authenticated identity.

The revised design closes several important paths: direct-child topology,
additions-only tree comparison, exact mode and blob digest matching,
fail-closed receipt scope, CI invalidation, event replay, stale-generation
protection, and a final repository identity recheck. It also names tests for
the requested Git and concurrency edge cases.

It still lacks a fixed artifact-type allowlist. The phrase “exact registered
strict artifact contract” could admit an invented but schema-valid type. The
existing `vss.agent-checkpoint` schema covers envelopes but does not bind file
bytes, and its helper explicitly does not inspect file content. The design
must name a closed repository-owned contract/type set and reject everything
else.

The receipt model must match existing controller facts: `REVIEW_READY` is a
projection of CI plus canonical validation, not a persisted implementation
review receipt. `mission_reviewed` receipts name an assessment digest and
disposition, while event-level `change_identity` is not presently enforced as
the receipt's exact content subject. Require unchanged assessment and
implementation identities and keep old receipts historical; newly introduced
artifacts need their own exact-content disposition.

Manifest cardinality and byte bounds are absent despite the 2,048-byte event
and 256-event history limits. Pre-registration must define a dedicated clean-A
flow: the existing `checkpoint()` path projects `WORKING` for dirty candidate
files. The design also needs an explicit post-check Git-ref movement model;
the controller lock cannot serialize arbitrary Git operations.

These are design-level blockers, not evidence that current tests cover them.
