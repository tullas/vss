# Architecture Review Governance

## Purpose

VSS uses evidence-led architecture review to distinguish current guarantees
from deferred architecture. Acceptance of an ADR records a decision; it does
not assert that every future subsystem described by that decision exists.

Reviews also apply the short [VSS Constitution](vss-constitution.md), consult
the [Architecture Entropy Ledger](architecture-entropy-ledger.md), and park
premature questions in the
[Architecture Debt and Research Ledger](architecture-debt-research-ledger.md).
These mechanisms inform existing reviews; they create no new authority center
and are not required paperwork for ordinary feature pull requests.

## Review modes

### Milestone Acceptance Board

The Milestone Board validates a change against accepted architecture and its
current scope. It inspects source, dependencies, tests, schemas, registries,
failure behavior, and authority boundaries. It classifies findings and blocks
the milestone when a current security, authority, compatibility, or material
evidence defect remains.

### Constitutional Architecture Board

The Constitutional Board attempts to falsify platform assumptions across
workloads unlike the implementation that originally established them. It runs
for a new architectural plane or authority boundary, persistent state,
external provider class, effectful or distributed execution model, large-data
path, Asset/Data or Compute/worker subsystem, Plan IR, a major checkpoint, or
an explicit concern that existing assumptions fail at scale. It is not
required for every small pull request.

High-impact acceptance uses a reviewer independent of the proposal's authorship
whose mandate is to disprove the architecture. The reviewer inspects actual
source and dependencies, runs actual tests, states assumptions, examines
negative space, and performs future-workload stress. No particular reviewer
product or model is required; evidence and independence are required.

### Strategic Review

A Strategic Review is a lightweight direction check, not an approval board. It
does not review ordinary pull requests or duplicate a Constitutional Board's
technical falsification. Trigger it roughly every five major milestones (not a
permanent milestone-number formula), at major mission expansion, when a major
checkpoint recommends it, when founder/architecture leadership raises a
strategic concern, or when material industry/research change may invalidate an
assumption.

It asks:

1. Are we still solving the correct problem?
2. If starting today, would we build the architecture the same way?
3. What assumption proved most wrong?
4. What assumption gained the strongest evidence?
5. What important assumption remains speculative?
6. Where is complexity accumulating?
7. What can be removed?
8. What are we refusing to build and why?
9. What technology or industry change should alter our thinking?
10. What architecture should remain deliberately unchanged?
11. Is the original VSS mission still recognizable?
12. Are we becoming model-driven rather than knowledge-driven?
13. Are we creating a God Object, Gateway, Registry, universal Context, or
    universal semantic framework?
14. Are operating and human cognitive costs growing faster than capability?
15. What should we research instead of build?
16. What should we stop doing?

Its concise outputs use only `KEEP`, `CHANGE`, `RESEARCH`, `REMOVE/RETIRE`, and
`DO_NOT_BUILD`, plus `BIGGEST_WRONG_ASSUMPTION` and `MISSION_ALIGNMENT`.
`MISSION_ALIGNMENT` is `ALIGNED`, `ALIGNED_WITH_DRIFT_RISK`, or
`REASSESS_BEFORE_MAJOR_EXPANSION`.

The review should be only as long as needed to support those outputs. It is not
a comprehensive re-acceptance of every ADR or a large recurring report.

Every Strategic Review answers: **If the original VSS mission were reviewed
against this milestone, would this still be recognizable as the intended
system?** The answer addresses governed creative intelligence, human intent,
explainability, accumulated knowledge, replaceable technology, autonomous movie
production as the current proving application, and simplicity/resource
efficiency. Possible cross-domain use does not expand scope automatically.

## Concept, domain, and framework admission

A new concept is not inherently undesirable. Growth is justified when it
represents an independent vocabulary, lifecycle, authority, provenance domain,
ownership boundary, workload boundary, or security boundary. Reviews challenge
concepts created only for naming, one feature, implementation convenience,
speculative reuse, or fashion.

A proposed first-class domain should normally demonstrate several of:
independent vocabulary, provenance, lifecycle, governance/policy, version
evolution, repeated value beyond one feature, and inability to fit cleanly in
an existing bounded domain. Failing this test requires explicit justification;
it does not impose an automatic prohibition. VSS creates no centralized Domain
Registry.

Frameworks are earned from repeated independent evidence. A first occurrence
is implemented locally; a second exposes possible duplication; a later
meaningful occurrence may document the pattern; further stable independent
evidence may justify a small shared utility; only repeated stable evidence
justifies a framework. This progression is a heuristic, not a numeric law.

A framework proposal answers: what repeated, across which independent domains,
which semantics are genuinely common, which remain domain-owned, what
complexity disappears, what coupling appears, and whether the framework can be
removed. Speculative generality is not a benefit.

The progression does not require duplicating security- or correctness-critical
logic merely to collect occurrences. A shared abstraction may be admitted
earlier when it is the smallest reliable way to enforce a proven invariant;
the proposal must still state its coupling, domain boundaries, and removal
path.

## Entropy, surfaces, and retirement

Major checkpoints and Strategic Reviews update the Entropy Ledger and consider
**Candidates for Removal**. `None` is valid. Candidates may include an obsolete
utility, duplicated registry, unnecessary adapter, unused non-historical
schema/version, redundant CI path, unnecessary dependency, or abandoned
experiment. Historical contracts and ADRs are not removed merely because they
are old; historical interpretation is a permanent requirement.

They also include **Things deliberately not built**, limited to relevant items.
Each records what was not built, why, and the evidence trigger for
reconsideration. This negative architecture prevents repeated speculative
debate without turning deferral into a permanent ban.

The authority surface remains explicit. Any new authority-bearing component
must state the exact authority, why existing Runtime or human authority is
insufficient, and the accepted ADR that admits it. Accidental authority
expansion is blocking. Legitimate authority boundaries are not collapsed to
improve a count.

The operational surface tracks persistent daemons, databases, queues, workers,
caches, schedulers, and external infrastructure. Growth is not automatically
wrong, but every persistent component retains ADR-0023 Component Admission
evidence and a removal/migration path.

Human cognitive cost is a real qualitative cost. Signals include difficult
onboarding, duplicated terminology, near-identical contracts, excessive
version cross-products or special-case dispatch, unmanageably long review
instructions, and repeated boundary misunderstandings. Reviews use `LOW`,
`WATCH`, or `HIGH`, never fake precision. `HIGH` normally requires
simplification before major expansion.

Architecture fitness considers correctness, reliability, security, quality,
runtime resources, operations, human attention, maintenance, migration, and
reversibility. Entropy is not runtime performance. A complex design may lower
lifetime cost; a simple one may be unsafe. Minimalism is a constraint, not an
ideology.

## Reversibility and Right to Pause

Prefer reversible decisions while evidence is weak. Permanent public contract
semantics, authoritative identity changes, durable data layouts, vendor lock-in,
major persistent infrastructure, and authority redistribution require stronger
evidence because migration or reversal is expensive. Ordinary implementation
is not labelled irreversible without evidence.

Any architecture reviewer or project owner may raise
`STRATEGIC_PAUSE_REQUESTED` for a reasonable concern about mission drift,
architectural contradiction, uncontrolled complexity, an irreversible design,
unsafe authority expansion, speculative framework creation, or a major untested
assumption. This is not an indefinite freeze. A bounded review resolves to
`CONTINUE`, `CONTINUE_WITH_GUARDRAIL`, `REMEDIATE_FIRST`, or
`STRATEGIC_REASSESSMENT`.

The requester must identify the concrete concern and affected scope. The pause
does not anonymously or indefinitely veto the project, and unrelated safe work
does not stop automatically. The legitimate project owner or assigned
architecture reviewer bounds the review and records one of the four outcomes.

## Proportional governance

Governance has operational and cognitive cost and must remain proportional.
Do not require Constitutional review for every pull request, Strategic Review
for every milestone, evidence documents without decision value, fake tests for
future systems, or duplicate reviews. A governance mechanism must justify its
maintenance cost and should be retired or simplified when it no longer changes
decisions.

Existing architecture fitness tests remain preferred where an invariant is
machine-enforceable: contract packages do not depend on CommandRunner,
semantic providers do not execute capabilities/workflows, exact version
resolution remains closed, and the baseline Semantic Plane requires no network
service. Add no speculative tests for absent Context/worker/service behavior.

### Proportionality examples

| Change | Normally applicable governance |
|---|---|
| Small bug fix | Ordinary code review and relevant tests |
| New Character Continuity fixture | Normal milestone scope and contract tests |
| New task contract version | Exact contract acceptance and compatibility evidence |
| New semantic domain | Domain-admission justification and applicable architecture review |
| New persistent database/service | Component Admission plus applicable architecture review |
| New Compute Plane worker | Constitutional review and Worker/Durable Execution architecture gate |
| Mission expansion into Film Learning | Strategic Review and Constitutional review as applicable |

These examples are defaults, not a way to bypass a material authority,
security, or contradiction concern.

## Future-workload stress matrix

Every Constitutional Board considers each applicable workload and records why
an invariant holds, fails, or is deferred.

| Workload stress | Assumption under attack |
|---|---|
| Bounded deterministic semantic request | Current reference case |
| Probabilistic AI request | Determinism, epistemic honesty, provider identity |
| GB/TB-scale asset workload | Bounded envelopes and control/data separation |
| GPU/CPU-intensive workload | Resource requirements versus authority |
| Hours/days-long operation | Expiry, revocation, cancellation, recovery |
| High fan-out parallel execution | Isolation, immutable binding, backpressure |
| Partial network/node failure | Partial effects, reconciliation, availability |
| Stale/revoked state during execution | Admission snapshot versus live validity |
| Cost/resource exhaustion | Dynamic admission and overrun policy |
| Disconnected/local cache | Exact identity/digest without global state |
| Malicious/untrusted file or plugin | Hard isolation and least authority |
| Mixed local/distributed deployment | Topology-independent meaning |

For every major invariant the Board asks what happens when payload size grows
by `10^6`, duration grows from milliseconds to hours, concurrency grows from 1
to 10,000, state changes in flight, physical location changes, a provider is
nondeterministic, an operation becomes effectful, or a machine is partially
disconnected.

## Negative-space review

Every Constitutional Board includes a section titled **What important
production property currently has no architectural owner?** It considers at
least artifact promotion, media delivery, production rollback, human-review
queues, model provenance, persistent revocation, asset deletion, storage
residency, worker isolation, durable state and recovery, and output admission.
`DEFERRED` is acceptable only with an owner-trigger or future decision gate.
Unrecognized ownership is not acceptable.

## Evidence classes

- **Machine-enforceable now:** dependency direction, registry immutability and
  exact resolution, bounded schemas, semantic Gateway isolation, and Context
  family/version behavior.
- **Machine-enforceable when the subsystem exists:** worker non-authorization,
  exact production snapshots, cache non-substitution, worker isolation,
  output admission, and durable retry/reconciliation.
- **Architecture-review-only:** shared governance without shared topology,
  workload rather than domain classification, avoiding premature distribution,
  and preventing universal God objects.

Reviews must not create fake tests for absent systems. The
[ADR evidence matrix](adr-evidence-matrix.md) records present evidence and the
gate at which deferred obligations become testable.

## Component Admission

Every proposal for a new persistent component or infrastructure service must
include the Component Admission evidence required by ADR-0023. The review
compares the measured need with an existing component, in-process library,
on-demand tool, and other simpler applicable alternatives. It accounts for
idle/peak resources, operations, availability, recovery, observability,
security, credentials, licensing/supply chain, data migration, local-first
impact, lock-in, removal, and the measured threshold at which the component is
worth its total platform tax.

Review depth is proportional to impact. A small library needs focused
dependency, licensing, security, maintenance, and removal evidence; a
persistent or distributed service requires the full operational review. A
hard security, reliability, isolation, or recovery requirement may justify a
more complex component and always overrides component-count minimalism.

Constitutional Boards additionally stress component count, idle resource cost,
startup/warm-up cost, network hops, storage copies, operational dependencies,
failure surfaces, migration/rollback, and operator or autonomous-agent
cognitive burden. They allow forecast evidence to begin migration planning
before a measured limit is actually breached.
