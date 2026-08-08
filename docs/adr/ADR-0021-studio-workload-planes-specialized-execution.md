# ADR-0021: Studio Workload Planes and Specialized Execution Architecture

## Status

Proposed

## Date

2026-08-08

## Context

VSS now has a governed semantic path from story material through Scene
Breakdown, Scene Production Options, and validation-only Character Continuity
contracts. That architecture deliberately uses small typed artifacts, bounded
Context Objects, the Reasoning Gateway, non-authorizing semantic providers,
and deterministic local validation.

Future studio workloads have materially different shapes. USD composition,
textures, geometry, audio, video, simulation caches, rendered frames, and
generated media may be gigabytes in size. Rendering, simulation, compositing,
transcoding, animation processing, and model execution may run for hours or
days, consume specialized hardware, create effects, require cancellation and
recovery, and produce large artifacts. Treating these as ordinary semantic
reasoning would overload Runtime, Context, registries, and Reasoning Gateway
with responsibilities they were not designed to own.

The permanent architectural principle is:

> **Shared governance does not imply shared execution topology.**

VSS needs common authorization, policy, identity, lifecycle, and governance
obligations while allowing operations to use workload-specialized paths. The
boundaries in this ADR are logical. They do not require microservices,
Kubernetes, cloud deployment, separate machines, separate repositories, or
distributed operation. The complete logical platform must remain runnable on
one workstation in accordance with
[ADR-0014](ADR-0014-local-first-scalability-performance-efficiency.md).

This ADR defines boundaries only. It implements no infrastructure, contract,
schema, queue, worker, catalog, resolver, provider, Plan IR, or execution path,
and selects no vendor or product.

## Decision

VSS adopts four logical workload planes:

1. **Governance / Control Plane** — admission, authorization, policy, lifecycle,
   budgets, cancellation, and governance evidence.
2. **Semantic / Reasoning Plane** — bounded knowledge, Context, semantic
   reasoning, and inert semantic results.
3. **Asset / Data Plane** — logical asset instances, versions, lineage,
   resolution, storage, caches, and heavy artifact bytes.
4. **Compute / Execution Plane** — authorized effectful or resource-heavy work
   performed by specialized workers.

Deployment may co-locate every plane in one process or workstation. Future
evidence may justify separate processes, hosts, pools, or services. Placement
never changes authority or contract meaning.

```text
                    GOVERNANCE / CONTROL PLANE
              Runtime: sole authorization and execution admission
                 policy | authorization | budgets | cancellation
                              | governed references
                              v
       +----------------------+------------------------+
       |                      |                        |
       v                      v                        v
 SEMANTIC / REASONING     ASSET / DATA          COMPUTE / EXECUTION
 Knowledge                Asset Catalog          Specialized workers
 Context                  Asset Resolver         Render / simulate
 Reasoning Gateway        USD / geometry         Composite / transcode
 Semantic providers       texture / audio        Generate / process media
 Movie / continuity       storage / cache        Long-running models
       |                      ^                        |
       +-- inert results -----+---- references -------+

 Governance reports and audit describe decisions.
 Telemetry describes operations. Lineage describes artifact history.
 A future planning/orchestration layer is reserved but not implemented.
```

The diagram expresses responsibility, not mandatory process or network
boundaries. A domain can contain operations in several planes. VSS classifies
operations and workloads, not whole domains.

## Plane 1 — Governance / Control Plane

The Governance / Control Plane owns:

- Runtime request and work admission;
- authorization and policy evaluation;
- approval gates where a future operation requires them;
- autonomy constraints, budgets, quotas, and kill switches;
- exact contract, registry, compatibility, and lifecycle resolution;
- resource-policy decisions and bounded work admission;
- cancellation or suspension decisions;
- governance audit and safe decision evidence; and
- issuance of narrowly authorized future work specifications.

Runtime remains the sole authorization and execution-admission authority. It
may authorize, reject, narrow, suspend, or cancel work. A scheduler, queue,
resolver, provider, catalog, or worker cannot grant authority. Registration,
resource availability, cache presence, a content digest, or possession of a
work message cannot substitute for current Runtime admission.

The Control Plane must not render frames, simulate, transcode, process large
assets, carry textures/models/video, become an asset database, perform
domain-specific semantic interpretation, or act as a general worker. It
coordinates bounded control messages and references. Runtime should not proxy
heavy payloads unless a later narrow requirement explicitly demonstrates that
need and preserves boundedness and isolation.

Centralized authority is conceptual, not a demand for serialized
implementation. Immutable policy/registry snapshots, bounded references, and
partitionable admission mechanisms may support scale without distributing
authorization authority.

## Plane 2 — Semantic / Reasoning Plane

The Semantic / Reasoning Plane is the architecture already proven by M3–M5.1:

- Knowledge and governed source claims;
- task-specific bounded Context Objects;
- the existing Reasoning Gateway;
- semantic strategy and provider admission;
- bounded inert semantic results;
- Scene Breakdown and Scene Production Options;
- Character Continuity M5.2/M5.3;
- future bounded music reasoning and shot semantics.

Semantic operations ordinarily use small, bounded, typed input and output;
provider-neutral public contracts; explicit uncertainty and provenance; and
non-authorizing providers. Semantic results are observations, analyses,
alternatives, or proposals. They are not authority or effects.

The Reasoning Gateway is permanently semantic-only. It owns generic reasoning
mechanics such as request/Context validation, exact compatibility,
expiry/revocation, minimal provider-view extraction, invocation binding,
semantic provider admission, independent result validation, semantic honesty,
and reasoning audit. It does not understand domain-specific execution topology.

Rendering, simulation, compositing, transcoding, asset ingest, large media
movement, and other compute-heavy work do not pass through Reasoning Gateway.
Not every future domain operation must use it. This prevents a God Gateway and
preserves its bounded, provider-neutral semantics.

M5.2 and M5.3 remain unchanged Semantic Plane work: bounded, local,
non-effectful Character Continuity using Context and the existing Reasoning
Gateway. ADR-0021 does not require their redesign.

## Plane 3 — Asset / Data Plane

The Asset / Data Plane conceptually owns:

- logical asset identity, immutable revision identity, and content digests;
- asset instance/version cataloging;
- logical-to-physical resolution;
- artifact lineage and transformation associations;
- storage references, caches, and retention data;
- USD layers/packages and references;
- geometry, textures, shaders, models, audio, video, frames, intermediate media,
  simulation caches, and generated artifacts.

No Asset Catalog or Resolver is implemented by this ADR.

### Contract Registry versus Asset Catalog

Contract Registries describe **kinds** of artifact. An Asset Catalog describes
**instances** of those kinds.

| Contract Registry | Asset Catalog |
| --- | --- |
| `asset_reference/1`, `render_request/1`, `render_result/1` kinds | a character model revision, palace asset revision, texture set, or output frame |
| repository/domain-owned contract definitions | potentially numerous project artifact instances |
| bounded growth with contract evolution | growth with produced/imported assets |
| structural compatibility, not instance truth | instance identity, versions, locations, and lineage |
| non-authorizing | non-authorizing |

Registries must never grow linearly with every asset instance. The Asset
Catalog must not become a Contract Registry, Runtime, provider registry,
workflow registry, universal Movie Object, Asset God Object, or Studio God
Registry. Both remain federated under
[ADR-0018](ADR-0018-federated-contract-registry-governance.md).

### Logical identity versus physical location

Logical asset identity is not physical storage location. Semantic and control
artifacts should normally carry a bounded logical asset ID, exact version or
revision, content digest, classification, and purpose qualification. They
should not embed environment-specific paths such as
`/home/user/project/assets/...` as semantic identity.

The same logical asset may resolve to a laptop path, workstation cache, render
farm cache, object store, or archive without changing semantic identity.
Physical locality and access mechanism are execution metadata.

### Asset Resolver

A future Asset Resolver maps:

```text
logical asset reference
  -> authorized resolution context
  -> physical location or access mechanism
```

The Resolver neither authorizes use nor defines semantic identity, truth,
ownership, clearance, or lifecycle eligibility. Runtime/policy must first
authorize the exact purpose and scope. Resolution cannot broaden purpose,
classification, retention, credentials, network access, or filesystem access.
The protocol and implementation remain unresolved.

### Reference versus payload

Small semantic facts and bounded metadata may be embedded in Context. Large
production artifacts are referenced by exact identity/version/digest and move
through the Data Plane. An asset reference may be suitable for Context; an
8-GB texture, full USD package, video file, or simulation cache is not.

Permanent rule:

> Heavy bytes travel through the Data Plane. Governance and semantic identity
> travel through the Control Plane.

### Control path versus data path

The control path carries authorization, admission, work identity, lifecycle,
budgets, cancellation, status, policy, and audit-safe identifiers. The data
path carries USD, geometry, textures, frames, audio, video, caches, and
generated media. Correlation and exact artifact references connect the paths;
the central Runtime does not become their bulk-data proxy.

## Plane 4 — Compute / Execution Plane

The Compute / Execution Plane eventually performs authorized effectful or
resource-heavy operations such as rendering, simulation, compositing,
transcoding, audio processing, image/video/audio generation, heavy animation
processing, and long-running model execution.

Specialized workers may differ by workload, software, hardware, isolation, and
data locality. A worker is not a semantic provider.

| Reasoning provider | Compute worker |
| --- | --- |
| produces a bounded semantic artifact | performs effectful or resource-heavy work |
| receives a minimal semantic provider view | receives an authorized bounded work specification and resolved data access |
| non-authorizing and typically short-lived | externally authorized, resource-aware, possibly long-running |
| no workflow/capability execution | may execute only the admitted operation |
| no heavy media payload path | may read/write heavy artifacts through the Data Plane |

The provider API v1 must not be widened into a worker protocol. Workers never
self-authorize, and queue delivery is not authorization.

### Future governed work specification

A later decision may define a bounded work specification binding operation
identity/version, exact artifact references/digests, project/environment,
classification/purpose, current authorization, resource requirements, budgets,
deadline/cancellation policy, retry/reconciliation policy, expected output
contract, and audit/lineage identity. This ADR neither defines its schema nor
names it Plan IR.

### Durable execution boundary

Work lasting seconds, minutes, hours, or days may need durable work and attempt
identities, leases, checkpoints, cancellation, deadlines, resumability,
recovery, retry, and reconciliation. Exactly-once delivery is not assumed.
Effectful retry requires an explicit idempotency guarantee, reconciliation or
compensation design, or a non-retryable classification. An unknown or partial
outcome is reconciled, not optimistically replayed.

A future scheduler/queue coordinates admitted work but does not authorize it.
It must account for stale/revoked work, bounded admission, queue limits,
backpressure, starvation prevention, protected critical-control capacity,
resource exhaustion, cancellation, and failed attempts. Infinite queueing is
not an accepted failure strategy.

### Resource requirements, compatibility, and authority

These are distinct decisions:

1. Runtime authorization: may this exact operation run for this purpose?
2. Workload requirements: what capabilities/resources does it need?
3. Worker compatibility: can this worker satisfy software/hardware constraints?
4. Resource availability: are the compatible resources currently available?

For example, `GPU memory >= 24 GB` grants no permission, proves no GPU exists,
and selects no worker. Future scheduling may consider CPU, RAM, GPU memory,
disk, network, cached assets, storage proximity, and software compatibility.
Physical locality never becomes semantic identity. No scheduling algorithm or
resource taxonomy is selected here.

## Authority matrix

| Component | Validate/resolve | Authorize/admit | Perform semantic reasoning | Move/store heavy bytes | Execute effects | Schedule/place | Expand authority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Runtime / Control Plane | yes | **sole authority** | no | no | admission only | policy constraints | never |
| Reasoning Gateway | semantic admission | no | invokes admitted provider | no | no | no | never |
| Semantic provider | view/result validation | no | yes | no | no | no | never |
| Contract Registry | exact kinds/versions | no | no | no | no | no | never |
| Asset Catalog | exact instances/versions | no | no | metadata only | no | no | never |
| Asset Resolver | authorized reference resolution | no | no | supplies access mechanism | no | no | never |
| Scheduler/queue | readiness/placement | no | no | references only | no | yes | never |
| Compute worker | work/input/output checks | no | not as worker | via scoped Data Plane access | admitted operation only | no | never |

Only Runtime authorizes and admits execution. Other components may narrow a
request by rejecting it; none may expand authority.

## Workload classification

VSS classifies operations rather than permanently classifying domains. One
domain may contain several workload types: animation can combine semantic
reasoning, lightweight transforms, and heavy simulation; music can combine
structure reasoning, synthesis, and mastering; movie work can combine semantic
analysis, compositing, and transcoding.

ADR-0014's conceptual classes remain useful: interactive semantic,
operational, batch, long-running, and critical control. Asset/data-intensive
and compute-intensive are additional workload characteristics, not a frozen
universal taxonomy. Each operation declares bounded needs appropriate to its
owner and lifecycle.

## Local-first topology and deployment equivalence

The full logical architecture remains runnable on one workstation:

```text
Workstation
├── Runtime / Control Plane
├── Semantic components and deterministic providers
├── local Asset Catalog
├── local Asset Resolver
├── local storage/cache
├── local bounded work queue
└── local CPU/GPU worker (or deterministic lightweight substitute)
```

These future local components are conceptual, not implemented here. Production
may later separate control services, asset services, storage, render farms, and
GPU pools. Semantic identity, contract identity, authorization meaning, audit
meaning, and artifact-lineage meaning remain equivalent. Shared governance
does not require shared deployment, and distribution is introduced only from
measured need.

## Audit, telemetry, and lineage

VSS permanently distinguishes:

- **Audit:** governance evidence answering what was admitted or rejected, by
  which policy/authorization decision, for which exact operation and purpose.
- **Telemetry:** operational evidence answering what happened, how long it
  took, what resources were used, and where it failed; for example metrics,
  traces, and logs.
- **Lineage/provenance:** artifact-history evidence answering which exact
  inputs, versions, transformations, provider/worker, and environment produced
  an output.

Audit is not telemetry. Audit is not lineage. Telemetry is not authorization
evidence. Lineage proves traceability, not truth, quality, rights, approval, or
permission. They may share bounded correlation identities, but VSS will not
create a universal God Event.

Future observability should correlate Runtime admission, Context or semantic
input, orchestration, queue attempt, worker, storage access, and output
artifact. Distributed trace context is operational metadata, not authority.
No observability product is selected.

Media lineage may need exact source scene, model, texture, shader, renderer and
version, settings, environment, worker, and transformation chain. Ownership
remains domain-specific; this ADR does not define one universal media
provenance schema.

## Semantic and production reproducibility

Semantic reproducibility means the same governed semantic inputs produce
equivalent deterministic outputs where a strategy explicitly claims
determinism. Production reproducibility is separate: GPU, driver, renderer,
plugin, codec, floating-point behavior, concurrency, and nondeterministic AI
may prevent byte-identical media.

Future production paths record enough lineage to make outputs reproducible
where supported or explainable where exact reproduction is impossible. VSS
does not promise global pixel-level determinism.

## Lifecycle ownership

Lifecycle remains domain-owned under ADR-0018. A semantic observation, texture
revision, render attempt, render result, approved shot, cache entry, and archive
have different state meanings. VSS will not create one universal status
vocabulary. The Control Plane asks whether an exact artifact is currently
eligible for an exact purpose under its owning lifecycle policy; the word
`active` alone never establishes eligibility.

## Worker isolation boundary

Before effectful production execution, DCC, render, media, and AI workers need
an enforceable hard isolation boundary. Such workers may load plugins, execute
scripts, parse untrusted formats, access large resources, spawn processes,
crash, hang, or attempt filesystem/network access. Required control properties
include process isolation, filesystem and credential scope, network policy,
resource limits, deadlines, cancellation, and output containment.

This ADR selects no isolation technology. Trusted in-process Python remains
acceptable only for current local non-effectful semantic work; it is not a
production worker sandbox.

## Future AI workloads

AI may appear in two planes. Semantic AI may interpret continuity or produce
creative alternatives through bounded semantic contracts. Compute AI may
generate image, video, audio, or other heavy artifacts through authorized
workers and the Data Plane. These have different operational and data
semantics.

Future AI governance must preserve provenance, uncertainty,
provider/model/version where policy requires it, classification, purpose,
cost/budget evidence, and appropriate output qualification. Probabilistic
output does not inherit deterministic guarantees. No AI provider or AI
infrastructure is introduced here.

## Planning and orchestration relationship

Plan IR remains deferred. ADR-0021 reserves architectural space for a future
durable planning/orchestration layer that may coordinate authorized work across
Semantic, Asset, and Compute planes. It does not assume one universal Plan, one
orchestration engine, or that every semantic result becomes a plan.

Planning begins only when implemented domain evidence repeatedly demonstrates
actions, ordering, dependencies, resources, approvals, retries, recovery,
compensation, and state transitions. A future work specification is an admitted
execution boundary, not automatically a Plan.

## Future Asset Management boundary

```text
Asset Contract (kind)
  -> logical asset reference
  -> Asset Catalog (instance/version)
  -> Asset Resolver (purpose-constrained resolution)
  -> physical storage/cache
```

Separate future decisions must own asset identity, version relationships,
mutable aliases, immutable revisions, USD package/layer identity, texture and
media variants, retention/deletion, lineage, signing, cache invalidation,
residency, and external asset-manager integration.

## Future Rendering boundary

```text
semantic requirement
  -> possible future plan or work proposal
  -> Runtime authorization/admission
  -> authorized work specification
  -> execution scheduler/queue
  -> compatible isolated render worker
  -> Asset Resolver / Data Plane
  -> render-result artifact reference
  -> validation + governance audit + artifact lineage
```

Heavy frames do not return through Reasoning Gateway or flow through Runtime.
This ADR defines no render request/result schema, engine, farm, or scheduler.

## Scalability, backpressure, and federation

The shared Control Plane must not become a serialized data or execution
bottleneck. Prefer immutable snapshots, exact references, bounded control
messages, and independently scalable domain components only where future
evidence requires them. Do not prematurely distribute current semantic code.

Future admission and execution require bounded queues, explicit backpressure,
cancellation, starvation prevention, protected critical-control capacity,
resource exhaustion handling, and attempt accounting. A failed control system
fails closed; overloaded media work must not prevent cancellation or security
response.

Asset, lineage, worker, and future execution registries/catalogs remain
domain-owned and federated. Shared governance obligations are conceptual
contracts, not a universal object, registry, lifecycle, or service.

## Security and trust boundaries

| Threat | Conceptual mitigation | Deferred implementation |
| --- | --- | --- |
| Contract Registry used as Asset Catalog / registry explosion | kinds and instances have separate ownership and scaling | Asset Catalog architecture |
| Asset God Object or Studio God Registry | bounded domain contracts and federated ownership | domain-specific asset decisions |
| Physical path becomes semantic identity | exact logical ID/version/digest; resolution is separate | resolver protocol and storage policy |
| Asset Resolver expands authority | requires authorized purpose/scope and can only narrow/fail | authenticated scoped resolution |
| Heavy payload routed through Runtime | reference-only bounded control path | enforceable payload limits |
| Reasoning Gateway executes compute | semantic-only admission and provider API | separate worker protocol |
| Worker self-authorization / queue as authority | current Runtime admission required; work possession grants nothing | authenticated work/lease identity |
| Requirement or availability mistaken for permission | four separate authorization/requirement/compatibility/availability decisions | scheduler policy model |
| Scheduler authority drift | placement only; cannot widen authorized work | independently enforced admission token/specification |
| Stale, expired, or revoked asset/work | domain lifecycle and current pre-execution eligibility | persistent revocation/distribution semantics |
| Asset, digest, or result substitution | exact type/instance/version/content binding and validation | signatures/authenticated lineage |
| Path traversal and unsafe formats | resolver containment and bounded hardened parsing | sandboxed format/DCC ingestion |
| Cache poisoning | content digest, classification/purpose partitions, lineage checks | cache signing/invalidation policy |
| Worker credentials or network exfiltration | least privilege and mandatory isolation | credential broker/network enforcement |
| Arbitrary DCC/plugin/script execution | untrusted effectful workload boundary | process/container/sandbox technology |
| Unbounded render/resource use | bounded admission, budgets, leases, resource ceilings, cancellation | scheduler/resource enforcement |
| Cancellation ignored | cancellation identity/deadline and terminal accounting | hard termination/reconciliation |
| Retry duplicates effects | no exactly-once assumption; idempotency/reconciliation/compensation | operation-specific recovery |
| Audit confused with telemetry | distinct semantics, retention, and trust | production backends |
| Telemetry treated as authorization | operational evidence grants no authority | authenticated audit association |
| Lineage treated as truth | traceability qualification | verification/signing policy |
| God Event | separate audit, telemetry, and lineage records with shared correlation only | domain-specific schemas |
| God Gateway | Reasoning Gateway semantic-only; workers separate | architecture conformance tests |
| Central Control bottleneck or data proxy | bounded references and scalable admission, never bulk bytes | measured partitioning design |

Other required controls include classification/trust preservation, purpose
limitation, cross-project isolation, safe errors and telemetry, output
containment, bounded fan-out, failed-attempt accounting, and critical-control
capacity. Persistent revocation, durable production audit, authenticated
artifacts, hard isolation, and production recovery remain gates before
effectful production.

## Alternatives considered

1. **One flat Runtime path for every workload — rejected.** It makes Runtime a
   data/compute bottleneck, forces incompatible synchronous semantics, and
   encourages Reasoning Gateway, registries, and Context to become God Objects.
2. **Independent domain stacks with separate governance — rejected.** It
   duplicates authorization and policy, permits inconsistent controls, and
   creates authority drift.
3. **Shared governance with specialized workload planes — selected.** It keeps
   one conceptual authority and common obligations while allowing semantic,
   asset, and compute operations to use appropriate topology.
4. **Microservices immediately — rejected.** It adds distribution, partial
   failure, deployment, and consistency costs without measured need and harms
   laptop operation.
5. **Adopt a render-farm architecture immediately — rejected.** It prematurely
   couples VSS to one production workload and technology before asset, work,
   lineage, and isolation contracts exist.

## Consequences

Positive consequences:

- current semantic architecture remains valid and bounded;
- Runtime and Reasoning Gateway avoid heavy-data and compute bottlenecks;
- Contract Registries avoid asset-instance explosion;
- logical identity remains portable across storage/deployment profiles;
- specialized workers can later support GPU and long-running workloads;
- local-first operation and future scale-out retain equivalent governance;
- authority remains centralized conceptually while execution can scale; and
- production risk receives an explicit isolation boundary.

Costs and risks:

- more explicit architectural boundaries and ownership decisions;
- future Asset Catalog, Resolver, worker protocol, durable execution state,
  telemetry, and lineage designs;
- possible duplication while evidence accumulates;
- ambiguous ownership at plane edges;
- eventual orchestration and deployment complexity; and
- temptation to implement speculative abstractions too early.

Mitigations are to define the boundaries now, defer technologies and schemas,
introduce components only from domain evidence, preserve a simple local
implementation, use federated ownership, and continue checkpoint reviews.

## Relationship to prior ADRs and checkpoints

- **ADR-0010:** Runtime remains the sole execution and authorization authority;
  specialized placement does not create another Runtime.
- **ADR-0011:** explicit boundaries, local-first operation, least privilege,
  provider neutrality, simplicity, and measurable claims govern all planes.
- **ADR-0012:** semantic provider replaceability remains within the Reasoning
  Plane; compute workers are a different abstraction.
- **ADR-0013:** bounded semantic contracts remain compositional and inert; no
  universal production object is introduced.
- **ADR-0014:** this ADR specializes its control/execution distinction,
  workload classes, local equivalence, bounded admission, and non-exactly-once
  delivery model.
- **ADR-0015:** knowledge provenance, classification, trust, retention,
  uncertainty, and revocation are preserved and not flattened into asset state.
- **ADR-0016:** approval and autonomy constraints remain Control Plane policy;
  workers and providers cannot approve themselves.
- **ADR-0017:** Context remains small, task-specific, purpose-limited, and
  provider-minimized rather than becoming an asset transport.
- **ADR-0018:** registries, future catalogs, lifecycle, and compatibility remain
  federated and domain-owned; no Studio God Registry is created.
- **ADR-0019:** movie semantic contracts and Scene Breakdown remain inert and
  separate from production execution.
- **ADR-0020:** Character Continuity remains bounded Semantic Plane work and
  Plan IR remains deferred.
- **M3/M4 checkpoints:** the proven single Context/Reasoning architecture is
  preserved; production audit, persistent revocation, and process isolation
  remain gates before external providers or effects.

## Roadmap impact

The immediate sequence remains:

1. ADR-0021 (this documentation decision).
2. M5.2 Character Continuity Context Assembly and deterministic reasoning.
3. M5.3 bounded transition/contradiction analysis.
4. M5 checkpoint.

The M5 checkpoint should choose among Shot Design, Plan IR, Asset Architecture,
and External AI architecture using implemented evidence. Before Rendering or
Asset Management implementation, separate explicit architecture decisions
must refine their contracts, authority, data, isolation, and lifecycle under
ADR-0021.

## Unresolved questions

- final operation/workload taxonomy;
- Asset Catalog ownership and schema;
- logical asset ID and immutable revision/version model;
- mutable aliases and external identity mapping;
- resolver protocol and authorization evidence;
- USD package/layer strategy and composition ownership;
- texture/media variants and artifact lineage;
- persistent/object storage and residency;
- deletion, retention, signing, and cache invalidation;
- data-locality model and cache policy;
- worker protocol, identity, leases, and checkpoints;
- queue and scheduler technologies;
- resource discovery, reservation, fairness, and GPU compatibility;
- retry, reconciliation, compensation, and resumability semantics;
- render-farm topology and renderer compatibility;
- telemetry, tracing, lineage, and media-provenance formats;
- DCC isolation, sandboxing, secrets delivery, and network controls;
- persistent revocation and durable production audit;
- orchestration ownership and Plan IR timing;
- production performance and availability objectives; and
- multi-region execution and disaster recovery.

These are future evidence-driven decisions, not permission to choose a product
or implement infrastructure under this ADR.

## Independent review perspectives

| Perspective | Review conclusion |
| --- | --- |
| Enterprise Architecture | Four logical planes preserve shared governance without a universal runtime path. |
| Distributed Systems | Durable identity, bounded queues, cancellation, and reconciliation precede scale-out; exactly once is rejected. |
| VFX Pipeline Architecture | USD/media bytes and artifact lineage belong outside semantic Context and Runtime. |
| Rendering Infrastructure | Long-running render workers require a distinct authorized worker boundary and data locality. |
| Asset Management | Contract kinds, asset instances, logical identity, and storage resolution are separated. |
| OpenUSD Pipeline Design | USD layers/packages are future Data Plane artifacts; no package or composition model is prematurely fixed. |
| Media Pipeline Architecture | Rendering, simulation, compositing, and transcoding use effectful compute paths, not Reasoning Gateway. |
| Runtime Authority | Runtime alone authorizes/admit effects; queues, schedulers, catalogs, resolvers, and workers cannot. |
| Data Governance | Classification, purpose, retention, residency, and revocation remain exact across references and resolution. |
| Product Security | Hard isolation, scoped credentials/network/filesystem, output containment, and current admission are production gates. |
| Reliability / SRE | Backpressure, cancellation, attempts, checkpoints, and reconciliation are required without selecting machinery. |
| Observability | Audit, telemetry, lineage, and distributed trace context retain separate meanings. |
| Artifact Provenance | Domain-owned lineage records transformations without claiming truth or authority. |
| Performance / Scalability | Bounded control messages and specialized workers avoid a central data/compute bottleneck. |
| Local-First Engineering | All planes may co-locate on one workstation with reduced workloads or deterministic substitutes. |
| Cloud-neutral Architecture | No vendor, orchestrator, storage, queue, GPU, or deployment topology is selected. |
| Contract Evolution | Federated kinds, instances, lifecycle, and worker protocols can version independently. |
| Independent Verification | Acceptance criteria are testable by later architecture/implementation checkpoints without infrastructure in this ADR. |

No perspective identified a reason to select a technology, broaden Runtime, or
introduce Plan IR now.

## Acceptance criteria

ADR-0021 is acceptable when it establishes that:

- Runtime remains the sole authorization and execution-admission authority;
- the current semantic architecture remains valid;
- Reasoning Gateway is semantic-only and heavy compute stays outside it;
- Contract Registries describe kinds and Asset Catalogs describe instances;
- logical asset identity differs from physical location;
- heavy payloads remain outside the central control path;
- a Semantic Provider differs from a Compute Worker;
- authority differs from requirements, compatibility, and availability;
- audit, telemetry, and lineage are distinct;
- semantic and production reproducibility are distinct;
- hard worker isolation is required before effectful production;
- deployment topology is independent of logical architecture;
- complete local operation remains possible;
- domain lifecycles and registries remain federated;
- no vendor or product is selected;
- Plan IR remains deferred; and
- no infrastructure, implementation, schema, test, or dependency accompanies
  this decision.
