# ADR-0025: Scoped Studio Resources, Rights, Canon, and Provenance

## Status

Accepted

## Date

2026-08-24

## Context

VSS is a multi-tenant, multi-universe, multi-production studio platform. A
particular story world, customer, production, storage system, or provider must
not become a platform assumption. Existing movie contracts prove bounded,
inert semantic artifacts, while [ADR-0021](ADR-0021-studio-workload-planes-specialized-execution.md)
and [ADR-0022](ADR-0022-cross-plane-admission-resource-bounds-artifact-consistency.md)
reserve logical Asset/Data Plane and exact artifact-consistency seams.

The next reusable production capability needs stable distinctions among scope,
identity, artifacts, reusable assets, rights, canon, provenance, and
dependencies. Without them, equal bytes could be mistaken for permission,
generated output for an owned reusable asset, a revised creative decision for
a historical rewrite, or cached material for an authorized production input.

This ADR defines constitutional resource semantics only. It does not implement
a catalog, registry, ledger, database, storage layout, resolver, legal engine,
export operation, media format, or universal resource schema.

## Decision

VSS adopts explicit scoped identity, admission, rights, decision, provenance,
and dependency boundaries. Validation or possession may establish facts; only
the owning policy and Runtime paths can admit governed effects.

### Tenant, universe, and production hierarchy

The logical hierarchy is:

```text
tenant
  -> optional universe
      -> production
          -> sequence / scene / shot as domain contracts require
```

A tenant is the default isolation and policy boundary. A universe groups
deliberately shared creative state across productions. A production may belong
to one universe or be standalone. Sequence, scene, and shot are narrower
domain scopes, not mandatory fields on every platform resource.

Every governed resource has a platform-stable logical identity, an owning
tenant, an explicit scope, and a version or revision where its meaning can
change. Authoritative identity and semantics do not depend on filesystem path,
object-store key, database row ID, provider ID, process, region, or current
physical location.

Tenant isolation is deny-by-default. Equal content digests, shared physical
storage, cache presence, knowledge of an identifier, operational possession,
or access to one derivative never implies discovery, access, rights, or reuse
across tenants. Cross-tenant sharing requires an explicit governed transaction
whose source authority, destination scope, purpose, rights, policy, and audit
evidence are independently admitted.

### Artifact and asset

An **artifact** is an immutable, identified output or intermediate associated
with an exact production activity and lineage. Generation creates an artifact;
it does not create ownership, clearance, or reusable-asset status.

An **asset** is an artifact or externally admitted resource that has passed an
explicit reusable-asset admission for a stated scope, purpose, lifecycle,
rights state, integrity binding, and policy version. An asset can have multiple
immutable revisions. Mutable labels such as `latest` may aid discovery but are
never admitted production input identities.

Derivative lineage binds exact source revisions, transformations, and output
revisions. A new derivation never mutates its ancestors. Resealing changed
content under an old logical claim cannot legitimize substitution.

Scope promotion is asymmetric. Movement from shot to production, production to
universe, universe to tenant, or tenant to VSS-shared visibility/reuse requires
explicit admission at every broader boundary. A broader admission may be
denied or narrower than the source rights. Moving or copying bytes, matching a
digest, or granting storage access never performs promotion. Narrowing access
may be allowed by policy but does not erase upstream obligations or lineage.

### Rights and commercial boundaries

Rights facts use closed ownership/source classes where a later contract needs
them: `customer_owned`, `vss_owned`, `third_party`, `public_domain`,
`open_licensed`, and `joint`. Classification alone is not clearance.

Rights state represents positive grants and negative restrictions. Relevant
dimensions may include owner/licensor, subject, territory, time, purpose,
media, audience, attribution, modification, reuse, training, redistribution,
sublicensing, confidentiality, residency, revocation, and source evidence.
Unknown applicable rights or conflicting restrictions fail closed.

Derived rights compose by intersection: a derivative cannot gain a permission
that an applicable source does not grant. Negative rights are first-class and
survive copying, transformation, promotion, and storage migration unless an
independently authoritative change explicitly supersedes them.

Machine-enforceable policy facts and legal interpretation are distinct.
Contracts may enforce explicit scopes, dates, territories, purposes,
prohibitions, and required evidence. Ambiguous ownership, fair-use questions,
contract interpretation, or conflicting law require later specialized policy
and/or authorized human legal review; VSS does not encode a universal legal
adjudicator.

Generation is not ownership. Storage is not ownership. Access is not
redistribution permission. Operating the service grants VSS no inferred
training, reuse, publication, sale, or cross-customer rights.

Export, sharing, publication, licensing, sale, and scope promotion are explicit
governed transactions. Their approvals bind exact resources/versions,
destination, purpose, rights snapshot, policy, environment, and operation.
They remain subject to Runtime authorization under
[ADR-0016](ADR-0016-autonomy-approval-execution-authority.md).

A Rights Registry and a Commercial Ledger are conceptually separate. Rights
state describes permissions, restrictions, obligations, and evidence. A
commercial ledger describes price, royalty, allocation, invoice, revenue,
spend, and budget facts. Payment does not create rights; rights do not prove
payment. Physical co-location is permitted only behind separate interfaces and
access policy.

### Decision graph and versioned canon

Creative decisions are first-class governed inputs with identity, version,
scope, author/proposer accountability, status, evidence, and dependencies.
Canon is a versioned decision set or snapshot, not mutable global truth.

A production pins the exact canon and decision versions used by an admitted
input snapshot. Changing canon or a creative decision creates a new version,
records supersession where appropriate, and produces impact analysis over
dependents. It never silently rewrites historical inputs, reviews, approvals,
artifacts, or provenance.

Draft, proposed, reviewed, accepted, rejected, deprecated, and superseded
states remain distinct where a domain defines them. Acceptance in one creative
scope grants no Runtime, rights, commercial, publication, or workflow
authority.

### Media BOM, provenance, preservation, and reproducibility

Every admitted media output must be able to produce an exportable Media Bill
of Materials and provenance view appropriate to its lifecycle. The view binds,
where applicable:

- exact source, reference, asset, canon, and decision identities/versions;
- input/output digests and derivative lineage;
- transformation/operation and contract versions;
- provider, model, model version, strategy, parameters, bounded projection,
  and reference influence;
- software/runtime/environment identities needed by the claimed level;
- rights/purpose and admission evidence references without embedding secrets;
- preservation class and reproducibility level; and
- known limitations, omissions, conflicts, and unavailable dependencies.

Preservation classes distinguish at least disposable/intermediate review
material, retained production artifacts, reusable assets, and archival records;
later contracts define retention and durability obligations. Reproducibility
levels distinguish identity/provenance reproducibility, semantic
reproducibility, operational reproducibility, and exact-byte reproducibility.
A level is claimed only when evidence supports it; nondeterministic provider or
media behavior is not presented as exact replay.

Provenance remains portable and exportable. Future adapters may map it to
C2PA-, MovieLabs-, or other industry-style metadata, but external formats,
signatures, manifests, or registries never become VSS policy or Runtime
authority merely by import.

### Incremental production dependency model

Movie production is modeled as an incremental dependency graph. Source,
asset, canon, decision, contract, policy, or provider changes invalidate only
artifacts whose declared dependencies or eligibility are affected. Unknown
required dependency impact fails closed; unrelated optional uncertainty does
not invalidate the whole studio.

Reuse is considered before adaptation, and adaptation before generation, only
when exact identity, quality, purpose, scope, rights, canon, freshness, and
policy permit it. Cache availability or cost never makes ineligible reuse
eligible. Reused or adapted outputs retain their original and new lineage and
must pass output admission for the destination scope.

Invalidation means “requires reassessment or rebuild,” not automatic deletion,
regeneration, or execution. Runtime remains the authority for any effectful
work.

## UNKNOWN_UNKNOWN_REVIEW findings

The bounded major-boundary review produced three material missing seams:

| Risk or missing seam | Required decision | Disposition |
| --- | --- | --- |
| Customer deletion/retention obligations can conflict with immutable lineage and long-horizon audit. | Separate payload availability from bounded identity/provenance tombstones; policy decides what evidence may lawfully remain, and unknown conflict blocks reuse/export. | `mitigate_before_acceptance` — incorporated above and required of later contracts. |
| Rights may be invalidated after many derivatives exist. | Rights revocation/eligibility changes propagate through dependency impact; affected outputs are quarantined from new use/promotion while historical evidence remains governed. No silent deletion or continued eligibility. | `mitigate_before_acceptance` — permanent downstream admission seam. |
| 100x assets and multi-year dependency history can make impact review itself unbounded. | Later graph contracts require bounded traversal, resumable evidence, and explicit incomplete-impact status that fails closed for affected use; they must not trigger automatic mass regeneration. | `defer_with_trigger` — required before persistent dependency-graph implementation. |

No additional service or feature was introduced.

## Consequences

Near-term production contracts must carry or reference explicit tenant,
production/universe scope, immutable resource versions, rights qualification,
canon/decision versions, and lineage where applicable. They need not adopt one
universal envelope or implement every future registry.

The model permits standalone productions, shared universes, customer exit,
vendor-neutral storage, incremental rebuilds, and future provenance export
without granting cross-tenant access or over-prescribing infrastructure.

Costs include more explicit admission and version references, impact analysis,
and rights uncertainty handling. Those costs are intentional; silent reuse or
historical mutation is more dangerous.

## Deferred

- concrete tenant, universe, asset, rights, decision, canon, BOM, and lineage schemas;
- authentication, SSO/RBAC, encryption tenancy, and residency implementations;
- catalog, Rights Registry, Commercial Ledger, export/share executor, and legal-policy engine;
- preservation storage, deletion workflows, C2PA/MovieLabs adapters, and signing;
- dependency-graph storage, rebuild scheduler, and production generation behavior.

Each requires a later executable vertical slice with strict contracts,
authority checks, adversarial tests, and an
[UNKNOWN_UNKNOWN_REVIEW](../architecture-boundary-review.md) when it creates a
major architecture boundary.

## Acceptance criteria

- tenant isolation is default and cross-tenant reuse requires explicit admission;
- broader scope promotion is asymmetric and never inferred from bytes or possession;
- artifact, asset, identity, revision, and lineage are distinct;
- negative rights and fail-closed derivative composition are explicit without pretending to universal legal adjudication;
- generation, storage, access, ownership, redistribution, and training rights are not conflated;
- canon/decision changes version and impact history rather than mutate it;
- Media BOM/provenance, preservation, and reproducibility remain exportable and evidence-qualified;
- incremental reuse does not bypass rights, policy, output admission, or Runtime.
