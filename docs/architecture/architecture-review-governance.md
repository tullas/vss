# Architecture Review Governance

## Purpose

VSS uses evidence-led architecture review to distinguish current guarantees
from deferred architecture. Acceptance of an ADR records a decision; it does
not assert that every future subsystem described by that decision exists.

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
