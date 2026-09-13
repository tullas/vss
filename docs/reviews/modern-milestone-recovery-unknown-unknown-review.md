# Modern milestone recovery: bounded material-risk review

**Disposition:** ACCEPT with the admission limits recorded below.

This is a bounded `UNKNOWN_UNKNOWN_REVIEW` of a local controller recovery
transition. The material risks are limited to source substitution during
recovery, stale evidence being replayed under a new identity, and refs moving
between proof and append.

- Source substitution is bounded by requiring the target merge's ordered
  parents to be the old bound HEAD and current `main`, and by comparing its
  tree with Git's deterministic merge result. Arbitrary descendants, rebases,
  octopus merges, and caller-selected bases are rejected.
- Evidence laundering is bounded by a typed recovery event that names prior
  validation and CI evidence digests, followed by a projection that clears both
  and requires fresh exact-identity validation. Historical events remain
  immutable and replayable only as history.
- Ref movement is bounded by re-reading the branch, `main`, repository tree,
  history tail, and generation at the append boundary; mismatch fails closed.
- Recovery itself grants no effect or merge authority. The ordinary
  `request_pr`, exact PR observation, pull-request CI, and `request_merge`
  boundaries remain unchanged.

No additional material unknown is identified within this narrow two-parent
merge case. This acceptance does not extend recovery to arbitrary rebases or
source rewrites. Review owner is accountability metadata, not authenticated
identity.
