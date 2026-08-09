# ADR-0023: Minimal-Component, Open-Source, Resource-Efficient Implementation Strategy

## Status

Proposed

## Date

2026-08-08

## Context

VSS has deliberately separated logical responsibilities without prescribing
physical deployment. [ADR-0014](ADR-0014-local-first-scalability-performance-efficiency.md)
requires local-first, measured scale; [ADR-0021](ADR-0021-studio-workload-planes-specialized-execution.md)
defines four logical workload planes while rejecting premature services; and
[ADR-0022](ADR-0022-cross-plane-admission-resource-bounds-artifact-consistency.md)
defines bounded cross-plane control and exact artifact consistency without a
central byte proxy or global mutable synchronization.

A logically sound platform can still become expensive and fragile through
architecture-by-accumulation. Every daemon, database, broker, cache, scheduler,
AI server, storage layer, observability system, process, network hop, and data
copy consumes CPU, RAM, disk, bandwidth, configuration, credentials, patching,
monitoring, backup capacity, operator knowledge, and autonomous-agent
maintenance. Open-source software removes neither this operational tax nor its
security and failure surface.

VSS needs a physical implementation philosophy before Asset/Data and
Compute/Execution work begins. It must preserve quality and safety while
keeping the current semantic architecture simple and allowing evidence-driven
growth. This ADR selects no product, vendor, permanent technology stack,
infrastructure, schema, dependency, or implementation. It introduces no Plan
IR, external AI, Asset/Data implementation, Compute/Execution implementation,
worker, scheduler, database, broker, cache service, object store, render farm,
or orchestration system.

## Decision

VSS adopts four implementation principles:

> **Boring core, experimental edges.**

> **Use the smallest implementation that satisfies measured requirements.**

> **One process until measurement proves another process is worth its
> operational cost. One copy of data until locality, durability, or
> availability proves another copy is worth its storage/network cost. One
> network hop only when the work cannot economically or safely happen where
> the data already is.**

> **Optimize cost per quality-approved artifact, not isolated component
> benchmarks.**

Minimalism is subordinate to correctness, governance, security, reliability,
and required quality. It removes unjustified machinery, never required safety
controls.

## Open-source-first, not open-source maximalism

VSS prefers open standards and open-source implementations when they satisfy
quality, security, performance, maintenance, portability, and licensing
requirements. GitHub availability is not proof of acceptable licensing,
maintenance, security, or cost.

Open-source-first does not mean installing every useful open-source component.
A candidate is rejected when it duplicates an existing capability, imposes
excessive operational or resource cost, has weak maintenance or security,
creates practical lock-in through proprietary formats or APIs, or misses
quality requirements. A component is admitted only for a demonstrated need.

Closed or commercial technology is not permanently prohibited. If later
evidence shows that no practical open-source alternative satisfies a critical
requirement, adoption requires an explicit architecture, licensing, security,
portability, exit, and total-cost review. This ADR authorizes none.

## Component-minimization hierarchy

The default implementation preference is:

1. standard library;
2. an existing VSS component;
3. an in-process open-source library;
4. an on-demand subprocess or tool;
5. an embedded database or store;
6. a local background process;
7. a shared service;
8. a distributed service; and
9. a managed or cloud service.

Moving downward requires measured evidence that every simpler applicable level
is insufficient. A server database is not justified when an embedded store
meets the workload. A broker is not justified when a bounded local queue meets
it. Cluster orchestration is not justified to run one process.

## Modular monolith and process boundaries

The modular monolith is the default deployment. ADR-0021's planes are logical
ownership boundaries, not service boundaries. Current Control and Semantic
modules may coexist in one VSS process.

A split requires an independently evidenced scaling, hardware, isolation,
availability, security, ownership, lifecycle, data-locality, or deployment
need. GPU worker isolation, crash containment, long-running worker lifecycle,
external-provider isolation, and independently scaled heavy-data operations
may become valid reasons. Conceptual purity, different domain names, fashion,
or unevidenced future scale are not valid reasons.

## Python and native-code strategy

Python remains the default VSS control and semantic implementation language.
It is appropriate for contracts, validation orchestration, Runtime policy and
coordination, CLI, Knowledge, Context, semantic reasoning, AI and VFX tool
integration, and tests. This ADR authorizes no rewrite.

The rule is:

> Python for policy and coordination. Native code only for measured hot paths.

High-rate scheduling, hashing/chunking, cache indexing, high-throughput
networking, host agents, CPU-heavy transformation, and sandbox hosts may later
justify established native libraries or a bounded native component. Rust and
C++ are examples, not selections. A benchmark must identify the hot path,
quality/correctness constraints, expected benefit, interoperability cost, and
rollback before a rewrite is admitted.

## State and data implementation

### Embedded state first

Local files and embedded transactional state are preferred before server
databases. Conceptual local choices include files, an embedded transactional
store where transactions are required, append-only local audit, immutable
content-addressed assets, and on-demand embedded analytics. No database is
selected or mandated.

An embedded transactional candidate must offer low idle CPU/RAM, crash-safe
transactions, migrations, deterministic backup/export, adequate measured local
concurrency, inspection, and mature maintenance.

A server database is considered only when measurements demonstrate multi-host
concurrent writes, shared durable state, write concurrency beyond the embedded
design, operational availability requirements, remote access, or transaction
scale that the embedded solution cannot meet. No server database product is
preselected.

### Transactional state versus analytics

Operational transactional state and analytics are separate concerns. Prefer
on-demand or in-process analysis before an analytics service. Large scans must
not burden Runtime's transactional or authorization path. No analytics product
is selected.

### Asset storage

The first Asset Plane should prefer immutable content-addressed local storage:

```text
logical asset -> exact revision -> authoritative digest -> immutable blob
```

This supports integrity, deduplication opportunities, stable identity,
cacheability, migration, and workstation operation. It does not freeze a
filesystem layout or implement storage.

Distributed or object storage becomes eligible only when measured capacity,
multi-worker access, durability, remote execution, multi-host scale, archival,
or geographic distribution exceeds practical local storage. S3, MinIO, Ceph,
and other products are not selected.

### Interoperability

VSS prefers open interchange standards and abstraction boundaries over
proprietary representations. OpenUSD, OpenAssetIO, MaterialX, OpenColorIO,
OpenImageIO, and OpenTimelineIO are examples for future individual evaluation,
not a mandatory bundle. Prefer format or library integration over an
always-running service when it meets the requirement.

## Locality and data movement

Move compute toward data where practical before moving large data toward
compute. Placement may consider cached assets, storage proximity, bandwidth,
transfer cost, RAM/VRAM, GPU availability, and software compatibility.
Locality is execution metadata—never semantic identity, authorization, or
artifact eligibility.

Every large-data path should measure bytes read and written, network bytes,
duplicate bytes, cache hit rate, and transfer time. Avoid repeated copying,
unnecessary conversion, Runtime proxying, central staging, and eager transfer
of unused content. Use governed references and lazy resolution where
appropriate.

Prefer lazy asset resolution, tile/chunk access, bounded caches, demand-driven
decoding, and streaming over loading entire assets or materializing every
intermediate. These techniques must preserve equivalent required quality,
integrity, authorization, and reproducibility evidence.

The preferred locality hierarchy is same-process, same-machine, local-network,
then remote-network when security and workload semantics permit. Crossing a
boundary requires a measured resource, isolation, scale, durability, or
sharing reason; it is not a hard routing rule.

## Progressive fidelity and quality-adjusted cost

Expensive production work should use progressive fidelity:

```text
semantic validation
  -> cheap structural validation
  -> proxy or preview
  -> low-cost evaluation
  -> quality gate
  -> higher-cost candidate
  -> final-quality computation
```

Examples include preview before final render, low samples before full ray
tracing, selected frames before a complete sequence, and proxy before final
simulation. Quality thresholds remain domain- and policy-owned.

Cost optimization must not silently lower accepted final quality. The primary
future measure is resource or cost per quality-approved artifact, not cost per
invocation. Relevant evidence may include wall time, CPU/GPU seconds, peak
RAM/VRAM, bytes read/written/transferred, storage growth, AI tokens,
estimated/actual monetary cost, retries, rejections, and output acceptance. A
cheap component that repeatedly fails may cost more than a higher-quality one.

## Deterministic-first and AI escalation

Use deterministic algorithms when they meet defined quality. They are often
fast, inspectable, offline, reproducible, and inexpensive. AI addresses needs
that deterministic logic cannot satisfy; it does not replace adequate simple
logic merely because it is available.

Future escalation should conceptually proceed:

```text
deterministic rule
  -> if insufficient: small/local model
  -> if insufficient: larger local/shared model
  -> if insufficient: premium/external model
```

Each escalation retains typed semantic contracts, qualification, provenance,
classification, purpose, budget, and human approval where required. No model,
runtime, API, or provider is selected.

Local inference is considered before permanent remote use when quality,
hardware, latency, energy/cost, privacy, and classification support it. Shared
inference becomes eligible when concurrency evidence shows per-process model
copies or GPU underutilization cost more. A smaller model is preferred when it
meets the quality threshold; a larger model requires measurable quality gain.
Model admission later evaluates size, quantization, VRAM, CPU, latency,
throughput, quality, provenance, licensing, security, update cadence, and cost.

## Rendering and durable execution evolution

Rendering evolves only as evidence requires:

```text
single workstation
  -> on-demand local subprocess or isolated worker
  -> small bounded worker pool
  -> specialized render scheduler or farm
```

Do not build a render farm while workstation execution is adequate. No render
manager is selected.

Durable workflow infrastructure is admitted only after workloads demonstrate
long-lived state, crash recovery, durable timers/waits, process-spanning
retries, human approval pauses, resumability, or durable external effects.
Current semantic operations do not justify it. No orchestration engine is
selected.

There is no default message broker. A broker requires demonstrated durable
multi-host queues, decoupled independently scaling producers/consumers, event
fan-out, or throughput beyond simpler bounded mechanisms. Kafka, RabbitMQ,
Redis Streams, NATS, and alternatives are neither selected nor baseline.

Redis is not introduced merely for caching, locks, queues, or session state;
each use must prove an in-process, local, or embedded mechanism insufficient.
A search cluster is not introduced merely because metadata grows. Prefer
structured indexes, embedded queries, filesystem metadata, and domain-specific
lookup until dedicated search requirements are measured. Elasticsearch and
vector databases are not baseline.

Logical planes do not imply Kubernetes. Cluster orchestration requires actual
deployed services/workers whose operation cannot be met more simply. No
orchestrator is selected.

## Minimum observability

Observability matches deployment topology. Current local semantic work uses
bounded logs, structured governance audit, simple metrics, and performance
reports. Distributed Compute may later justify tracing, centralized logs, and
distributed metrics. Do not operate that stack before distributed diagnosis
requires it.

ADR-0021 remains authoritative: audit is not telemetry, telemetry is not
lineage, and lineage is not authorization. Shared correlation identifiers do
not justify a universal event system.

## Component Admission Review

Every new persistent software component or infrastructure service requires a
Component Admission section in its ADR or milestone review. It must answer:

1. What measured problem does it solve?
2. Why cannot an existing component solve it?
3. Why cannot an in-process library solve it?
4. Why cannot an on-demand subprocess solve it?
5. What are idle and peak CPU costs?
6. What are idle and peak RAM costs?
7. What disk cost does it create?
8. What network cost does it create?
9. What storage amplification does it create?
10. What maintenance and operator knowledge does it require?
11. What backup and recovery obligations does it create?
12. What security and CVE surface does it add?
13. What credentials and secrets does it introduce?
14. What are its failure and degraded-mode behaviors?
15. What upgrade, migration, compatibility, and rollback burden does it add?
16. How does it affect local-first operation?
17. What vendor, format, protocol, or data-layout lock-in does it create?
18. How is it removed or replaced?
19. At what measured threshold is it cheaper or safer than not having it?

An unanswered material question rejects admission. Review considers total
platform tax, not only feature benefit. A technically excellent component may
be rejected when its marginal platform complexity exceeds measurable value.

### Scale-trigger model

Triggers are evidence categories, not arbitrary numbers:

| Evolution | Evidence required |
|---|---|
| Embedded to server database | Multi-host/shared-state need, measured concurrency limit, durability/availability gap |
| Local to distributed/object assets | Capacity, sharing, durability, remote execution, or archive need |
| Local to shared inference | Concurrency, GPU utilization, duplicated model memory, throughput |
| Local worker to render farm | Queue depth, wall-time pressure, worker count/utilization, production deadline |
| Simple coordination to durable orchestration | Hours/days, crash-resume, durable timers, cross-attempt recovery |
| Local to distributed observability | Multi-host incidents and cross-service latency/failure attribution |

Measurements establish thresholds in a future workload profile or decision;
this ADR invents none.

## Measurement discipline

Measure before major optimization. Relevant operations eventually collect wall
time, CPU, RAM, GPU, VRAM, storage, I/O, network, concurrency, cost,
quality/acceptance, retries, and failures. Reject an optimization that reduces
one resource while materially increasing total system cost or risk without
justification. Avoid premature native rewrites and benchmark components in the
governed end-to-end path, not only in isolation.

Zero-idle-cost components are preferred: in-process libraries, embedded state,
and on-demand tools should approach zero resource use when idle. A daemon may
be justified by measured throughput, latency, cache warmth, model load cost,
multi-client sharing, or durability.

Storage efficiency minimizes duplicate immutable blobs, unnecessary
intermediates, unbounded caches, and duplicate model copies without destroying
required provenance, reproducibility, checkpoints, or governance evidence.
Retention remains domain/policy owned. Network efficiency favors locality,
references, resumable or chunked transfer, and worthwhile compression without
weakening integrity or authorization.

Do not optimize Python control work without evidence. Actual CPU hotspots
should prefer mature vectorized/native libraries over Python loops. GPU time is
high-cost: validate exact inputs before admission, avoid doomed jobs, use
compatible batching/model reuse/cache reuse, and apply progressive fidelity.
Do not keep a GPU service warm solely for convenience when workload evidence
does not justify idle cost.

## Reliability and security constraints

Minimal components must not compromise required durability, recovery,
availability, isolation, or security. A component is justified when it is the
smallest way to deliver a required safety property. Compare total risk and
cost, including the risk of omission.

Never weaken validation, authorization, revocation, digest verification,
worker isolation, output admission, provenance, or required audit for
throughput. Optimize redundant work, copies, processes, hops, and model use—not
correctness controls.

## Experimental technology track

Research technology remains optional, replaceable, reversible, benchmarked
against a stable baseline, behind stable interfaces, and locally testable where
possible. It is excluded from authority and authoritative identity semantics
until explicitly promoted. Candidate experiments include content-defined
chunking, SIMD/vectorized deduplication, high-speed hashing, WASM/WASI
isolation, inference engines, schedulers, compression, and media models. This
ADR adopts none.

Promotion requires correctness, security, claimed determinism, performance,
resource use, maintainability, portability, licensing, supply-chain evidence,
fallback, recovery, migration, and rollback. Experimental technology cannot
underpin Runtime authorization, authoritative audit, contract identity,
revocation, approval, or artifact eligibility before promotion.

### Content-defined chunking research

Asset Plane research may compare fixed-size chunks, FastCDC-style
content-defined chunking, and newer vector/SIMD approaches using original
synthetic, non-sensitive assets. Measure CPU, memory, deduplication ratio,
storage and network savings, update behavior, and recovery complexity. The
goal is reduced duplicate storage, backup volume, synchronization, and revision
transfer. No chunker or layout is selected.

### High-speed hashing research

SHA-256 remains authoritative for current governance identities unless a
future ADR changes it. Faster hashes may be evaluated only for
non-authoritative chunk lookup, cache indexing, or deduplication when measured
CPU benefit exceeds dual-hash storage and implementation risk. No digest domain
changes here.

### WebAssembly/WASI research

WASM/WASI may be evaluated for bounded metadata transforms, validators, and
lightweight deterministic or agent-generated extensions with explicit imports
and low startup overhead. It is not presumed suitable for Blender, render
engines, arbitrary DCC applications, or GPU-heavy work. Promotion requires a
security/isolation review; no sandbox is implemented.

## Stable core

Core components favor mature, inspectable, broadly supported, testable
technology with stable formats, low idle resources, and straightforward
backup/restore. Experimental dependencies remain outside authority,
authoritative identity, revocation, approval, and eligibility until promoted.
This is the practical meaning of boring core, experimental edges.

## Licensing, supply chain, and build-versus-adopt

Admission evaluates license compatibility, redistribution, commercial use,
model/data/plugin licensing, and patent concerns where applicable. Open source
does not waive these obligations.

Every dependency adds supply-chain and update cost. Prefer fewer dependencies;
new ones must justify functionality, provenance, maintenance, security,
pinning, SBOM/provenance impact, and removal. Existing VSS supply-chain controls
remain mandatory.

Do not build commodity infrastructure that mature open-source systems solve
well, and do not adopt heavyweight infrastructure when a small VSS-local
mechanism meets the need. Evidence avoids both NIH and infrastructure
maximalism.

## Conceptual deployment profiles

These profiles describe an evolution, not commitments or separate semantics:

- **Development Laptop:** one VSS process, local/embedded state, local
  filesystem/content-addressed storage, optional on-demand AI/render tool, no
  mandatory network infrastructure, and zero or near-zero idle services.
- **Production Workstation:** VSS, local transactional state, local asset
  cache/storage, optional GPU and on-demand AI/render tools, and optional local
  analytics.
- **Small Studio Cluster:** only when measured—shared state/assets where
  necessary, a bounded worker pool, and shared inference when more efficient.
- **Render Farm:** only when required—a specialized scheduler, worker fleet,
  shared/distributed Asset Plane, and operational telemetry.
- **Large Autonomous Studio:** only with demonstrated needs—durable
  orchestration, distributed observability, multi-site assets, specialized AI
  pools, and a large compute fleet.

Deployment changes topology, never Runtime authority, contract meaning,
identity, classification, purpose, or governance.

## Architecture-review integration

The existing [Architecture Review Governance](../architecture/architecture-review-governance.md)
applies. Every infrastructure proposal includes Component Admission evidence.
A Constitutional Board additionally attacks component count, idle CPU/RAM,
network hops, storage duplication, operational dependencies, credentials,
failure surfaces, and removal paths across the future-workload stress matrix.

Future evidence-matrix entries should distinguish architecture-review evidence
for open-source-first, Component Admission evidence for no unnecessary
service, machine evidence for local/no-daemon paths where implemented, and
test/review evidence that experiments remain non-authoritative. The matrix is
not changed while this ADR is Proposed and no implementation exists.

## Relationship to M5 and future planes

M5.2 and M5.3 remain unchanged: Python, deterministic-first, bounded, local,
non-effectful Semantic Plane work with no external service. ADR-0023 neither
delays nor redesigns Character Continuity.

Before Asset Plane implementation, a dedicated Asset Architecture ADR must
decide logical identity, catalog, resolver, storage, cache, revisions, and
lineage within this minimal-component constraint. Before effectful Compute
implementation, a Worker/Durable Execution ADR must decide protocol,
isolation, scheduler, durable state, retries, checkpoints, and output admission,
starting with the smallest measured design.

## Alternatives considered

1. **Enterprise infrastructure from day one.** Rejected: idle resource,
   operational, credential, backup, failure, and maintenance costs precede the
   need.
2. **Cloud/microservice-first.** Rejected: premature network, distribution,
   locality, availability, and cost complexity undermines local-first work.
3. **Open-source maximalism.** Rejected: open-source components still impose
   operational, licensing, security, and integration tax.
4. **Minimal-component, evidence-driven architecture. Selected.** It preserves
   quality and governance, starts locally, measures, and scales at named gates.
5. **Build everything ourselves.** Rejected: wastes engineering effort,
   duplicates mature infrastructure, and risks weak security/reliability.

## Consequences

Positive consequences include low idle CPU/RAM, low operational and network
cost, fewer failure modes and dependencies, simpler local backup/recovery,
smaller attack surface, faster iteration, autonomous-maintenance simplicity,
replaceability, and evidence-driven scale.

Costs include measurement discipline, possible later migrations, monitoring
scale triggers, eventual adapters, and replacing embedded/local components
when proven insufficient.

Risks include under-engineering, scaling too late, local bottlenecks,
experimental distraction, and local optimizations that increase total cost.
Mitigations are performance-laboratory evidence, the ADR evidence matrix,
Component Admission, scale triggers, checkpoint reviews, progressive fidelity,
stable interfaces, and tested rollback paths.

## Unresolved questions

- embedded state technology and server-database thresholds;
- content-addressed storage layout, compression, chunking, and object storage;
- OpenUSD and OpenAssetIO integration timing;
- AI runtime, inference serving, model lifecycle, and GPU scheduling;
- render scheduler, worker protocol, and durable orchestration;
- observability, tracing, and distributed caching;
- content-defined chunking, WASM isolation, and high-speed hashing;
- serverless execution and multi-site operation;
- archive, backup, residency, retention, and recovery strategy;
- production quality metrics and cost-per-quality-approved-artifact formula;
- energy/carbon measurement if it becomes a material policy requirement.

These questions require domain evidence and are not resolved by this ADR.

## Acceptance criteria

This decision is acceptable only when independent review confirms:

- open-source-first is explicit but non-dogmatic;
- the minimum-component hierarchy and modular-monolith default are clear;
- logical planes do not imply services;
- embedded/local implementation and zero-idle-cost components are preferred;
- persistent services and scale transitions require measured evidence;
- no database server, broker, Redis, search cluster, Kubernetes, render farm,
  orchestration engine, AI runtime, or other product is baseline;
- Python remains the default control/semantic language and native rewrites need
  benchmark evidence;
- data locality, minimized movement, lazy loading, and progressive fidelity are
  quality-preserving requirements;
- deterministic-first escalation and quality-adjusted cost are explicit;
- experimental technology is replaceable and non-authoritative until promoted;
- security, reliability, governance, and required quality cannot be traded
  away for efficiency;
- Component Admission and evidence-driven scale triggers govern growth;
- M5 remains unchanged; and
- no implementation, dependency, or vendor commitment is introduced.

## Independent implementation-cost stress review

The Proposed decision was reviewed against all required perspectives. No
blocking contradiction with ADR-0014, ADR-0021, or ADR-0022 was found:

- Enterprise and distributed-systems review found that the modular-monolith
  default preserves plane ownership without forcing deployment boundaries.
- HPC, rendering, VFX, storage, and performance review found that locality,
  bounded movement, progressive fidelity, and measured scale triggers preserve
  paths to specialized hardware without prematurely operating a farm.
- Database, analytics, and reliability review found that embedded-first is a
  preference rather than a denial of future durability, availability, shared
  state, or recovery requirements.
- AI inference and FinOps review found that deterministic-first escalation and
  cost per quality-approved artifact avoid both largest-model-by-default and
  quality-eroding cost optimization.
- Security and supply-chain review found that isolation, validation,
  authorization, revocation, digest verification, output admission, licensing,
  provenance, and dependency controls cannot be removed as “overhead.”
- Open-source, local-first, and autonomous-maintainability review found that
  open-source-first remains conditional on fitness and operational tax, while
  every profile retains a complete local logical path.
- Experimental-systems review found that chunking, alternate hashes, WASM/WASI,
  and research runtimes remain optional, reversible, and excluded from
  authority and authoritative identity.

Component-count stress considered zero, one, and many persistent components;
idle and peak resources; credential and backup multiplication; partial
failure; network and storage amplification; and removal. Future workload stress
covered GB/TB assets, GPU saturation, long duration, fan-out, disconnection,
revocation in flight, and mixed local/distributed deployment. The resulting
rule remains evidence-based: introduce the next component only when its total
risk-adjusted cost is lower than the measured simpler alternative.

## Independent review requirements

Review must include Enterprise Architecture, HPC, VFX pipeline and rendering,
Asset/Storage, AI inference, Distributed Systems, Database Architecture,
Performance, FinOps, Reliability/SRE, Product Security, Supply Chain,
Open-Source Governance, Local-First Engineering, Experimental Systems,
Autonomous-Agent Maintainability, and Independent Verification perspectives.

The review must attack assumptions that every plane needs a service, shared
state needs a server database, queues need brokers, caches need Redis, search
needs a cluster/vector database, deployments need Kubernetes, long operations
immediately need durable orchestration, AI needs the largest model, renders
need final quality first, asset revisions need complete duplicate copies,
optimization needs a native rewrite, or open source automatically means low
cost.
