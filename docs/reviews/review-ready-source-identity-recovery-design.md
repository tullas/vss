# Issue #160: REVIEW_READY source-identity recovery

**Status:** Design accepted; bounded implementation is present. Fresh exact-HEAD CI remains pending.
**Issue:** [tullas/vss#160](https://github.com/tullas/vss/issues/160)
**Maintenance milestone:** `review-ready-source-identity-recovery`

## Scope

Add one human-gated recovery for the reported case where a milestone reached
`REVIEW_READY` at HEAD A, then a descendant HEAD B committed only admissible,
governed checkpoint artifacts. Recovery may bind B and move the milestone to
`CI_PENDING`; it must require fresh CI for B. It must not accept implementation
or unrelated changes, revive stale CI, restore `REVIEW_READY` directly, or
grant push, merge, production, provider, Runtime, publication, or workflow
authority.

This milestone covers the repository milestone controller, its event/state
contract, CLI routing, focused tests, and coordination documentation. The
design requires one strict manifest schema for pre-registered checkpoint
artifacts. It does not change the frozen M11.P milestone state.

## Root cause and current seam

The controller reports `CONFLICT` when the checked-out branch or HEAD differs
from the source identity bound by milestone history. `recover-state-identity`
only invalidates a legacy, unbound `validation_completed` tail, clears reusable
validation, and routes to local validation. It does not recover modern semantic
identity conflicts.

`rebind-committed-head` already appends `identity_rebound`. It requires the
expected generation, unchanged branch and base, a clean worktree, and descendant
ancestry. It resets CI and projects `CI_PENDING` / `ingest_ci`, preserving prior
review and validation events. It currently accepts only `CI_PENDING`; a changed
semantic identity needs prior reviewed evidence and is limited to an exact
registered controller-repair path set. Therefore it cannot admit the reported
`REVIEW_READY` checkpoint-artifact commit.

The existing GitHub agent-checkpoint contract binds the issue, repository,
branch, base, HEAD, changed-path summary, and canonical payload digest.
`scripts/vss-agent` does not inspect changed-file contents or register their
artifact types. A path prefix or caller-provided digest alone is insufficient
proof of admissibility. The implementation design must define a bounded,
reconstructible provenance rule for every admitted artifact and reject recovery
when that proof is absent or incomplete.

## Proposed implementation seam

Extend the existing `rebind-committed-head` / `identity_rebound` transition
rather than adding a second recovery architecture. Add a narrowly selected
`REVIEW_READY` branch that is reachable only after explicit human-gated
invocation and proves all of the following before appending history:

- the expected generation is current and the event history/materialized state
  agree;
- branch, repository, and base identity are unchanged;
- B is a descendant of the previously bound A, and the worktree is clean;
- the complete A..B diff consists only of artifacts whose provenance and
  contents validate against the exact governed checkpoint/review contracts;
- no implementation, source-code, unrelated documentation, deletion, or
  unclassified change is present.

The appended identity-rebound event records A, B, the admissibility evidence,
and the generation. Projection preserves prior append-only review history,
invalidates all CI observations for A, binds B, and enters `CI_PENDING`.
Only fresh exact-HEAD CI(B) can advance the existing flow. Any ambiguous,
unregistered, incomplete, or unverifiable artifact evidence fails closed.

Design review must settle the exact provenance source and content validation
for committed checkpoint artifacts before implementation. The evidence must be
reconstructed from authoritative repository/contract material, not trusted
caller-supplied paths or digests, and it must not create a general source-
identity override.

## Review findings and required design constraints

The first fresh-context review returned `REVISE` for both Constitutional and
UNKNOWN_UNKNOWN_REVIEW: the prior proposal named provenance as a requirement
but did not specify its source or how an existing receipt could remain
applicable. The following constraints narrow that proposal.

### Artifact registration and admissibility

The admissible artifact type set is closed in controller code: protocol
`vss.agent-checkpoint`, schema
`schemas/agent-checkpoint-v1.schema.json`, version `1`, and only
`checkpoint_type` values `design` and `review`. Each payload must validate
against that exact schema and match the milestone issue, repository, branch,
base SHA, and HEAD A; `subject.kind` must be exactly `issue` and its number
must equal issue #160. `approval` must be null and `omitted_path_count` must be
zero. Unknown protocols, schema references, types, versions, approval records,
and free-form Markdown are rejected. The envelope is metadata, not proof that
its summary is true or that its author is authenticated.

Before B exists, an explicit registration command reads a bounded candidate
bundle from outside the repository while the milestone is clean and bound to
`REVIEW_READY` at HEAD A. It validates each envelope against the closed set,
computes the canonical manifest and raw content digests itself, and appends a
`checkpoint_artifacts_registered` event. The event binds the manifest digest
and fixed manifest path to issue, milestone, repository, branch, base SHA, HEAD
A, A's change identity, active assessment digest, generation/history tail, an
inventory of applicable review receipts and their evidence blob identities,
and explicit human disposition. It preserves A, its CI, validation, and
`REVIEW_READY` projection. Registration is a dedicated explicit action: the
normal checkpoint route cannot register dirty candidate files because
`load()` projects a changed worktree as `WORKING`.

The registered manifest uses one new closed schema,
`schemas/dev-milestone-checkpoint-artifact-manifest-v1.schema.json`, for
protocol `vss.dev-milestone-checkpoint-artifact-manifest` version `1`, at the
single path `docs/reviews/<milestone-id>-checkpoint-artifact-manifest.json`.
Each artifact is a canonical JSON payload stored at the controller-derived
path `docs/reviews/<milestone-id>-checkpoint-artifacts/<raw-blob-sha256>.json`;
the controller derives the directory from the exact milestone ID and the file
name from the raw SHA-256 of the candidate bytes; the caller cannot choose or
override a repository path. These are the only admissible artifact paths and
cannot point into source, configuration, or other documentation trees. The
manifest records
these exact paths, types, modes, and digests. The A event
computes and records the manifest digest; callers cannot choose another schema,
type, path, or digest. Bound it to at most four checkpoint artifacts,
240-byte paths, 16 KiB per envelope, and 16 KiB total canonical manifest
size, with an 80-KiB aggregate candidate-bundle limit. Registration event data
stores the fixed path and digest rather than repeating entries, so it remains
within the existing 2,048-byte event cap. Reserve two event slots under the
256-event history cap for registration and recovery; otherwise fail closed.
Oversized bundles fail closed.

At recovery, read the manifest and envelopes from pinned Git blobs, validate
their strict contracts and exact repository/issue/source identities, and
compare the canonical manifest digest with the value registered at A.
Reconstruct the complete A..B tree delta from Git objects and require it to
equal exactly one manifest addition at its fixed path plus all listed artifact
additions at their controller-derived paths: regular `100644` mode,
artifact type/schema version, and raw blob digest. The manifest cannot list
itself as an artifact. The manifest file is a separate tree addition, is not a
manifest entry, and does not count against the four-artifact limit. Allow
additions only and require every path, including the manifest path, to have
been absent at A.
Reject modifications, deletions, renames, executable files, symlinks,
submodules/gitlinks, generated or unregistered files, and any mixed diff.
Read committed blobs by object ID, never from the worktree. The first version
should accept only a direct single-parent child B of A; reject merge commits,
rebases/cherry-picks whose parent is not A, and multiple commits. A
content-equivalent artifact commit is admissible only when its exact blob bytes
and mode match the pre-registered manifest. This narrow topology removes
history ambiguity while still accepting the reported one-commit recovery.
Case, Unicode, and path normalization are exact Git path bytes; unsupported or
ambiguous names fail closed. Ignored or untracked worktree files never
contribute to the proof: registration reads the bounded external bundle and
recovery reads immutable Git blobs, not filesystem copies.

The existing `vss.agent-checkpoint` envelope alone is insufficient: it binds
HEAD and changed paths but not its content bytes. The pre-registration event
and controller-computed manifest digest bind the exact envelope bytes and
their relationship to A. A path prefix or filename alone never establishes
artifact type. Validly resealed substitutions fail unless their bytes were
the exact bytes registered at A.

### Receipt and human-decision semantics

`REVIEW_READY` means exact-HEAD CI and canonical validation passed; it is not
an implementation-review receipt. The controller's `mission_reviewed` events
are receipts for a specific `mission_assessed` event and
mechanism/disposition. Preserve them as immutable history. They continue to
count only for the same assessment digest when each applicable receipt's
recorded `change_identity` equals A's bound change identity and the assessment,
disposition, evidence paths/content, and scope remain unchanged. Existing
`mission_reviewed` stores evidence path strings but does not bind their bytes,
so registration must resolve every evidence path used by each retained receipt
against A's Git tree. Each path must name an existing regular `100644` blob at
A; record its exact path bytes, Git blob object ID, and SHA-256 of the blob
contents in the registration event, alongside a digest of the canonical
receipt event and its exact assessment subject. At recovery, require the same
path to resolve to the same blob object ID and content digest at B. Reject
missing, untracked, ignored, ambiguous, non-blob, or newly added evidence
paths, and reject any receipt whose evidence inventory cannot be reconstructed
completely. Artifact additions cannot supply or replace evidence. Rebuild and
compare the receipt's assessment subject, disposition, evidence path set,
scope, and recorded change identity to the registration snapshot. Reconstruct
B's implementation identity after excluding only the registered additions
and require it to equal A's bound change identity. Additions-only means no
evidence or reviewed implementation file at A can be replaced. Otherwise
require fresh applicable receipts; never reinterpret an old receipt as
covering B.

A `vss.agent-checkpoint` of type `review` is a report about the HEAD it names,
not an authenticated review of a later HEAD. New artifacts are covered only by
the exact-content human disposition recorded in their pre-registration event;
that disposition does not imply implementation acceptance. After recovery,
fresh CI(B), canonical validation, and the existing `request_merge` human
boundary still apply. A human must review or reconfirm B before any merge
workflow; the controller stores no code-review approval and grants no merge
authority.

Recovery must be a deliberate controller command with current generation and
an explicit human disposition tied to the registered manifest digest. The
event records that disposition as accountability metadata only; reviewer IDs,
summaries, and command invocation do not authenticate identity. `status`,
`next`, CI ingestion, or projection must never perform recovery automatically.

The `identity_rebound` event needs a distinct, schema-closed recovery variant
so replay can distinguish an ordinary identity-preserving CI rebind from this
exception. Record recovery kind, A/B HEADs and change identities, fixed
manifest path and digest, assessment and receipt digests, the exact receipt
evidence path/object-ID/content-digest inventory, human disposition metadata,
ancestry proof, expected generation, prior history tail, and fixed
resulting state (`CI_PENDING`, CI `not_observed`, null CI HEAD, `ingest_ci`).
The manifest blob carries bounded entries; the event stays under the existing
event-size limit. Event validation and projection must reject missing, extra,
inconsistent, or authority-bearing fields and reconstruct the full A..B
admissibility proof on replay. Preserve previous events verbatim.

Use the existing per-milestone lock and expected-generation check, then pin A
and B object IDs for all verification. Immediately before append, recheck the
current branch, HEAD, stored base SHA, worktree status, generation, and history
tail; if any changed, append nothing. A second concurrent controller call must
fail its stale generation check. Treat the final successful ref/worktree check
as the event's linearization point: later Git ref movement is a new
source-identity conflict on load, never a silent change to recorded B. The
local lock cannot make a Git ref update atomic with history append. Local hash
chains are consistency checks, not protection from a hostile writer who can
rewrite all local state.

### Additional adversarial coverage

In addition to the acceptance tests above, synthetic repositories must cover
merge and multi-commit descendants, rebases/cherry-picks, case/Unicode path
ambiguity, symlink and gitlink modes, rename/deletion, ignored and untracked
files, validly resealed artifact substitutions, stale/spoofed registrations,
receipt-to-blob mismatch, generated files, base-ref movement, branch movement
during verification, concurrent recovery calls, repeated attempts, wrong-SHA
CI, and deterministic replay. The final projection must retain audit history
but never treat a receipt whose exact subject digest changed as current review.

Tests must also prove registration accepts only the exact agent-checkpoint v1
`design`/`review` contracts, rejects caller-selected schema/type references,
enforces the four-artifact and byte/path bounds plus the 2,048-byte event cap,
leaves A's `REVIEW_READY` and CI unchanged, and rejects recovery without an
earlier registration event. They must also exercise exhaustion of the
256-event history cap and the 80-KiB aggregate input cap. A registration is
consumed once; replay or repeated calls cannot consume it twice. The base SHA
stays pinned if an upstream ref moves, while substitution with another base
SHA or branch fails.

## Acceptance criteria

Positive path:

- Begin with `REVIEW_READY` bound to HEAD A and valid append-only review history.
- While still at A, explicitly register the exact candidate artifact inventory
  and applicable receipt digests in controller history; registration leaves
  A and its CI binding unchanged.
- Commit only admissible, fully provenance-verified governed checkpoint
  artifacts in descendant HEAD B.
- Detect the stale source identity as a conflict; no implicit recovery occurs.
- An explicit governed recovery with the current generation records old and new
  identities, binds B, preserves prior review history, invalidates CI(A), and
  transitions to `CI_PENDING` / `ingest_ci`.
- CI(A) cannot satisfy the new identity. Fresh exact-head CI(B) is required
  before the existing flow advances.
- Every authority field remains false; recovery grants no push, merge,
  production, provider, Runtime, publication, or workflow authority.

Negative-path tests must reject:

- implementation or source-code changes after `REVIEW_READY`;
- unrelated documentation, mixed diffs, deletions, and unclassified paths;
- dirty worktrees, non-descendant/re-written HEADs, or branch/base mismatch;
- stale expected generations, corrupt history, or state/history disagreement;
- incomplete or unverifiable artifact provenance, malformed artifacts, and
  caller-supplied digest/path substitution;
- registration attempted after B, or a B tree whose added blob/path/mode does
  not exactly match the prior manifest;
- a recovery that directly restores `REVIEW_READY` or reuses CI from A;
- any transition whose event or projected state adds authority.

## Review and implementation boundary

Constitutional review accepted this design and UNKNOWN_UNKNOWN_REVIEW passed.
The implementation adds clean-HEAD artifact registration and a typed
`identity_rebound` recovery variant. Recovery reconstructs the complete direct
child A-to-B Git tree delta, verifies the exact registered envelope and
manifest bytes, preserves retained receipt evidence blobs, and projects only
to `CI_PENDING`. Synthetic repository tests cover the positive path and
adversarial identity, provenance, worktree, ancestry, path, and stale-CI cases.

The implementation retains the documented limitation that a local lock cannot
make Git ref movement atomic with event append. It does not use
`recover-state-identity` as a source-identity bypass or grant additional
authority. The milestone still requires fresh CI for the exact committed HEAD;
this local validation checkpoint does not supply that CI observation.
