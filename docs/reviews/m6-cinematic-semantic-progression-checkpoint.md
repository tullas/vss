# M6 Cinematic Semantic Progression Checkpoint

## Review metadata

- Review date: 2026-08-16
- Authoritative reviewed `main`: `0b94e837eceb9b4d533739699070fe86050a4e97`
- Review branch: `agent/m6-architecture-checkpoint`
- Scope: merged PRs #71 through #74 (M6.1 through M6.4) and readiness for
  bounded Shot/Cinematography Admitted Knowledge
- Method: accepted ADR, source, schema, registry, dependency, threat-model,
  public-path, adversarial-test, audit, determinism, and negative-space review

This is a point-in-time architecture checkpoint. It changes no semantic
contract, implementation, authority, registry, or lifecycle. It does not
implement or authorize M6.5.

## Checkpoint verdict

`READY_WITH_NON_BLOCKING_GUARDRAILS`

M6 has established a coherent and independently validated progression:

```text
manual/synthetic Observation
  -> bounded unordered Observation Set
  -> immutable task Context
  -> deterministic Context-scoped Pattern
  -> deterministic Context-scoped Lesson Candidate
```

The accepted architecture is sufficient for a narrow M6.5 without a new
architecture decision. ADR-0015 defines typed, lifecycle-governed Knowledge;
ADR-0016 prevents a semantic producer from approving itself; and ADR-0024
defines domain-owned explicit promotion, challenge, evidence evolution, and
withdrawal. M6.5 must implement those existing decisions conservatively. It
must not treat the existence, frequency, or provider origin of a candidate as
an admission decision.

## Findings

No Critical, High, or Medium finding and no current source violation was found.

| Severity | Finding | Required disposition |
|---|---|---|
| Low | `ReasoningGateway` has grown from the post-M5 724-line checkpoint to 942 lines and now contains two additional cinematic route adapters. The routes remain semantic-only and contain no cinematic recurrence or Lesson transformation rules, but exact validation, provider-view binding, lifecycle, result validation, and terminal-audit mechanics repeat. | Classify `HEALTHY_WITH_PRESSURE`. Do not refactor before M6.5 solely for size. Reassess if M6.5 would add another provider route, if one integrity fix must be repeated, or if route behavior drifts. The smallest future extraction would be a typed semantic-route lifecycle adapter; domain validation and rules must remain outside it. |
| Low | Lesson Candidates deliberately add a thin semantic layer: a closed, scoped proposition and fixed limitations over one exact Pattern. This is real value because it names a reviewable promotion input, but another restatement layer after M6.5 would be wrapper inflation. | M6.5 should consume the candidate directly and add only admission decision, lifecycle, governed-use eligibility, and exact lineage. Do not add a generic Lesson framework or another intermediate proposal wrapper. |
| Low | Admitted Knowledge creates reusable eligibility and therefore raises stale-evidence and withdrawal risk beyond inert M6.1-M6.4 artifacts. | M6.5 must fail closed on challenged, disputed, superseded, withdrawn, or unverifiable lineage; preserve historical interpretation separately from current-use eligibility; and test revalidation before reuse. No synchronization service or database is justified. |
| Observation | M6 tests are numerous and some determinism/concurrency suites are comparatively expensive, but they found material resealing and lineage defects during acceptance and have remained deterministic. | Keep focused and full layers. Optimize only from measured CI evidence; do not delete integrity, concurrency, or security coverage to reduce count. |

## Semantic progression

| Milestone | Exact artifact boundary | Verdict |
|---|---|---|
| M6.1 | `shot_cinematography_observation/1` | Genuine domain evidence artifact. Closed observable vocabulary, explicit qualification, manual/synthetic provenance, exact identity, and inert non-truth semantics are preserved. |
| M6.2 | `shot_cinematography_observation_set/1` and `shot_cinematography_context/1` | Genuine aggregation and delivery boundaries. The set is bounded (2-8), single-project, single-scene, single-classification, and explicitly unordered. Context independently revalidates and projects only governed semantic material. Assembly performs no reasoning. |
| M6.3 | `analyze_shot_cinematography_patterns/1` and `shot_cinematography_pattern_set/1` | Genuine task/result boundary. Only observed values participate; recurrence threshold is exactly two; variation is distinct observed values; exclusions stay visible. Counts are evidence, never confidence or authority. |
| M6.4 | `derive_shot_cinematography_lesson_candidates/1` and `shot_cinematography_lesson_candidate_set/1` | Genuine, intentionally thin promotion-input boundary. Closed recurrence/variation propositions add exact Context scope and fixed epistemic limitations without recommendation, causality, evaluation, or Knowledge eligibility. |

The set and Context are not redundant: the first is a domain aggregation of
accepted observations; the second is the minimized, purpose-bound semantic
carrier delivered to future reasoning. The task/result pairs are likewise not
implementation wrappers: each records an independently governed semantic
operation and its inert output. No universal Cinematic Observation, Pattern,
Lesson, or Knowledge object emerged.

## Boundary verdicts

### Observation

`HEALTHY`. Observation remains supplied manually or synthetically, versioned,
immutable, provenance-bound, non-authorizing, non-recommending, and explicitly
not truth. `observed`, `uncertain`, `unknown`, `not_observed`, and
`not_applicable` remain distinct. Only `observed` and `uncertain` may carry a
value; downstream strict Pattern analysis admits only `observed`. No downstream
stage upgrades qualification or converts absence into a value.

### Pattern

`HEALTHY`. Patterns are exact `repeated_value` or `variation` evidence within
one Context. They bind supporting observation identities and content digests,
excluded evidence, exact values, and canonical identities. They express no
chronology, combinations, causality, quality, preference, recommendation, or
probability. Frequency and occurrence count grant no confidence or authority.

### Lesson Candidate

`HEALTHY`. Candidates are structured, deterministic, one-per-source-Pattern
propositions with exact source Context scope and fixed limitations. They add a
stable reviewable claim suitable for an explicit admission decision; they do
not merely rename Pattern identity. The semantic addition is deliberately
small: recurrence or variation is stated as an exact Context-local proposition
while causal, evaluative, prescriptive, universal, and Knowledge meanings are
structurally unavailable.

## End-to-end lineage and integrity

Lineage is sufficient for the narrow local M6.5 slice:

1. An observation binds contract kind/version, observation/project/scene/shot
   identities, evidence reference, qualification/value, observer/method,
   provenance, purpose/classification, and canonical content digest.
2. The unordered set binds each exact observation kind/version, identity,
   shot, and content digest. Assembly independently revalidates source
   observations and rejects duplicate observation or shot identities,
   substitution, resealing, and scope/classification mismatch.
3. Context carries immutable minimal projections plus exact observation and
   complete-context integrity. Caller-owned aliases do not become sealed state.
4. Each Pattern binds its source Context, exact supporting and excluded
   observation evidence, deterministic Pattern identity/digest, and the Pattern
   Set's complete result and invocation binding.
5. Each Lesson Candidate binds the exact Pattern identity/digest,
   supporting-evidence digest, Pattern Set semantic and complete digests, and
   source Context identity/content/complete digests. Result validation
   reconstructs the one-to-one proposition and limitations rather than trusting
   provider output or an outer hash.

The accepted adversarial suites cover stable IDs with modified content,
outer-hash resealing, omitted and duplicate evidence, scope and limitation
tampering, forged provider output, qualification loss, deterministic ordering,
working-directory and hash-seed changes, and shared-Gateway concurrency. The
lineage proves recorded consistency and historical interpretation, not truth.

## Context architecture

ADR-0017 generalized cleanly. M6.2 reuses bounded purpose/classification
admission, exact binding, canonical digests, immutable projections, and an
assembly report without moving reasoning into assembly. M6.3 receives only the
task-specific cinematic Context. M6.4 consumes the validated Pattern result
rather than raw observations and revalidates Context lineage solely for
integrity. Context transports no raw media, registry, callback, Runtime,
provider, filesystem path, or authority handle.

Context pressure is `LOW`. No new Context version is required for M6.5 unless
an admitted Knowledge consumer later needs a materially different task input.
The admission operation itself should consume the exact Lesson Candidate Set,
not manufacture a universal Knowledge Context.

## ReasoningGateway health

Classification: `HEALTHY_WITH_PRESSURE`.

The Gateway still performs exact contract admission, immutable provider-view
construction, trusted exact implementation resolution, lifecycle checks,
one-call invocation, independent result validation, and bounded terminal audit.
Cinematic recurrence and Lesson mapping remain in their domain services and
deterministic providers. Runtime, capabilities, workflows, media, persistence,
and promotion authority are absent.

Pressure is real because route adapters repeat generic mechanics and M6.5
admission does not need semantic provider execution. M6.5 should therefore not
add a third cinematic provider route merely for symmetry. Admission is a
domain-owned governed decision over an exact candidate, not creative reasoning.
If later implementation evidence requires Gateway extraction, the smallest
candidate is a typed exact-route lifecycle adapter with hooks for domain-owned
input/result validation; it is not a generic rule engine or evidence framework.

## ADRL-002

Classification: `WAIT_FOR_EVIDENCE`.

M5, M6.2, M6.3, and M6.4 document a recognizable validation -> exact projection
-> binding -> independent result-validation pattern. M6.3 and M6.4 remain one
Movie domain, their evidence recomputation invariants differ, and no stable
cross-domain unit can yet be removed without obscuring domain rules. This is
documented pattern pressure, not a utility or framework admission. The ledger
state remains unchanged.

## Registry and contract health

- Registry pressure: `WATCH`.
- Contract/versioning health: `HEALTHY_WITH_PRESSURE`.

Movie owns the observation, aggregation, Pattern task/result, and Lesson task/
result families; Context owns the cinematic Context; the implementation
registry owns exact strategies/providers. These ownership choices remain
coherent. Registries contain no artifact instances, no capacity or policy
authority, and no dynamic/latest/wildcard/range resolution. Historical schema
and registry digests remain evidence rather than being overwritten.

The current Movie registry has 20 exact registrations across 18 families; the
Context registry has nine exact registrations across eight families. Growth is
semantically justified, but manual exact maps and registry digest evidence now
deserve monitoring. No registry split or Knowledge instance registry is
justified by count. M6.5 should add only a narrowly owned Knowledge artifact
registration if its contract truly crosses the admission boundary.

## Readiness for Knowledge admission

### Semantic distinction

Lesson Candidate means an inert, exact-Context proposition derived from local
evidence. Admitted Knowledge must add only that the proposition passed an exact
domain-owned promotion policy and is eligible for named governed future uses.
Admission still does not mean true, authoritative, approved creative direction,
recommended, universal, or executable.

### Admission authority

`READY_WITH_GUARDRAILS`. ADR-0024 makes promotion domain-owned and requires an
accountable promotion owner, policy identity/version, evidence eligibility,
contradiction treatment, review requirements, and lifecycle outcome. ADR-0016
prevents a proposer, provider, strategy, or candidate from approving itself and
keeps Runtime as execution authority. No new universal authority center is
needed.

For the initial slice, require an explicit human-attributable admission
decision after deterministic fail-closed policy validation. Human review is a
conservative first-domain policy, not a claim that ADR-0016's Runtime execution
approval artifact is reusable unchanged. The deterministic provider that
created a candidate must never be the admitting authority. A later low-risk
rule-only admission policy would require separate evidence and explicit policy.

### Promotion criteria

`READY_WITH_GUARDRAILS`. The exact v1 policy must require:

- the accepted Lesson Candidate kind/version and independently reconstructed
  candidate, Pattern, Context, observation, and provenance lineage;
- one Shot/Cinematography domain and exact-project scope;
- only manual-observation or synthetic-test lineage and their accepted method
  pairings;
- fixed candidate limitations and no recommendation, causal, evaluative,
  confidence, or truth semantics;
- current evidence eligibility with no unresolved integrity failure,
  contradiction, challenge, withdrawal, or supersession that policy forbids;
- an accountable admission owner and explicit human-attributable decision;
- exact promotion-policy identity/version, purpose, classification, lifecycle,
  effective scope/period, retention, and historical interpretation; and
- a rejection outcome that creates no admitted artifact.

No numerical sufficiency, frequency, confidence, popularity, model agreement,
or provider identity may promote a candidate. One accepted candidate should
yield at most one semantically equivalent admitted item for the same policy and
scope.

### Lifecycle and withdrawal

`READY_WITH_GUARDRAILS`. ADR-0015 and ADR-0024 define sufficient domain-owned
semantics without imposing a universal enum. M6.5 should minimally distinguish
active/admitted current-use eligibility from disputed/challenged, superseded,
withdrawn/revoked, and historical/archived interpretation. Current-use checks
must fail closed when eligibility is unknown.

Withdrawal and supersession cannot be postponed entirely because admission
makes reuse possible. M6.5 need not build propagation infrastructure, but its
contract and tests must represent lineage impact and prohibit new use of an
inactive item. Historical identity must remain interpretable and must not be
rewritten or deleted merely to model a lifecycle transition.

### Evidence accumulation and semantic evolution

`READY`. Current canonical identity and separate complete-result/invocation
bindings support the ADR-0024 distinction:

- unchanged meaning with additional evidence changes attributable evidence or
  provenance state, not necessarily semantic version;
- changed calibration or qualification changes its owned state and never
  silently becomes authority; and
- changed conclusion, scope, limitations, lifecycle interpretation, or
  governed use creates a new semantic identity/version and may explicitly
  supersede history.

M6.5 must not mutate a historical Knowledge item in place to attach new
evidence or make a changed claim appear historically admitted.

### Persistence

Classification: `NOT_REQUIRED_YET`.

A bounded repository/local or in-memory artifact plus deterministic fixtures
is sufficient to prove admission semantics. Reuse eligibility and historical
lineage do not by themselves justify a database, graph store, vector store,
service, daemon, or synchronization mechanism. Storage identity must remain
independent of any later persistence choice. If durable multi-process mutation,
large reverse-lineage traversal, concurrent writers, or measured retrieval
scale appears, ADR-0023 Component Admission must precede a persistent product.

### Audit

The current bounded semantic audit pattern is sufficient as a model, but M6.5
needs an admission-specific record of candidate identity/digest, decision,
policy/owner or approver identity, resulting Knowledge identity when accepted,
rejection reason, lifecycle outcome, and correlation identity. Audit remains
evidence and cannot create admission authority. Semantic identity should remain
deterministic; decision/event identity may be intentionally separate and
non-semantic.

### Security readiness

`READY_WITH_GUARDRAILS`. M6.5 acceptance must adversarially cover forged
promotion, candidate/Pattern/evidence substitution, outer-hash resealing,
evidence laundering, duplicate admission, scope or purpose escalation,
limitation removal, recommendation smuggling, self-promotion by a provider,
policy/approver substitution, stale or revoked evidence reuse, and poisoned
lineage. Inputs remain hostile inert data. No file access, network, subprocess,
dynamic import, source execution, arbitrary construction, raw media, or
external retrieval belongs in the admission path.

## Test and CI health

Classification: `WATCH`.

Focused M6 coverage (11 M6.1, 15 M6.2, 17 M6.3, and 11 M6.4 tests) exercises
qualification, exact dispatch, resealing, lineage, provider lifecycle,
determinism, and concurrency rather than merely accumulating happy paths. The
complete Python suite has reached 474 tests. CI and Security Supply Chain are
green on the reviewed main. No flaky result is evidenced, but full local and CI
time is material and several domains repeat broad regression runs. Preserve the
layers and reassess only with measured duration/flakiness data.

## Architecture entropy

| Dimension | Pressure | Checkpoint evidence |
|---|---|---|
| Gateway | `WATCH` | Sound semantic boundary; two additional domain adapters and repeated lifecycle/audit mechanics |
| Registry | `WATCH` | Coherent federation and exact versions; Movie mappings and digest evidence are growing |
| Versioning | `LOW` | Every M6 family/version represents a distinct semantic boundary; no compatibility fallbacks |
| Operational | `LOW` | No database, service, queue, worker, cache, model server, or external dependency |
| Cognitive | `WATCH` | Long exact lineage chains and digest domains demand careful review |
| Domain coupling | `LOW` | Movie, Context, Knowledge, Reasoning, and Runtime dependency directions remain protected |
| CI/test | `WATCH` | Valuable 474-test suite with material deterministic/concurrency and full-regression cost |
| Governance | `WATCH` | Acceptance reviews found real defects, while review size and repeated evidence are costly |

Decision: `WATCH`. Current complexity is justified and bounded. M6.5 should
add a single narrow admission boundary and no provider path, generic framework,
or infrastructure.

## Removal and deliberate negative architecture

Candidates for removal: `None`. No dead provider path or semantically redundant
accepted artifact was found. Historical contracts are not removal candidates.

Things deliberately not built:

| Deferred item | Why absent | Reconsideration trigger |
|---|---|---|
| Generic evidence, Pattern, Lesson, or Knowledge framework | Independent stable cross-domain mechanics and net simplification are not proved | Measured copy drift or another independent domain isolates a removable invariant |
| AI/CV, media decoding, or model observation | Manual/synthetic evidence is sufficient and model/calibration workload is absent | Accepted probabilistic/model provenance contracts plus measured need |
| External/reference learning or ingestion | Rights eligibility, retention, derivative use, and withdrawal remain separate governance | Resolve ADRL-005 through a dedicated rights/source decision before ingestion |
| Persistent Knowledge service/database/graph/vector store | No measured durable-state or scale requirement | ADR-0023 Component Admission after concrete persistence/scale evidence |
| Cross-project or studio-wide Knowledge | Current evidence and candidate semantics are exact-Context/project local | Separate domain policy and independent corroboration/generalization evidence |
| Recommendation, Creative Intent, Shot Design, or production approval | Knowledge eligibility is not creative or production authority | Explicit later semantic milestone and human/Runtime authority review |
| Plan IR, Data/Compute implementation, rendering, workers, or queues | M6 remains bounded Semantic Plane work with no execution graph or heavy workload | Accepted workload/plane decision supported by implementation evidence |

## Mission alignment

Classification: `ALIGNED_WITH_DRIFT_RISK`.

M6 directly supports autonomous movie production by converting explicit shot
observations into inspectable local propositions that future cinematic
reasoning may use. It remains recognizable as governed creative intelligence:
human intent and Runtime authority are preserved, technology is replaceable,
and every result is explainable. The drift risk begins at Knowledge admission:
generalizing beyond Shot/Cinematography, local project scope, or accepted
lineage would turn a movie-production proving slice into a general epistemic
platform. The M6.5 bounds below contain that risk.

## Exact recommended M6.5 scope

Implement one bounded, local Shot/Cinematography Admitted Knowledge contract
and an explicit admission-decision operation over the accepted
`shot_cinematography_lesson_candidate_set/1`:

1. accept exactly one independently validated Lesson Candidate at a time;
2. restrict scope to its exact source project, exact cinematic domain, and
   local manual/synthetic lineage;
3. bind exact candidate, Pattern Set, Pattern, Context, observation, evidence,
   provenance, purpose/classification, and policy identities/digests;
4. require deterministic fail-closed policy gates plus an explicit
   human-attributable admission decision for v1;
5. produce either no admitted item or one inert, exact-versioned Knowledge item
   with domain-owned lifecycle, governed-use purpose, limitations, effective
   scope/period, retention, and historical interpretation;
6. represent challenge/dispute, supersession, withdrawal/revocation, and
   historical state sufficiently to block current reuse without rewriting
   history;
7. keep semantic identity deterministic and separate from admission/audit event
   identity; and
8. stop at eligibility. Do not package for reasoning, recommend, execute,
   persist through a service/database, generalize across projects, ingest
   external sources, invoke AI/CV, or add another Gateway provider route.

No new ADR is required for this scope. A proposal for automatic admission,
cross-project reuse, external/reference evidence, probabilistic promotion, or
a persistent Knowledge subsystem would exceed this readiness verdict and
requires its own architecture evidence or decision.

## Validation evidence

- Focused M6 suites: 11 M6.1, 15 M6.2, 17 M6.3, and 11 M6.4 tests passed.
- Complete Python regression: 474 tests passed across architecture, M3-M6,
  Runtime, Context, Gateway, providers, command/public paths, security,
  determinism, and concurrency suites.
- Bash syntax, ADR/reference validation, Ansible syntax, OpenTofu formatting/
  initialization/validation, JSON and JSON Schema tests, supply-chain policy,
  Python vulnerability and license checks, secret scanning, SBOM/provenance,
  release-artifact/sensitive-content validation, and `git diff --check` passed.
- Container/IaC scanning and CodeQL remain workflow-owned gates and must pass on
  the checkpoint pull request before review completion.
- There is no public cinematic CLI execution route to exercise; existing
  CommandRunner/public-path regression tests passed unchanged.

## Baseline verification

- PR #71 merged as `205adec3dbae3c7b39ff842913e714aec125d918`.
- PR #72 merged as `b7d064dd766163630929ad74c35951655d536599`.
- PR #73 merged as `5625f84dc827ff3ba4ab0557a2444f45f43cf4a0`.
- PR #74 merged as `0b94e837eceb9b4d533739699070fe86050a4e97`.
- ADR-0010 through ADR-0024 are `Accepted`.
- ADRL-002 remains `WAIT_FOR_EVIDENCE`.
- Main CI, ADR Validation, Ansible Validation, Security Supply Chain, and the
  current Dependabot workflow completed successfully at the checkpoint.
- `.local/secrets/development.auto.tfvars.example` was neither inspected nor
  modified; it remains an unrelated untracked path and is excluded from this
  checkpoint.
