# ADR-0024: Governed Cinematic Observation, Reference Learning, and Knowledge Evolution

## Status

Proposed

## Date

2026-08-09

## Context

M3 through M5 proved bounded deterministic semantic contracts, task-specific
Context Assembly, isolated provider views, exact version dispatch, and inert
reasoning results. Cinematic Observation introduces a different epistemic
problem: an observation may be manually declared, deterministically derived,
model-derived, probabilistic, uncertain, disputed, and dependent on a source
whose eligibility can change.

Without an explicit boundary, source availability could become an uncontrolled
path from material to observation, pattern, lesson, and purported knowledge.
That would erase uncertainty and rights constraints, make model output appear
authoritative, and couple accumulated knowledge to an implementation, model,
storage product, or language.

This decision extends, rather than replaces, the typed Knowledge Item and
bounded Knowledge Package architecture of [ADR-0015](ADR-0015-knowledge-architecture.md).
It is also governed by:

- [ADR-0013](ADR-0013-semantic-reasoning-contracts.md): provider-neutral,
  independently versioned semantic contracts;
- [ADR-0017](ADR-0017-context-assembly-architecture.md): bounded,
  task-specific Context Assembly;
- [ADR-0018](ADR-0018-federated-contract-registry-governance.md): federated
  ownership, exact versions, explicit compatibility and historical meaning;
- [ADR-0021](ADR-0021-studio-workload-planes-specialized-execution.md): logical
  workload planes;
- [ADR-0022](ADR-0022-cross-plane-admission-resource-bounds-artifact-consistency.md):
  exact cross-plane admission and artifact consistency;
- [ADR-0023](ADR-0023-minimal-component-open-source-resource-efficient-implementation.md):
  smallest sufficient reliable implementation, open-source-first, and native
  code only for measured needs;
- the [VSS Constitution](../architecture/vss-constitution.md), especially human
  authority, observation not truth, replaceable models, provenance, rights,
  simplicity, and evidence-earned frameworks; and
- the [M5 checkpoint](../reviews/m5-character-continuity-semantic-engine-checkpoint.md),
  which requires confidence, model provenance, source eligibility, withdrawal,
  and reference influence to be owned before probabilistic or external-media
  implementation.

Movie production remains the proving application. This ADR does not turn VSS
into a general-purpose knowledge-research platform.

## Decision

VSS adopts a governed, domain-owned knowledge-evolution sequence:

```text
Source Evidence
    ↓
Observation
    ↓
Pattern
    ↓
Lesson
    ↓
Admitted Knowledge
```

Source material may contribute evidence. Evidence may support observations.
Observations may support patterns. Patterns may support lessons. Lessons may
become admitted knowledge only through an explicit, versioned, domain-owned
promotion policy. No level automatically grants the semantics of the next.

These are semantic roles, not storage tiers, a programming-language
inheritance hierarchy, or mandatory service boundaries. ADR-0015 typed
Knowledge Items may represent domain-owned Observation, Pattern, Lesson, and
Admitted Knowledge families without changing the common envelope. Source
Evidence may remain an integrity-bound source or evidence artifact rather than
being mislabeled as Knowledge. No universal Knowledge object, Knowledge Engine,
promotion service, or graph is created.

### Source Evidence

Source Evidence is material, or a bounded reference to material, used to
support a claim. It may include original or synthetic fixtures, current-project
media, studio-history evidence, books, papers, university material, eligible
websites or reference cinema, human expert statements, and controlled
experiments.

Accessibility is not eligibility. A host, connector, URL, or ability to read
bytes proves neither analytical rights nor permission to retain derivatives.
Source Evidence is not itself an Observation, Pattern, Lesson, or Admitted
Knowledge item.

### Observation

An Observation is a bounded, attributable statement describing what an
admitted observer or method reported about admitted evidence. Observation is
never truth.

Where material, an Observation preserves its exact identity and version;
project and domain; subject and evidence identity; observer or method identity;
method, runtime, model, and preprocessing versions; observation time and
effective scope; structured value; confidence qualification; uncertainty and
abstention; limitations; evidence bindings; provenance; rights/source
eligibility binding; classification; and integrity.

Manual and deterministic observations are first-class. A model-derived
observation remains an observation and gains no additional authority because a
model produced it.

### Pattern

A Pattern is a bounded claim that a recurrence or relationship appears across
an explicit set of admitted Observations. It is not universal knowledge.

A Pattern binds exact supporting observations and material contradicting
evidence. It preserves scope; represented sources, projects, or populations;
bounded evidence references or counts; exceptions and conflicts; uncertainty;
the method used to establish it; temporal applicability; and limitations.
Statistical inference is not required for the first version: an attributable,
deterministically curated Pattern may be valid.

### Lesson

A Lesson is a qualified, context-bound proposition that a Pattern may have
creative or production relevance under stated conditions. It is inert,
explainable, provenance-preserving, challengeable, and scope-qualified.

A Lesson is not universal truth, a ranking, recommendation, approval, creative
command, execution instruction, or Plan.

### Admitted Knowledge

Admitted Knowledge is a domain-owned Knowledge artifact that has passed its
applicable explicit promotion policy. Admission means known and eligible for
specified governed uses. It does not mean true, authoritative, approved,
universally applicable, or executable.

Admitted Knowledge retains exact identity and version, lifecycle, evidence
lineage, provenance, scope, limitations, effective period, rights and retention
obligations, contradiction or disagreement state, and promotion-policy
identity and version.

### Promotion and challenge

Promotion is an explicit semantic operation owned by the knowledge domain. It
does not select a universal workflow. Each domain defines eligible evidence
classes, required evidence, corroboration or independence where applicable,
contradiction treatment, uncertainty requirements, review requirements,
source eligibility, temporal conditions, accountable promotion owner, policy
identity/version, and lifecycle outcome.

Confidence, model agreement, popularity, frequency, or source fame alone can
never promote knowledge. Promotion grants no Runtime capability, approval, or
execution authority.

Admitted Knowledge remains challengeable. Domain lifecycles must represent
semantics equivalent to candidate, active/admitted, qualified/restricted,
disputed, superseded, withdrawn/revoked, and historical/archived where those
states apply. This ADR does not impose one universal lifecycle enum. Competing
Lessons may remain active when scopes differ; conflict resolution is explicit,
versioned, attributable, and never a universal truth resolver.

### Representation migration and knowledge evolution

Representation migration preserves semantic meaning while changing schema,
serialization, or implementation. It uses an explicit, owned, bounded
translator and independent target validation under ADR-0018. For example,
`shot_observation/1` may translate to `shot_observation/2` only when the owning
domain declares the relevant meaning preserved.

Knowledge evolution changes meaning, scope, evidence, conclusion, or
limitations because understanding changed. It therefore creates a new exact
semantic identity or version according to the owning domain. A superseding
Lesson does not rewrite its predecessor to make the new conclusion appear
historically known.

Storage migration, source migration, model migration, representation
migration, language migration, and knowledge evolution remain distinct. No
universal Migration Engine is introduced. High-migration commitments require
stronger evidence under the Constitution.

### Historical interpretation

Superseded or inactive artifacts may be retained where rights and policy permit
to explain prior project decisions, reasoning outputs, audits, reproducibility,
and changes in studio understanding. Historical retention grants no active-use
authority and is bounded by classification, rights, retention, and withdrawal
policy. Historical interpretation does not imply indefinite retention.

### Language neutrality and conformance

Python is an implementation choice, not semantic identity. Durable identity
must not depend on Python class names, module paths, dataclass representation,
object identity, pickle, Python hash behavior, non-canonical insertion order,
or implementation-native enums.

Rust, C++, or another language may implement a bounded component only when
measured evidence justifies it. When a native implementation replaces an
existing authoritative semantic implementation, or two languages concurrently
claim equivalent authoritative behavior, a cross-language conformance suite is
required. Given the same exact admitted semantic input, implementations
claiming semantic equivalence must agree on all contract-defined externally
meaningful behavior, including where applicable:

- contract identity and version;
- canonical representation and semantic digest;
- validation acceptance or rejection;
- deterministic identities;
- lifecycle interpretation and exact compatibility mapping;
- safe failure classification and bounds; and
- provenance preservation.

Equivalent implementations need not use identical algorithms, data
structures, timing, performance, or non-canonical bytes. Exact digest equality
is required only for a digest domain whose contract defines canonical input.
A native internal hot path hidden behind one authoritative implementation may
use narrower boundary tests. This ADR selects no language, FFI, RPC, or rewrite.

### Storage neutrality

Knowledge identity is independent of filesystem path, database row ID,
graph-node ID, object-store URL, vector-store key, cache location, cloud
account, or connector identity. Storage may evolve from local files to an
embedded store, local index, object/distributed storage, or another admitted
technology without redefining semantic identity.

Graph-shaped relationships do not imply a graph database. This ADR selects no
storage product, database, or service.

### Lineage and reverse impact

Lineage relationships are closed, versioned, and domain-owned rather than an
arbitrary relationship bag. Candidate relationship families include
`derived_from`, `supports`, `contradicts`, `supersedes`, `superseded_by`,
`materially_influenced_by`, and policy-owned `affected_by` or invalidation
relationships. Each family must define exact endpoint kinds, direction,
meaning, bounds, and lifecycle before use. Lineage is evidence, not authority.

The logical model must make downstream impact identifiable when a source is
withdrawn or revoked, rights change, evidence is poisoned, research is
retracted, an Observation is invalidated, or a Pattern is superseded. Reverse
lineage must be indexable; a permanent design based on recursive whole-corpus
scans is unacceptable. Small deterministic local indexes are sufficient
initially. A specialized store or service requires measured scale evidence and
Component Admission. No graph service is authorized.

### Rights and knowledge domains

The following provenance and policy domains remain distinct:

1. external or reference knowledge;
2. current-project knowledge;
3. studio-history knowledge;
4. human or expert-contributed knowledge; and
5. experimental or synthetic evidence.

They may have different rights basis, purpose, classification, provenance,
retention, redistribution, withdrawal behavior, trust, and promotion
eligibility. They must not silently pool or merge. Shared contract patterns do
not erase their policy boundaries.

External accessibility is never legal or analytical eligibility. YouTube or
another host is transport or discovery, not a license. VSS may eventually
study lawfully eligible reference material to extract qualified principles and
understanding, not to reproduce unattributed material or clone style. Material
reference influence remains attributable where policy requires it.

### Withdrawal

Withdrawal policy must separately determine effects on raw/reference material,
Observations, Patterns, Lessons, Admitted Knowledge, cached Context, future
reasoning outputs, and historical audit. Domain-owned outcomes may include
delete, quarantine, revoke, recompute, mark affected, prohibit new use, or
retain minimal historical audit evidence where legally and policy permitted.

This ADR does not mandate universal destructive deletion of every derivative.
It requires traceable impact and fail-closed future use whenever current
eligibility is required but unknown. Caches and historical artifacts cannot
bypass current-use revocation.

### Confidence, calibration, and abstention

Observation confidence, calibration evidence, model confidence, human
certainty, and deterministic qualification are distinct. Confidence never
means truth, authority, approval, or authorization. Confidence values from
different model families, versions, populations, or observation domains are
not assumed comparable.

A numeric probability is admitted only when its event/domain semantics and
calibration basis are explicit. Otherwise the owning contract uses bounded,
qualified confidence semantics. Probabilistic observations support abstention;
unknown or uncertain is a successful outcome when appropriate. Thresholds may
govern inclusion or review only through explicit policy and never grant truth
or authority. Deterministic and probabilistic observations may coexist or
disagree without one silently overwriting the other.

### Model provenance

For model-derived observations, material provenance may include model family,
exact model or weights identity and digest, model version, runtime,
preprocessing, inference policy, thresholds, input and output binding,
calibration artifact/version, known limitations, and license or usage
restrictions. Fields genuinely irrelevant to the observation need not be
fabricated. The owning contract defines the minimum sufficient provenance.
Models remain replaceable and non-authoritative.

### First M6 slice

The first M6 implementation uses only original manual and/or synthetic
fixtures. It requires no persistent external media, computer vision, GPU, or
external AI.

The recommended first family is a narrow Shot/Cinematography Observation. M6.1
may define a closed vocabulary for shot scale, camera elevation or height,
camera angle, static or moving state, bounded movement category, subject count,
and basic composition. Exact vocabulary remains contract work and is not
frozen here. Emotion, humor, acting quality, cultural meaning, music quality,
and aesthetic scoring are outside the first slice.

This slice is comparatively observable, bounded, manually testable, useful to
future Shot Design, local-first, and able to exercise later probabilistic
observation without requiring it now.

### Context, Runtime, and workload planes

Context remains bounded task-specific delivery material. It is not the
knowledge hierarchy, persistent knowledge store, lineage database, migration
mechanism, or source synchronization system. Reasoning receives only the
admitted, purpose-limited Context required for its task.

Runtime remains the sole authorization and execution-admission authority. It
is not a knowledge curator, promotion engine, graph engine, or migration
engine. Knowledge promotion never becomes Runtime authority. Runtime carries
bounded authority, identity, digests, and references—not external video or
audio bytes.

Manual and synthetic observation may remain bounded Semantic Plane work. Heavy
media bytes belong to the Data Plane. Decoding, computer vision inference, GPU
feature extraction, or expensive transforms may become Compute/Execution
Plane operations when measured workload requires it. Bounded derived
observations return through governed semantic contracts and exact cross-plane
admission. A domain is not classified wholesale into one plane, and logical
plane separation does not require separate services.

### Minimal components and local-first operation

The first implementation remains workstation-capable and uses existing
contract, Knowledge, Context, and Reasoning boundaries. No vector database,
graph database, video database, Redis, broker, model server, Kubernetes, GPU
farm, crawler, ingestion daemon, Knowledge Engine, Pattern service, or Lesson
service is justified.

Future acquisition, indexing, model, native-code, or storage choices follow
ADR-0023: use the smallest sufficient reliable implementation, measure quality
and full lifecycle cost, preserve replacement and exit paths, and perform
Component Admission when a persistent component is proposed.

### Innovation and reference influence

Reference learning must not force imitation. Future creative reasoning may
combine independently admitted knowledge from cinema, photography, painting,
architecture, music, psychology, science, and other eligible domains while
retaining material source influence. Such synthesis produces a candidate
creative hypothesis or option, not new truth. Novelty does not equal quality,
and governed knowledge does not prohibit intentional rule-breaking.

No originality score, plagiarism detector, Innovation Engine, universal
creativity score, or external-media model training is authorized.

### Creative Intent and prompt editing

Future human natural-language editing should follow this direction:

```text
natural-language edit request
    → governed Creative Intent interpretation
    → affected semantic domains
    → inert candidate options
    → human selection or approval
    → separately governed future execution
```

Prompts must not directly mutate production artifacts by architecture. This
ADR defines no Creative Intent contract and does not implement prompt editing.

### Security boundaries

Source content is inert data. Observation and provider outputs are
non-authorizing. Future contracts and implementations must address, as their
scope requires:

- malformed media, decoder/parser vulnerabilities, decompression bombs, hidden
  streams and metadata, and excessive or recursive structures;
- adversarial media, model or data poisoning, malicious academic/web content,
  and prompt/instruction injection embedded in source material;
- source spoofing, provenance forgery, classification downgrade, rights
  spoofing, withdrawal bypass, cached revoked evidence, and lineage mutation;
- false confidence/calibration, model substitution, poisoned Patterns or
  Lessons, and silent conflict suppression;
- cross-project leakage, privacy, biometrics, real-person identity inference,
  and sensitive-trait inference.

Exact parsing/isolation, privacy, biometric, and real-person policies remain
future scope gates. Real-person or sensitive-trait semantics require separate
explicit architecture if ever proposed. Manual/synthetic fixtures avoid but do
not solve production-media threats.

### Plan IR remains deferred

Observation, Pattern, Lesson, and Admitted Knowledge introduce no executable
steps, workflow graph, scheduling, resources, retry, compensation, recovery,
execution approval, or durable orchestration. They provide no evidence for Plan
IR, which remains deferred.

## Compatibility and Evolution

M3 through M5 behavior remains unchanged. This ADR widens no existing contract
or Context version, changes no registry or digest, and changes no provider,
Gateway, Runtime, or CommandRunner behavior. Future families follow ADR-0018
exact identity/version rules; no `latest`, wildcard, nearest-version,
automatic upgrade, or automatic downgrade resolution is implied.

The four semantic roles justify durable distinctions because they carry
different claim meanings, evidence aggregation, challenge, lifecycle, and use
eligibility. They do not require four universal schemas or four services.
ADR-0015's envelope and federated typed families remain the implementation
architecture.

## Alternatives Considered

### 1. Learn directly into model weights

This can preserve nuance and compact large datasets, but obscures individual
lineage, complicates withdrawal and historical interpretation, increases GPU
and retraining cost, and couples knowledge to model provenance. Rejected as the
initial knowledge architecture; later bounded experiments may supplement, not
replace, governed artifacts.

### 2. Treat every Observation as Knowledge

This is simple initially but collapses report into admitted use, erases
corroboration and challenge, and makes model output appear true. Rejected.

### 3. Universal Knowledge Graph or graph database

Graph traversal could help reverse lineage at scale, but a product-centric
model would freeze storage before measured need and encourage an arbitrary
relationship vocabulary. Rejected. Closed lineage may be indexed locally and
later stored differently without changing semantic identity.

### 4. Universal knowledge-hierarchy object

One object with optional fields for Evidence, Observation, Pattern, Lesson,
and Knowledge would simplify early serialization but recreate the God Object
rejected by ADR-0015 and couple unrelated domains. Rejected.

### 5. External-media-first implementation

Real footage could provide immediate realism but prematurely requires rights
admission, media sanitization, Data/Compute infrastructure, retention, and
possibly models. Rejected in favor of manual/original synthetic fixtures.

### 6. Governed typed knowledge evolution over ADR-0015

Selected. It preserves domain ownership, exact versions, provenance,
challenge, rights withdrawal, historical interpretation, local-first work, and
implementation/storage replacement without another authority or service.

### 7. Delay knowledge evolution until after external AI

This reduces upfront architecture work but lets the first model and dataset
implicitly define confidence, rights, lineage, and promotion. Rejected because
those boundaries must precede probabilistic or external-source implementation.

## Independent Challenge

| Challenge | Resolution |
|---|---|
| Are four levels premature? | They are bounded semantic roles with distinct meanings, not mandatory physical tiers. M6.1 introduces only the families its narrow slice needs. |
| Can ADR-0015 already express them? | Yes: its typed Knowledge Items are the representation foundation. ADR-0024 defines promotion and epistemic meaning that ADR-0015 intentionally did not define. |
| Does promotion create authority? | No. A domain policy records eligibility for governed use; Runtime and humans retain their existing authority. |
| Does historical interpretation require unbounded storage? | No. Retention, rights, classification, minimization, and withdrawal bound storage; metadata may suffice where policy permits. |
| Is reverse impact computationally infeasible? | It must be indexable. A small local index is sufficient first; measured scale can admit another component without changing lineage semantics. |
| Is this a graph architecture in disguise? | Relationships are graph-shaped, but closed semantic edges do not select a graph data model, database, or service. |
| Does cross-language conformance block optimization? | No. It constrains only contract-defined externally meaningful semantics, not algorithms, internal layouts, timing, or non-canonical bytes. |
| Is model provenance too expensive for simple observations? | Requirements are materiality-based. Manual observations do not fabricate model fields; model-derived claims retain enough identity to interpret and reproduce them. |
| Are rights controls too broad for original/synthetic fixtures? | Rights domains remain distinct. Original/synthetic material records applicable provenance and purpose without pretending external-source obligations apply. |
| Does this expand the mission into general knowledge research? | No. Autonomous movie production remains the proving application, the first slice is cinematography, and other domains require separate evidence. |
| Can it remain workstation-local? | Yes. The first slice uses bounded manual/synthetic fixtures, in-process contracts, and no external service, model, or media pipeline. |

## Consequences

### Positive

- Observation remains distinct from truth and knowledge admission.
- Rights, confidence, uncertainty, withdrawal, and influence survive learning.
- Existing ADR-0015 typed Knowledge Items gain a controlled evolution model
  without a second Knowledge architecture.
- Models, languages, and storage can change while semantic identity and
  historical interpretation remain stable.
- The initial movie-focused implementation stays bounded and workstation-local.

### Costs and risks

- Exact evidence lineage, promotion policy, and historical interpretation add
  contract and review work.
- Domain-owned lifecycles may require explicit compatibility and translation.
- Reverse-lineage indexes and withdrawal recomputation may become costly at
  scale.
- The four-role vocabulary could become ceremony if implementations create
  artifacts without decision value.

### Mitigations

- Introduce only the typed families required by one narrow M6 slice.
- Do not create services or registries by category.
- Keep promotion policies domain-owned and proportional to source risk.
- Measure lineage, retention, validation, and migration cost before selecting
  storage or distribution.
- Reassess concept and version pressure at major integration checkpoints under
  the Architecture Entropy Ledger.

## Decision Boundaries

This ADR decides semantic roles, explicit promotion and challenge, confidence
and calibration constraints, model/source provenance, rights-domain
separation, withdrawal traceability, lineage, historical interpretation,
language/storage neutrality, and the manual/synthetic first slice.

It does not define final schemas, cinematic vocabularies, numerical bounds,
source-rights taxonomy, one universal lifecycle, a promotion workflow,
retention durations, a storage/index product, media ingestion, model choice,
calibration technique, provider, native language, FFI, Creative Intent, Shot
Design, or Plan IR.

## Roadmap Impact

The governed sequence is:

1. accept ADR-0024 after independent architecture review;
2. define the narrow M6.1 Shot/Cinematography Observation contracts using
   original manual/synthetic fixtures;
3. implement and verify deterministic/manual observation without external
   services or media ingestion;
4. define only the Pattern, Lesson, and promotion artifacts demonstrated by
   actual observation evidence;
5. separately admit external sources, media processing, or model experiments
   only after their rights, security, Data/Compute, calibration, and Component
   Admission gates are satisfied; and
6. approach Shot Design only through bounded admitted Context.

## Unresolved Questions

- Exact first cinematography vocabulary, bounds, and evidence coordinates.
- Which first Observation, Pattern, Lesson, and admitted-item families are
  justified by M6.1 evidence.
- Domain promotion-policy contracts and accountable human review semantics.
- Rights/eligibility taxonomy and jurisdiction-specific policy ownership.
- Withdrawal outcomes for each source class and derivative kind.
- Calibration artifacts, populations, metrics, and model-update policy before
  probabilistic implementation.
- Local reverse-lineage index representation and the measured scale trigger for
  another component.
- Production media sanitization, parser isolation, privacy, and biometric
  boundaries before non-fixture decoding.
- Quality evaluation for observations, patterns, lessons, and downstream movie
  value.

## Acceptance Criteria

This ADR is acceptable when:

- existing Runtime, Knowledge, Context, Registry, and Reasoning authority and
  behavior remain intact;
- Observation is explicitly not truth and confidence is neither truth nor
  authority;
- source or model access cannot automatically create Admitted Knowledge;
- promotion is explicit, versioned, domain-owned, challengeable, and
  non-authorizing;
- no universal Knowledge object, hierarchy implementation, promotion engine,
  graph, registry, or service is assumed;
- source eligibility, influence, withdrawal, and reverse impact are traceable;
- external, project, studio, human, and synthetic knowledge remain distinct;
- representation migration and knowledge evolution remain separate;
- historical artifacts remain interpretable where policy permits;
- canonical semantics survive language and storage replacement without
  over-constraining internal algorithms;
- the first implementation is manual/synthetic, bounded, local, and movie
  focused;
- no graph/vector database, external AI, media ingestion, new service, or Plan
  IR is required; and
- governance and provenance requirements remain proportional to material risk.

## Architecture Entropy and Mission Alignment

ADR-0024 introduces durable semantic distinctions but no current contract,
Context, registry, provider, package, authority, service, or dependency. A
Proposed ADR alone does not meet the Architecture Entropy Ledger snapshot
trigger, so no entropy baseline is rewritten. Expected future pressure is
limited to typed-family/version growth, evidence-lineage cognition, and
promotion-policy governance; M6 checkpoints must reassess those pressures.

The decision remains recognizable as VSS: governed creative intelligence,
human intent and final authority, explainable accumulated knowledge,
replaceable technology, movie production as the proving application, and
resource-efficient local-first evolution.

## References

- [VSS Constitution](../architecture/vss-constitution.md)
- [Architecture Review Governance](../architecture/architecture-review-governance.md)
- [Architecture Entropy Ledger](../architecture/architecture-entropy-ledger.md)
- [Architecture Debt and Research Ledger](../architecture/architecture-debt-research-ledger.md)
- [M5 Character Continuity and Semantic Engine Integration Checkpoint](../reviews/m5-character-continuity-semantic-engine-checkpoint.md)
- [ADR-0013: Semantic Reasoning Contracts](ADR-0013-semantic-reasoning-contracts.md)
- [ADR-0015: Knowledge Architecture and Bounded Knowledge Packages](ADR-0015-knowledge-architecture.md)
- [ADR-0017: Bounded Context Assembly Between Knowledge and Reasoning](ADR-0017-context-assembly-architecture.md)
- [ADR-0018: Federated Contract Registry Governance](ADR-0018-federated-contract-registry-governance.md)
- [ADR-0021: Studio Workload Planes and Specialized Execution](ADR-0021-studio-workload-planes-specialized-execution.md)
- [ADR-0022: Cross-Plane Admission, Resource Bounds, and Artifact Consistency](ADR-0022-cross-plane-admission-resource-bounds-artifact-consistency.md)
- [ADR-0023: Minimal-Component, Open-Source, Resource-Efficient Implementation](ADR-0023-minimal-component-open-source-resource-efficient-implementation.md)
