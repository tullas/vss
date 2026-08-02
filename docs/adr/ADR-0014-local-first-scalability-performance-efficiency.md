# ADR-0014: Local-First Scalability, Performance, and Resource Efficiency

## Status

Accepted

## Date

2026-08-01

## Context

VSS has established a capability-oriented Runtime, sequential workflows, an
internal Capability SDK, provider-neutral services, migrated legacy commands,
and semantic reasoning contracts. The platform now needs an explicit position
on how those contracts behave under concurrency, long-running workloads,
resource pressure, and eventual production scale without turning ordinary
development into a cloud-dependent activity.

Scalability is not permission to bypass the Runtime. Policy, authorization,
approval, contracts, budgets, and audit apply at every deployment size. Nor is
scalability a reason to introduce a distributed system before measurements
justify its operational cost.

This decision is governed by:

- [ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md), which makes the
  Runtime the execution authority;
- [ADR-0011](ADR-0011-engineering-principles.md), especially Runtime First,
  Local First, provider neutrality, security by construction, auditability,
  measurable quality, and simplicity;
- [ADR-0012](ADR-0012-evolvable-reasoning-architecture.md), which separates
  replaceable reasoning from Runtime authority and requires deterministic
  non-reasoning recovery; and
- [ADR-0013](ADR-0013-semantic-reasoning-contracts.md), which keeps semantic
  contracts provider neutral and independently replaceable under the Rule of
  Five.

The [M2 architecture checkpoint](../reviews/m2-architecture-checkpoint.md)
found that cooperative thread cancellation is insufficient for effectful or
sensitive work and that local JSON Lines audit lacks production retention,
rotation, size limits, durable flush, and tamper resistance. This ADR preserves
those findings as production gates rather than treating scale as a workaround.

## Decision

VSS adopts a **local-first, profile-driven, scale-ready architecture**. The
guiding principle is:

> Scale-ready, not prematurely distributed.

Every VSS workflow and platform control path must be executable on one
supported developer workstation using local implementations, reduced-quality
workloads, deterministic substitutes, simulation, or bounded fixtures. Larger
infrastructure may reduce elapsed time, increase throughput or quality, support
larger models, increase concurrency, or improve durability and availability.
It must not be required for architectural correctness, ordinary feature
development, standard CI, contract and policy validation, security and
workflow testing, reasoning-governance and Knowledge Package testing, approval
and recovery testing, or demonstration of the complete logical platform.

The same semantic, capability, workflow, policy, approval, and audit contracts
apply across deployment profiles. No profile may weaken correctness, security,
or governance.

### Complete local platform

“Complete autonomous platform on a laptop” means that a workstation can
exercise the complete logical path, including project configuration, bounded
knowledge preparation, deterministic or local semantic reasoning, option
generation, future planning and approval paths, capability and workflow
execution, asset tracking, draft media generation, quality and continuity
checks, draft assembly, audit and evidence, and pause, resume, failure
classification, and recovery.

The local profile may reduce resolution, frame rate, clip duration, model size,
sample rate, render complexity, asset count, concurrency, inference quality,
and speed. It may substitute deterministic fixtures or simulations for costly
or unavailable providers. It must retain validation, authorization, policy,
approval, budgets, audit, failure handling, workflow semantics, and
provider-neutral boundaries.

> Reduced quality or throughput is acceptable in development. Reduced
> correctness, security, or governance is not.

A laptop can eventually produce a complete movie through bounded sequential
work, checkpoints, reduced-quality local providers, and extended elapsed time.
This is a logical completeness requirement, not a claim that a typical laptop
can produce feature-length cinema-quality media at production speed.

### Contract constraints

Public contracts must not assume one operating-system process, one host, one
worker, shared memory, local filesystem identity, exactly-once transport,
unlimited resources, immediate execution, permanent connectivity, cloud
availability, or a particular queue, scheduler, database, container platform,
GPU, observability system, or cloud vendor. A simple one-process implementation
remains valid where it satisfies the contract.

### Evolutionary deployment profiles

Deployment profiles are versioned configuration and evidence identities, not
different business contracts.

1. **Developer workstation.** Local Runtime and control components,
   deterministic providers and fixtures, local development state,
   reduced-duration and reduced-resolution media, and hardware-aware bounded
   concurrency. It requires no cloud account, external AI key, or GPU and runs
   standard functional, security, concurrency, and regression validation.
2. **Workstation scale-up.** Multiple isolated local workers, optional local
   GPU and larger local models, higher-quality media, bounded worker pools, and
   resumable long-running jobs. A local queue or scheduler abstraction may be
   introduced only when measurements justify it.
3. **Temporary scale validation.** Approved Infrastructure as Code creates
   short-lived infrastructure tied to one commit and workload profile, with an
   explicit budget ceiling, automatic expiry and teardown, and retained
   performance, resource, and cost evidence.
4. **Production scale-out.** Horizontally scalable control services where
   justified, isolated workers, durable execution state, durable audit and
   evidence, workload partitioning, quotas, admission control, recovery,
   production observability, and infrastructure/provider neutrality.
5. **Distributed or regional deployment.** Adopted only for measured needs and
   governed by future ADRs defining state ownership, partitioning, consistency,
   residency, regional failure, and disaster recovery.

This ADR selects no Kubernetes distribution, service mesh, cloud, queue,
scheduler, database, or object store.

### Logical control plane and execution plane

The control plane is a logical responsibility boundary, not a second execution
authority. Its responsibilities may include request admission, contract
validation, Runtime policy and authorization, budgets and quotas, execution
identity, scheduling decisions, lifecycle state, approval coordination,
permitted provider and worker selection, audit coordination, cancellation
requests, and workload status. It should remain lightweight and stateless where
practical, but durable coordination must not be falsely described as stateless.

The execution plane may perform capability execution, provider invocation,
knowledge retrieval, media processing, rendering, transcoding, model inference,
infrastructure operations, and isolated cleanup. It may not independently make
policy, authorization, approval, or provider-selection decisions.

A worker receives only a validated execution identity, bounded input, exact
operation identity and version, authorized resource scope, budget, deadline,
cancellation context, and narrowly approved credentials where later required.
It receives no ambient platform authority. Runtime remains the sole authority
for execution admission and authorization; distribution changes placement, not
authority.

### Bounded production work

Long-running media production must be decomposed rather than submitted as one
indivisible request:

```text
movie
└── acts
    └── sequences
        └── scenes
            └── shots
                └── takes or variants
                    └── frames and media assets
```

Future long-running production requires checkpoints, resumable work, stable
asset identity and version, deterministic manifests, partial completion,
dependency tracking, classified safe retries, cancellation, quality gates,
approval gates, and incremental assembly. This ADR defines neither the final
movie schema nor movie capabilities.

### Workload classes

One timeout and one worker pool are insufficient. Deployment profiles must
classify work and protect critical capacity:

| Class | Examples | Required characteristics |
| --- | --- | --- |
| Interactive | System inspection, configuration validation, semantic option generation, small metadata operations | Low latency, small bounded payloads, short deadlines, responsiveness |
| Operational | Infrastructure validation, repository analysis, approval preparation, deployment checks | Seconds to minutes, moderate resources, security sensitivity, bounded retries |
| Batch | Knowledge indexing, bulk asset validation, media conversion, evaluation corpora | Delay tolerant, throughput oriented, resumable, checkpointable |
| Long running | High-quality rendering, video generation, large media processing, model preparation | Minutes to hours, isolated workers, checkpoints, explicit cancellation, durable production state |
| Critical control | Emergency disable, approval, cancellation, security response, teardown | Prioritized, low latency, isolated from overloaded reasoning/media work, deterministic non-AI path |

Workload-specific pools may be introduced later. This ADR selects no scheduler.

### Concurrency, admission, and overload

Concurrency must be bounded at the scopes appropriate to the workload: global
platform, environment, project, user or tenant, workflow, capability, provider,
worker class, external service, CPU, memory, GPU, storage, network, and cost.
Numeric limits belong to versioned deployment and workload profiles.

On overload, VSS must explicitly reject or boundedly queue work with a named
admission result, apply backpressure, reserve critical-control capacity, avoid
starvation, isolate projects and workloads, and fail closed when governance
controls are unavailable. It must never accept unbounded work or silently
discard admitted work.

Future queues must be bounded, observable, partitionable by workload class,
capable of priority without starvation, compatible with cancellation,
deadlines, expiration, duplicate delivery, and recovery, and independent of
provider-native formats. Queue admission is not authorization. Cancelled,
expired, unauthorized, or incompatible work must not execute merely because it
remains queued.

### Execution identity and delivery semantics

VSS does not assume exactly-once delivery. Future effectful execution requires
a globally unique execution identity, operation identity and version,
idempotency key, attempt identity, lease or ownership identity, deadline,
cancellation state, checkpoint identity, outcome classification, duplicate
detection, and safe completion evidence.

At-least-once delivery is possible after distribution. Before production use,
each effectful capability must define idempotency, reconciliation, or explicit
non-retryable semantics. Failure classes include validation, authorization,
permanent input, transient provider, capacity, timeout, cancellation, unknown
outcome, partial effect, retryable, non-retryable, and reconciliation required.

Retries are policy controlled. An operation must not be automatically retried
when it could duplicate a purchase or publication, create infrastructure twice,
rotate credentials twice, overwrite an asset, produce inconsistent external
state, or create uncontrolled provider cost. A retry retains the original
operation identity, authorization, and budget or obtains a new explicit
decision. Unknown and partially effected outcomes require reconciliation, not
optimistic replay.

### Local performance laboratory

A laptop-compatible performance laboratory must exercise real VSS governance
paths with deterministic substitutes for expensive or unavailable services.
Future profiles may include `laptop-small`, `laptop-standard`, `laptop-large`,
`workstation`, and `CI-safe`. They may declare concurrency, request count,
duration, queue depth, worker count, CPU, memory and optional GPU budgets, fake
provider latency and failure rate, output bounds, audit volume, and test-asset
size. No profile may weaken validation or security.

Deterministic fakes are the default. Standard performance validation requires
no live provider or paid service and must be able to simulate success, delay,
CPU work, memory pressure, throttling, transient and permanent failures, worker
crash, timeout, cancellation, duplicate delivery, dependency loss, saturation,
overload rejection, and audit backpressure.

Performance validation categories are:

- **Functional smoke:** complete logical platform with minimal work.
- **Concurrency:** correctness under simultaneous independent requests.
- **Load:** expected throughput and latency under a declared profile.
- **Stress:** controlled saturation and safe overload behavior.
- **Endurance:** leaks, unbounded audit or queue growth, descriptor leakage,
  orphaned work, and resource degradation.
- **Fault:** worker, provider, storage, audit, timeout, and cancellation faults.
- **Recovery:** restart, resume, reconciliation, and duplicate suppression.
- **Cost simulation:** deterministic usage and price fixtures without spending.
- **Temporary production-scale test:** short-lived infrastructure only where
  physical scale, GPU, network, storage, or autoscaling cannot be represented
  adequately locally.

### Measurement and regression model

No unsupported production SLO is established here. Every benchmark declares
its workload and deployment profiles, commit SHA, hardware and operating
environment, duration, concurrency, request count, input/output sizes, warm or
cold state, provider type, success criteria, and measurement method.

Metrics include, where applicable, admission and queue latency, execution and
end-to-end latency, throughput, success/failure and timeout rates, cancellation
latency, overload rejection, retries, duplicate suppression, CPU, memory, GPU,
disk and network use, audit latency, provider calls, knowledge latency, workflow
step duration, cost or simulated cost per validated result, and future cache
hit rate. Latency reporting uses percentiles where meaningful, not averages
alone.

Performance gates have two forms:

- **Absolute safety requirements:** no authorization bypass; no admitted work
  lost without a terminal record; no unreconciled duplicate effect; bounded
  queues, data, and memory growth; controlled overload; no secret leakage; no
  orphan after confirmed cancellation; and a responsive critical-control path.
- **Relative regression requirements:** compare an approved baseline and
  candidate under the same profile for latency, throughput, memory and CPU per
  request, audit overhead, queue behavior, and startup/discovery overhead.

Thresholds belong to versioned performance policies and profiles, not one
universal percentage in this ADR. Measurement precedes optimization.

### Efficiency and cost governance

Efficiency means useful, validated work per unit of elapsed time, CPU, memory,
GPU, storage, network, measurable energy, provider usage, and monetary cost.
Future implementations support provider ceilings; project and workflow
budgets; semantically safe batching and deduplication; caching only under
explicit correctness, freshness, and confidentiality rules; task-appropriate
provider tiers; idle shutdown; storage lifecycle; sampled shadow execution;
reduced-quality development media; checkpoint reuse; and avoidance of needless
recomputation.

Cost reduction must not weaken authorization, privacy, evidence, validation,
approval, security, or recovery.

Cloud-cost policy is mandatory:

- No permanent cloud development environment by default.
- Standard development and CI require neither paid infrastructure nor external
  AI credentials.
- Deterministic local simulation precedes paid validation.
- Temporary infrastructure uses approved VSS and Infrastructure-as-Code paths.
- Every paid test declares a budget ceiling, commit, and workload profile.
- Every temporary environment has automatic expiry and teardown; teardown
  failure is surfaced and remediated.
- Tests retain a cost and resource report without credentials.
- No test may silently exceed its approved budget.

### Provider and quality profiles

Provider-neutral execution profiles may include `mock`, `local-small`,
`local-cpu`, `local-gpu`, `workstation`, `remote-temporary`, and `production`.
Conceptual media-quality profiles may include `contract-only`, `thumbnail`,
`draft`, `preview`, `review`, and `final`.

Workflows request semantic quality and resource requirements, not a vendor or
hardware implementation. Providers declare whether they can satisfy them.
Unsupported requirements fail safely or require an explicit authorized
downgrade; quality downgrades are never silent.

Business workflows are not rewritten when moving among laptop, workstation,
on-premises server, temporary cloud, private cluster, or future production.
Profiles may change provider selection, worker capacity, concurrency,
resolution, model size, storage, queue implementation, durability, and
availability. They may not change semantic meaning, capability identity,
authorization, approvals, audit meaning, workflow intent, asset identity, or
contract versions without explicit migration.

### Security and isolation

Scale must not expand authority. Designs must address noisy-neighbor denial of
service, queue flooding, budget exhaustion, worker impersonation, duplicates,
stale authorization, lease theft, cancellation races, checkpoint poisoning,
result substitution, provider throttling, audit overload, metric-based secret
exposure, cross-project leakage, unsafe caching, uncontrolled fan-out, runaway
workers, and GPU or memory exhaustion.

Controls include bounded admission and fan-out, authenticated execution and
lease identities, current authorization checks, integrity-bound checkpoints
and results, scoped credentials, project isolation, safe telemetry, resource
ceilings, reconciliation, and protected critical-control capacity. Future
process or worker isolation is required before effectful, sensitive,
long-running, or untrusted workloads. Existing cooperative thread timeout does
not satisfy that requirement.

### Audit and observability

Local JSON Lines audit is a development facility, not the final production
audit system. Local performance tests exercise audit volume, latency,
backpressure, and failure behavior. Production scale-out requires a separately
approved design for retention, rotation, durability, integrity, ordering,
partitioning, correlation, queryability, backpressure, and sensitive-data
controls.

Metrics, logs, and benchmark evidence must not contain secrets, provider
credentials, raw prompts, sensitive Knowledge Package content, hidden
reasoning, unrestricted source data, or personal data without approved
governance. No production scalability claim may rely on local JSONL as its
final audit guarantee.

### Portability

The architecture requires no specific cloud, Kubernetes, queue, database,
object store, GPU vendor, AI provider, media generator, or observability vendor.
Future adapters and deployment profiles may support them while Runtime and
semantic contracts remain neutral.

## Alternatives Considered

### 1. Cloud-first permanent development platform

This can expose production-like capacity early, but creates recurring cost,
credential and connectivity dependencies, onboarding friction, and vendor
pressure before requirements are measured. Rejected.

### 2. Laptop-only platform with no production scale-out path

This minimizes initial operations but embeds assumptions that fail under
durability, availability, and throughput needs. Rejected.

### 3. Premature microservices and distributed architecture

This adds partial failure, coordination, deployment, observability, and data
consistency costs before demonstrated need. Rejected.

### 4. Separate laptop and production workflows

This produces semantic drift and allows local validation to cease proving the
production path. Rejected.

### 5. Unlimited concurrency with provider-side throttling

This delegates admission and cost control, cannot protect local resources or
critical work, and encourages unbounded queues. Rejected.

### 6. Local-first, profile-driven, scale-ready architecture with temporary paid validation

Selected. It balances affordability, developer productivity, portability,
architectural correctness, production evolution, operational simplicity, and
vendor neutrality while deferring distributed machinery until evidence
justifies it.

## Consequences

Positive consequences include complete local logical validation, low routine
development cost, reproducible profiles, cloud independence, easier onboarding,
safe concurrency evolution, measured capacity decisions, consistent workflows,
temporary rather than permanent scale infrastructure, on-premises portability,
and production scaling without semantic-contract rewrites.

Costs and risks include inability of local tests to prove final multi-node
capacity, gaps between deterministic fakes and real providers, profile and
baseline maintenance, benchmark variability, eventual distributed-state,
queue, worker, durable audit and state complexity, long elapsed time and lower
media quality locally, and over-abstraction risk.

Mitigations are narrow versioned profiles, deterministic fixtures, measurement
before optimization, budgeted temporary scale tests, explicit unresolved
questions, no infrastructure selection here, periodic architecture and
performance checkpoints, and preservation of simple local execution until
evidence warrants expansion.

## Roadmap Impact

The conceptual sequence is:

1. ADR-0014 Local-First Scalability, Performance, and Resource Efficiency.
2. ADR-0015 Knowledge Architecture.
3. ADR-0016 Autonomy and Approval Policy.
4. M3.1 Semantic Contract Registry and first schemas.
5. M3.2 Deterministic `GenerateOptions` implementation.
6. M3.3 Local concurrency and performance baseline.
7. M3.4 Knowledge Packages.
8. M3.5 Plan IR.
9. M3.6 First external reasoning provider.
10. Later: workload workers, production audit, isolation, and temporary scale
    validation.

This ADR implements none of these items.

## Unresolved Questions

The following require evidence or separate decisions:

- supported developer-workstation minimum and laptop-profile calibration;
- concurrency defaults;
- queue and durable execution-state technologies;
- process and worker isolation;
- production audit backend;
- object and media asset storage and lifecycle;
- distributed consistency model;
- lease duration and renewal;
- idempotency details and checkpoint format;
- cancellation acknowledgement and worker protocol;
- scheduling, fairness, and priority policy;
- autoscaling signals;
- GPU abstraction and hardware-acceleration portability;
- cache eligibility and invalidation;
- benchmark baseline storage and regression thresholds;
- energy measurement;
- temporary-cloud provider selection;
- production availability and disaster-recovery objectives;
- final-media production profile; and
- acceptable laptop elapsed time for a complete draft movie.

## Acceptance Criteria

This ADR is acceptable when it establishes that:

- the complete logical platform is testable on one workstation;
- a complete autonomous movie workflow can run locally using reduced quality,
  deterministic substitutes, or extended elapsed time;
- local mode never reduces correctness or governance;
- standard development and CI require no paid infrastructure;
- production-scale tests are temporary and budget capped;
- public contracts assume neither one process nor one machine;
- concurrency is bounded and overload is explicit and safe;
- workload classes are distinct and critical-control capacity is protected;
- delivery is not assumed exactly once;
- retries require idempotency, reconciliation, or explicit non-retryability;
- declared profiles govern performance measurement;
- efficiency and cost are first-class metrics;
- laptop and production retain the same semantic and workflow contracts;
- no cloud, scheduler, queue, database, GPU, or observability vendor is selected;
- existing audit and cancellation limitations are acknowledged; and
- no implementation or dependency accompanies this decision.

## Independent Review Perspectives

The draft was assessed against the requested perspectives with these outcomes:

| Perspective | Conclusion |
| --- | --- |
| Enterprise Software Architecture | Profiles change deployment qualities without fragmenting public contracts. |
| Distributed Systems | Exactly-once is rejected; identity, attempts, reconciliation, leases, and bounded queues precede scale-out. |
| Runtime Architecture | Runtime remains the single authority; placement and scheduling do not confer authorization. |
| Performance Engineering | Declared profiles, percentiles, safety gates, and comparable baselines precede optimization. |
| Capacity Planning | Workload classes and resource scopes permit evidence-based limits without inventing numbers. |
| Developer Experience | A complete governed logical path remains available without cloud, credentials, or GPU. |
| Local-First and Offline Operation | Deterministic substitutes preserve offline correctness and recovery paths. |
| Product Security | Scale does not expand authority; isolation, cancellation, audit, and resource controls remain production gates. |
| FinOps and Cost Governance | Paid validation is optional, capped, attributable, expiring, and reported. |
| Media Pipeline Engineering | Work is decomposed and resumable; local quality and speed may fall while semantics remain. |
| Reliability and Recovery | Critical controls are protected; retries distinguish unknown and partial effects. |
| Provider Neutrality | No infrastructure, hardware, media, reasoning, queue, or telemetry vendor enters Runtime contracts. |
| Independent Verification | No contradiction with ADR-0010 through ADR-0013 was identified; unresolved implementation choices remain explicit. |

No review perspective justifies selecting an implementation technology in this
decision.

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [ADR-0012: Evolvable and Reversible Reasoning Architecture](ADR-0012-evolvable-reasoning-architecture.md)
- [ADR-0013: Semantic Reasoning Contracts](ADR-0013-semantic-reasoning-contracts.md)
- [M2 Architecture Checkpoint](../reviews/m2-architecture-checkpoint.md)
- [Bootstrap](../bootstrap.md)
- [New Workstation Runbook](../runbooks/new-workstation.md)
- [Infrastructure](../infrastructure.md)

## Verification

Acceptance requires ADR validation, repository-relative reference validation,
documentation-only scope verification, whitespace validation, and existing
Markdown validation when available. This decision adds no implementation,
schema, workflow, provider, dependency, queue, database, worker, or
infrastructure resource.
