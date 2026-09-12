# Issue #160 Constitutional Review — Final Design

**Disposition:** ACCEPT
**Review basis:** Independent fresh-context review of the current design.
Reviewer and owner labels are accountability metadata, not authenticated
identity.

The design preserves the source-identity boundary. Recovery is explicit and
generation-checked; it records A and B, requires an unchanged branch/base and a
direct-child descendant, a clean worktree, and reconstructs the complete Git
tree delta from pinned blobs. The admissible artifact protocol is closed to
the exact checkpoint v1 design/review contracts for issue #160. Paths are
controller-derived under the milestone checkpoint-artifact directory, and
the fixed manifest is accounted for as a separate addition. Mixed, modified,
deleted, unregistered, or otherwise inadmissible changes fail closed.

The design preserves review events as immutable history without claiming they
reviewed B. Retained receipts are tied to their assessment, disposition,
scope, source identity, and evidence blobs already present at A; the same blob
object IDs and content digests must remain at B, and an artifact addition may
not supply missing evidence. Recovery invalidates CI(A), binds B, and routes
only to `CI_PENDING`; exact-HEAD CI(B), canonical validation, and the existing
human review boundary remain required.

Registration and recovery remain separate explicit human-governed actions.
Disposition and reviewer fields are accountability metadata, not
authentication. The typed `identity_rebound` variant makes the exceptional
transition auditable and replay-verifiable. No merge, push, implementation,
runtime, provider, publication, workflow, production, or security-exception
authority is added.

The design is accepted for the design gate only. It does not authorize
implementation. Preserve the documented limitations: local locking cannot
make arbitrary Git ref updates atomic with event append, and the local hash
chain is not protection against a hostile writer able to rewrite local state.
