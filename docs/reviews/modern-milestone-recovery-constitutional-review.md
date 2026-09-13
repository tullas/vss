# Modern milestone recovery: constitutional review

**Disposition:** ACCEPT the bounded design for implementation.

This review covers the proposed recovery for a modern milestone whose persisted
projection predates the #166 PR boundary and whose feature branch has merged a
newer `main`. It does not accept arbitrary history repair or grant merge, push,
Runtime, provider, production, publication, or workflow authority.

The admission rule is limited to an exact two-parent merge: first parent is the
currently bound milestone HEAD, second parent is the current `main` HEAD, the
old base is an ancestor of that `main`, and Git's deterministic merge tree for
the two parents equals the target commit tree. This makes the advancement
reproducible and prevents using the recovery to substitute a different governed
tree. The event records old and new base, HEAD, and change identities plus the
history tail and generation; replay re-proves these bindings.

Recovery appends a typed immutable event and clears both validation and CI.
Only a fresh validation bound to the recovered base, exact HEAD, current policy,
and change identity may progress. PR observation and pull-request CI remain on
the existing #166 route. Legacy `recover-state-identity` keeps its current
legacy-tail preconditions.

Material boundaries: reject non-merge or wrong-parent descendants, unrelated
tree changes, branch or base movement during admission, stale generations,
replays, malformed records, and any attempt to carry old validation or CI into
the new identity. If the deterministic tree proof or exact ref recheck fails,
the controller remains in conflict. Review owner is accountability metadata,
not authenticated identity.
