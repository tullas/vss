# Issue #160 UNKNOWN_UNKNOWN_REVIEW — Final Design

**Disposition:** PASS
**Review basis:** Independent fresh-context adversarial review of the current
design. Reviewer and owner labels are accountability metadata, not
authenticated identity.

The reviewed design closes the material unknowns identified in earlier
rounds. The manifest is a fixed-path tree addition separate from its bounded
artifact entries. Entry paths derive from the milestone ID and raw blob
digest, so a candidate cannot place a valid envelope under source,
configuration, or arbitrary documentation paths. The checkpoint envelope
must name `subject.kind: issue` and issue 160 exactly. Each applicable retained
review receipt snapshots its assessment subject and evidence inventory from
HEAD A; every evidence path must already resolve to a regular tracked blob,
and path bytes, Git object ID, and content digest must match at B. Newly added
artifacts cannot supply evidence for an old receipt.

The proposal also explicitly bounds direct-child topology, additions-only
tree comparison, modes and blob digests, registration consumption, history
and event size, generation and concurrency checks, pinned reads, ref movement,
CI invalidation, and deterministic replay. Merge commits, rewritten or
multi-commit descendants, symlinks, gitlinks, renames, deletions, mixed diffs,
dirty trees, stale registrations, wrong-SHA CI, and ambiguous paths fail
closed. The identified non-atomic Git-ref boundary and local-history rewrite
limitation are explicit implementation constraints, not claims of stronger
atomicity or tamper resistance.

No material residual design blocker was identified. This is a design review
outcome only and does not authorize implementation.
