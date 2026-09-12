# Controller integrity: governed identity, validation, and CI binding

**Status:** Revised design checkpoint after independent review; implementation is not authorized.
**Issues:** [#161](https://github.com/tullas/vss/issues/161), [#162](https://github.com/tullas/vss/issues/162)
**Maintenance milestone:** `controller-integrity-evidence-binding`
**Primary controller issue:** #161 (the native milestone record has one issue field; #162 is explicitly co-scoped here).
**Baseline:** `feature/review-ready-source-identity-recovery` at `86079355379c3577fc516cafe03cefa5a7471c77`; at this baseline `.github/workflows/ci.yml` has Git blob `854774e24c3e7bc79838a20f9296dbf14d12891a` <!-- pragma: allowlist secret -- public workflow Git blob identity --> (raw SHA-256 `7a3a1bff0922a73a6130cd2a629fabf244654b2aceb6a177c3f463c32c5dd7b3`). This milestone does not alter that milestone's record/history.

## Mission assessment

The controller must ensure that validation evidence, committed source identity, and CI observations all describe the same bounded governed change. The current implementation derives change identity from a worktree-wide changed-path snapshot, and the CI projection can treat a generic `ci_observed` event as a new source binding while retaining prior validation evidence. These failures share one evidence-binding invariant and should be addressed in one milestone; separate fixes could leave an unsafe interval between them.

The observable result is a replay-deterministic controller that preserves strict clean-worktree requirements while accounting only for controller-registered, provenance-backed pre-existing residue, and that never lets CI observation perform source recovery or make stale validation reusable.

This is an `architecture_boundary` maintenance change. DEC-0001 is followed: the work does not redirect product milestones or grant product/production authority. DEC-0002 is not applicable because this work does not revalidate existing media or alter its lineage rules. The latest completed product milestone inspected was M10.5 (`m10-5`), which recorded the grounded-storyboard asset catalog boundary; this advanced the `image` capability rung through durable asset identity.

## Root-cause model

1. `_changed_paths` includes an admitted `.secrets.baseline` worktree edit, and `_change_identity` hashes its path, type, mode, and content along with governed milestone changes. Stashing that pre-existing edit to satisfy strict clean-worktree checks necessarily changes the identity used by earlier validation. Existing recovery transitions do not admit that identity change.
2. Validation reuse is projected primarily from its level and digest. The identity binding is carried by event data, but the projection/reuse path does not consistently require that evidence to match the exact currently bound governed identity after conflict and CI observation.
3. `ingest_ci` can accept an empty check list as success and append an event carrying the current worktree identity. Replay then treats the generic CI event as a source-binding update, can clear `CONFLICT`, and can leave prior L3 evidence available for reuse.
4. Consequently, a source transition, validation evidence, and CI can become internally inconsistent even though each individual event is structurally valid.

Issue #114 established the broad controller architecture and exact-head evidence intent; it is not a duplicate of these concrete defects. Issue #160 is a separate, narrowly governed REVIEW_READY checkpoint-artifact recovery. This milestone must preserve that path and must not turn it into generic identity acceptance.

## Review disposition and design decisions

The first independent Constitutional review and the first UNKNOWN_UNKNOWN_REVIEW both returned `REVISE`. This revision resolves their material findings as follows.

**Residue eligibility and capture.** The first version admits only the exact tracked path `.secrets.baseline` through the existing repository-governance validator. That validator checks fixed scope and structural consistency; it does not authenticate baseline suppressions. Therefore captured residue affects identity bookkeeping only: secret scanning for the governed change must use the `.secrets.baseline` blob from the bound base HEAD, never the modified worktree residue. The captured content cannot suppress findings or otherwise change validation behavior. A deliberate baseline update is governed work and cannot be excluded. The controller exposes no path/exclusion argument and records no caller-selected paths. The existing exact `.local/secrets/development.auto.tfvars.example` exception remains a separate, unchanged repository exception; it is not enrolled in residue provenance. Any second candidate path, including another docs/source/config path, is rejected as residue. This bounded rule addresses the observed case without providing a general dirty-worktree bypass.

Initialization captures the eligible path before computing governed identity and puts its provenance in the first append-only initialization event. The snapshot binds the path's exact UTF-8 Git path bytes, HEAD entry/mode/blob (or absence), index entry/mode/blob (or absence), worktree entry type/mode/content digest (or absence), and the governance-validator result. Only a regular file with supported mode is eligible. This establishes that the exact candidate existed before this milestone's first governed validation; it does not claim to authenticate who created it or when before initialization. The fixed path restriction and validator prevent other source changes from being relabeled as residue. A later committed change to the reserved path is governed work and cannot be excluded. The existing validation tool's raw worktree identity must match the captured validation snapshot; the controller separately binds the normalized governed identity and residue-provenance digest to that exact evidence digest.

The governed identity is computed from the base and complete changed-path snapshot after excluding only the captured eligible path; the immutable residue-provenance digest is bound alongside that identity in validation and recovery events. The same exact residue may be present, stashed externally, or restored without changing governed identity. If restored, path/type/mode/content must match the captured fingerprint. Absence is acceptable only when the worktree is otherwise clean; it does not certify that an external stash is durable. A partial restore, conflict markers, changed content, changed mode/type, or baseline regeneration fails identity/provenance validation. Staged and unstaged states are both captured; status changes alone do not excuse a different index or worktree fingerprint.

**Validation and identity equivalence.** A validation receipt binds the canonical governed-change identity, residue-provenance digest, exact evidence digest, validation level/profile, policy/map identity, and evidence subject HEAD. The controller verifies the evidence body against the pre-validation snapshot and recomputes repository identity immediately before append under the milestone lock and expected-generation check. Any mismatch appends no validation receipt. Reuse requires exact governed identity and residue provenance plus unchanged policy/map/profile inputs; level alone never suffices. A HEAD-only movement may preserve validation only when the governed identity is proven identical under an explicit admitted transition.

The sole current equivalence is the already-reviewed #160 checkpoint-artifact recovery: its registration manifest and exact blobs must prove that B adds only the registered review artifacts and that reconstructing governed identity after excluding exactly those proven additions yields A's identity. Only that proof permits preserving the L3 receipt for the unchanged governed identity. CI for A is always invalidated and exact CI(B) remains mandatory. If the proof, source identity, or receipt binding differs, validation is invalidated and fresh L3 is required. Ordinary `CI_PENDING` rebind may retain L3 only when its governed identity and residue provenance remain byte-for-byte identical under the pre-existing guards; no identity-change repair inherits this equivalence.

**CI authority and replay.** Passing CI can be produced only by the controller's read-only GitHub API refresh path; caller-provided `--input` data cannot produce success and the generic checkpoint command cannot write `ci_observed`. Synthetic tests replace the API adapter at the boundary, not the state-transition path. Version 1 uses a closed controller-owned required-check inventory for the repository's `ci.yml` jobs `Scan for secrets`, `Validate`, and `Test`; changing that inventory is a controller change subject to its own validation. The trusted workflow identity is also closed: the `.github/workflows/ci.yml` Git blob at the observed commit must equal baseline blob `854774e24c3e7bc79838a20f9296dbf14d12891a` <!-- pragma: allowlist secret -- public workflow Git blob identity -->. Keeping job names while changing workflow content does not preserve trust. A different, missing, or ambiguous workflow blob/run identity cannot produce passing CI and requires a separately governed design/controller change to revise the pin. Admission also requires exact repository and commit SHA, the expected workflow identity at that commit, unique identities for exactly the complete required-check set, and complete terminal results with conclusion `success` for every required check. Missing/empty/partial sets, duplicate or unknown identities, mismatched SHA/workflow/run attempt, API error or ambiguity, and `cancelled`, `skipped`, `neutral`, or any non-success conclusion cannot pass. A failed check may be classified only after failure; classification never changes pass/fail admission.

An admitted CI event records bounded API observation identity, inventory digest, exact subject HEAD, and the already-bound governed identity. Projection requires these values to equal the existing binding and CI can never advance branch, HEAD, base, or change identity. `CONFLICT` rejects CI ingestion before event append and remains latched until a separate authorized source-recovery event. If source identity changes while checks are arriving, the expected generation and locked re-read reject the stale observation. Git ref movement and a local event append remain non-atomic; a later mismatch becomes `CONFLICT`, as under current documented limitations. Local history is tamper-evident, not authenticated: the API adapter is the only supported success writer; the controller blocks supported caller-supplied/resealed event injection and classification, but does not claim protection from a local operator who rewrites and re-seals the complete history/state. That pre-existing trust boundary is not expanded into authentication work by this milestone.

**Legacy replay.** Existing history is never rewritten. Replay keeps the recorded legacy event meaning deterministic, but a historical validation receipt that lacks a complete verifiable governed-identity binding is quarantined from reuse. A resumed legacy milestone requires a generation-checked append-only migration/invalidation event before new CI or validation can advance it. That event identifies the prior history tail and bound source, records the quarantine decision, and leaves authority false. Ambiguous histories fail closed; no event is silently upgraded or treated as fresh evidence.

## Formal scope and implementation seam

Extend the existing `MilestoneController` identity, evidence, CI, and replay paths; do not create a parallel controller or generic exclusion/rebind mechanism. The likely bounded surface is:

- `src/vss_dev/milestone.py` and `src/vss_commands/cli.py` for controller-owned residue provenance, identity-bound validation invalidation/reuse, CI admission, and event replay;
- the milestone and validation-evidence schemas, plus a narrowly required provenance contract if the design review finds it necessary;
- `tests/dev_milestone/test_milestone.py` for real controller-path synthetic histories;
- `docs/agent-coordination.md` for implemented behavior and limitations;
- this design record and the repository-native milestone history.

Residue exclusion is controller-owned and limited to `.secrets.baseline` with the capture and validation rule above. No second residue path is admissible in version 1. Exact path bytes are UTF-8 NFC with `/` separators, no empty, `.` or `..` component, no normalization alias, and no case-fold collision; Git tree comparison is byte-exact. Symlinks, special files, gitlinks/submodules, nested repositories, unsupported modes, and ignored or untracked files cannot become eligible residue. The existing `.local` exception remains exactly scoped and unchanged. Ordinary clean-worktree guards still reject every non-protected dirty or untracked path; provenance does not authorize a dirty worktree.

Validation evidence must bind one exact governed change identity and provenance digest as defined above. Any identity transition invalidates or quarantines validation unless the single reviewed #160 equivalence rule proves the governed identity is unchanged. CI ingestion cannot perform a source transition: `CONFLICT` remains `CONFLICT` until a separate authorized recovery succeeds. CI success requires a GitHub API observation for the exact HEAD and the complete versioned required-check set; empty, incomplete, ambiguous, wrong-SHA, cancelled/skipped/neutral, caller-provided, or caller-classified success is rejected or remains unusable. Projection and canonical-validation reuse enforce these rules after replay and under expected-generation concurrency checks.

Retain the existing #160 `identity_rebound` REVIEW_READY recovery contract unchanged in authority and narrow artifact admissibility. Its explicit recovery remains separate from CI ingestion, still requires the reviewed artifact-registration proof and human disposition, and still lands in `CI_PENDING` with stale CI cleared.

## Acceptance criteria

Tests must exercise synthetic repository histories through the public controller operations and replay, not only helper methods.

**Pre-existing residue:**

- Pre-existing `.secrets.baseline` at initialization is captured atomically before identity calculation, including HEAD/index/worktree path, type, mode, and content identities and validator outcome.
- A bounded milestone change validates independently of that exact captured residue; secret scanning uses the bound base HEAD baseline, so residue entries cannot suppress findings. External preservation/removal/restoration leaves governed identity stable, while rebind still requires a clean worktree.
- Changed/regenerated content, deletion committed as governed work, rename, mode/type change, partial/stash-conflict restore, or substitution fails closed. Exact bytes with unchanged path/type/mode are content-equivalent; timestamps and inode identity are not semantic inputs.
- Any second residue path, newly created unrelated/untracked item, malicious source/docs/config candidate, or caller-supplied exclusion is rejected. Ignored files are never residue candidates; existing environment/cache ignore rules remain separate from governed identity, and ignored files under executable or scoped paths must cause validation to fail closed. The exact existing `.local` exception remains separate.
- A pre-initialization residue baseline containing an added or substituted suppression cannot hide a finding in a governed file because the validation scanner reads the bound base-HEAD baseline; a deliberate baseline change is governed work and is not eligible residue.
- Multiple candidates are tested: only the single closed-set baseline candidate is admitted; every additional path fails.

**Validation evidence:**

- L3 evidence is reusable only when its recorded governed identity and residue provenance equal the current binding and all policy/map/profile freshness requirements still match.
- A governed identity change clears or quarantines stale validation; a higher validation level alone cannot make it reusable.
- Validation before/after commit or rebind is compared against the exact validation snapshot; identity change during execution or append fails under lock/generation checks.
- Replay preserves exact evidence binding; unbound legacy evidence remains historical but is quarantined from reuse through an explicit append-only migration/invalidation event.
- #160 preserves L3 only when its existing artifact proof reconstructs the identical governed identity; otherwise L3 is invalidated. Exact CI(B) is always required.

**CI ingestion:**

- The read-only GitHub API adapter admits only the exact repository/head and the baseline-pinned `.github/workflows/ci.yml` blob (`854774e24c3e7bc79838a20f9296dbf14d12891a` <!-- pragma: allowlist secret -- public workflow Git blob identity -->), plus the complete unique required inventory (`Scan for secrets`, `Validate`, `Test`) with terminal `success` conclusions. A workflow change retaining the same job names is rejected; unavailable or ambiguous API workflow metadata fails closed.
- Empty/partial sets, duplicate or unknown checks, wrong SHA, workflow/run attempt mismatch, API ambiguity/failure, and cancelled/skipped/neutral conclusions cannot produce passed CI. Caller-supplied input/classification cannot produce success.
- A changed `.github/workflows/ci.yml` blob cannot pass under the old inventory even if all required job names and conclusions match; tests cover same-name workflow weakening and missing/ambiguous workflow metadata.
- In `CONFLICT`, even exact-HEAD CI cannot mutate source identity, clear conflict, or retain stale validation as reusable.
- Generic `checkpoint` cannot write `ci_observed`; only the API adapter's typed writer can append it. Replay requires event subject and identity to equal the existing source binding and never advances that binding.
- Source movement, stale expected generation, concurrent write, and CI arrival for an older SHA append no success event. API failures leave the state pending/conflicted.
- CI and validation remain distinct evidence classes; CI never satisfies L3 and validation never satisfies CI. Replay is deterministic and authority remains constant false.

**Integration and regression:**

- Reproduce the #161 residue/clean-worktree identity break end to end and show the governed identity remains stable only for exact provenance-matched residue.
- Reproduce the #162 empty-check conflict sequence end to end and prove CI cannot rebind or lead canonical validation to reuse old L3 evidence.
- Cover staged and unstaged residue, multiple candidate paths, ignored-file candidates in executable/scoped locations, stash/pop conflict, case/normalization aliases, and same-byte metadata/type changes.
- Cover zero/partial/duplicate/wrong-SHA/wrong-workflow CI, cancelled/skipped/neutral results, API failure/ambiguity, generic CI event injection, caller classifications, and replay of a resealed but schema-invalid event.
- Cover legacy histories with and without identity-bound validation; preserve old projection deterministically and require explicit quarantine before evidence reuse.
- Cover validation identity change during the run/append and stale generation/concurrent writer rejection.
- Ordinary clean-worktree `rebind-committed-head` still succeeds under its existing guards.
- The #160 REVIEW_READY artifact-only recovery remains exact, explicit, descendant-bound, and routes only to `CI_PENDING`; only its existing complete proof may establish the single unchanged-governed-identity equivalence. Its admissibility or authority guards are not weakened.
- No push, merge, implementation, production, provider, publication, workflow activation, Runtime, product, or security-exception authority is added.

## Explicit exclusions and review boundary

No implementation, controller-state repair, recovery of #160, M11.P mutation, push, merge, production/provider execution, publication, workflow activation, product authority, security exception, or generic source-identity acceptance is in scope. This checkpoint requests new Constitutional and UNKNOWN_UNKNOWN_REVIEW receipts for the revised design. Work stops until the native milestone records both final dispositions and explicitly advances to implementation.
