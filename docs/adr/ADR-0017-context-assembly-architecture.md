# ADR-0017: Bounded Context Assembly Between Knowledge and Reasoning

## Status

Accepted

## Date

2026-08-02

## Context

VSS now has governed, inert Knowledge Packages and a separate, provider-neutral
reasoning boundary. Passing complete Knowledge Packages directly to reasoning
would expose governance metadata and unrelated content, couple providers to
knowledge contracts, weaken purpose limitation, and encourage a universal
context object. Allowing providers to browse packages would also give them a
source-access role they do not possess.

VSS therefore needs an architectural boundary that converts one or more already
validated Knowledge Packages into the minimum bounded semantic context needed
for one admitted task. That conversion must preserve governance evidence without
turning knowledge, context, confidence, evidence, or validation into authority.

The permanent rule is:

> Knowledge Packages contain governed knowledge. Context Assembly selects and
> transforms only the minimum authorized knowledge required for one semantic
> reasoning task. Runtime remains the sole policy, authorization, approval, and
> execution authority.

This ADR defines that boundary. It does not implement contracts, schemas,
assembly, retrieval, provider integration, or execution.

## Decision

VSS will introduce a distinct, bounded, deterministic, policy-governed Context
Assembly subsystem between validated Knowledge Packages and the Reasoning
Gateway. It will produce task-specific, typed, inert Context Objects plus a
separate governance-side Assembly Report.

The initial conceptual family is `generate_options_context/1`, compatible only
with `generate_options/1`, `option_set/1`, `reference_note/1`, and an admitted
package purpose compatible with `local_validation_context`. The first
implementation milestone may refine the exact purpose identifier, but it must
express a scope equivalent to `generate_options_local_validation` and may not
broaden the source package purpose.

Context Assembly is not a second Runtime. It evaluates eligibility under an
immutable Runtime-authorized policy snapshot, but it cannot grant permission,
select an execution path, invoke reasoning on its own, or expand any authority.

### Relationship to existing decisions

ADR-0017 is subordinate to and consistent with:

- [ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md): Runtime remains
  the sole execution and authorization authority. Context Assembly cannot invoke
  capabilities or workflows.
- [ADR-0011](ADR-0011-engineering-principles.md): explicit contracts, least
  privilege, fail-closed behavior, provider neutrality, local-first operation,
  bounded audit, and deterministic testing govern assembly.
- [ADR-0012](ADR-0012-evolvable-reasoning-architecture.md): the Reasoning
  Gateway remains the sole reasoning boundary; providers remain source blind;
  Knowledge Packages are governed inputs rather than prompt fragments.
- [ADR-0013](ADR-0013-semantic-reasoning-contracts.md): envelope and typed
  payload remain separate, evidence references remain inert, and no universal
  Reasoning or Context God Object is allowed.
- [ADR-0014](ADR-0014-local-first-scalability-performance-efficiency.md):
  assembly is bounded, measurable, profile-driven, deadline-aware, and locally
  testable without unbounded concurrency or production-capacity claims.
- [ADR-0015](ADR-0015-knowledge-architecture.md): Knowledge Packages retain
  authority over provenance, classification, purpose, freshness, revocation,
  conflicts, uncertainty, retention, and integrity.
- [ADR-0016](ADR-0016-autonomy-approval-execution-authority.md): context is an
  inert input to a proposal path and cannot approve itself, grant autonomy, or
  become execution authority.

M3.1 supplies exact semantic versions; M3.2 supplies the deterministic
GenerateOptions path; M3.3 supplies local concurrency and performance evidence;
and M3.4 supplies `reference_note/1` and `knowledge_package/1`. Context Assembly
must not reinterpret or supersede any of them. No M3.1 or M3.4 contract changes
are made by this ADR.

### Architectural boundary

The conceptual flow is:

```text
Validated Knowledge Package(s)
        |
        v
Context Assembly Request
        |
        v
Context Policy
        |
        v
Eligibility and minimization
        |
        v
Task-specific Context Payload
        |
        v
Context validation and digest
        |
        v
Semantic Request construction
        |
        v
Reasoning Gateway
```

Context Assembly is a distinct subsystem. It is not implemented inside the
Knowledge Contract Registry, Knowledge Package builder, Runtime Kernel,
Reasoning Gateway provider or strategy, workflow engine, capability SDK,
connector, or future search implementation.

It may accept validated packages; independently verify integrity and lifecycle;
enforce purpose, classification, trust, freshness, revocation, retention, and
bounds; select and deterministically order eligible items; preserve provenance,
conflict, uncertainty, and limitations; apply admitted task-specific
transformations; build and validate an inert Context Object; create an Assembly
Report; and emit safe audit metadata.

It must not retrieve, browse, search, query a database, resolve URLs,
authenticate to sources, create or modify packages, change classification or
trust, decide truth, silently remove material conflict or uncertainty, invoke a
provider, select a model, construct provider-native prompts, compile plans,
approve, execute, invoke capabilities or workflows, or grant source access.

### Authority boundary

An Assembly Request is not authorization. Runtime policy must already authorize
its complete scope. Eligibility can only narrow authority already represented
by the authorized policy and admitted packages.

A Context Object grants no source, connector, package, provider, workflow,
capability, execution, approval, autonomy, classification, purpose, retention,
or replay authority. Validation means structurally and policy-admitted for the
specified task at the specified time, not true, correct, recommended, approved,
or executable. Context delivery means only that a validated inert object crossed
the assembly boundary.

### Context Contract Registry

VSS will define an explicit Context Contract Registry before implementation. It
will resolve Context Request Envelope and Context Object Envelope versions,
context-family identity and version, compatible knowledge item and semantic
task identities, context policy identity and version, bounds, lifecycle,
compatibility, ownership, schema identity, deprecation and retirement metadata,
and a deterministic registry integrity digest.

The registry must be repository-owned, explicit, deterministic, immutable for
an invocation, provider/source/storage neutral, non-executable, non-authorizing,
and fail closed. Registration means known, not authorized.

It remains independently owned from the Semantic Contract Registry, Knowledge
Contract Registry, Runtime registry, and provider registry. Compatibility is an
explicit immutable mapping across identities and versions; no registry may own,
mutate, or dynamically aggregate every contract system into a God Registry.

Dynamic imports, entry-point discovery, arbitrary schema or contract paths,
environment-selected schemas, caller-selected transformations, arbitrary
modules, and third-party runtime registration are prohibited. Unknown identity,
version, lifecycle, policy, schema, or compatibility combinations fail closed.

### First context family

The first conceptual family is `generate_options_context/1`. It admits only:

- semantic task `generate_options/1`;
- semantic result family `option_set/1`;
- knowledge item family `reference_note/1`; and
- packages whose purpose is compatible with `local_validation_context`.

Its typed payload may contain bounded selected note content, selected item and
package references, citations, provenance references, classification, trust and
freshness qualifications, conflicts, uncertainty, assembly limitations,
omissions, limit consumption, policy identity/version, and a context-content
digest.

It must not automatically contain a complete package, source credentials,
connector or storage handles, paths, provider-native messages, model settings,
tools, commands, workflow or capability invocations, approval, raw audit data,
or an extension/metadata bag. This ADR defines no schema.

### Envelope and payload discipline

A minimal Context Object Envelope contains only stable cross-family metadata:
schema version, context and correlation identities, semantic task and context
family identities/versions, package references, classification, purpose, policy
identity/version, construction time, expiry, lifecycle, content digest, and
exactly one typed context payload.

Task-specific selected content belongs only in that typed payload. Every future
context family owns its identity, schema/version, bounds, compatible source and
task families, lifecycle, owner, security and conformance rules, migration,
deprecation, and retirement. Unknown families and envelope/payload mismatches
fail closed. VSS will not create one object with optional fields for all future
tasks or movie domains.

### Context Assembly Request

The conceptual request is bounded and may carry request/correlation identities,
target task and context-family versions, package identities and digests,
purpose, classification ceiling, minimum trust, freshness requirement, byte and
item limits, evidence-reference limit, deadline, required/optional declarations,
and policy identity/version.

It must not carry a query language, SQL, search or embedding expression, source
or package path, connector/provider/model selection, prompt, tool call,
capability, workflow, execution request, or arbitrary transformation.

### Purpose binding

Context purpose must be explicit and compatible with the source package
purpose, target semantic task, assembly policy, classification, retention, and
expiry. The first purpose is conceptually
`generate_options_local_validation`; its exact stable identifier is deferred to
M3.5 contract review.

Compatibility must be an exact, versioned, repository-owned policy mapping of
source package purpose, target task/version, context family/version, project,
environment, classification, retention, and expiry. Prefix matching, lexical
similarity, caller assertion, provider interpretation, and ad hoc implementation
rules cannot establish compatibility. Unknown mappings fail closed.

Packages cannot be silently reused across project, environment, task, public
release, advisory/execution, or other purpose boundaries. Purpose
incompatibility fails closed. Assembly can narrow a package purpose but cannot
broaden or replace it.

### Classification and trust

The Context Object classification is at least the highest classification of
included content. Assembly enforces package and item classification, request
ceiling, task eligibility, output classification, and safe audit metadata using
an explicit ordering, never lexical comparison.

The first local architecture supports `public` and `internal`. Confidential,
restricted, regulated, personal, and secret-bearing production handling is
deferred. Unknown classifications fail closed. Classification does not grant
disclosure permission.

The governance-side Assembly Report and audit classification are derived
independently from every package, selected or referenced item, omission/rejection
record, and governance field they describe. They may be more restrictive than
the provider-visible payload and can never be downgraded merely because
minimization removed higher-classified provider-visible content.

Trust remains an explicit qualification. `approved_fixture` may be admitted;
`unverified` may be represented but is rejected by the first production
assembly policy.
Assembly cannot promote trust or convert claims into truth. Corroboration,
external origin, or filesystem location does not create authority.
Relevant trust qualifications remain visible in the provider-visible typed
payload; governance-only detail remains in the Assembly Report.

### Freshness, temporal validity, and revocation

Assembly revalidates package expiry, item effective time and freshness,
retention, source/item/package lifecycle, and current policy-owned revocation at
assembly time. Validity at package construction is insufficient. Unknown
freshness fails closed when current knowledge is required.

Validation time is supplied by an immutable Runtime-authorized policy clock,
bound to the assembly request, policy version, selection decision, report, and
safe audit metadata. A caller, package, strategy, provider, or environment
variable cannot select or move the validation clock. Deterministic fixtures may
use a repository-owned fixed clock under an explicit test profile.

Context expiry cannot exceed the earliest package expiry, selected-item
stale-after/effective-until/retention deadline, assembly-policy lifetime, or
task deadline. Revocation propagates to selection, context validity, future
cache and replay eligibility, and downstream reasoning eligibility. A previously
assembled object cannot preserve eligibility after its source material becomes
revoked. Persistent revocation services remain deferred.

### Deterministic selection and minimization

The M3.5 selection algorithm will be deterministic, inspectable, bounded,
versioned, policy-owned, and provider neutral. The initial rule will:

1. Admit only compatible item families and purpose.
2. Enforce classification ceiling, trust, freshness, retention, and revocation.
3. Normalize package order and sort items by stable identity.
4. Detect duplicates according to an explicit, deterministic, versioned policy
   and record the disposition safely without hiding divergent or conflicting
   content.
5. Include all required eligible items if they fit.
6. Select optional eligible items in deterministic order within item, byte,
   evidence, conflict, uncertainty, provenance, node, depth, duration, and
   transformation budgets.
7. Record every omission or rejection with a bounded reason.

Selection cannot use randomness, filesystem or mapping iteration order, model
ranking, embedding similarity, the current provider, machine state, or
nondeterministic tie-breaking. Exact duplicate representation remains an M3.5
contract question, but duplicate handling must be attributable, bounded,
inspectable, and unable to collapse unequal content under one identity.

Data minimization is mandatory. Provider-visible context contains the minimum
semantic subset. Governance-side records preserve sufficient package/item
identity, digest, policy, selection, omission, conflict, uncertainty, and
provenance evidence. Complete packages, full provenance records, unrelated
items, unused citations, package audit data, and governance-only retention/legal
metadata are not copied to providers by default.

Minimization must not remove relevant constraints, evidence references,
classification, trust/freshness qualification, material conflicts, uncertainty,
limitations, or provenance bindings.

### Full-note inclusion and transformations

The first family may include a complete bounded `reference_note/1` body when it
fits. Arbitrary excerpts, summarization, semantic rewriting, lossy truncation,
and silent clipping are deferred and prohibited in v1.

If required content cannot fit, assembly fails. Optional content may be omitted
only under explicit deterministic policy and the omission must be recorded.
Future excerpts require a separately versioned transformation contract that
preserves provenance and omission semantics.

### Required and optional knowledge

Required/optional status applies conceptually at both package and item level. It
must be explicit in the admitted request or policy and is never inferred from
package order, item order, file order, source priority, or trust. The exact v1
representation at each level remains an M3.5 contract question.

Required content must be eligible, fit all limits, and be included or assembly
fails. Optional content may be omitted deterministically for policy or budget
reasons, but the Assembly Report must record the omission. Omitted content does
not create hidden fallback or source access.

### Conflicts and uncertainty

Material conflicts among selected content remain visible. Assembly cannot
silently choose a winner, merge claims into a fact, omit conflict metadata while
including the claims, or rank a source as true without an explicit future
contract. Eligibility and assembly must evaluate conflicts across all selected
packages and items, not only conflicts already summarized inside one package.
For every material conflict, the first family must carry conflict identity,
involved item identities, qualification, resolution status, and handling
policy. Reasoning must treat unresolved conflict as uncertainty.

Relevant uncertainty must also remain visible, including that truth,
applicability, completeness, and absence of other sources have not been
established. Assembly cannot convert unknown into true or false, unverified into
fact, omitted into absent from reality, or `none_detected` into a claim of global
consistency.

Omission categories distinguish at least ineligible, optional-budget omission,
stale, revoked, classification denied, purpose incompatible, unsupported family,
duplicate, and superseded. Exact taxonomy is deferred to M3.5, but it must be
explicit, bounded, non-secret-bearing, attributable to package/item identity,
and incapable of converting required-content failure into successful omission.

### Provenance and evidence references

Provider-visible context may carry bounded inert evidence references. The
governance record retains source package and item identities/digests, package
and item content digests, source identity, admitted transformation and selection
policy versions, omission reasons, and context digest.

Providers cannot resolve evidence references or use them as source, connector,
file, package, URL, credential, or authority handles. Provenance supports
traceability and still does not prove truth.

### Digest semantics

Context Assembly will distinguish:

1. input package-set digest;
2. selection-decision digest;
3. provider-visible context-content digest;
4. governance Assembly Report digest; and
5. complete event-bound Context Object digest.

Canonical inputs and self-field exclusions must be explicit. Package ordering
is normalized. Identical package content, policy/version, task/version, context
contract/version, budgets, and semantically fixed validation time produce the
same provider-visible context-content digest. Correlation ID, event ID, or event
timestamp may change the complete event digest without changing semantic
content identity.

Digests are integrity evidence only, never authenticity, signature, truth,
authorization, approval, trust, or provider eligibility.

### Lifecycle, expiry, replay, and reuse

Conceptual lifecycle states are `requested`, `assembling`, `validated`,
`delivered`, `expired`, `revoked`, and `rejected`. Only `validated` context may
be delivered. Delivery does not imply provider invocation or execution.

Immediately before binding or delivery, Runtime rechecks the Context Object's
expiry, purpose, classification, task/context compatibility, package digests,
and current revocation snapshot. An expired, revoked, or mismatched object is
rejected rather than delivered for reasoning.

Expired or revoked context cannot be reused. Reuse is denied by default. A
future reuse policy must revalidate current authorization, purpose,
classification, package and item digests, lifecycle, freshness, revocation,
retention, task/context versions, and expiry. Caching is deferred and may not
bypass any of those checks.

### Assembly Report and audit

Assembly produces a separate immutable, bounded report containing safe
governance evidence: request/context and policy identities, input package
references, eligible/included/omitted/rejected counts and references, bounded
omission categories, classification/trust/freshness/revocation results, budget
consumption, conflict and uncertainty counts, context-content digest, status,
and limitations.

The report excludes note bodies, complete package/context payloads, credentials,
paths, raw provenance, prompts, and hidden reasoning. It is evidence, not
authority. A successful Assembly Report means only that assembly completed; it
does not mean reasoning ran, a proposal was accepted, or any action was approved.

Audit records safe identities, versions, counts, classifications, outcomes,
policy-clock identity, validation time, budget usage, digest evidence, expiry,
status, exit code, and duration. Audit
must not contain note titles/bodies, full packages or Context Objects,
credentials, paths, source sessions, raw provenance, provider-native input, or
hidden reasoning. Audit failure fails the operation. Local JSONL remains
development-only.

### Reasoning Gateway integration boundary

ADR-0017 defines but does not implement this boundary. A future semantic
invocation will bind exactly one validated Context Object by identity, version,
and digest. Runtime will supply it through either a typed task field or a narrow
immutable invocation-state handle. The provider receives only the typed
provider-visible payload, never the complete Knowledge Package, Context
Assembly registry, Assembly Report, or source resolver.

The provider cannot request more context, resolve evidence, mutate context,
broaden purpose, or select assembly policy. Whether the semantic request embeds
the Context Object or references Runtime-owned invocation state remains an M3.5
contract-impact decision. Either design must bind exact context
identity/version/digest, preserve an immutable provider-visible payload, reject
arbitrary handles and provider-directed fetching, and keep semantic-request and
context-contract versions independent. No M3.1 contract is changed by this ADR.

### Provider neutrality

Public Context contracts contain no prompt roles or messages, model names,
tokens, temperature, top-p, tools, vendor metadata, embeddings, search scores,
or vector-store results. Future adapters may translate typed context to
provider-native input behind the provider boundary; that translation does not
enter public context contracts.

### Bounds, performance, concurrency, and local-first operation

Versioned policy and implementation profiles own numeric limits for input
packages, selected items, provider-visible and governance bytes, evidence,
conflicts, uncertainty, provenance, depth, nodes, assembly duration, and
transformation count. Conservative initial values may be proposed by M3.5 but
are not permanent public contracts in this ADR.

Unsupported budget semantics fail closed. Required content exhaustion fails.
Optional deterministic omission is allowed only with explicit evidence. There
is no silent truncation or loss of material conflict or uncertainty.

Assembly must support bounded concurrent use with no unbounded submission,
package accumulation, or item accumulation. Future local measurements may cover
latency, bytes, counts, and policy failure categories, but define no production
SLO or distributed architecture.

M3.5 must be fully testable on a laptop with committed packages and deterministic
policy, clock, ordering, conflict, staleness, revocation, classification,
purpose, and budget fixtures. CI requires no cloud, database, search, vector
store, embeddings, AI, paid connector, key, GPU, or external identity provider.
The same authority and validation boundaries apply locally and in future
deployments.

### Caching

Caching is deferred. Any future cache key and admission check must bind package
content digests and lifecycle, current revocation snapshot, freshness, purpose,
classification, task/context/policy versions, budgets, and expiry. A cache hit
cannot bypass current authorization, classification, freshness, or revocation.

### Security threat assessment

| Threat | Trust boundary and mitigation | Deferred control |
|---|---|---|
| Complete-package or governance leakage | Assembly separates provider-visible payload from governance evidence and minimizes by typed family. | Production DLP and external-provider controls. |
| Purpose, project, or classification expansion | Runtime-authorized policy, exact purpose binding, explicit classification ordering, and fail-closed compatibility. | Expanded production taxonomy and identity. |
| Trust inflation or false truth | Trust and provenance remain qualifications; claims are not promoted to facts. | Corroboration and source-assurance policy. |
| Stale, expired, revoked, or replayed context | Revalidation at assembly, bounded expiry, reuse denied by default, and revocation propagation. | Durable revocation and cache invalidation service. |
| Package, item, context, policy, or digest substitution | Exact identities/versions, immutable snapshots, independent validation, and distinct digest domains. | Package authentication/signing where required. |
| Omission, optionality, ordering, conflict, or uncertainty manipulation | Explicit required/optional declarations, deterministic ordering, fail on missing required data, bounded omission report, and preserved conflict/uncertainty. | Cross-package semantic conflict tooling. |
| Budget bypass or oversized/deep content | Versioned limits, pre/post validation, deadlines, bounded nodes/depth/counts, no silent truncation. | Production admission control and isolation. |
| Prompt injection or executable-looking text | Context text remains inert typed data and grants no authority; providers cannot invoke Runtime. | External-provider content filtering where justified. |
| Evidence interpreted as access | Stable digest-bound references are non-resolvable by providers. | Governed resolver outside provider authority. |
| Provider requests more data or changes context | One immutable payload; no assembly/source handles in provider context. | Process isolation for untrusted providers. |
| Audit or report payload leakage | Safe metadata allowlists exclude semantic payload and raw provenance; audit failure is fatal. | Durable production audit and retention. |
| Malicious Unicode or canonicalization confusion | Strict UTF-8/JSON policy, versioned canonicalization, explicit digest domains, bounded text. | Expanded confusable-character policy if required. |
| TOCTOU between validation and assembly | Immutable validated package snapshot, current policy snapshot, and validation immediately before context construction. | Durable transactional state. |
| Arbitrary transformation or family registration | Repository-owned registry; no dynamic imports, caller paths, or runtime registration. | Governed extension lifecycle. |
| Context Assembly becomes a second Runtime | It can only narrow eligibility and produce inert data; Runtime owns policy authorization and execution. | Independent recurring authority review. |

Context replay after delivery, revocation after package construction,
cross-project reuse, event/content digest confusion, and false benchmark claims
are included in these controls. Production identity, isolation, durable state,
and external-provider handling remain prerequisites rather than claims of M3.5.

### Movie-production interpretation

Future families may cover character continuity, scene planning, costume or
location consistency, shot review, script revision, music style, voice
consistency, schedules, legal/license review, and rendering budgets. Each is a
separately owned, versioned, typed context family with its own purpose,
classification, bounds, compatibility, and review.

VSS will not create one movie or production Context God Object. A task receives
only the minimum authorized movie knowledge required. This ADR adds no
movie-production capability.

### Production prerequisites

Production-sensitive assembly is gated on production identity and
authorization, durable audit and revocation, secure package storage,
process/worker isolation, privacy and residency policy, retention and deletion
enforcement, authenticated or signed packages where required, cache
invalidation, incident response, policy lifecycle, external-provider data
handling controls, and effective cancellation if future transformations gain
side effects.

M3.5 remains local, deterministic, in-process, and non-authorizing.

## Alternatives Considered

### 1. Pass complete Knowledge Packages to providers

Rejected because it violates minimization, exposes governance metadata, couples
providers to package evolution, and increases privacy, classification, cost, and
prompt-injection exposure.

### 2. Let providers browse packages dynamically

Rejected because it grants providers source-selection and access behavior,
undermines deterministic replay, and bypasses Runtime-owned policy.

### 3. Convert all knowledge into a universal prompt or context object

Rejected because it creates a God Object, hides typed compatibility, couples
governance to prompt design, and makes bounds and evolution unsafe.

### 4. Assemble provider-native prompts in each adapter

Rejected because purpose, minimization, conflict, provenance, and classification
would vary by vendor and become difficult to verify locally.

### 5. Deterministic task-specific Context Assembly

Selected. A bounded, typed, policy-governed layer best preserves least
privilege, provider neutrality, deterministic local testing, classification,
provenance, freshness, revocation, conflict and uncertainty, semantic stability,
future movie-family separation, and performance/cost control.

## Consequences

### Positive

- Reasoning receives only necessary task-specific data.
- Knowledge Packages and providers remain mutually decoupled and provider/source
  neutral.
- Providers remain source blind and receive no governance handles.
- Privacy and classification exposure are reduced.
- Selection, ordering, omission, and digests are deterministic and reproducible.
- Provenance, conflict, uncertainty, freshness, and revocation remain explicit.
- Bounded context lowers future provider cost and denial-of-service exposure.
- Local conformance testing and provider replacement become easier.
- Movie contexts can evolve as independent families.

### Costs and risks

- Another contract registry, lifecycle, compatibility surface, and audit record.
- Policy and required/optional omission semantics require careful ownership.
- Assembly adds latency and resource consumption.
- Over-minimization can remove meaning; under-minimization can leak data.
- Context-family proliferation and migration require governance.
- Future excerpts and transformations can weaken provenance.
- There will be recurring pressure to create a God Context or hide prompt design
  in public contracts.

### Mitigations

Start with one task family and one knowledge family; include complete bounded
notes without summarization; prohibit search, embeddings, and arbitrary
transformations; require explicit optionality and omission evidence; centralize
strict limits; retain independent acceptance and periodic architecture review;
and prefer simple deterministic rules over clever ranking.

## Roadmap Impact

The conceptual sequence is:

1. ADR-0017 Context Assembly Architecture.
2. M3.5 Context Contract Registry and deterministic Context Assembly.
3. M3.6 validated-context integration with deterministic GenerateOptions.
4. M3.7 Plan IR architecture and contracts.
5. M3.8 deterministic Plan IR implementation.
6. M3.9 approval contract and deterministic local approver.
7. M3.10 first external reasoning provider behind existing boundaries.
8. Later: connectors, search, embeddings, provider translation, movie context
   families, production audit, and distributed execution.

This ADR implements none of these milestones.

## Unresolved Questions

- Exact Context Request and Context Object Envelope schemas.
- Exact `generate_options_context/1` payload and stable purpose identifier.
- Whether semantic requests embed context or reference Runtime invocation state.
- Context ownership between Runtime and the Reasoning Gateway.
- Required/optional representation and package/item granularity.
- Provider-visible versus governance-visible metadata split.
- Expiry defaults and long-running lifecycle behavior.
- Package and item ordering, duplicate handling, and supersession semantics.
- Cross-package conflict identification and resolution status.
- Excerpting, truncation, summarization, and transformation contracts.
- Citation and omission-report representation.
- Assembly Report schema and exact digest canonical inputs.
- Event identity, policy language, policy ownership, and promotion lifecycle.
- Expanded classification/trust taxonomies and personal-data handling.
- Package, item, byte, node, evidence, conflict, and duration limits.
- Provider-specific maximum context sizes and external-provider eligibility.
- Cache identity, invalidation, replay, and current-policy revalidation.
- Context streaming, media context, binary asset references, and movie sequencing.
- Context performance baselines and production audit retention.

## Acceptance Criteria

ADR-0017 is acceptable only if:

- Context Assembly is distinct from Knowledge, Reasoning, and Runtime.
- Context Assembly and its artifacts are non-authorizing; Runtime remains sole
  execution authority.
- Complete packages are not provider-visible by default.
- Selection is deterministic, inspectable, versioned, and bounded.
- Minimization is mandatory and required content cannot be silently omitted.
- Optional omission is explicit, deterministic, reported, and audited safely.
- Purpose cannot silently expand; classification cannot downgrade; trust cannot
  inflate.
- Freshness, expiry, retention, lifecycle, and revocation are revalidated at
  assembly time.
- Material conflict and uncertainty remain visible and provenance remains
  traceable.
- Evidence references grant no access and context expires.
- Envelope/payload separation prevents a Context God Object.
- Provider-native concepts remain outside public contracts.
- Local testing requires no paid or external service.
- Production prerequisites and unresolved contract decisions are explicit.
- No implementation, schema, test, provider, prompt, search, connector,
  database, embedding, Plan IR, approval, execution, dependency, or
  infrastructure change is included.

## Independent Review Perspectives

The proposal was reviewed independently from these perspectives:

1. Enterprise Software Architecture: the boundary is distinct, evolvable, and
   does not become a second Runtime.
2. Context Engineering: one task-specific family, explicit optionality, and
   deterministic minimization prevent a universal context object.
3. Knowledge Architecture: package purpose, classification, provenance,
   freshness, retention, revocation, conflict, and uncertainty survive assembly.
4. Reasoning Architecture: the Gateway remains sole reasoning entry and the
   provider remains source blind.
5. Runtime Authority: assembly only narrows an already authorized scope and
   grants no policy, approval, or execution authority.
6. Product Security: substitution, replay, overexposure, injection, budget, and
   TOCTOU threats fail closed or have explicit production prerequisites.
7. Data Governance: purpose, classification, trust, lineage, retention, and
   omission evidence remain explicit.
8. Privacy and Data Minimization: provider-visible data is separated from
   governance evidence and complete-package exposure is prohibited by default.
9. Contract Evolution: family-specific envelopes, exact compatibility, and
   deferred contract-impact decisions avoid weakening M3.1 or M3.4.
10. Performance and Local-First Engineering: all work is bounded, deterministic,
    profile-driven, and laptop-testable without production SLO claims.
11. AI Governance: context, confidence, evidence, and provider translation grant
    no authority; prompts and models remain outside contracts.
12. Media and Movie Pipeline Architecture: future domains are separate typed
    families rather than a movie God Object.
13. Provider Neutrality: no vendor roles, messages, tokens, models, embeddings,
    or search scores enter public contracts.
14. Independent Verification: acceptance criteria trace to explicit decisions,
    threats, deferrals, and validation requirements.

No contradiction was identified with ADR-0010 through ADR-0016. The main risks
are over-minimization, semantic conflict detection, lifecycle complexity, and
pressure toward a God Context; they are constrained by the first-family scope,
full-note inclusion, explicit omissions, strict bounds, and independent review.

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [ADR-0012: Evolvable and Reversible Reasoning Architecture](ADR-0012-evolvable-reasoning-architecture.md)
- [ADR-0013: Semantic Reasoning Contracts](ADR-0013-semantic-reasoning-contracts.md)
- [ADR-0014: Local-First Scalability, Performance, and Resource Efficiency](ADR-0014-local-first-scalability-performance-efficiency.md)
- [ADR-0015: Knowledge Architecture and Bounded Knowledge Packages](ADR-0015-knowledge-architecture.md)
- [ADR-0016: Autonomy, Approval, and Execution Authority](ADR-0016-autonomy-approval-execution-authority.md)
- [Reasoning Contracts](../reasoning-contracts.md)
- [Reasoning Gateway](../reasoning-gateway.md)
- [Performance Laboratory](../performance-laboratory.md)
- [Knowledge Packages](../knowledge-packages.md)
- [Threat Model](../security/threat-model.md)

## Verification

Before acceptance:

- run `./scripts/validate_adr.sh`;
- validate repository-relative references;
- confirm status is `Accepted` only after independent architecture acceptance;
- confirm only this ADR is tracked as changed;
- run `git diff --check` and the repository's existing Markdown validation, if
  available;
- conduct independent architecture, authority, security, privacy, contract,
  performance, provider-neutrality, movie-domain, and verification reviews; and
- confirm that no implementation or dependency accompanies the decision.
