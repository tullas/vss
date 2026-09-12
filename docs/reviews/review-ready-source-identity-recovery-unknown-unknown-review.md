# Issue #160 UNKNOWN_UNKNOWN_REVIEW

**Disposition:** REVISE (initial design review)
**Review basis:** Fresh-context adversarial review of the proposed general
controller recovery. Reviewer/owner labels are accountability metadata, not
authentication.

## Material falsification attempts

The first proposal failed closed for named mixed diffs and stale generations,
but its undefined provenance rule left validly resealed substitutions and
schema-valid invented artifacts unaddressed. The current agent-checkpoint
contract binds HEAD and changed paths but not file bytes or artifact-to-receipt
association.

The eventual event needs to bind both HEADs and change identities, the exact
artifact manifest and source receipt digests, assessment and history tail,
explicit human disposition, expected generation, and fixed `CI_PENDING` result.
Replay must reconstruct admissibility. Verification must use immutable Git
object IDs, then recheck branch, HEAD, worktree, generation, and history tail
before append; the per-milestone lock alone does not freeze Git refs.

Adversarial coverage must define merge/rebase/multiple-commit behavior; reject
unsupported path/mode cases such as rename, deletion, symlink and gitlink;
cover stale/spoofed registration and receipt-to-blob mismatch; and exercise
concurrent calls, ref movement, wrong-SHA CI, repeat recovery, and replay.

The initial design was revised to require pre-registration at HEAD A and exact
manifest/content binding. It must remain fail-closed where that provenance is
absent; the issue's reported historical state cannot be presumed admissible.
