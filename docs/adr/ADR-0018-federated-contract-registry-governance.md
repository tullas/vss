# ADR-0018: Federated Contract and Registry Governance

## Status

Proposed

## Date

2026-08-02

## Context

VSS contains or anticipates independent contract domains for capabilities,
providers, workflows, semantic reasoning, Knowledge Items and Packages, Context
Objects, performance evidence, Plan IR, approvals, execution artifacts, and
movie-production concepts. These domains share recurring engineering concerns:
identity, versioning, ownership, lifecycle, compatibility, bounds, validation,
canonicalization, integrity evidence, safe schema loading, deterministic
registration, migration, retirement, audit-safe metadata, and local conformance.

Without a common constitutional standard, their meanings can drift. Drift can
produce unsafe schema loading, implicit version downgrade, ambiguous ownership,
incompatible lifecycle meanings, indefinite deprecation, inconsistent digest
claims, cross-registry coupling, duplicated security defects, migration dead
ends, and pressure for a single universal registry.

Uniform governance does not require uniform code. The existing registries were
built at different milestones and legitimately use different domain models,
schema mechanisms, lifecycle states, and bindings. An immediate common
framework or retrofit would create abstraction before shared semantics have
been proven.

The permanent rule is:

> VSS contract registries are federated. Each domain owns its contracts,
> schemas, compatibility, lifecycle, validation, and registration. Shared
> governance defines required qualities and interoperability rules, but no
> central registry owns, mutates, loads, authorizes, or executes all contract
> domains.

Registration means only structurally known. It never means authorized,
approved, true, trusted, execution-eligible, provider-eligible, source-accessible,
disclosable, or active outside the owning domain's policy.

This ADR is documentation only. It neither creates a shared registry framework
nor authorizes refactoring of an existing registry.

## Decision

VSS will govern contract systems as a federation of independently owned,
versioned, constructed, validated, and lifecycle-managed domain registries.
Cross-domain use is expressed through explicit, inert, versioned compatibility
mappings. Common obligations define outcomes and security properties, not one
implementation, base class, schema, service, lifecycle enumeration, or error
hierarchy.

### Relationship to existing decisions

- [ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md): Runtime remains
  the sole execution and authorization authority. Registries cannot grant
  permission, approve, invoke capabilities/workflows, autonomously select a
  provider, or become a second Runtime.
- [ADR-0011](ADR-0011-engineering-principles.md): explicit contracts, least
  privilege, fail-closed behavior, provider neutrality, local-first operation,
  bounded resources, auditable decisions, simplicity, and supply-chain
  governance apply to every domain.
- [ADR-0012](ADR-0012-evolvable-reasoning-architecture.md): reasoning tasks,
  strategies, provider adapters, and knowledge implementations retain separate
  evolution and replacement boundaries.
- [ADR-0013](ADR-0013-semantic-reasoning-contracts.md): envelope-versus-typed-
  payload discipline, independent family versions, explicit translators, and
  prohibition of silent semantic loss and God Objects remain authoritative.
- [ADR-0014](ADR-0014-local-first-scalability-performance-efficiency.md):
  loading and validation are bounded, reproducible, measurable, local-first,
  cost-aware, and make no unsupported production claims.
- [ADR-0015](ADR-0015-knowledge-architecture.md): classification, trust,
  freshness, provenance, retention, revocation, conflict, and uncertainty remain
  Knowledge-domain semantics. Federation cannot flatten them into universal
  metadata.
- [ADR-0016](ADR-0016-autonomy-approval-execution-authority.md): contract and
  registry admission grants no approval, autonomy, or execution authority.
- [ADR-0017](ADR-0017-context-assembly-architecture.md): the Context Contract
  Registry remains independent of Semantic, Knowledge, Runtime, and provider
  registries; explicit mappings do not create a God Registry.

Existing M2 and M3 implementations demonstrate repository-built registration,
immutable models, exact resolution, integrity evidence, and hardened schema
loading in several forms. This ADR recognizes those patterns but does not
declare older implementations invalid or require refactoring merely for visual
uniformity.

### Domain ownership

Each registry belongs to one bounded domain:

- Capability Registry: capability identity, commands, permissions, handlers,
  manifests, and compatibility.
- Provider Registry: provider type/identity, API compatibility, admitted
  implementation binding, trust, and lifecycle.
- Workflow Registry: workflow identity, grammar, operation compatibility, and
  lifecycle.
- Semantic Contract Registry: semantic tasks, envelopes, object families, and
  semantic compatibility.
- Knowledge Contract Registry: Knowledge Item/Package envelopes, item families,
  package contracts, and knowledge-contract lifecycle.
- Context Contract Registry: context families, task/knowledge compatibility
  mappings, and assembly-contract lifecycle.
- Performance evidence ownership: report formats and profile compatibility;
  this needs a registry only if future requirements justify one.
- Future Plan IR Registry: Plan IR and node-family compatibility.
- Future Approval Contract Registry: approval artifact formats and lifecycle,
  never approval authority.

Future domains follow the same ownership rule. Every registry and public
contract family identifies an accountable domain owner, technical owner,
security owner, compatibility/migration owner, lifecycle owner, schema owner,
and retirement authority. One team may initially hold several roles, but each
role remains explicit. Ownership is not inferred from the latest committer.

Lifecycle or compatibility changes require accountable review. Documentation
is sufficient for initial repository ownership; this ADR does not mandate a
CODEOWNERS change or external ownership service.

### Federation model

Each domain registry is separate, independently versioned, independently
constructed and tested, immutable for an invocation, repository-owned,
deterministic, non-authorizing, and fail closed. It is non-executable except for
narrow retrieval of already admitted built-in bindings where the owning domain
requires that behavior. Retrieval of a binding is not authorization to use it.

Federation edges are explicit mappings, for example:

- a semantic task/version admits a context family/version;
- a context family/version admits knowledge package/item family versions and an
  exact purpose mapping;
- a capability version requires a provider type/identity/API version;
- a workflow grammar/version admits operation identities/versions;
- a future Plan IR node/version references admitted operation versions; and
- a future approval artifact binds an exact plan digest and operation versions.

A registry cannot inspect arbitrary internals of, mutate, dynamically import,
or assume ownership of another registry. A mapping joins compatibility facts,
not implementation state or authority.

### No God Registry or universal contract

VSS prohibits:

- one registry containing every VSS contract;
- one mutable global registry or universal registration API;
- one universal Contract Object or base class accumulating every domain field;
- one universal schema with optional fields for all domains;
- one universal lifecycle manager with execution or authorization authority;
- one central runtime contract-registration or installation service;
- reflection, module scanning, entry-point discovery, or arbitrary plugin
  directories for authoritative contract discovery;
- forced inheritance across contract domains;
- one registry required for every unrelated validation operation; and
- unnecessary blast radius where failure in one domain disables another.

Shared governance is not a shared runtime dependency. A common utility may be
introduced later only after a repeated requirement is proven, the semantics are
genuinely identical, security behavior is preserved, the utility contains no
domain policy, packages remain independently testable, adoption is incremental,
and no public contract change is forced. This ADR requires no common package,
interface, base class, lifecycle enum, error type, or framework.

### Common registry obligations

Every contract registry defines, or explicitly documents why inapplicable:

1. domain identity;
2. registry identity and version;
3. contract identity and version;
4. schema or validation identity and supported dialect/version;
5. lifecycle state and owning-domain meaning;
6. compatibility policy;
7. accountable and security owners;
8. migration and retirement owners;
9. deprecation and retirement metadata;
10. centralized bounds;
11. validation and failure behavior;
12. canonicalization behavior when applicable;
13. digest behavior when applicable;
14. authoritative registration source;
15. built-in implementation trust classification when applicable;
16. audit-safe metadata policy; and
17. local conformance coverage.

The obligation is an explicit declaration, not accumulation of meaningless
fields in one universal payload. Domain semantics remain in domain contracts.

### Registry identity and snapshot digest

A registry exposes a stable domain-specific identity/version such as
`semantic_contract_registry/1`, `knowledge_contract_registry/1`,
`context_contract_registry/1`, or `provider_registry/1`. Exact identifiers stay
under domain ownership.

Where a snapshot digest is used, its documented canonical input includes
security-significant registry identity/version, admitted contract identities and
versions, lifecycle states, compatibility mappings, schema identities/digests,
admitted built-in implementation identities where relevant, and policy
metadata. It excludes wall time, PID, hostname, request authorization, secrets,
mutable state, and filesystem location when content identity suffices.

Digest equality means deterministic integrity evidence only. It is not
authorization, authenticity, signature, approval, trust, truth, or activation.

### Contract identity

Every public or cross-domain contract has a stable identity, explicit version,
owning domain, lifecycle, schema/validation identity, compatibility rules,
bounds, deprecation path, and retirement policy.

Identity cannot be inferred solely from a Python class, module/file path,
working directory, provider-native type, or registration order. Identifiers are
bounded, conservative, stable, provider/filesystem neutral, audit safe, and
have explicit case and Unicode behavior.

### Independent versioning and exact resolution

Registry, envelope, task, object/item/context family, provider API, workflow
grammar, capability API, and future plan/approval/execution artifacts version
independently. Changing one does not automatically change all others.

The default is exact-version compatibility unless the owning domain declares a
bounded explicit mapping. Authoritative paths prohibit implicit semantic-version
ranges, automatic upgrade/downgrade, silent coercion or field dropping,
`latest`, floating versions, wildcard identities, lexical nearest versions,
registration-order priority, and missing-version fallback. Unknown or ambiguous
identity/version resolution fails closed.

Semantic version strings may describe implementations, but `1.2.0` is not
assumed compatible with `1.1.0`. Compatibility meaning is explicit.

### Compatibility mappings

Cross-version and cross-registry mappings identify source and target
identities/versions, mapping identity/version and owner, lifecycle, effective
period, compatibility classification, validator, translator identity/version
where required, limitations, deprecation deadline, rollback path, bounds, and
failure behavior.

Conceptual classifications may include exact, backward compatible, forward
readable, translator required, and incompatible. Each domain finalizes its
taxonomy. Unknown compatibility fails closed. A mapping cannot grant permission,
authorization, execution, disclosure, source access, or approval.

### Translators

Translation is explicit, owned, bounded, versioned, and independently validated
against its target. A translator declares source/target identities and versions,
owner, lifecycle, bounds, deterministic requirements, semantic-loss policy,
limitations, and rollback/migration behavior.

Where applicable, it preserves classification, trust, purpose, provenance,
assumptions, conflicts, uncertainty, limitations, expiry, retention, and
revocation. It fails rather than silently discard mandatory semantics.

A translator cannot authorize, downgrade classification, promote trust, broaden
purpose, extend expiry/retention, remove revocation, hide conflict/uncertainty,
invent provenance, silently synthesize unknowns, invoke capabilities/workflows,
or execute. No generic automatic schema translator is selected.

### Lifecycle governance

Federation provides a common conceptual vocabulary only where meanings align:

- `proposed`: not admitted to authoritative use;
- `active`: admitted under explicit domain policy, not automatically authorized
  for an invocation;
- `deprecated`: bounded existing use may continue during a declared window;
  replacement, deadline, and new-use restrictions are documented;
- `disabled`: ordinary/new resolution fails closed; retention is only for
  policy-permitted migration, historical validation, or audit; and
- `retired`: removed from ordinary resolution; historical interpretation needs
  an explicit retained-validator or archival strategy.

Domains may add experimental, shadow, suspended, revoked, constructed,
validated, expired, or other states. A shared word must document its domain
meaning. VSS does not force one lifecycle enumeration that erases domain
semantics. Unknown lifecycle fails closed; callers cannot select lifecycle;
changes require review and audit evidence.

### Deprecation and retirement

Deprecation records identity/version, replacement if known, reason category,
owner, effective date/release, compatibility window, affected consumers,
migration and rollback paths, retirement criteria, and security implications.
Indefinite undocumented deprecation is prohibited.

Emergency security disablement may omit a normal window only when explicit,
auditable, narrowly scoped, recoverable, and followed by incident and
compatibility review.

Retirement accounts for producers, consumers, stored artifacts, audit
interpretation, replay, migrations, rollback, retention/legal obligations,
security defects, local fixtures, and release artifacts. Apparent lack of a
current code path is insufficient reason to delete a contract.

Historical validators, where required, are isolated, bounded, non-authorizing,
read-only where practical, excluded from new production use, and security
maintained or explicitly quarantined.

### Schema governance

Where JSON Schema is used, the owning domain requires an explicit supported
dialect, conservative identifiers, appropriate unknown-field rejection, bounds
for strings/arrays/mappings/depth/nodes/bytes, no network or remote resolution,
no caller/environment-selected roots, repository-contained admitted schemas,
traversal and symlink-escape rejection, regular-file/no-follow/bounded reads,
duplicate-key rejection, controlled anchor/dynamic references, schema identity
verification, immutable snapshots, deterministic schema digests, and
post-construction substitution resistance.

Schema validates structure, never truth, authorization, trust, feasibility,
safety, authenticity, approval, or provider eligibility. Cross-field domain
invariants remain independent validation. A schema cannot become executable
policy.

JSON Schema is not mandatory for every internal structure. Immutable typed
models, explicit validators, canonical JSON validation, fixed manifests, and
narrow parsers are acceptable when they retain deterministic bounded behavior,
safe errors, exact identity/version/lifecycle/compatibility checks, conformance
tests, and audit-safe metadata. No universal schema language is selected.

### Canonicalization and digest domains

A domain computing digests documents admitted types, Unicode behavior, object
key ordering, array-order semantics, whitespace/separators, numeric form,
non-finite and huge-integer policy, duplicate keys, temporal normalization,
event-specific metadata, self-digest exclusions, and unsupported-object failure.
Fallback stringification, `repr()` identity, and machine-dependent serialization
are prohibited.

Different domains may use different canonical forms when semantics differ. Each
form is explicit, versioned where its meaning changes, and tested.

Every digest names/documents its domain, such as schema, registry snapshot,
source bytes, normalized/item/package/context content, selection decision,
event-bound artifact, or report. Documentation states exact included/excluded
material, deterministic substitution-evidence properties, and non-properties:
no authenticity, signature, authorization, truth, approval, confidentiality, or
trust. Digest-semantic changes require a contract version or versioned digest
policy.

### Bounds and resource behavior

Every registry/contract centralizes applicable bounds or explains
non-applicability: raw/canonical bytes, strings, arrays, fields, depth, nodes,
schema size, contract/mapping count, translation steps, duration, recursion,
references, and audit metadata.

Bounds are explicit, testable, owned, versioned or policy-bound, local-safe, and
resistant to denial of service. Unexplained scattered constants and unverified
production-capacity assumptions are prohibited. Unsupported size semantics fail
closed.

Construction and validation avoid repeated schema reads or validator compilation
in tight loops, uncontrolled references, unbounded error collection,
unbounded-quadratic duplicate work, global snapshot reconstruction per item,
network calls, and filesystem discovery. Immutable snapshot reuse is preferred
where safe. No universal latency SLO is defined.

### Immutability and invocation isolation

Registry snapshots and validated artifacts resist ordinary supported-API
mutation, including direct assignment, nested collection/reference mutation,
mutable defaults, schema/record/policy backing mutation, and exported-copy
escape. Exported representations cannot mutate validated state.

An invocation observes one stable snapshot, never a partial refresh, mid-call
lifecycle/mapping/schema change, implementation substitution, or
environment-dependent registration. This is supported-API immutability, not a
claim of sandboxing against malicious trusted in-process Python.

Hot reload is deferred. A future design builds and independently validates a new
immutable snapshot, atomically admits it only for new invocations, allows
in-flight work to retain its original snapshot, retains rollback, and audits
promotion/rejection.

### Authoritative registration sources

Authoritative registration is repository-built: exact repository-owned
mappings, hardened admitted built-in manifest directories, immutable compiled
tables, and fixed admitted schemas.

Caller paths, environment-selected roots, current-directory discovery,
`PYTHONPATH` discovery, entry points, arbitrary module scanning, network
registries, runtime package installation, provider-supplied schemas, and
user-supplied implementation classes are prohibited for authoritative contract
registration.

Existing non-contract command discovery mechanisms are not silently reclassified
or refactored by this ADR; material changes must assess whether they cross into
authoritative contract registration.

Dynamic third-party registration remains unsupported. A future ADR must address
signing, trust roots, provenance, dependency resolution, sandboxing/isolation,
permissions, revocation, lifecycle, compatibility, rollback, incident response,
and supply-chain scanning before it can be considered.

### Cross-registry edges and dependency direction

Every federation edge has an owning domain, mapping identity/version, lifecycle,
exact endpoints, bounds, compatibility and failure behavior, and test coverage.
Edges are inert mappings, not imports, handles, shared mutable records, or
authority. Cross-registry mappings cannot create circular authority.

Lower-level contracts do not import higher-level implementations merely to
validate themselves:

- Knowledge contracts do not import reasoning providers.
- Semantic contracts do not import Runtime execution logic.
- Context contracts reference Semantic/Knowledge identities through bounded
  mappings, not implementation internals.
- Provider contracts do not import capabilities.
- Workflow contracts reference operations without owning implementations.
- Future approval contracts may bind Plan IR digests but cannot execute plans.

Circular runtime imports and mutual registry mutation are prohibited.

Cross-domain references are bounded qualified identities carrying domain,
identity, version, and digest where binding is required. They grant no access or
authorization. The referenced domain independently resolves/validates its own
contract. Arbitrary Python/object handles are prohibited.

### Fail-closed resolution

Registries fail closed for unknown identity/version/lifecycle/compatibility,
duplicates, ambiguity, disabled or ordinarily retired contracts, malformed or
mismatched schemas, digest mismatch, unsafe paths, mutable substitution,
unsupported external references, and missing governance metadata where
required. Failure never returns a generic fallback, nearest, or latest contract.

Federation reduces blast radius: failure cannot corrupt unrelated registries.
An operation requiring several registries still fails if any required registry
cannot validate its portion. Construction failure cannot leave partial mutable
global state. This ADR introduces no distributed registry service.

### Audit and errors

Audit-safe metadata may include registry identity/version/digest, contract and
schema identity/version/digest, lifecycle, compatibility mapping, resolution or
validation outcome, deprecation category, correlation identity, duration,
status, and exit code.

Audit excludes full payloads, Knowledge or Context content, prompts, secrets,
credentials, paths, provider-native data, hidden reasoning, and raw traces.
Each domain decides when persistent audit is mandatory, optional, aggregated,
or development-only; pure validation does not automatically require persistent
audit. Invoking operations own persistent-audit failure behavior. A registry is
not a universal audit service.

Domains use typed safe errors for relevant unknown, unsupported, incompatible,
disabled/retired, invalid-schema/artifact, integrity, duplicate, unsafe-source,
translation, migration, and internal failures. Errors expose no payload,
secrets, private paths, schemas, implementation objects, provider output, or
stack traces. No universal error hierarchy or new numeric exit code is required;
domains map through existing response/exit conventions.

### Testing and conformance

Every registry has focused tests for applicable construction, resolution,
schema-source safety, validation bounds, compatibility, lifecycle, migration,
security non-authority, safe errors/audit, and intended concurrent snapshot use.

Expected categories include deterministic construction/digest, duplicate
identity/schema rejection, immutable snapshots; exact and unknown resolution;
disabled/retired behavior; traversal, symlink, non-regular, remote/dynamic
reference, duplicate-key, identity mismatch, and substitution tests; minimum and
maximum artifacts; unknown fields, depth/nodes/size/non-finite/unsupported
objects; exact/missing/incompatible/translator mappings; no downgrade or field
loss; activation/deprecation/disablement/retirement; migration/rollback where
implemented; and registration/digest/lifecycle/reference non-authority.

Requirements that do not apply are documented rather than tested meaninglessly.

A repository-maintained conceptual conformance matrix should identify registry
identity/version, domain owner, schema mechanism, lifecycle, compatibility,
digest, schema-loading policy, dynamic-registration status, audit behavior,
tests, deviations, and migration status. Its exact documentation or
machine-readable form is deferred. M3.5 is not blocked on retroactively
completing every historical row.

### Incremental migration and deviations

Existing registries are not noncompliant merely because they predate this ADR:

1. New registries comply from initial implementation.
2. Material changes assess ADR-0018 compliance.
3. Security-critical gaps are corrected promptly.
4. Cosmetic differences do not trigger churn.
5. Common utilities emerge only from proven repeated needs.
6. No broad registry rewrite is authorized.
7. Public behavior and compatibility are preserved.
8. Deviations are explicit, justified, owned, and time-bounded where suitable.

A deviation requires a materially different domain need, named owner, security
and compatibility review, local testability, safe failure, no added authority,
and a review/expiry point where appropriate. It cannot hide in implementation.
Critical deviations may require a separate ADR.

This is governance against drift, not architecture astronautics or forced
uniform code.

### Supply-chain and upgrade governance

Contract systems remain subject to existing supply-chain policy. A new schema or
validator dependency requires demonstrated need, license and vulnerability
review, pinning, SBOM/provenance evidence, maintenance assessment, upgrade path,
and removal/replacement strategy. Existing pinned dependencies and standard
library behavior are preferred. Validation cannot require network availability,
and no schema-registry product is selected.

Contract artifact version, registry implementation version, and validation-
library/dependency version are independent upgrade dimensions. A library upgrade
must demonstrate unchanged or intentionally reviewed schema behavior, tests for
changed behavior, no newly accepted unsafe data, no remote-resolution expansion,
canonical/digest stability where required, migration/rollback, and supply-chain
checks.

A registry implementation upgrade preserves admitted contract semantics unless
an explicit contract or compatibility-policy version changes. A contract change
cannot be disguised as refactoring. External dependencies have an owner, pinned
policy, compatibility tests, security-update and rollback paths, supported
runtime versions, and deprecation monitoring. This ADR selects no automated
dependency-update product.

### Local-first and availability

Every registry constructs and tests locally without cloud, network schema
registry, identity provider, paid service, AI provider, database, queue, GPU,
external secrets, or container-registry access during ordinary validation.
Authoritative registrations/schemas are repository-owned or in an approved
local distribution artifact. CI and workstation validation use equivalent
semantics.

Federation limits unrelated failure blast radius, while required multi-registry
operations fail closed if a dependency is unavailable. Future remote
distribution, process isolation, hot reload, or production availability design
requires separate architecture.

### Security threat assessment

| Threat | Trust boundary and mitigation | Deferred control |
|---|---|---|
| God Registry/universal object growth | Domain ownership, independent packages/snapshots, explicit edges, no universal API/base/schema. | Periodic conformance review. |
| Arbitrary registration, dynamic import, or dependency confusion | Repository-built exact mappings, no entry points/network/runtime installation, pinned supply chain. | Signed isolated third-party bundles require separate ADR. |
| Schema path/remote/substitution attacks | Containment, no-follow bounded reads, identity/digest checks, immutable snapshots, restricted references. | Additional OS isolation. |
| Version downgrade, latest, wildcard, or lifecycle spoofing | Exact keys/mappings, policy-owned lifecycle, no caller selection or fallback. | Formal compatibility verification. |
| Registry/schema/mapping/translator digest substitution | Domain-specific canonical inputs, immutable snapshots, independent target validation. | Signing/trust roots where required. |
| Translator semantic loss, classification downgrade, purpose expansion, trust inflation, expiry/revocation loss | Versioned translator contract, preservation invariants, fail on mandatory loss, target validation. | Formal semantic-loss tooling. |
| Circular authority or arbitrary handles | Inert qualified identities, allowed dependency direction, independent resolution, no mutual mutation. | Automated dependency-cycle analysis. |
| Mutable state, partial refresh, stale snapshot | Invocation-scoped immutable snapshots; hot reload deferred; current policy revalidation belongs to invoking domain. | Atomic reload and durable distribution design. |
| Indefinite deprecated use or premature validator removal | Owned windows, consumer/artifact inventory, retained bounded historical validation. | Archived-validator storage policy. |
| Audit/error payload leakage | Metadata allowlists and typed safe domain errors. | Production audit retention. |
| Oversized/recursive input and Unicode/case ambiguity | Central bounds, restricted references, explicit Unicode/case/canonical rules. | Expanded confusable-identifier policy. |
| Conflicting ownership | Named domain/security/migration/retirement roles and accountable lifecycle review. | External ownership service if later justified. |
| Validation-library behavioral drift or supply-chain compromise | Independent upgrade dimension, pinned dependencies, semantic regression tests, SBOM/provenance/vulnerability checks. | Reproducible-build expansion. |
| Registry success interpreted as authority | Permanent known-not-authorized rule; Runtime owns authorization/execution. | Recurrent authority acceptance review. |

The same controls address duplicate identities, incompatible mappings, stale
snapshots, retired artifacts, denial of service, cross-domain substitution, and
false digest-authenticity claims. Deferred controls are not implied to exist.

### Open-source and vendor neutrality

This decision selects no schema-registry/API-management product, service mesh,
commercial testing service, cloud metadata service, database, marketplace,
identity provider, policy engine, event bus, or plugin protocol. Governance and
formats remain portable and use open formats where practical. A non-JSON domain
representation requires explicit justification but is not prohibited.

### Movie-platform application

Future project, screenplay, character, scene, shot, continuity, costume,
location, camera, lighting, animation, voice, music, sound, asset, render,
review, release, licensing, budget, and schedule contracts follow federation.

They may use separate registries where ownership, lifecycle, security,
classification, release cadence, or operational coupling differs, or one bounded
domain registry with independently versioned families where semantics genuinely
align. Business-domain similarity alone does not justify one Movie Contract
Registry. A universal Movie Object containing all production data is prohibited.

## Alternatives Considered

### 1. Independent registries with no common governance

Rejected because domain drift would produce inconsistent version, lifecycle,
security, digest, retirement, and compatibility behavior.

### 2. Universal registry and contract model

Rejected because it centralizes failure and policy, erases domain semantics,
creates a God Object, encourages shared authority, and couples unrelated change.

### 3. Immediate shared framework and full migration

Rejected because repeated implementation semantics have not been proven
identical, broad refactoring risks compatibility, and a framework would become a
premature mandatory dependency.

### 4. External schema-registry product

Rejected because it introduces vendor/network/runtime coupling without solving
domain ownership, semantic compatibility, authorization, or local-first needs.

### 5. Federated principles with incremental utilities

Selected. It balances consistent security/governance with domain autonomy,
evolvability, compatibility, local-first operation, provider neutrality,
maintainability, and avoidance of premature abstraction. Utilities may emerge
only from demonstrated identical needs.

## Consequences

### Positive

- Consistent ownership, lifecycle expectations, compatibility, loading safety,
  digest meaning, migration, audit interpretation, and upgrade review.
- Preserved domain independence and smaller failure blast radius.
- Less pressure for a God Registry, universal contract, or universal movie
  object.
- Clearer review/conformance checklists and safer future contract domains.
- Incremental improvement without breaking public behavior.

### Costs and risks

- More governance and conformance-review work.
- Some implementation duplication remains intentionally.
- Over-standardization and architecture-astronautics remain risks.
- Migration, lifecycle administration, translators, retained validators, and
  ownership coordination require maintenance.
- New contracts may take longer to introduce safely.

### Mitigations

Adopt incrementally; require no shared base class or broad retrofit; allow owned
deviations; preserve domain semantics; assess one new/materially changed
registry at a time; focus on security-significant consistency; extract utilities
only after repeated evidence; review periodically; and prefer simplicity over
abstraction.

## Decision Boundaries

This ADR decides the federated model, common obligations, ownership,
identity/version principles, exact-by-default resolution, explicit
compatibility/translators, lifecycle/deprecation/retirement, schema loading,
canonicalization/digests, bounds, immutability, registration sources,
cross-registry mappings/dependency direction, fail-closed behavior,
testing/conformance, incremental migration/deviations, and supply-chain/upgrades.

It does not decide common Python interfaces/base classes, metadata schemas, one
lifecycle enum, one registry implementation or schema language, one canonical
format, one audit service/error hierarchy, a plugin protocol/product, dynamic
registration, or final movie registry boundaries.

## Roadmap Impact

1. ADR-0018 Federated Contract and Registry Governance.
2. M3.5 Context Contract Registry and deterministic Context Assembly.
3. M3.6 Context-to-Reasoning Gateway integration.
4. Architecture conformance checkpoint after M3.6.
5. M3.7 Plan IR architecture.
6. Later contract domains comply from inception; existing registries are
   assessed incrementally on material change.

No broad retrofit precedes M3.5, and this ADR implements no roadmap item.

## Unresolved Questions

- Whether lightweight conformance metadata or a common inspection interface is
  useful.
- Whether hardened schema-loading or canonicalization utilities should be
  consolidated after further repeated evidence.
- Whether qualified cross-domain identities should use one standard format.
- Exact shared lifecycle vocabulary and deprecation-window defaults.
- Retirement/archive storage, historical replay, and retained-validator policy.
- Expanded schema-dialect policy and migration-tool ownership.
- Compatibility-map and translator-registration representations.
- Contract dependency graphs and automated cycle detection.
- Hot reload and production snapshot distribution/availability.
- Signed remote bundles, contract signing, trust roots, and third-party
  registration.
- Multi-repository contracts, generated contracts, and language-neutral SDKs.
- Movie-domain registry boundaries and conformance-report automation.
- Long-term audit retention and formal verification.

## Acceptance Criteria

ADR-0018 is acceptable only if:

- registries remain federated, independently owned, and non-authorizing;
- no God Registry, universal Contract Object/schema, central registration
  service, forced base class, or universal lifecycle is introduced;
- Runtime remains sole execution/authorization authority and registration means
  known, not authorized;
- public/cross-domain contracts have explicit identity, version, owner,
  lifecycle, bounds, validation, compatibility, and retirement behavior;
- exact resolution is default and authoritative paths have no latest, wildcard,
  implicit range, silent downgrade, or field loss;
- mappings/translators are explicit and preserve security-significant semantics;
- lifecycle, deprecation, retirement, historical validation, and deviations are
  governed;
- schema loading is bounded, repository-contained, immutable, and fail closed;
- canonical and digest meanings are explicit and non-authorizing;
- snapshots are immutable per invocation and cross-domain references are inert
  identities rather than handles;
- dynamic third-party registration remains unsupported;
- local conformance, supply-chain review, and independent upgrade dimensions are
  required;
- existing registries migrate incrementally without forced refactoring;
- future movie contracts do not collapse into a universal Movie Object; and
- no implementation, schema, test, dependency, registry refactor, plugin,
  provider, connector, Plan IR, approval, execution, or infrastructure is added.

## Independent Review Perspectives

1. Enterprise Software Architecture: federation limits coupling and blast radius
   without creating a central service.
2. Contract and Schema Architecture: exact identities, domain validation, and
   explicit translation preserve semantic boundaries.
3. Runtime Authority: registration, activation, digest, and compatibility grant
   no execution or authorization authority.
4. Product Security: loading, resolution, immutability, bounds, and translators
   fail closed.
5. Supply-Chain Security: dependencies, validator upgrades, SBOM/provenance, and
   dynamic-install prohibitions remain governed.
6. Compatibility and Migration: mappings, windows, rollback, retained validators,
   and incremental adoption avoid migration dead ends.
7. API and Versioning Design: every version dimension is independent; semantic
   version syntax has no implicit compatibility.
8. Developer Experience: common review obligations improve predictability while
   avoiding a forced framework.
9. Local-First Engineering: authoritative operation is repository-local and
   network-independent.
10. Performance Engineering: snapshots, loading, validation, and error work are
    bounded without universal SLOs.
11. Data Governance: domain-specific purpose, classification, trust, retention,
    revocation, conflict, and uncertainty are not flattened.
12. AI Governance: semantic/context/knowledge contracts remain provider neutral
    and grant no reasoning or autonomy authority.
13. Movie and Media Platform Architecture: ownership and lifecycle determine
    bounded families; business-domain similarity does not create one registry.
14. Open-Source Governance: no product is selected and dependency admission
    remains governed.
15. Independent Verification: acceptance criteria trace to explicit decisions,
    threats, migration rules, and deferrals.

No contradiction was identified with ADR-0010 through ADR-0017. Existing
implementation diversity is an explicit migration input, not evidence for a
universal framework or a finding that requires immediate refactoring.

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [ADR-0012: Evolvable and Reversible Reasoning Architecture](ADR-0012-evolvable-reasoning-architecture.md)
- [ADR-0013: Semantic Reasoning Contracts](ADR-0013-semantic-reasoning-contracts.md)
- [ADR-0014: Local-First Scalability, Performance, and Resource Efficiency](ADR-0014-local-first-scalability-performance-efficiency.md)
- [ADR-0015: Knowledge Architecture and Bounded Knowledge Packages](ADR-0015-knowledge-architecture.md)
- [ADR-0016: Autonomy, Approval, and Execution Authority](ADR-0016-autonomy-approval-execution-authority.md)
- [ADR-0017: Bounded Context Assembly Between Knowledge and Reasoning](ADR-0017-context-assembly-architecture.md)
- [Runtime Kernel](../runtime-kernel.md)
- [Provider Abstraction](../provider-abstraction.md)
- [Workflow Engine](../workflow-engine.md)
- [Reasoning Contracts](../reasoning-contracts.md)
- [Knowledge Packages](../knowledge-packages.md)
- [Performance Laboratory](../performance-laboratory.md)
- [Threat Model](../security/threat-model.md)
- [M2 Architecture Checkpoint](../reviews/m2-architecture-checkpoint.md)

## Verification

Before acceptance:

- run `./scripts/validate_adr.sh`;
- validate repository-relative references;
- confirm status remains `Proposed`;
- confirm only ADR-0018 is tracked as changed;
- run the repository secret scan and `git diff --check`;
- use existing Markdown validation if present; and
- conduct independent architecture, schema, authority, security, supply-chain,
  compatibility, developer-experience, performance, governance, AI, movie, open-
  source, and verification reviews.
