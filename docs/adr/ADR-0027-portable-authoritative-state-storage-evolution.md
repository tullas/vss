# ADR-0027: Portable Authoritative State and Storage Evolution

## Status

Accepted

## Date

2026-08-24

## Context

VSS begins local-first with files, Git, JSON/YAML, local Runtime/provider APIs,
and small provider-neutral infrastructure contracts. Later evidence may justify
relational state, object storage, jobs, indexes, distributed workers, and
regional operation. Selecting a lowest-common-denominator data model would
waste useful database features; leaking vendor identity and storage semantics
into creative contracts would make migration, customer exit, recovery, and
autonomous maintenance unsafe.

[ADR-0023](ADR-0023-minimal-component-open-source-resource-efficient-implementation.md)
owns when new components are justified. [ADR-0022](ADR-0022-cross-plane-admission-resource-bounds-artifact-consistency.md)
owns immutable artifact consistency. [ADR-0026](ADR-0026-studio-governance-principal-identity-lifecycle-operations.md)
owns lifecycle authority. This ADR defines only the persistence portability
and evolution seam.

## Decision

VSS uses portable canonical domain contracts and repository interfaces while
allowing vendor-specific storage/database capabilities behind explicit
adapters, owned migrations, and conformance evidence.

### Authoritative semantics and adapters

Domain and creative logic depend on canonical VSS identities, contracts, and
repository operations—not SQL dialect, table layout, ORM entity, database row
ID, object-store key/version ID, filesystem inode/path, search score, or vendor
transaction token.

Authoritative identifiers and semantic versions are created and validated by
VSS domain rules. Persistence adapters map them to physical representations.
A storage-generated identifier may be retained as operational metadata but
cannot replace or silently alter canonical identity.

Repository interfaces express domain operations and required consistency,
atomicity, ordering, isolation, retention, and query semantics. They are not a
generic CRUD abstraction. SQL/schema/index/migration ownership is isolated in
the persistence adapter or infrastructure boundary rather than creative/domain
logic.

### Useful features without lock-in denial

Adapters may use transactions, constraints, JSON/document fields, partitioning,
full-text search, vector extensions, object versioning, lifecycle policies,
change feeds, or other vendor-specific features when they materially improve
correctness, safety, performance, or cost.

Every such optimization declares:

- the canonical semantic requirement it implements;
- whether it is authoritative or derived;
- fallback/export/rebuild/migration behavior;
- compatibility and failure semantics;
- operational and licensing constraints; and
- adapter conformance tests against portable domain behavior.

Portability means tested semantic equivalence and an explicit exit path, not
feature suppression. No adapter may expose a vendor feature as new domain
authority or contaminate canonical resource identities/contracts.

### Schema ownership and evolution

Persistence schema versions and migrations are owned by their adapter. Every
deployed application and schema version declares a compatibility window.
Expand/migrate/contract is preferred when it permits safe mixed-version
operation. Migration state, checkpoints, verification, and recovery are
explicit and auditable.

Destructive or major migrations follow ADR-0026. They bind exact source/target
versions, environment, data/tenant scope, transformation digest, compatibility
evidence, backup/restore proof, validation queries, cost/time bounds, and
rollback/reconciliation/forward-recovery plan. Partial completion never becomes
implicit success. Drift invalidates approval.

### Backup, export, recovery, and portability proof

Logical export formats preserve canonical identities and semantics for
migration, customer exit, inspection, and long-term accessibility. Physical
backups preserve engine-native state for efficient same-engine recovery. Where
both needs apply, both are required: logical export is not crash recovery and a
physical snapshot is not portable migration evidence.

Backups are evidence only after integrity checking and periodic restore tests.
Portability is evidence only after a periodic bounded drill imports a logical
export through another conforming adapter or an independently maintained
reference implementation and verifies semantic invariants. A document claiming
vendor independence without such a path is insufficient.

Drills cover at least loss of the current vendor, failed major upgrade, partial
migration, interrupted export/import, incompatible application/schema window,
and reconciliation of writes around a cutover. Production drills additionally
respect tenant isolation, residency, encryption, retention/deletion, rights,
SLA, audit, and cost constraints.

### Derived indexes and projections

Vector indexes, search indexes, embeddings, caches, thumbnails, analytics
views, materialized projections, and recommendation features are derived and
rebuildable. They are never authoritative for rights, ownership, tenant scope,
canon, creative decisions, approval, budget/commercial facts, audit, deletion
obligations, or production admission.

A derived index records source identities/versions, builder/model/version,
policy/purpose, freshness, and rebuild/invalidation state as applicable. Missing
or stale indexes may reduce capability or require rebuild; they cannot fabricate
authority or override the source of record.

### Storage-format migration

Moving between filesystems, object stores, databases, archives, or media
containers preserves:

- VSS logical identity, version, and authoritative digest semantics;
- tenant and resource scope isolation;
- exact derivative lineage and Media BOM/provenance associations;
- rights, retention, deletion, residency, and classification obligations;
- canon/decision, approval, commercial, and audit associations; and
- logical exportability and declared reproducibility/preservation level.

Physical keys, chunks, compression, database layout, and locations may change.
The migration independently verifies source and destination before promotion,
records omissions/conflicts, and keeps a governed recovery path until the
declared point of no return.

## UNKNOWN_UNKNOWN_REVIEW findings

The bounded major-boundary review produced three material missing seams:

| Risk or missing seam | Required decision | Disposition |
| --- | --- | --- |
| Restoring an old backup can resurrect deleted, revoked, expired, or tenant-ineligible state. | Restored state remains isolated until reconciled against current deletion/legal-hold, rights/revocation, tenant, policy, and credential state; restore success is not production admission. | `mitigate_before_acceptance` — permanent restore gate. |
| A conforming adapter can still drift on transaction, ordering, null/unknown, collation, or failure semantics. | Conformance fixtures bind domain invariants and failure behavior; high-risk cutovers require source/destination comparison and explicit unresolved-difference handling. | `defer_with_trigger` — required with the first second adapter. |
| Vendor/site loss can make a logical export unusable when keys, codecs, schemas, or readers are unavailable. | Portability evidence includes independently recoverable format/schema/reader and governed key-recovery dependencies without embedding secrets; unavailable required dependencies fail the drill. | `mitigate_before_acceptance` — required of export/DR contracts. |

No database, storage service, or migration tool was introduced.

## Consequences

VSS can begin with local files/embedded state, adopt a relational database or
object store when evidence requires it, and use valuable product-specific
features without turning them into platform semantics. Migration and recovery
become testable obligations rather than architectural claims.

Costs include adapter ownership, conformance suites, canonical exports,
restore/portability drills, and explicit compatibility windows. These are paid
when a persistence implementation is introduced, not by speculative services
in this milestone.

## Deferred

- database, object storage, queue, workflow, ORM, migration, search, and vector products;
- repository APIs, canonical export schemas, adapter SDKs, and conformance fixtures;
- backup/archive infrastructure, retention/deletion executors, encryption/key management;
- migration schedules, availability targets, recovery objectives, and regional topology.

Selection follows ADR-0023 and implementation follows ADR-0026 with an
applicable bounded [UNKNOWN_UNKNOWN_REVIEW](../architecture-boundary-review.md).

## Acceptance criteria

- canonical identity and semantics are independent of vendor object IDs and layouts;
- persistence ownership is isolated from creative/domain logic through meaningful repositories;
- vendor-specific features remain permitted behind adapters and conformance tests;
- logical exports and physical backups have separate purposes and tested restore/import evidence;
- portability is tested periodically rather than asserted;
- derived vector/search/cache/projection state never becomes authoritative governance state;
- migrations preserve tenant, rights, lineage, retention, audit, and export semantics;
- no database, storage, queue, policy, orchestration, or identity product is selected.
