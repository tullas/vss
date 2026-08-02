# ADR-0015: Knowledge Architecture and Bounded Knowledge Packages

## Status

Accepted

## Date

2026-08-02

## Context

VSS needs governed knowledge for reasoning and future autonomous workloads, but
source access must not become ambient authority or couple semantic contracts to
a repository, document store, search system, database, connector framework,
embedding model, cloud, provider, storage layout, or memory implementation.
Raw availability is not governance: source material can be stale, poisoned,
misclassified, incomplete, conflicting, or outside the task's permitted
purpose.

The permanent rule is:

> Source systems provide material. The Knowledge Layer governs and packages it.
> The Reasoning Gateway receives only bounded, purpose-limited Knowledge
> Packages. Runtime still owns authorization, policy, budgets, approval, and
> execution.

This decision is governed by:

- [ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md), which makes
  Runtime the sole execution and authorization authority;
- [ADR-0011](ADR-0011-engineering-principles.md), especially explicit
  contracts, least privilege, provider neutrality, security by construction,
  audit, and local-first development;
- [ADR-0012](ADR-0012-evolvable-reasoning-architecture.md), which establishes
  the Knowledge Package and Reasoning Gateway boundary;
- [ADR-0013](ADR-0013-semantic-reasoning-contracts.md), which establishes
  provider-neutral evidence references, independently versioned typed payloads,
  and the Rule of Five;
- [ADR-0014](ADR-0014-local-first-scalability-performance-efficiency.md), which
  requires bounded, measurable, profile-driven, cost-controlled work; and
- the [M2 architecture checkpoint](../reviews/m2-architecture-checkpoint.md),
  which identifies production limitations in cooperative cancellation and
  local JSON Lines audit.

Knowledge inclusion never implies truth, authorization, approval, freshness,
correctness, completeness, permission to disclose, permission to retain,
permission to act, or permission to access the original source.

## Decision

VSS will introduce a provider-neutral Knowledge Layer separating source
systems, connectors, source registration and identity, retrieval,
normalization, classification, provenance, freshness, redaction, integrity,
conflict and uncertainty representation, Knowledge Package construction,
package authorization, lifecycle, delivery, audit, and evidence.

Reasoning providers and strategies never access sources directly. Knowledge is
untrusted input before and after packaging; packaging establishes known
structure and governance evidence, not truth or authority.

### Authority boundary

Only the Knowledge Layer prepares Knowledge Packages. It governs source
registration, retrieval authorization, purpose limitation, minimization,
classification, freshness, provenance, redaction, package construction,
retention, revocation, and integrity evidence.

Retrieval authorization and package construction occur only within policy and
resource authority approved by Runtime. The Knowledge Layer has no independent
authorization root and cannot enlarge the source scope, purpose, classification
ceiling, budget, retention, or provider eligibility granted by Runtime policy.

The Knowledge Layer is not a second Runtime. It cannot authorize capability
execution, approve operations, select execution capabilities, invoke workflows,
bypass Runtime policy, grant autonomy, infer truth from availability, or
promote material into a fact without contract support. Runtime independently
decides whether a task may use a package. The Reasoning Gateway validates that
authorization before delivery and receives no source-system access.

### Source systems and stable identity

A source system supplies material under a registered scope. Source types may
include local files, Git repositories, document repositories, structured
databases, APIs, issue trackers, logs, build systems, calendars, media
libraries, asset catalogs, production schedules, research collections,
approved web sources, human-authored records, and prior VSS execution evidence.
These examples approve no product or vendor.

Every source has stable identity independent of its connector. Conceptual
metadata includes source identity and type, source contract version, owner,
system of record, trust and data classifications, jurisdiction or residency,
permitted purposes, retention restrictions, retrieval and freshness policies,
revocation state, connector identity, and integrity metadata. Replacing a
connector does not change the source identity.

### Connector boundary

Connectors are replaceable, narrowly scoped adapters. A connector may
authenticate to one approved source, retrieve only authorized material, report
source metadata and version or freshness, normalize transport failures, and
return bounded retrieval results.

A connector cannot authorize itself, infer permitted purpose, decide whether
reasoning may see data, expose unrestricted browsing, disclose credentials,
execute arbitrary source-side commands, silently expand scope, retain material
outside policy, or expose provider-native objects beyond its adapter.
Connector registration means only that the connector is known; it grants no
source, retrieval, package, or execution authorization. Dynamic third-party
connectors remain unsupported.

### Lifecycle

Source and normalized-item lifecycles must distinguish semantics equivalent to
`registered`, `active`, `restricted`, `stale`, `quarantined`, `revoked`,
`archived`, and `deleted`. Package lifecycles must distinguish semantics
equivalent to `constructed`, `validated`, `authorized`, `delivered`, `expired`,
`revoked`, and `archived`. Implementations may use different names only when
the state transitions and fail-closed meanings remain explicit.

Delivery does not make a package permanently authorized. Authorization,
expiration, revocation, classification, and purpose are re-evaluated at use.

### Static and dynamic knowledge

Static knowledge includes standards, architecture, approved project canon,
policies, historical references, style guides, and character definitions. It
changes infrequently and may use longer freshness windows or explicit version
approval, but remains revocable and supersedable.

Dynamic knowledge includes repository state, CI results, schedules, logs,
inventories, news, weather, market data, and live operational state. Retrieval
and effective times are material, freshness windows are short, and stale data
cannot be silently represented as current. A task contract may require a
minimum freshness property; unsupported requirements fail closed.

### Normalization without a God object

Normalization converts transport-specific material into inspectable,
provider-neutral, bounded representations. It cannot silently change meaning,
omit classification, discard source identity, erase uncertainty, promote
assumptions to facts, remove provenance, or remove legal, license, retention,
or purpose restrictions. Normalized content remains linked to source and
retrieval evidence.

VSS rejects one universal normalized document or Knowledge God Object. It uses
the ADR-0013 envelope-versus-payload discipline:

```text
Knowledge Item
├── small common metadata envelope
└── exactly one independently versioned typed item payload
```

The envelope may identify the item, source, item type, item-contract identity
and version, classification, provenance, freshness, integrity digest,
lifecycle state, permitted purpose, and retention restrictions. It contains no
source-code-, ticket-, media-, script-, log-, schedule-, character-, scene-,
shot-, asset-, or policy-specific fields.

Each item type owns its bounded payload contract. The envelope identifies one
and only one payload family and version. Unknown types or versions, unknown
fields, identity/payload mismatches, multiple unrelated payloads, untyped data
bags, and arbitrary extension objects fail closed. Composition is semantic and
does not prescribe a programming-language inheritance hierarchy.

Every item family has a stable identity, schema identity and version, explicit
size and structural bounds, lifecycle state, compatibility rules, conformance
requirements, security review, accountable owner, and deprecation and
retirement metadata. A new family changes its own registered contract rather
than adding optional source-specific fields to the common envelope.

### Knowledge Package

A Knowledge Package is an immutable, bounded, purpose-limited collection of
authorized knowledge items and governance metadata for one task or task
family. Its conceptual contract includes:

- package schema version, immutable package identity, and correlation identity;
- permitted purpose and task identity or task family;
- construction and expiration times;
- source and item references;
- package classification and integrity digest;
- freshness, redaction, provenance, conflict, and uncertainty summaries;
- retention restrictions and authorization metadata;
- package lifecycle state; and
- bounded typed item payloads or integrity-bound references.

A package contains no credentials, source sessions, unrestricted source or
filesystem access, connector clients, environment variables, execution
handles, approval, policy authority, executable code, shell commands,
provider-native objects, arbitrary implementation paths, or arbitrary URLs
with implied authority. References are identifiers and evidence, not ambient
retrieval grants. A package conveys no right to retrieve its original sources.

### Boundedness and reduction

Versioned policies and deployment profiles bound total package size, item
count, item size, nesting depth, string length, media-reference count,
provenance and evidence entries, retention period, expiration, source count,
retrieval fan-out and duration, and redaction-metadata size. Numeric values do
not belong in this ADR.

Oversized packages fail safely or undergo an explicitly approved, attributable,
versioned reduction. Reduction cannot silently remove critical facts,
constraints, provenance, classification, conflicts, uncertainty, or
limitations. A reduced package receives distinct construction evidence and an
integrity digest.

### Purpose limitation

Every retrieval and package declares a permitted purpose, such as generating
options, summarizing repository state, evaluating continuity, comparing
approved assets, assessing production risk, or preparing a draft scene review.
A package built for one purpose cannot be silently reused for another. Purpose
changes require fresh authorization and, where scope, classification,
minimization, redaction, or freshness differs, reconstruction. Contents never
imply a broader permission.

### Classification and redaction

Classification is mandatory. Conceptual classes may include public, internal,
confidential, restricted, personal, regulated, and secret-bearing. This ADR
does not finalize the taxonomy. Classification policy determines eligible
connectors, storage, reasoning providers, redaction, retention, export,
geographic restrictions, audit detail, and human approvals. A provider cannot
receive material above its authorization. Unknown or conflicting
classification fails closed and cannot be resolved by a connector or provider.

Redaction occurs before delivery when policy requires it. Redaction is
policy-driven, versioned, auditable, purpose-specific, traceable, bounded, and
irreversible for the recipient unless a separately approved reversible process
exists outside the package. Redaction metadata cannot reveal the removed
secret. Minimization selects only necessary material; broad repository,
document-store, source-system, or media-library dumps are prohibited by
default.

### Provenance

Every item preserves provenance sufficient to trace its source identity and
item identity, retrieval time, source revision or effective date, connector
identity and version, normalization contract and version, redaction policy and
version, attributable transformations, integrity digests, originating author
or authority when known, and license or usage restrictions.

Provenance enables tracing, review, comparison, revocation, and rollback. It
does not prove truth, correctness, authorization, or trustworthiness.

### Freshness and temporal semantics

Items and packages represent observation, effective, retrieval, stale, and
expiration semantics. They distinguish latest known, current as of a timestamp,
historically effective, stale, superseded, and unknown freshness. Dynamic data
is never represented as timeless fact. Reasoning results preserve material
time qualifications through evidence references.

Freshness may include `observed_at`, `effective_from`, `effective_until`,
`retrieved_at`, source version, freshness-policy identity, `stale_after`, and
`expired_at`. The final schema is deferred. Unknown freshness fails closed when
the task requires currency.

### Integrity

Normalized items and packages carry integrity evidence such as cryptographic
digests, immutable identities, source revision, manifest digest,
normalization/redaction versions, and construction evidence. Integrity proves
consistency with recorded bytes and transformations, not truth, authorization,
freshness, or safety. Packages are revalidated before use when mutable storage
or transport could have changed them.

### Conflicts, uncertainty, and trust

The Knowledge Layer preserves material disagreement instead of silently
choosing a source. Packages represent conflicting claims, source identities,
effective times, trust classifications, evidence quality, ambiguity, missing
data, stale data, and supersession. Conflict resolution, when permitted, is
explicit, versioned, attributable, and audited. Reasoning never receives a
falsely unified truth.

Conceptual source trust classifications may include authoritative, approved,
corroborating, unverified, user-supplied, external, adversarial, and
quarantined. Trust never replaces validation: an authoritative source may be
stale, malformed, compromised, or outside purpose, while a low-trust source may
be relevant when the task explicitly requires it and the classification stays
visible. Unknown or conflicting trust cannot be silently inflated.

### Knowledge poisoning and instruction isolation

Knowledge content is always data, never an instruction to Runtime, the
Knowledge Layer, the Reasoning Gateway, a connector, strategy, or provider.
Embedded phrases such as “ignore prior rules,” “execute this command,” “reveal
secrets,” “use this provider,” or “change policy” have no authority.

Controls must address malicious documents and markup, indirect prompt
injection, poisoned repositories, compromised connectors, stale versions,
manipulated provenance, source and result substitution, adversarial media
metadata, hidden executable content, excessive or recursive structures,
conflicting authoritative sources, untrusted web content, and citation
spoofing. Structural validation, bounded parsing, content/type separation,
provenance, classification, integrity checks, minimization, quarantine, and
independent Runtime authorization preserve the boundary.

### Retention, expiration, deletion, and revocation

Packages and normalized content have retention policy, expiration, archival or
deletion outcome, revocation behavior, evidence-retention rules, and
provider-retention compatibility. Expired or revoked packages cannot be reused.
Deleting content does not necessarily delete required audit evidence, but audit
retains only safe metadata consistent with policy.

Sources and items may be revoked for access removal, legal or license
restriction, classification change, compromise, poisoning, staleness,
supersession, owner request, or incident response. Revocation propagates
through lineage. Derived packages are invalidated, quarantined, or explicitly
flagged according to policy before further delivery or reuse. A cache,
checkpoint, replay fixture, or retained provider result cannot bypass current
revocation.

### Governed retrieval

Retrieval is a governed request, not ambient browsing. Its conceptual contract
identifies source scope, purpose, task, item types, classification ceiling,
freshness requirement, size, count and time bounds, trust and retention
requirements, caller identity, and correlation identity.

Results remain untrusted until normalized and validated. Retrieval does not
automatically create or authorize a Knowledge Package; package construction is
a separate governed and attributable step.

Retrieval implementations may later use exact lookup, metadata filtering,
lexical or semantic search, graph traversal, embeddings, hybrid search,
deterministic rules, or human curation. No retrieval technique enters the
public reasoning contract.

### Knowledge Contract Registry

An explicit conceptual Knowledge Contract Registry maps known source types,
item-contract identities and versions, package-contract versions,
normalization contracts, classification rules, provenance requirements,
freshness policies, size and structural bounds, lifecycle, ownership, and
deprecation metadata.

The registry is immutable for one invocation, repository controlled, fail
closed, non-executable, non-authorizing, and independent of connector
implementations. It cannot dynamically import code or register arbitrary
third-party types at runtime. Registration means “known,” not “authorized.”

### Local-first operation

The complete logical Knowledge Architecture is testable on one workstation
using local files, repository and deterministic source fixtures, bounded media
metadata, static approved canon, simulated dynamic sources, freshness and
conflict cases, poisoning and redaction fixtures, revocation, construction,
validation, expiration, and integrity checks.

Standard development and CI require no external database, vector store, search
service, embedding API, paid connector, cloud account, or external AI
credentials. A laptop is not claimed to index or search production-scale
corpora at production speed. Local mode may reduce corpus size and throughput,
but cannot reduce classification, authorization, purpose limitation,
provenance, integrity, redaction, revocation, validation, audit, or failure
semantics.

### Provider and storage neutrality

This decision selects no vector database, embedding model, search engine, graph
database, object store, document database, connector framework, cloud,
source-control provider, or media-asset system. Replaceable interfaces and
independently versioned typed contracts isolate all such choices. Storage and
retrieval implementation details never enter Knowledge Package or semantic
reasoning contracts.

### Movie knowledge

Future movie knowledge may include project canon, mythology and history,
screenplays, characters, relationships, costumes, props, locations, sets,
continuity, shot history, visual, camera, lighting and music styles, voice
profiles, approved assets, legal and licensing restrictions, budgets,
schedules, production status, and generated-media metadata.

Each domain receives its own bounded, independently versioned item contract. No
universal movie-knowledge object or final movie schema is defined here. Movie
knowledge remains governed material and cannot itself approve assets, direct
execution, or alter production policy.

### Knowledge supply chain

The future governed sequence is:

```text
source
→ retrieve
→ normalize
→ classify
→ validate
→ deduplicate
→ detect conflicts
→ redact
→ verify integrity
→ record provenance
→ package
→ authorize
→ deliver
→ expire or revoke
```

Each transformation is attributable and versioned. Ordering does not imply one
monolithic implementation, and this ADR implements none of the stages.

### Audit and evidence

Knowledge audit records safe metadata: source and connector identities and
versions, retrieval request and package identities, purpose, task,
classification, source/item counts, bounded package size, freshness and
conflict summaries, redaction-policy identity, normalization version, integrity
digest, lifecycle state, authorization result, expiration, revocation outcome,
duration, and safe failure classification.

Audit excludes raw source content, raw package payloads, secrets, credentials,
personal data, unrestricted media, hidden reasoning, connector tokens, and
source sessions by default. Existing local JSON Lines audit remains a
development-only facility; production knowledge claims require the durable,
integrity-protected audit design deferred by the M2 checkpoint and ADR-0014.

### Performance, scalability, and cost

Under ADR-0014, retrieval, normalization, redaction, package construction, and
revocation propagation are bounded, profile driven, measurable, cancellable,
workload classified, local-first, budgeted, admitted under load, and eligible
for temporary scale validation.

Metrics may include retrieval, normalization, and package-construction latency;
item/package sizes; source, conflict and redaction counts; freshness failures;
revocation propagation time; permitted cache use; and cost or simulated cost.
This ADR sets no production SLO.

Caching is deferred and governed. A future cache preserves authorization,
purpose, classification, freshness, revocation, retention, provenance, source
version, package identity, and project or tenant isolation. A hit never bypasses
current authorization. Unknown freshness or revocation fails closed.

### Security threat assessment

| Threat | Boundary and architectural mitigation | Deferred control |
| --- | --- | --- |
| Connector compromise | Connector/source boundary; scoped identity, fixed source registration, bounded retrieval, integrity, provenance, and quarantine | Connector process isolation and credential mechanism |
| Source impersonation or substitution | Source identity boundary; registered identity, revision and integrity evidence, connector binding | External trust roots and source attestation |
| Poisoned document or indirect prompt injection | Content/reasoning boundary; content is inert data, bounded typed parsing, provenance, quarantine, and no instruction authority | Domain-specific detection techniques |
| Stale knowledge or false freshness | Temporal boundary; explicit effective/retrieval times, freshness policy, expiry, fail closed | Per-source freshness defaults |
| Provenance forgery or integrity mismatch | Transformation boundary; attributable versions and digests, revalidation before use | Package signing and external timestamping |
| Classification downgrade or redaction failure | Governance/delivery boundary; fail-closed classification, versioned policy, pre-delivery redaction, safe metadata | Final taxonomy and redaction engine |
| Cross-project leakage | Project/package boundary; scoped authorization, minimization, package identity, and future cache isolation | Production storage isolation design |
| Package replay, expiry, or revoked-source reuse | Package/Runtime boundary; current lifecycle, purpose, authorization, expiry, and lineage revocation checks | Distributed revocation propagation protocol |
| Unauthorized purpose reuse | Task/package boundary; explicit purpose and reconstruction/reauthorization | Final purpose-policy language |
| Retrieval fan-out, excessive size, or denial of service | Admission/resource boundary; source, result, size, depth, duration, and budget bounds | Numeric profile limits and worker isolation |
| Malicious media metadata or hidden executable content | Parser/execution boundary; typed inert payloads, no execution handles, bounded parsing | Format-specific safe parser selection |
| Citation spoofing or trust inflation | Evidence boundary; stable source identity, explicit trust, provenance, conflict preservation | Citation normalization and trust taxonomy |
| Conflict suppression | Normalization/package boundary; material conflict and uncertainty are mandatory and attributable | Domain resolution policy |
| Audit leakage | Evidence/audit boundary; safe metadata only and classification-aware detail | Production audit backend and retention policy |
| Cache authorization bypass | Cache/use boundary; fresh authorization, purpose, version, revocation and project checks on every hit | Cache technology and invalidation protocol |
| Provider retention mismatch | Delivery/provider boundary; provider eligibility follows classification, purpose and retention policy | External-provider contractual controls |

Built-in Python connectors, normalizers, classifiers, redactors, package
builders, and retrieval strategies remain trusted in-process code and are not
sandboxed. Dynamic third-party connectors, normalizers, classifiers, redactors,
package builders, retrieval strategies, and item contracts remain unsupported.
Future third-party support requires separate architecture for signing,
provenance, trust roots, isolation, revocation, upgrade policy, compatibility,
and incident response.

Production operation is not justified by deterministic fixtures, cooperative
thread cancellation, local JSON Lines audit, or trusted in-process Python.
Before sensitive, effectful, long-running, or production-scale knowledge work,
separate accepted designs and implementations must address process or worker
isolation, enforceable cancellation, durable and integrity-protected audit,
production storage, connector credential scope, privacy and residency,
revocation propagation, incident response, and package signing or encryption
where classification and threat analysis require them.

## Alternatives Considered

### 1. Direct source-system access from reasoning providers

This couples providers to sources, exposes ambient credentials, defeats
minimization and purpose control, and turns provider behavior into policy.
Rejected.

### 2. One universal knowledge object

A growing optional-field object would couple unrelated source domains, blur
versioning and bounds, and require consumers to understand everything.
Rejected in favor of a small envelope plus typed payloads.

### 3. Vector-database-centric architecture

This prematurely treats one retrieval technique and storage product category as
the knowledge model, introducing embedding and vendor lock-in. Rejected.

### 4. Prompt-time retrieval inside provider adapters

This hides source access, provenance, classification and policy inside a
replaceable intelligence layer and prevents consistent audit. Rejected.

### 5. Unbounded repository or document ingestion

This increases leakage, poisoning, cost, denial-of-service, retention, and
freshness risks without purpose limitation. Rejected.

### 6. Provider-neutral Knowledge Layer with bounded typed Knowledge Packages

Selected. It isolates reasoning from sources while supporting security, source
and provider neutrality, local-first development, auditability, provenance,
evolution, movie continuity and asset governance, and future scale.

## Consequences

Positive consequences include reasoning isolation from sources; storage and
retrieval independence; traceability and freshness awareness; preservation of
conflict and uncertainty; resistance to poisoning and instruction injection;
purpose limitation and bounded context; local reproducibility; provider
neutrality; controlled revocation; improved future movie continuity and asset
governance; and future replay and comparison using approved evidence.

Costs and risks include more contracts, provenance overhead, redaction and
package-construction complexity, freshness management, source-registration
administration, conflict and retention governance, future connector
maintenance, slower initial delivery, and over-abstraction risk.

Mitigations are a narrow first source type, deterministic fixtures, one item
family at a time, no external connector in the first implementation, no vector
database selection, explicit bounds, measurable profiles, periodic review, and
simplicity over cleverness.

## Roadmap Impact

The conceptual sequence is:

1. ADR-0015 Knowledge Architecture.
2. ADR-0016 Autonomy and Approval Policy.
3. M3.1 Semantic Contract Registry and first schemas.
4. M3.2 Deterministic `GenerateOptions` implementation.
5. M3.3 Local concurrency and performance baseline.
6. M3.4 Knowledge Contract Registry and bounded Knowledge Packages.
7. M3.5 Plan IR.
8. M3.6 First external reasoning provider.
9. Later: governed connectors, search, indexing, production audit, and
   scale-out.

This ADR implements none of these items.

## Unresolved Questions

The following remain separate, evidence-based decisions:

- first source type, item family, and package contract;
- classification and trust taxonomies;
- freshness and retention defaults;
- maximum package and item sizes and retrieval-result limits;
- redaction policy language;
- provenance format and citation normalization;
- conflict representation;
- source ownership and human-curation processes;
- revocation propagation;
- cache eligibility and invalidation;
- connector protocol and authentication;
- production storage;
- indexing, search, embedding, and graph strategies;
- media metadata, legal and license metadata;
- personal-data governance and regional residency;
- package signing and encryption;
- approved web-source policy;
- acceptable laptop corpus size; and
- movie-domain schema sequencing.

## Acceptance Criteria

This ADR is acceptable when it establishes that:

- reasoning cannot directly access source systems;
- connectors are replaceable and non-authorizing;
- the Knowledge Layer is not a second Runtime;
- knowledge remains untrusted and inclusion implies neither truth nor
  permission;
- small item envelopes plus independently versioned typed payloads prevent a
  God object;
- packages are immutable, bounded, purpose-limited, inert, and independently
  authorized;
- provenance, freshness, classification, redaction, integrity, conflicts, and
  uncertainty are preserved;
- source revocation propagates through package lineage;
- local development and CI need no external database or paid service;
- no storage, search, embedding, graph, connector, cloud, or provider product is
  selected;
- dynamic third-party knowledge code remains unsupported;
- audit, cancellation, isolation, and performance limitations are explicit;
  and
- no implementation or dependency accompanies this decision.

## Independent Review Perspectives

| Perspective | Conclusion |
| --- | --- |
| Enterprise Software Architecture | The layer separates governance from storage and source implementations without creating a second Runtime. |
| Knowledge and Information Architecture | Stable identities, typed items, provenance, time, conflict, and lifecycle prevent a universal knowledge object. |
| Runtime Authority | Runtime retains task-use authorization, approval, policy, budgets, and execution. |
| Product Security | Sources remain untrusted; boundedness, inert content, purpose, classification, integrity, and revocation fail closed. |
| Data Governance | Classification, residency, purpose, minimization, retention, and deletion are explicit policy inputs. |
| Privacy and Retention | Delivery is minimized and redacted; provider retention must match policy; audit excludes raw content. |
| AI Governance | Reasoning receives bounded packages rather than ambient source access, and embedded instructions convey no authority. |
| Search and Retrieval Architecture | Retrieval is independently replaceable and cannot automatically create or authorize a package. |
| Distributed Systems | Stable identity, immutable packages, lineage, expiry, and revocation semantics precede distributed storage or caching. |
| Local-First Developer Experience | Deterministic fixtures exercise the complete governance path without paid or external services. |
| Media Pipeline Architecture | Movie domains remain separate typed families; no movie God Object or final schema is frozen. |
| Provider Neutrality | No source, connector, storage, retrieval, embedding, cloud, or AI vendor enters public contracts. |
| Supply-Chain Security | Dynamic third-party knowledge code is deferred pending signing, provenance, isolation, revocation, and incident response. |
| Independent Verification | No contradiction with ADR-0010 through ADR-0014 was identified; deferred product and policy choices remain explicit. |

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [ADR-0012: Evolvable and Reversible Reasoning Architecture](ADR-0012-evolvable-reasoning-architecture.md)
- [ADR-0013: Semantic Reasoning Contracts](ADR-0013-semantic-reasoning-contracts.md)
- [ADR-0014: Local-First Scalability, Performance, and Resource Efficiency](ADR-0014-local-first-scalability-performance-efficiency.md)
- [M2 Architecture Checkpoint](../reviews/m2-architecture-checkpoint.md)
- [Threat Model](../security/threat-model.md)
- [Secure Development](../security/secure-development.md)
- [Component Approval](../security/component-approval.md)
- [Upgrade Policy](../security/upgrade-policy.md)

## Verification

Acceptance requires ADR validation, repository-relative reference validation,
documentation-only scope verification, whitespace validation, and existing
Markdown validation when available. This decision adds no runtime code, test,
schema, workflow, connector, database, vector store, embedding model, search
engine, graph database, external API, provider, dependency, or infrastructure.
