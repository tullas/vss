# GitHub agent coordination protocol

VSS uses GitHub issues and pull requests as the durable coordination record for human,
ChatGPT, and Codex handoffs. This protocol reduces repeated prose; it does not create an agent,
workflow engine, identity system, or execution authority.

`AGENTS.md` remains repository guidance. Runtime remains the only capability/provider execution
authority. A GitHub checkpoint or approval record cannot authorize Runtime, a provider call,
production, publication, or workflow activation. Caller-supplied `recorded_by` is accountability
metadata, not authenticated or signed identity.

## Checkpoints

The strict contract is `schemas/agent-checkpoint-v1.schema.json`. Checkpoint types are:

- `design`: proposed architecture before implementation;
- `implementation`: implementation and test delta ready for review;
- `review`: adversarial review result;
- `blocked`: concise blocking condition and current evidence;
- `complete`: completed milestone evidence;
- `approval_record`: a human decision recorded against exact code and operation identities.

Every payload binds repository, branch, base SHA, HEAD SHA, bounded delta counts/paths, closed check
statuses, and constant-false authority fields. Changed paths are sorted and capped. `.local/**` and
credential-looking paths are omitted from payloads, but omission does not make them safe: only
`.local/secrets/development.auto.tfvars.example` is the repository-defined protected residue ignored
for approval worktree freshness. Any other dirty path, including another `.local/**` path, blocks an
approval record.

Comments use this envelope:

````text
<!-- vss-agent-checkpoint:v1 sha256=<canonical-payload-sha256> -->
```json
<canonical JSON payload>
```
````

The digest covers the exact canonical JSON bytes. Consumers validate the marker, digest, closed
contract, and—when freshness matters—current HEAD. Exact markers make repeated posting idempotent;
checkpoints remain immutable comments rather than mutable hidden state.

## Helper

`scripts/vss-agent` is a stdlib-only local helper. It reads bounded Git metadata and explicitly
supplied check outcomes. It never reads diffs or changed-file contents, executes tests, invokes VSS
Runtime/providers, merges, pushes, or interprets GitHub approval as execution permission.

Emit a local checkpoint without network access:

```bash
scripts/vss-agent checkpoint \
  --target issue:90 \
  --type implementation \
  --base 0694824cf3adea03c90762483342811808c41cbb \
  --summary 'Implementation ready for adversarial review.' \
  --check focused-tests=passed
```

Add `--post` only when authorized to write a GitHub issue/PR comment. Pull requests use
`--target pr:<number>`. Posting validates first, calls `gh` with fixed argument vectors, fetches
existing comments, and posts only if the exact marker is absent.

Record coordination approval metadata only from a clean code worktree:

```bash
scripts/vss-agent approval \
  --target issue:90 \
  --scope effectful_operation \
  --operation-digest <64-lowercase-hex> \
  --decision approved \
  --recorded-by <accountability-id>
```

Approval scopes are closed: `paid_provider_attempt`, `effectful_operation`, `merge`, and `push`.
The record binds current HEAD and the operation digest. Any HEAD change makes it stale. It still
grants no Runtime or provider authority; effectful systems must perform their own admission and
authorization through existing boundaries.

Validate raw payload JSON or a complete comment envelope:

```bash
scripts/vss-agent validate --input checkpoint.txt
scripts/vss-agent validate --input checkpoint.txt --require-current-head
```

Malformed, oversized, secret-looking, ambiguous, stale, detached-HEAD, unsupported-origin, or
unexpected-dirty states fail closed with bounded diagnostics.

## Harness v2 routing and validation

`config/agent-harness-v2.json` is the strict repository-owned navigation and impact map. It contains
closed domain IDs, authoritative documentation/code/test paths, ordered exact-or-prefix impact
rules, and validation profiles expressed only as fixed argument vectors. It is configuration, not
executable authority: callers cannot supply commands, shell expressions, imports, or fallback
profiles.

Route a disposable session to paths without reading source contents:

```bash
scripts/vss-agent context --domain agent-coordination --domain security
```

Plan the current change against an explicit ancestor:

```bash
scripts/vss-agent impact --base <base-sha>
```

The plan deterministically unions every matching rule. Validation levels are `L0` for bounded
syntax/schema/diff checks, `L1` for direct domain tests, `L2` for declared architecture/security
dependencies, and `L3` for the canonical `scripts/validate-change.sh` repository gate. Lower levels
speed up inner-loop work; L3 is always required for merge readiness. Unknown paths and changes to
the map, helper, schemas, CI, or validation machinery fail closed to at least `shared` risk and L3.

Risks are closed and ordered: `docs`, `isolated`, `shared`, `external-effect`, and
`paid-authority`. Risk can only increase required validation, review, or human gates. It never
authorizes Runtime, providers, payment, merge, or push. Existing explicit Runtime/provider
authorization remains mandatory.

Run the selected fixed profiles and write compact proof-carrying evidence:

```bash
scripts/vss-agent validate-change --base <base-sha> --level L3 --output /tmp/evidence.json
scripts/vss-agent evidence --input /tmp/evidence.json --require-current-change
```

Successful evidence contains no command logs. It binds the repository, branch, base and HEAD SHA,
canonical map digest, exact tracked diff plus bounded untracked-content identity, selected plan,
fixed profile IDs, and pass results. Any HEAD, map, or worktree change makes it stale. Unexpected
`.local/**`, sensitive-looking, or unclassified paths are not silently omitted; only
`.local/secrets/development.auto.tfvars.example` retains its narrow protected-residue exception.
Failure output is bounded and written only as diagnostic material.

Validation evidence also records bounded elapsed milliseconds, per-profile timing, and a
`resource.getrusage(RUSAGE_CHILDREN)` process-children high-water mark. The RSS value is reported
with its platform unit (`bytes` on macOS, `kibibytes` on Linux/other supported hosts) and platform
identifier; it is not instantaneous usage, deterministically comparable across runs, or
cross-platform comparable without interpretation. These observations are advisory only; they do
not change validation requirements or grant authority.
`scripts/vss-agent doctor` reports redacted platform, CPU, available memory, free disk, and
environment-category signals, plus an advisory validation parallelism recommendation. It never
returns environment values or credentials. The controller's `analyze` action derives only the
known local-green/CI-failure-loop and repeated-repair relay findings from its existing history;
unknown opportunities remain an explicit empty result for later governed work.

Execution packets carry repository references only, a bounded reference count, and an explicit
`content_included: false` marker. Durable friction observations may be appended through
`vss dev milestone checkpoint --type checkpointed --observation-input <file>` using the strict
observation contract. These records remain advisory development evidence and do not authorize
Runtime, provider, production, publication, deployment, canon, or workflow activity.
Evidence output paths must be absolute and outside the repository so writing evidence cannot make
the evidence stale or turn a local artifact into repository authority.

A reset session reconstructs state from the GitHub issue or PR, `AGENTS.md`, requested domain IDs,
router output, and the latest fresh checkpoint/evidence digest. Hidden agent memory and local
evidence files are never authoritative.

After an accepted implementation is committed, `vss dev milestone rebind-committed-head` may
append one explicit identity-rebind event for a modern `CI_PENDING` milestone. It requires the
expected generation, unchanged branch/base and reviewed change identity, a descendant HEAD, and
a worktree containing only the protected residue. The event preserves review and validation
history, clears any prior CI observation, and keeps `ingest_ci` as the next route; it grants no
authority and does not rewrite history. Change identity includes committed diff paths so a commit
does not itself appear as a semantic change to the reviewed implementation.

A `REVIEW_READY` source-identity conflict has one narrower path for issue #160. Before creating
the descendant commit, while still at clean `REVIEW_READY` HEAD A, provide a JSON array of one to
four canonical `vss.agent-checkpoint` v1 `design`/`review` envelopes from outside the repository:

```text
vss dev milestone register-checkpoint-artifacts --milestone-id <id> --input <external-bundle.json> \
  --summary "Register the reviewed checkpoint artifacts." --expected-generation <N> \
  --human-disposition "I reviewed this exact checkpoint bundle for issue #160." --reviewer <accountability-id>
```

The controller prints the exact manifest with paths derived from each envelope's raw blob digest.
Commit only that manifest at `docs/reviews/<id>-checkpoint-artifact-manifest.json` and those
envelopes under `docs/reviews/<id>-checkpoint-artifacts/`. Any extra, modified, deleted, renamed,
or differently-moded path makes recovery fail. After the commit, explicitly bind the printed
manifest digest using the ordinary rebound command:

```text
vss dev milestone rebind-committed-head --milestone-id <id> \
  --summary "Recover the registered REVIEW_READY checkpoint artifacts." \
  --expected-generation <N> --checkpoint-manifest-sha256 <registered-manifest-sha256> \
  --human-disposition "I authorize this exact checkpoint recovery to CI_PENDING." \
  --reviewer <accountability-id>
```

This variant requires a direct child of A, unchanged branch and pinned base SHA, a clean worktree,
complete Git-tree-delta accounting, and unchanged A-tree evidence blobs for retained review
receipts. It appends a typed `identity_rebound` event, preserves prior receipts as history, clears
CI(A), and routes to fresh exact-HEAD CI(B). It cannot restore `REVIEW_READY` or grant push, merge,
production, provider, Runtime, publication, or workflow authority. A later Git ref movement is a
new identity conflict: the local lock cannot make Git ref movement atomic with event append.

The one-time `vss dev milestone bootstrap-controller-upgrade` transition is narrower: it is
available only for `dev-wf-2-engineering-observability`, requires explicit base, old, reviewed,
and target heads plus the expected generation, and accepts only the registered controller-repair
path set between the reviewed and target commits. It records both controller identities and the
repair digest, resets CI to `not_observed`, and cannot be replayed.

## Short handoff workflow

## DEV-WF-1 repository milestone controller

`vss dev milestone` is repository-development coordination only. It does not
use Runtime, providers, production authority, GitHub approval as execution
authority, or arbitrary commands. It reuses the strict harness-v2 impact and
fixed-profile evidence route, while `.vss/milestones/<id>/history.ndjson` and
its materialized `state.json` hold compact local milestone state. GitHub CI is
an exact-HEAD external observation and GitHub issue/PR comments remain an
audit mirror.

Use `init`, `transition-branch`, `status`, `next`, `checkpoint`, `validate`, and `ci`; `pr` is
status-only in this first slice. State/history corruption, a changed HEAD,
stale CI, security/infrastructure/unknown classification, writer conflict,
or repair-budget exhaustion fails closed. The controller may classify routine
code or registered-fixture failure but never authorizes the repair, push, PR,
merge, paid call, or Runtime/provider execution.

Milestone initialization may record one pre-existing residue candidate: a modified
tracked `.secrets.baseline` whose HEAD/base blobs agree and whose fixed-path governance
check passes. Its append-only provenance binds the HEAD, index, and worktree path,
type, mode, and content. This is identity bookkeeping only: validation secret scanning
uses the baseline blob from the milestone's pinned base HEAD. No caller-selected
exclusion is accepted, a later baseline edit is governed work, and strict clean-worktree
checks still apply to every non-protected path.

Validation receipts bind the governed change identity, residue-provenance digest,
evidence subject HEAD, harness map, and controller policy. A legacy receipt without
that binding remains in history but is quarantined before new validation can advance
the milestone. CI is admitted only through the controller's read-only API refresh for
the exact committed HEAD and bound branch, on the pinned `.github/workflows/ci.yml` blob,
using the `pull_request` workflow event and complete required job set (`Scan for secrets`,
`Validate`, `Test`). The event filter excludes a same-commit `push` run from making the
pull-request observation ambiguous. CI cannot change source identity or clear `CONFLICT`;
every identity rebound clears CI and requires a fresh exact-HEAD observation. The API
refresh and local history append cannot be atomic with Git ref movement, so any movement
during admission fails closed and requires recovery.

`vss dev milestone next --packet` emits a strict, deterministic
`vss.dev-milestone-execution-packet` for reset-session handoff. The packet binds the exact
milestone generation and history tail, base and HEAD SHAs, worktree change identity, issue,
policy, harness-v2 map, validation evidence, CI observation, and repair budget. Its context is a
bounded set of harness-v2 repository references grouped as guidance, implementation, tests, and
validation/config/contracts; it contains no file contents, commands, logs, prompts, or credentials.
Unregistered domains, unclassified changed paths, sensitive residue, stale HEAD, corrupt state,
map disagreement, and oversized context fail closed. Ordinary `next` retains its compact shape.

For a reset session, give the fresh repository-aware agent only the canonical packet and repository
access. The agent verifies the bound checkout, reads the referenced guidance/context, performs only
the controller-selected bounded action, and returns durable controller validation or checkpoint
evidence. Hidden ChatGPT/Codex memory, copied terminal output, and hand-written milestone history
are not authoritative. The packet is advisory coordination data and all Runtime, provider,
production, publication, workflow, security-exception, product, merge, and push authority fields
remain constant false.

### Durable improvement backlog

`docs/engineering/improvement-backlog-v1.json` is the small Git-durable backlog for deferred
engineering findings. Its strict candidate contract is
`schemas/dev-improvement-candidate-v1.schema.json`. A candidate binds a stable deterministic ID
to a milestone observation/finding, evidence references and digests, expected benefit dimensions,
risk, architectural fit, disposition, trigger, priority, required review, and status. Candidates
are advisory records only: `queued`, `implement-now`, and `prerequisite` never authorize
implementation, Runtime, providers, production, publication, workflow activation, merge, or push.

DEV-WF observations can be materialized only when the supplied finding exactly matches an
observation already in that milestone's append-only history:

```text
vss dev milestone backlog-admit --milestone-id <id> --input candidate-spec.json
vss dev milestone backlog-report --milestone-id <id>
```

The report selects queued candidates whose explicit trigger is a milestone boundary, ordered by
priority and stable ID. It is a review list, not a scheduler or implementation queue. Admission
does not change milestone routing or status. This slice does not implement deferred improvements,
add autonomous scheduling, or create a generic governor.

### Mission checkpoint and stop/challenge contract

The pre-implementation gate uses the existing controller's initialization,
checkpoints, history, and `DESIGN_REVIEW_REQUIRED / request_design_review`
route. Its only outcomes are `PROCEED`, `REVISE`, and
`STRATEGIC_REVIEW_REQUIRED`. Initialization without mission evidence stops;
legacy histories remain readable but must append an assessment before work
can proceed. There is no implicit grandfathering of prior implementation,
validation, or CI into mission clearance.

Read `docs/architecture/decisions/index.json` first. It lists only active
decision records; each compact record points to its governing ADRs and reviews.
This is Git-native institutional memory, not a new authority center. A
decision is authoritative until its record is explicitly superseded or
retired; a hypothesis or backlog item is not a decision. Do not copy records
into packets or conversations.

`init --mission-input <file>` accepts this compact declaration (example
values describe an intended slice, not an implemented moving-shot feature):

```json
{
  "gap": "Film #1 has still review images but no moving shot.",
  "observable_result": "One governed moving-shot review candidate.",
  "authority_alignment": "aligned",
  "active_decisions": [{
    "id": "DEC-0001",
    "disposition": "COMPLY",
    "rationale": "This advances the Foundation Closure direction."
  }],
  "triggers": ["provider_media_transition", "architecture_boundary"],
  "heartbeat": [
    {
      "milestone_id": "m10-7",
      "capability": "image",
      "advanced": true,
      "evidence": "src/vss_movie_storyboard/visual_production_set.py"
    }
  ]
}
```

The bounded index holds at most eight ACTIVE decisions, and every one must
appear exactly once in every mission assessment. Each declared active decision
needs one disposition. `COMPLY` means the work
is consistent. `NOT_APPLICABLE` gives the short reason it does not govern.
`CHALLENGE` identifies the record and concise new rationale, then requires the
existing Strategic and Constitutional review receipts before implementation.
The controller rejects unknown, missing, retired, malformed, or duplicate
decision evidence. A successful challenge does not change a record: the review owner
must explicitly preserve its lineage as `ACTIVE` to `SUPERSEDED` or `RETIRED`
and add the replacement/rationale before a later assessment can comply.

`authority_alignment` must be explicitly `aligned`, `unknown`, or
`conflicting`. Unknown or conflicting authority always stops, even when
positive review receipts exist; record the resolution in repository evidence
and submit a new assessment. `aligned` asserts compatibility with existing
authority boundaries and never delegates creative or production authority.

Supply the last one to five completed milestones in chronological order,
with unique milestone IDs, an observed capability, whether it advanced, and
a compact evidence reference. The ladder is `story`, `scene`, `storyboard`,
`image`, `moving_shot`, `multi_shot_scene`, `dialogue_audio`, `edited_scene`,
`rough_film`, `finished_poc`. Improvements within a rung count when observable;
projected future results do not. Three consecutive `advanced: false` entries
require Strategic Review. This fixed bounded signal is not the governance
document's roughly-five-major-milestones review cadence or a production
ontology. The controller checks declarations, not historical completeness or
the truth of media-quality claims; the repository-aware reviewer checks the
references. No global history scanner or new persistence is introduced.

| Declared trigger | Existing review mechanisms required |
| --- | --- |
| `strategic_concern` (including an explicit strategic pause) | Strategic Review / Right to Pause |
| `creative_production_authority` | Strategic, Constitutional, UNKNOWN_UNKNOWN_REVIEW |
| `provider_media_transition` where architecture requires review | Constitutional |
| `architecture_boundary` (major plane, durable authority, external dependency, or material recovery/security/rights transition) | Constitutional, UNKNOWN_UNKNOWN_REVIEW |

Declare every applicable trigger. A provider transition that also crosses a
major boundary declares both; ordinary compatible extensions do not trigger
boundary review. A declared requirement stays latched for that milestone so
removing a trigger or shortening the heartbeat cannot erase it.

Use the existing checkpoint command to assess or reassess:

```text
vss dev milestone checkpoint --type mission_assessed --input assessment.json --summary "Film #1 gap and scope checked." --expected-generation N
```

The input is exactly `{"mission": <declaration above>}`. For each applicable
review, record its actual disposition using `--type mission_reviewed` with:

```json
{
  "assessment_sha256": "<current state mission_gate.assessment_sha256>",
  "review": {
    "mechanism": "strategic",
    "disposition": "CONTINUE_WITH_GUARDRAIL",
    "owner": "<accountable project owner or assigned reviewer>",
    "evidence": "docs/reviews/<actual bounded review record>.md"
  }
}
```

These commands require the current `--expected-generation`. Strategic
receipts use the existing Right to Pause outcomes: `CONTINUE`,
`CONTINUE_WITH_GUARDRAIL`, `REMEDIATE_FIRST`, `STRATEGIC_REASSESSMENT`.
The referenced Strategic Review retains its existing concise output format;
guardrails and their affected scope belong in that record. Constitutional and
UNKNOWN_UNKNOWN_REVIEW receipts use `ACCEPT`, `REVISE`, or `REJECT`; each
references the applicable existing review evidence, including independent
review where architecture governance requires it. Review owner strings are
accountability metadata, not authenticated identity or proof of authorization.
The controller records dispositions; it does not perform or authenticate the
reviews. References are bounded repository paths, not copied review contents.

Only all required positive dispositions permit `PROCEED`. Remediation or
rejection yields `REVISE`; missing review or strategic reassessment stops.
Receipts bind to the exact assessment event digest, not a caller-selected
substitute. A new assessment invalidates earlier receipts; subsequent review
checkpoints can record changed dispositions for the same assessment. Replay
reconstructs the gate from history and rejects a resealed materialized gate
that disagrees. Local hashes detect inconsistency, not a hostile writer who
controls the entire local history and all materializations.

The gate overrides normal implementation, validation, CI, and repair packet
routing while unresolved. Diagnostic validation and CI observations remain
available but cannot clear it; repair/completion checkpoints cannot cross it.
After clearance, existing validation, CI, repair budgets, and human boundaries
still apply. The packet includes the compact gate projection, active-decision
IDs and index digest, and constant `stop_and_challenge: true`, within the
existing 16-KiB / 64-reference limits.

That constant obliges the executing agent to inspect the issue, Constitution,
governance, boundary-review guidance, and actual repository evidence before
acting. If those contradict the requested milestone, stop affected work,
state the concrete contradiction and smallest viable revision, and append a
`mission_assessed` checkpoint declaring `strategic_concern` and all other
applicable triggers. Unknown authority uses `unknown`; a material unresolved
contradiction uses `conflicting`. Do not continue ordinary implementation
because a previous packet said `PROCEED`. The controller cannot detect an
undeclared prose contradiction or enforce behavior outside its own flow.

### A10 strategic conclusion

Issue #128 records the direction following the M10.8 pause: movie production
remains VSS's proving application. Select work from observable Film #1 gaps,
with a concrete movie-production result, rather than previous-milestone
adjacency. The current visual-production-set implementation explicitly
excludes motion/video generation; still-image coordination does not close
that gap. A10 adds a development stop, not audiovisual capability.

The existing Strategic Review vocabulary captures this direction:

- `KEEP`: governed creative intent, accumulated knowledge, replaceable
  providers, Runtime effect authority, and human creative/production control.
- `CHANGE`: select milestones mission-forward from Film #1 capability gaps.
- `RESEARCH`: only bounded questions needed to admit the first moving shot.
- `REMOVE/RETIRE`: no component removal justified by this slice.
- `DO_NOT_BUILD`: a Studio Director, governor, agent framework, or additional
  persistent subsystem for this development checkpoint.
- `BIGGEST_WRONG_ASSUMPTION`: local milestone coherence establishes sustained
  progress toward a demonstrable film.
- `MISSION_ALIGNMENT`: `ALIGNED_WITH_DRIFT_RISK`; the intended system remains
  recognizable when explainability, human intent, governed creative
  intelligence, knowledge, and simplicity lead capability selection.

After A10 the next product milestone must add observable audiovisual
production capability; the preferred target is the first governed moving/video
shot. A deviation needs an explicit strategic justification in the existing
review, declared as `strategic_concern` in its mission assessment. Capability
does not imply autonomous production authority. Future delegated agent work
must operate under an explicit resource envelope covering scope, authoritative
context references, context/token budget, model class, turns, retries,
provider-call and monetary limits, allowed actions/artifacts, stop conditions,
and escalation. Route work to the least costly adequate model, bound retries
to actionable evidence, and ultimately attribute production cost to useful
film, scene, or shot units. Conversations are disposable execution state;
durable bounded repository artifacts are authoritative context. These are
architectural constraints for later work, not an A10 agent or cost system.

The compact state may recommend GPT-5.6 Sol High for architecture/security
stops, GPT-5.6 Terra Medium for bounded repairs, and GPT-5.6 Terra Low for
status/maintenance. This is advisory routing metadata only: it neither proves
the active model nor changes validation, review, or authority requirements.

Only the repository-defined protected local residue is excluded from state
change identity. No other `.local` or sensitive path is accepted.

After initialization, one explicit branch transition may bind the milestone to
exactly `feature/<milestone-id>`. The append-only transition event records the
initial and target branch plus the unchanged base, requires the current and
initial branches to point at the stored HEAD, and uses expected-generation
optimistic concurrency. It preserves the prior change identity so an existing
worktree delta remains visible as work. Replays, a second transition, arbitrary
branch names, changed ancestry/HEAD, later branch switching, or modified history
fail closed; the event grants no execution, push, merge, or product authority.
Every newly appended controller event also seals its exact worktree change
identity. A narrowly explicit `recover-state-identity` action may upgrade one
legacy unbound validation tail only by appending `validation_invalidated`,
clearing reusable evidence, and routing back to affected validation. It never
rewrites the legacy event, grandfathers its evidence, or recovers semantic
conflicts automatically.

1. Human or ChatGPT creates the milestone issue: `Work issue #N`.
2. Codex reads `AGENTS.md`, this protocol, and the issue, then posts a `design` checkpoint.
3. After issue review, Codex implements and posts `implementation`: user says `Continue #N`.
4. ChatGPT fetches and validates the checkpoint: user says `Check #N`.
5. Once a PR exists, subsequent checkpoints target the PR rather than duplicating issue prose.
6. Human approvals are recorded as SHA/operation-bound metadata; actual effects still require their
   normal explicit authorization and Runtime policy.

Use verbose prose only for exceptions, blocking evidence, or material design changes. Normal
handoffs should be the marker, canonical payload, and at most a short human-readable sentence.
