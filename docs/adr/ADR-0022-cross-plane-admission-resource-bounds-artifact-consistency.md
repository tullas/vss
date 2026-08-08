# ADR-0022: Cross-Plane Admission, Resource Bounds, and Artifact Consistency

## Status

Accepted

## Date

2026-08-08

## Context

ADR-0010 established Runtime-controlled capability invocation before VSS had
the four-plane architecture of ADR-0021. ADR-0013, ADR-0015, ADR-0017, and
ADR-0018 subsequently established bounded semantic contracts, governed
Knowledge and Context freshness, and static federated registries. ADR-0014
established local-first dynamic admission, resource governance, backpressure,
and non-exactly-once execution semantics.

Those decisions are compatible, but future effectful studio work needs an
explicit cross-plane handoff. Without one, an implementation might proxy large
USD, texture, video, audio, or simulation payloads through Runtime; store
dynamic budgets and worker state in static Contract Registries; treat available
hardware or cached assets as authorization; resolve mutable `latest` during
execution; or require every node to synchronize one mutable filesystem/cache.

Effectful production adds an artifact-consistency boundary distinct from
Knowledge and Context freshness. A worker must consume the exact admitted
artifact revision and bytes even when physical locations and caches differ. A
successful worker attempt must not automatically admit an output whose inputs,
authorization, lifecycle, or result contract became ineligible.

This ADR defines constitutional interaction rules only. It introduces no work
schema, Plan IR, Runtime code, policy engine, Asset Catalog, Resolver, queue,
scheduler, worker, storage, database, rendering system, authorization token,
distributed service, or vendor selection.

## Decision

VSS adopts these permanent cross-plane principles:

1. Runtime routes bounded authority, identities, and references—not heavy
   production bytes.
2. Static contracts define hard structural and semantic bounds.
3. Runtime policy evaluates dynamic authorization, resource, cost, quota, and
   deployment bounds.
4. Effective admission is the intersection of every applicable constraint.
5. Effectful production consumes exact immutable artifact identity,
   revision/version, and digest—never unresolved mutable `latest`.
6. Physical cache/location may change without changing logical identity.
7. Freshness, revocation, lifecycle, authorization, and artifact eligibility
   are revalidated at defined safe gates.
8. Long-running operation families define behavior when eligibility changes
   after admission.
9. Outputs retain exact lineage to their admitted input snapshot.
10. Unknown required validity fails closed; irrelevant optional unknowns do not.
11. These rules grant no Plan IR, execution authority, or infrastructure.

ADR-0022 refines cross-plane handoff under ADR-0021. It does not alter the four
planes or make their logical boundaries deployment services.

## Runtime, capability, and heavy payload boundary

A capability remains a versioned unit of functionality. It is not an asset,
payload, permission token, physical worker, queue message, or pointer-only
abstraction. Runtime remains the sole authorization and execution-admission
authority under ADR-0010.

Future cross-plane invocation may reference bounded control information such
as:

- exact capability/operation identity and version;
- work and project/environment identity;
- exact purpose and authorization/admission evidence;
- exact artifact identities, revisions/versions, and content digests;
- resource and budget envelopes;
- deadline and cancellation state; and
- expected output contract identity/version.

This list is conceptual and does not define a universal work schema.

```text
Runtime / Control Plane
  -> validates and admits bounded operation + authority + references
  -> authorized downstream operation

Worker / Compute Plane
  -> resolves exact admitted artifact references
  -> reads/writes heavy bytes through governed Asset/Data Plane

Runtime does not download, serialize, forward, or receive the heavy bytes.
```

Permanent rule:

> Runtime routes authority and references, not production payloads.

Bytes bypassing Runtime as a transport hop never bypass Runtime authorization.
Data Plane access remains purpose-, project-, classification-, identity-, and
scope-constrained. Existing local bounded capability handlers remain valid;
ordinary bounded handler input is not prohibited, and no M3/M4/M5.1 retrofit is
required. Provider handles do not become unrestricted Data Plane handles.

## Static contract bounds and dynamic admission

### Static contract bounds

Contracts and their domain registries may define deterministic, versioned,
invocation-immutable hard limits such as:

- maximum input/output bytes and object/item counts;
- maximum scenes, frames, observations, variants, references, depth, and nodes;
- algorithmic or complexity ceilings;
- admitted workload classes and quality/resource semantics;
- permitted resource-requirement fields and units; and
- absolute implementation safety ceilings.

These definitions remain repository/domain owned, deterministic,
non-authorizing, and immutable within an invocation. A registry describes
contract kinds and compatibility, not current spend, capacity, price, quota,
worker state, cache contents, or policy decisions.

### Dynamic Runtime admission

Runtime policy may evaluate changing evidence including:

- remaining project or approved budget;
- user, tenant, project, provider, or storage quota;
- provider price and estimated cost;
- current GPU/CPU/RAM/storage/network availability;
- compatible worker capacity and current concurrency;
- current consumption, attempt count, and retry consumption;
- remaining deadline;
- deployment/workload profile;
- emergency limits and kill switches; and
- environmental, classification, residency, or other current policy.

Dynamic state belongs to Runtime admission and its domain sources, not static
Contract Registries.

Permanent rule:

> Contracts define hard bounds. Runtime admission evaluates dynamic bounds.

Contract validation is necessary but never sufficient for authorization.

## Effective admission

Effective admission is the conceptual intersection of every applicable
constraint:

```text
EffectiveAdmission =
    ContractBounds
  ∩ Compatibility
  ∩ Purpose
  ∩ Classification
  ∩ Authorization
  ∩ ApprovalWhereRequired
  ∩ Budget
  ∩ ResourcePolicy
  ∩ DeploymentProfile
  ∩ Lifecycle
  ∩ Freshness
  ∩ Revocation
  ∩ ArtifactEligibility
  ∩ Deadline
  ∩ WorkloadPolicy
```

This is a constitutional rule, not a Universal Admission Object. Each domain
may own and validate its constraint through federated components. Every layer
may narrow or reject; none may expand upstream authority. All applicable
constraints must pass. Unknown required validity fails closed.

Registration, schema validity, remaining budget, hardware availability, cached
bytes, provider compatibility, or worker placement never independently grants
authorization.

Examples:

1. A contract allows at most 24 GB VRAM, work estimates 18 GB, and current
   project policy authorizes at most 16 GB: deny admission.
2. Authorized estimated cost is USD 42 and remaining approved budget is USD 17:
   deny before compute invocation.
3. A compatible 48-GB GPU worker exists but the operation is unauthorized:
   deny. Availability cannot convert denial into admission.
4. An operation and budget are authorized, but the required artifact digest is
   unknown: deny because required artifact eligibility is unresolved.

Applicability is explicit and operation/policy owned. A task that needs no GPU
does not fail because GPU availability is unknown. Fail-closed behavior must not
turn unrelated optional state into a platform outage.

## Cost and resource evidence

Cost estimation is evidence for admission, not truth. Future estimates may be
deterministic, historical, provider-supplied, or profile-based. Where relevant,
they identify estimator/version, assumptions, uncertainty, units/currency,
ceiling or reservation semantics, and validity period.

Underestimation cannot silently expand approved budget. When remaining
authority is insufficient, future execution must stop at an applicable safe
gate, obtain new admission, or follow an explicitly authorized overrun policy.
This ADR defines no cost schema, price source, billing system, or reservation
technology.

Budget/resource admission differs from physical reservation. Runtime may
authorize work up to a bound; a future scheduler may reserve actual capacity.
Neither implies the other. Capacity disappearing between admission and attempt
start is a readiness/capacity failure, not an authorization change or reason to
substitute resources outside policy.

## Production Input Snapshot

Effectful work consumes a conceptual immutable Production Input Snapshot (or
manifest). The name describes a consistency boundary, not a finalized public
schema or Plan.

It conceptually binds exact:

- project and operation/work identity;
- artifact logical identities;
- artifact revisions/versions and content digests;
- classification and purpose;
- lifecycle eligibility at construction/admission;
- relevant source and lineage identities;
- policy/admission identity;
- construction time; and
- validity/expiry where applicable.

Examples include exact character-model, costume, environment, texture-set, USD
composition, shader, and audio-source revisions with their digests.

Permanent rule:

> Admitted effectful work uses exact immutable artifact identity + revision +
> digest.

No floating version, unresolved alias, environment-dependent path, process,
hostname, or cache location forms semantic artifact identity. Snapshot
integrity proves exact binding, not truth, quality, rights, approval, or current
authorization forever.

## Mutable aliases

User-facing aliases such as `latest`, `approved`, `current`, or `hero-model`
may exist for discovery. They must resolve before Runtime admission to an exact
immutable logical identity, revision/version, and digest.

Alias resolution is identification only. It grants no authorization, approval,
classification change, purpose expansion, lifecycle eligibility, or artifact
admission; Runtime and the owning artifact domain evaluate those constraints
separately.

```text
hero-model/current
  -> governed resolution before admission
  -> asset character-vikramaditya
  -> revision 18
  -> digest ABC123
  -> exact immutable admitted binding
```

The admitted work specification never retains the unresolved alias. If the
alias later points to revision 19, existing admitted work remains bound to
revision 18. Using revision 19 requires a new snapshot and admission or an
explicit reconciliation policy. Workers never resolve `latest` at execution.

## Cache and resolver consistency

A cache is an optimization, not evidence of identity, currency,
authorization, integrity, classification, purpose, or lineage. A cached
artifact may be consumed only when its logical identity, revision/version,
content digest, and applicable access scope exactly match admitted work.

If a cache contains revision 17 but admitted work requires revision 18, the
worker resolves exact revision 18 or fails safely. It must not use the previous,
nearest, locally discovered, or latest-available revision. A cache miss is a
readiness/data-availability outcome, neither authorization failure nor
permission to substitute.

The Asset Resolver maps an already governed logical reference to scoped
physical access. It cannot authorize, expand purpose, change classification,
invent identity, establish truth, or silently fall back. Digest verification
detects cache/resolver substitution; future signing or authenticated transport
remains separately undecided.

## Consistency without global mutable synchronization

VSS rejects mandatory global mutable state synchronization as the default
consistency model. It prefers immutable revisions, exact admitted snapshots,
digest verification, bounded resolver/cache validation, explicit
invalidation/revocation, and lineage.

This permits a laptop, render node, farm, disconnected cache, and archive to
store different physical copies or no local copy at all. Synchronization may
later optimize discovery or cache warming but never replaces exact validation.

The narrow consistency guarantee is:

> VSS does not promise every node stores identical bytes at all times. VSS does
> require an admitted operation to consume content matching its exact
> authorized artifact identities, revisions, and digests.

Consistency is verified at applicable admission/consumption gates, not created
by global mutable replication.

## Knowledge, Context, and artifact freshness

These related concepts remain distinct:

| Domain | Freshness/eligibility question |
| --- | --- |
| Knowledge | Is this exact semantic evidence/source/package eligible and current for the purpose? |
| Context | May this exact minimized evidence snapshot be delivered to this reasoning task now? |
| Production asset | May this exact artifact revision/digest be consumed by this effectful operation now? |

A current Knowledge Package does not prove a worker's production asset is
current. A valid production asset does not prove Knowledge is current. A valid
Context does not prove worker cache currency. Each domain owns lifecycle,
freshness, retention, and revocation semantics. Cross-domain binding uses exact
qualified references and explicit compatibility, never shared mutable state.

## Admission and revalidation gates

Potential safe gates are:

1. request construction;
2. Runtime admission;
3. queue admission;
4. lease/attempt start;
5. immediately pre-effect;
6. checkpoint/resume;
7. pre-output publication/admission; and
8. downstream consumption.

Not every operation uses every gate. Every future effectful long-running
operation family declares applicable gates, validation obligations, failure
behavior, and bounded policy-owned frequency. Constant polling is not required,
and a gate must not create an unbounded dependency on irrelevant domains.

At applicable gates, validation may cover current authorization,
cancellation, expiry, revocation, artifact identity/revision/digest,
classification, purpose, lifecycle, remaining budget/resources, and worker
compatibility. The same policy-owned time should be used for checks whose
boundary semantics require one atomic decision.

### Admission snapshot versus live validity

An admission snapshot proves applicable constraints passed at one admission
time. It does not freeze authorization, cancellation, revocation, expiry,
budget, or artifact eligibility forever. Live validity asks whether required
authority and inputs remain eligible at a later safe gate.

Queued work is not permanently authorized. At minimum, current applicable
authorization and artifact eligibility are revalidated before the first
effect. A queue message is not a bearer token and cannot grant permanent
execution rights.

## Long-running eligibility changes

Every future effectful operation family defines policy for relevant change
while queued, leased, executing, checkpointed, completing, or publishing.
Possible operation-specific outcomes include:

- cancel before effect;
- stop at a checkpoint;
- finish an indivisible atomic sub-unit;
- quarantine a result;
- complete the attempt but prohibit downstream admission; or
- reconcile partial effects.

There is no universal choice. Revoked/expired input cannot silently continue
and publish normally. Unknown or partially effected outcomes require
reconciliation, not optimistic replay.

If validity changes mid-atomic effect where immediate stopping is unsafe or
impossible, the operation follows its predeclared containment and
reconciliation policy. Worker success remains an operational fact, not output
admission.

## Partial updates and mixed revisions

A Production Input Snapshot never mutates under running work. If character
model revision 18 changes to 19, revision 19 forms a distinct snapshot. Policy
may allow old attempts to finish, cancel them, or quarantine their outputs, but
workers cannot mix 18 and 19 within one admitted snapshot.

An operation may use independently versioned component snapshots only when its
contract explicitly defines those components, exact bindings, and permitted
independence. Implicit partial refresh is prohibited.

## Authorization references

ADR-0022 mandates no bearer token. If distributed work later uses an
authorization artifact, it must be bounded, purpose-, work-, operation/version-,
project/environment-, expiry-, attempt-, and resource-scoped where applicable;
revocable or safely revalidated; non-transferable where feasible; and audit
associated. Possession alone cannot imply ambient or unlimited authority.

The mechanism remains future work. This ADR selects no JWT, macaroon, OAuth,
signed URL, credential broker, or signing system. A capability identity itself
is not an authorization reference.

## Heavy data transport example

```text
Runtime admits: asset A / revision 18 / digest X
Worker resolves: exact A/18/X through approved Data Plane scope
Worker consumes: bytes whose digest is X

Runtime does not download A, serialize A, forward A, or receive A's bytes.
```

Direct worker/Data Plane access does not create direct worker authority. The
worker receives only the bounded admitted scope and cannot browse, choose a
different revision, or broaden purpose merely because storage is reachable.

## Output lineage and admission

Every future effectful output is attributable to the exact admitted input
snapshot. Domain-owned lineage may include:

- output logical identity, revision, and digest;
- work and attempt identities;
- operation identity/version;
- exact input artifact identities/revisions/digests;
- worker/implementation identity where relevant;
- environment/deployment profile;
- transformation identity/version;
- output time; and
- validation/admission status.

Lineage provides traceability, not authorization, truth, quality, rights, or
approval. ADR-0022 defines no universal lineage schema.

A technically successful output may remain ineligible when generated from a
revoked or policy-superseded input, after authorization expiry or cancellation,
by an incompatible worker, with incomplete required lineage, or with an invalid
output contract/digest. It is quarantined, rejected, reconciled, or explicitly
revalidated according to domain policy. Worker success never automatically
creates an admitted production artifact.

## Concurrency and scalability

Immutable snapshots support safe fan-out. For example, 100 frame attempts can
reference one exact admitted artifact snapshot while workers resolve identical
logical revisions/digests from different physical caches. No central byte proxy
or globally synchronized cache is required, and no worker may substitute an
input because its local cache differs.

Expected architectural properties are:

- bounded control messages and snapshots;
- Runtime bandwidth does not scale with heavy artifact bytes;
- parallel workers obtain heavy data directly through governed resolution;
- immutable bindings permit deterministic input association across attempts;
- caches improve locality without changing identity;
- no global synchronization on every invocation;
- Contract Registries scale with kinds, not asset instances; and
- dynamic cost/resource admission occurs before expensive work.

This ADR promises no production throughput or latency. Snapshot construction,
eligibility checks, resolver operations, and digest verification remain bounded
and measurable under future workload profiles.

## Revocation federation

Revocation may independently apply to source material, Knowledge Items,
Knowledge Packages, Context, artifact revisions, work authorization,
implementations, worker eligibility, or credentials. VSS creates no universal
revocation registry. Each owning domain defines exact identity, effective-time,
expiry, failure, and retention semantics.

Cross-plane work binds enough exact identity for every applicable check. A
source/package revocation may invalidate derived work when domain-owned lineage
and policy declare that dependency. Persistent production revocation and
distribution remain future work. Existing documented known-empty development
snapshots remain valid only in their current local scope.

## Fail-closed applicability

Required unknowns that fail closed include, when applicable:

- unresolved artifact revision or unknown digest;
- unavailable authorization decision;
- unavailable budget state;
- classification or purpose conflict;
- unavailable current revocation status where a check is required;
- unknown required worker compatibility;
- unknown required freshness/lifecycle eligibility; and
- invalid or unresolved output identity/digest.

Optional or irrelevant unknowns do not fail an operation. Applicability is
explicit in the operation contract and policy so safety does not become an
unbounded dependency on every registry, resource, asset, or deployment fact.

## God-object prevention

VSS rejects:

- a Universal Admission Object;
- a Universal Work Object;
- Global Mutable Studio State;
- a Universal Resource Registry;
- a Universal Asset State Object;
- a centralized heavy-data proxy;
- a globally synchronized asset cache;
- a registry combining contracts, asset instances, budgets, policy, and worker
  state; and
- a capability or token carrying arbitrary ambient authority.

Constraint intersection is a constitutional behavior, not a mandatory shared
payload, database, policy engine, or service. Federated owners expose exact
bounded evidence and retain independent lifecycle meanings.

## Security and trust boundaries

| Threat | Boundary and mitigation | Deferred implementation |
| --- | --- | --- |
| Heavy-data proxy denial of service | Runtime carries bounded references, never required bulk bytes | enforceable control-message/payload ceilings |
| Capability confused with authorization token | capability identifies functionality; Runtime separately admits exact work | distributed authorization artifact design |
| Bearer-token replay/ambient authority | no token selected; future artifacts are scoped, expiring, revalidated, and attempt associated | cryptographic/non-transferable mechanism |
| Stale authorization / queue stale work | admission snapshot is not permanent; revalidate at applicable pre-effect gates | durable policy/revocation transport |
| Stale cache or resolver fallback | exact identity/revision/digest; no nearest/latest/filesystem fallback | authenticated resolver and cache invalidation |
| Mutable alias race | alias resolves before admission; snapshot retains exact immutable revision | atomic catalog alias-resolution semantics |
| Revision/digest substitution | exact snapshot binding and consumption-time verification | signing/attestation |
| Admission-to-effect TOCTOU | operation-owned safe gates and live eligibility checks | durable admission evidence protocol |
| Budget race/cost underestimation | dynamic current budget check, ceilings, reservations/overrun policy | cost and reservation systems |
| Resource exhaustion | static ceilings plus dynamic quotas, bounded admission and cancellation | scheduler/resource enforcement |
| Revoked work continues/publishes | pre-effect/restart/output gates; cancellation, quarantine, reconciliation | persistent revocation distribution |
| Mixed-revision output | immutable snapshot; no mid-work mutation or implicit partial refresh | output attestation |
| Cache poisoning | digest, identity, classification/purpose scope, lineage validation | signed cache metadata |
| Worker success treated as admission | independent output validation and current eligibility | production artifact admission service/process |
| Lineage tampering | exact domain-owned associations and digest binding | signed/tamper-evident lineage |
| Cross-project substitution | exact project/purpose/classification and artifact scope | authenticated tenancy/storage isolation |
| God Admission Object/global mutable state | federated intersection and immutable invocation snapshots | conformance automation |
| Central Runtime data bottleneck | governed direct Data Plane transport | measured topology-specific transport controls |
| Global synchronization outage/partition | exact immutable snapshots and local consumption verification; synchronized discovery is never correctness authority | distributed invalidation and offline-worker policy |

Path traversal, unsafe file types, credential leakage, network exfiltration,
worker isolation, cancellation enforcement, retries, and partial effects remain
governed by ADR-0014/ADR-0021 and future Asset/Worker decisions. None is solved
by a digest or snapshot alone.

## Relationship to ADR-0010

ADR-0010 remains authoritative: capabilities are versioned functionality and
Runtime alone validates, authorizes, and admits execution. Local bounded
handler invocation remains valid. Future cross-plane compute pairs exact
operation identity with bounded admitted scope and artifact references; heavy
production data need not transit handler input. Capability/provider identity
is neither asset identity nor unrestricted Data Plane access. No current
capability implementation is retrofitted.

## Relationship to ADR-0013

Semantic tasks/results retain bounded provider-neutral meaning and remain
inert. Semantic schema validation never authorizes compute. Semantic contracts
may express static hard limits; current budgets, capacity, price, and resource
policy belong to Runtime admission. ADR-0022 introduces no execution semantics
into Reasoning Objects.

## Relationship to ADR-0014

Workload, deployment, resource, and cost profiles provide current admission
evidence under Runtime policy. Bounded queues/backpressure, protected control
capacity, attempts, cancellation, and non-exactly-once delivery remain
authoritative. Cost and available capacity cannot expand authority. Deployment
profiles never change semantic or artifact identity.

## Relationship to ADR-0015

Knowledge identity, classification, provenance, freshness, retention, and
revocation remain Knowledge-domain responsibilities. Production asset
eligibility is separate. Exact lineage/policy may make source or Knowledge
revocation relevant to downstream derived work, but a Knowledge Package is not
a production asset, Asset Catalog, or heavy-byte container.

## Relationship to ADR-0017

Context Assembly independently revalidates semantic evidence freshness and
creates a minimized purpose-specific reasoning snapshot. Context may include
bounded exact asset references when semantically necessary, never heavy asset
bytes. Context is not asset synchronization, and valid Context does not prove
the worker cache or production artifact is current.

## Relationship to ADR-0018

Registries retain repository/domain-owned static contracts, compatibility,
lifecycle declarations, bounds, and immutable invocation snapshots. They are
non-authorizing and do not hold dynamic budget/resource/worker/cache state or
asset instances. Exact cross-registry mappings remain immutable, federated,
and non-authorizing.

## Relationship to ADR-0021

ADR-0022 refines, without changing, ADR-0021's four planes, control/data
separation, logical identity/location distinction, Contract Registry/Asset
Catalog distinction, Semantic Provider/Compute Worker boundary, governed direct
Data Plane access, and durable execution boundary.

## M5 relationship

M5.2 and M5.3 remain bounded non-effectful Semantic Plane work using the
existing Context Registry and Reasoning Gateway. ADR-0022 adds no asset handling
to Character Continuity and requires no M5 redesign. Its rules constrain later
Asset/Data and Compute/Execution implementation.

## Local-first operation

A local profile may resolve every exact artifact revision/digest to a local
filesystem or cache and run all logical components on one workstation without
a network service. Local paths remain physical resolution, not identity. The
same admitted logical identity/revision/digest and authority semantics apply in
future distributed deployments.

## Alternatives considered

1. **Pass all payloads through Runtime — rejected.** This centralizes bandwidth,
   memory, serialization, failure, and attack surface and conflates authority
   with data transport.
2. **Globally synchronize mutable `latest` assets — rejected.** It requires
   constant global state, creates race/partition ambiguity, and still cannot
   prove consumed bytes.
3. **Let workers use whatever current asset is available — rejected.** It
   silently substitutes revisions, destroys reproducibility and lineage, and
   lets cache locality change semantic input.
4. **Put dynamic budgets/resources in Contract Registries — rejected.** It turns
   deterministic versioned registries into mutable policy/state services and
   confuses structure with authorization.
5. **Immutable exact snapshots + Runtime dynamic admission + direct governed
   Data Plane access — selected.** This preserves one authority, bounded static
   contracts, exact input consistency, cache locality, parallelism, and local/
   distributed equivalence without a central byte proxy or global mutable
   synchronization.

The selected option costs more identity/digest management, safe-gate
revalidation, and future resolver/catalog coordination, but those costs are
explicit and measurable rather than hidden as stale or unauthorized work.

## Consequences

Positive consequences include avoiding a central Runtime bandwidth bottleneck,
preventing stale revision substitution, supporting parallel rendering and
cache locality, keeping Contract Registries bounded, separating static
contracts from dynamic policy, providing cost/resource guardrails, retaining
exact lineage, and preserving laptop/distributed equivalence.

Costs include a future bounded input-snapshot/manifest concept, more explicit
identity/digest domains, pre-effect revalidation, future Resolver/Catalog
coordination, long-running revocation reconciliation, and cost estimation.

Risks include digest terminology burden, overly conservative fail-closed
behavior, excessive repeated checks, snapshot construction cost, and stale
aliases before resolution. Mitigations are domain-owned applicability,
operation-specific gates, bounded snapshots, cached verified metadata, exact
immutable identities, explicit digest-domain documentation, and measurement
before optimization.

## Roadmap impact

The immediate sequence remains:

1. ADR-0022 (this documentation decision).
2. M5.2 Character Continuity Context and deterministic reasoning.
3. M5.3 bounded continuity analysis.
4. M5 checkpoint.

Before Asset Management implementation, VSS requires an explicit Asset
Architecture ADR. Before effectful compute, it requires a Worker/Durable
Execution ADR. Before production rendering, it requires explicit Render Work
and Asset Snapshot architecture. ADR-0022 authorizes none of those
implementations.

## Unresolved questions

- final Production Input Snapshot/manifest schema and ownership;
- exact asset logical identity and revision model;
- mutable alias and supersession semantics;
- Asset Catalog architecture and Resolver protocol;
- signed references, content attestations, and authorization artifact format;
- distributed policy snapshots and revocation transport;
- operation-specific gate frequency and atomic-effect boundaries;
- long-running cancellation, containment, and reconciliation semantics;
- budget reservation, cost estimator, pricing, and overrun policy;
- physical resource reservation and worker leases;
- queue state, duplicate delivery, and checkpoint ownership;
- output quarantine and production-artifact admission;
- lineage format, signing, retention, and privacy;
- snapshot retention and cache invalidation;
- offline workers, partial connectivity, and multi-site consistency;
- storage residency and cross-site transfer policy; and
- production output supersession and downstream-consumption policy.

These require implementation evidence and separate decisions. They cannot be
resolved through hidden defaults.

## Independent review perspectives

| Perspective | Conclusion |
| --- | --- |
| Enterprise Architecture | Constraint intersection and exact references bridge planes without a universal state service. |
| Runtime Kernel Architecture | Runtime retains sole admission authority while bounded local handlers remain compatible. |
| Distributed Systems | Immutable snapshots and gate revalidation replace global mutable synchronization and exactly-once assumptions. |
| Resource/Cost Governance | Static ceilings and dynamic budget/capacity decisions remain separate and narrowing-only. |
| VFX Pipeline Architecture | Heavy production bytes use direct governed data paths with exact revisions and lineage. |
| Asset Management | Aliases resolve before admission; catalog/resolver ownership remains future and separate from registries. |
| Rendering Infrastructure | Parallel attempts may use different caches but must consume identical admitted revisions/digests. |
| Data Consistency | The guarantee concerns bytes consumed, not identical global storage state. |
| Cache Architecture | Cache presence is optimization only; misses and mismatches never authorize substitution. |
| Reliability | Long-running families must define cancellation, quarantine, atomic-unit, and reconciliation behavior. |
| Product Security | TOCTOU, stale authorization, substitution, replay, budget races, and output admission are explicit boundaries. |
| Data Governance | Project, purpose, classification, lifecycle, retention, and revocation remain domain-owned and exact. |
| Performance/Scalability | Runtime carries bounded control messages while immutable snapshots support fan-out and locality. |
| Local-First Engineering | One workstation can resolve the same exact identities locally without network services. |
| Contract/Registry Governance | Registries retain static kinds/bounds and never become dynamic resource or asset-state stores. |
| Artifact Provenance | Outputs retain exact admitted input lineage without a universal lineage object. |
| Independent Verification | Rules are explicit and reviewable without choosing or implementing infrastructure. |

No perspective justifies Plan IR, a global mutable service, or a technology
selection in this decision.

## Acceptance criteria

ADR-0022 is acceptable when it establishes that:

- Runtime remains the sole authorization and execution-admission authority;
- capability identity differs from asset and authorization identity;
- heavy bytes are not required to transit Runtime;
- static contract bounds differ from dynamic policy bounds;
- effective admission is an intersection that only narrows;
- dynamic cost/resource state stays outside Contract Registries;
- effectful work requires exact artifact identity/revision/digest;
- mutable aliases resolve before admission;
- caches cannot substitute revisions;
- global mutable synchronization is unnecessary;
- valid Context does not prove worker cache currency;
- admission-time validity is not permanent live validity;
- long-running eligibility changes have explicit operation policy;
- queued work is revalidated before effect where applicable;
- output retains exact admitted input lineage;
- worker success does not automatically admit output;
- no God Admission, Work, Resource, Asset State, or Studio State object exists;
- no Plan IR or infrastructure/vendor choice is introduced; and
- M5.2 remains unchanged.
