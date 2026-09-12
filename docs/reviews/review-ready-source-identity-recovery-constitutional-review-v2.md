# Issue #160 Constitutional Review — Revised Design

**Disposition:** REVISE
**Review basis:** Fresh-context re-review of the revised design. Reviewer and
owner labels are accountability metadata, not authenticated identity.

The revision now binds a pre-registered artifact manifest to A, reconstructs
the A..B Git tree delta, distinguishes retained receipts from review of B,
invalidates CI(A), and requires fresh CI(B). It uses `identity_rebound` with
additional replay metadata rather than a second recovery architecture.

Three design details remain blocking before implementation:

1. The design does not name a closed repository-owned registry of admissible
   artifact protocols, versions, and types. A caller must not be able to
   register arbitrary strict documents merely by supplying a schema.
2. Existing `REVIEW_READY` means exact CI and canonical validation passed; it
   is not itself a code-review receipt. The controller's `mission_reviewed`
   events bind an assessment digest and disposition, while each event's
   `change_identity` is not currently checked as the receipt's content subject.
   The design must say exactly which existing receipts it preserves and prove
   their subjects unchanged, or require fresh receipts.
3. The manifest entries and artifact bytes need explicit count, path, and byte
   limits compatible with the 2,048-byte event and 256-event history bounds.

Pre-registration can be implemented only as an explicit controller operation
that validates candidate bytes while the milestone is still bound to clean
HEAD A, appends a neutral registration event, and preserves the `REVIEW_READY`
projection. The generic checkpoint path changes to `WORKING` for dirty
candidate files and cannot perform this step unchanged. Pinning object IDs and
rechecking refs narrows Git races, but ordinary branch movement cannot be made
atomic with the local milestone lock; define the final check as the operation's
linearization point and treat later movement as a new conflict.

No implementation is authorized until these points are resolved and the
revised design is reviewed again.
