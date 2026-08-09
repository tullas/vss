# M5 Character Continuity and Semantic Engine Integration Checkpoint

## Review metadata

- Review date: 2026-08-09
- Authoritative reviewed `main`: `94ca95e1313c034da8cef61ae5013b24c7b1fd50`
- Review branch: `review/m5-character-continuity-semantic-engine-checkpoint`
- Scope: M3 semantic platform, M4 movie-domain integration, M5.1–M5.3
  Character Continuity, and readiness for a Cinematic Observation / Film
  Learning architecture decision
- Method: source, schema, registry, dependency, public-path, test, audit,
  performance, negative-space, and constitutional workload review

This is a point-in-time implementation and governance checkpoint. It is not an
ADR and does not authorize the next domain or any infrastructure.

## Executive decisions

| Question | Decision |
|---|---|
| M5 overall architecture | **ACCEPTED_WITH_NON_BLOCKING_FINDINGS** |
| Contract versioning | **HEALTHY** |
| Context versioning | **HEALTHY** |
| ReasoningGateway | **SHOWING_PRESSURE** |
| Registry federation | **HEALTHY** |
| Semantic-engine taxonomy | **DOCUMENT_ONLY** |
| Plan IR | **STILL_PREMATURE** |
| Cinematic Observation | **READY_FOR_ADR** |
| Initial cinematic slice | Narrow Shot/Cinematography Observation, beginning with governed manual/synthetic fixtures |

No Critical or High finding, current source violation, semantic widening,
authority defect, or progression blocker was found. M5 reused rather than
redesigned the M3 platform. The next activity should be a Cinematic Observation
/ Film Learning ADR, not implementation.

## Findings

| Severity | Secondary classification | Finding | Disposition |
|---|---|---|---|
| Medium | `FUTURE_ADR_REQUIREMENT` | Current contracts can carry confidence, provenance, qualifications, unknowns, and limitations, but do not define calibrated probabilistic observation semantics, model identity/evidence, or cross-model comparability. | The Cinematic Observation ADR must own confidence/calibration and model provenance before probabilistic implementation. |
| Medium | `FUTURE_ADR_REQUIREMENT` | External film analysis needs explicit rights basis, allowed analytical purpose, retention, derivative-metadata treatment, withdrawal, and reference-influence governance. Existing provenance and revocation are useful primitives but do not constitute rights admission. | Make source eligibility and withdrawal a fail-closed part of the next ADR; do not ingest external media first. |
| Medium | `CURRENT_ARCHITECTURE_DEBT` | `ReasoningGateway` is 724 lines and has three movie-specific public adapters in addition to Generate Options lifecycle handling. It contains no continuity rules or effect authority, but audit, validation, view extraction, and dispatch boilerplate are growing. | Classify as `SHOWING_PRESSURE`. Reassess when the next domain adds a fourth materially distinct adapter or when lifecycle fixes must be repeated; do not refactor speculatively. |
| Low | `HEALTHY_EXPLICIT_VERSIONING` | Continuity uses task versions 1–3, Context versions 1–2, catalogue versions 1.0/1.1, and one transition-evidence family. Each increment reflects changed lifecycle or admitted evidence, and old meanings remain exact. | Preserve explicit mappings; monitor branch density and documentation as families grow. |
| Low | `CURRENT_ARCHITECTURE_DEBT` | Implementation registries use several small domain-specific classes and Character Continuity contains explicit v2/v3 dispatch. This is readable at current size but would become repetitive across many probabilistic engines. | Retain healthy explicitness now. Consider a small shared exact-registration utility only after another domain repeats the full pattern. |
| Low | `FUTURE_IMPLEMENTATION_GUARDRAIL` | CI has strong public-path and full-regression evidence, but domain steps repeat suites and the security suite dominates local validation time. | Keep focused, integration, architecture, and full-regression layers distinct; optimize scheduling only from measured CI data and never remove security evidence for speed. |
| Observation | `NO_ACTION` | The independent M5 boards caught the task-v1/v2 executability mismatch, Context/evidence contract mismatch, and transition reassociation weakness before merge. | Existing milestone plus constitutional cadence is working. Use a constitutional board at the next probabilistic, large-media, external-provider, or new-plane boundary—not every PR. |

There are no `CURRENT_SOURCE_VIOLATION` findings.

## M3 through M5 stability

| Foundation | Classification | M5 evidence |
|---|---|---|
| Runtime authority | `UNCHANGED_REUSED` | Character Continuity is inert semantic reasoning and adds no capability, permission, worker, or alternate authority path. |
| Federated Context Registry | `EXTENDED_CLEANLY` | Exact Context v1/v2 registrations and compatibility coexist with earlier families. |
| Context Assembly | `EXTENDED_CLEANLY` | Task-specific assembly validates, minimizes, binds, expires, revokes, reports, and audits without reasoning. |
| ReasoningGateway | `SHOWING_PRESSURE` | The established lifecycle is reused, but domain adapter and terminal-audit branches are accumulating in one module. |
| Provider-view pattern | `EXTENDED_CLEANLY` | Deeply immutable, minimized Character Continuity views preserve the existing provider-isolation model. |
| Strategy/provider registration | `EXTENDED_CLEANLY` | Exact 1.0 and 1.1 implementations preserve historical behavior and reject substitution. |
| Audit | `EXTENDED_CLEANLY` | One terminal attempt, bounded metadata, exact digests, and actual gate outcomes remain consistent. |
| Response envelope and CLI | `UNCHANGED_REUSED` | CommandRunner loads bounded files, binds correlation, routes, and maps results; it owns no continuity rule. |
| Canonical digests | `UNCHANGED_REUSED` | Registry, artifact, Context, view, invocation, and result domains remain explicit and mutation-tested. |
| Contract Registry discipline | `UNCHANGED_REUSED` | Registries contain static kinds and exact compatibility, not instances, capacity, budget, or authority. |

M5 required no fundamental M3 redesign. The architectural pressure is
maintainability inside adapters, not a broken authority or semantic boundary.

## Runtime, Context, Gateway, and CommandRunner

Runtime remains the sole capability execution and authorization authority. It
is not called by Character Continuity providers and does not transport media,
resolve assets, schedule work, or treat a semantic result as authority.

Context remains task-specific semantic delivery. Context v1 admits task v2 and
observation evidence; Context v2 admits task v3 and independently validated
transition evidence. Neither is a universal Context, asset snapshot, cache
claim, or production-validity claim. A new semantic evidence class—not an
implementation convenience—caused Context v2.

ReasoningGateway remains **generic semantic lifecycle plus bounded adapters**.
It validates exact contracts and Context, binds correlation and digests,
checks expiry/revocation, extracts immutable views, resolves trusted semantic
implementations, invokes once, independently validates inert output, and
audits. Continuity rules, comparison logic, and transition construction live
outside it. It has no Runtime, workflow, capability, queue, worker, storage, or
media execution path. Its size and adapter repetition justify monitoring, not
redesign. The refactoring trigger is repeated lifecycle code becoming
inconsistent or a fourth materially different semantic family requiring
another large branch; the likely response would be small typed adapters around
one lifecycle, not a universal engine object.

The independent acceptance classification is
`HEALTHY_WITH_SIZE_PRESSURE`, approaching a `SMALL_REFACTOR_TRIGGER` rather
than requiring remediation now. Extraction becomes warranted when another
domain materially duplicates the lifecycle, adapter code outweighs the generic
lifecycle, task/version branches cease to be a small closed set, a domain rule
enters Gateway, or a provider class requires genuinely different lifecycle
machinery. Line count alone is not a trigger.

CommandRunner remains presentation and routing: strict bounded file loading,
correlation, public API selection, envelope construction, and exit mapping. No
Character Continuity or future film-learning policy resides there.

## Contract and version matrices

### Character Continuity contracts

| Contract | Meaning | Executable path | Historical status |
|---|---|---|---|
| `analyze_character_continuity/1` | M5.1 defined validation-only task | none | Preserved: `defined_validation_only`, `not_implemented` |
| `analyze_character_continuity/2` | M5.2 bounded observation comparison | Context v1 → catalogue 1.0 → result v1 | Active and reproducible |
| `analyze_character_continuity/3` | M5.3 explicit-transition-aware analysis | Context v2 → catalogue 1.1 → result v1 | Active and exact |
| `character_identity/1` | Exact semantic character identity | assembly input | Unchanged |
| `continuity_sequence/1` | Explicit linear continuity positions | assembly input | Unchanged |
| `character_observation/1` | Positive scene-local observation vocabulary | assembly input | Unchanged |
| `character_continuity_transition_evidence/1` | Independently validated explicit transition claim | Context v2 input only | New in M5.3; inert/non-authorizing |
| `character_continuity_observation_set/1` | Qualified inert observations/transitions/contradictions/unknowns | result for task v1/v2/v3 through explicit mappings | Reused without widening |

The three task versions are healthy independent versioning. V1 could not be
made executable without changing historical meaning; v2 could not admit new
transition evidence without changing its Context contract; v3 expresses the
new exact compatibility. No latest, range, nearest, upgrade, or downgrade
resolution exists. Result v1 already contained the qualified structural fields
needed by v3 and therefore did not require artificial version growth.

### Context versions

| Context | Exact task | Evidence | Catalogue |
|---|---|---|---|
| `character_continuity_context/1` | `analyze_character_continuity/2` | independently validated sequence, identities, observations | `vss.character-continuity.rules.deterministic/1.0.0` |
| `character_continuity_context/2` | `analyze_character_continuity/3` | v1 material plus independently validated transition evidence IDs/digests and minimal projections | `vss.character-continuity.rules.deterministic/1.1.0` |

Context versioning is **HEALTHY**: semantic input meaning caused the new
version. There is no extension bag or universal movie Context pressure.

### Rule catalogues

| Catalogue | Semantics | Assessment |
|---|---|---|
| `vss.character-continuity.rules.deterministic/1.0.0` | Explicit repeat qualification, persistence off, no discovered transitions/contradictions | Immutable M5.2 history |
| `vss.character-continuity.rules.deterministic/1.1.0` | Adds bounded exact-repeat, explicit-transition, incomparable/insufficient-evidence and contradiction-eligibility structure | Closed M5.3 evolution; current incompatibility set remains empty |

Catalogues are repository-owned, immutable, exact, deterministic,
non-authorizing, and caller-inaccessible. They are useful domain policy
artifacts, not evidence for a general rules DSL. Other domains may adopt the
same governance properties without sharing a universal rules engine.

### Provider and strategy families

| Semantic path | Strategy | Provider/API | Calls/retries/fallback |
|---|---|---|---|
| Generate Options | deterministic Generate Options 1.0 | deterministic options 1.0/API 1 | one / none / none |
| Scene Breakdown | deterministic Scene Breakdown 1.0 | deterministic scene breakdown 1.0/API 1 | one / none / none |
| Scene Production Options | `vss.generate-scene-production-options.deterministic/1.0.0` | `vss.reasoning.deterministic-scene-production-options/1.0.0`, API 1 | one / none / none |
| Character Continuity M5.2 | `vss.analyze-character-continuity.deterministic/1.0.0` | `vss.reasoning.character-continuity.deterministic/1.0.0`, API 1 | one / none / none |
| Character Continuity M5.3 | `vss.analyze-character-continuity.deterministic/1.1.0` | `vss.reasoning.character-continuity.deterministic/1.1.0`, API 1 | one / none / none |

The duplication verdict is **HEALTHY_EXPLICITNESS**. Exact identities,
provider-view isolation, one-call semantics, independent validation, and
dry-run zero-call behavior are consistent. A shared utility is not yet earned;
an external/probabilistic provider class would be a constitutional trigger.

## Registries and dependency direction

| Registry | Current bounded content | Assessment |
|---|---|---|
| Semantic Contract | generic semantic task/result kinds and exact mappings | Static and non-authorizing |
| Context Contract | eight exact schema registrations plus fixed domain compatibility | Healthy; no instances or runtime state |
| Knowledge Contract | Knowledge item/package kinds and lifecycle compatibility | Federated and domain-owned |
| Movie Contract | fourteen exact schema registrations, including three continuity task versions and transition evidence; three exact task/result mappings | Bounded; no reason to split by count alone |
| Reasoning implementation | trusted built-in exact strategy/provider pairs | Static implementation admission, not worker registration |

Registry lookup is small and deterministic. Registration counts do not create
an ownership or runtime complexity problem. Contract packages remain below
providers, Gateway, Runtime, and CommandRunner; architecture dependency tests
protect these directions. Movie Registry should split only after repeated
distinct ownership, lifecycle, or security boundaries—not because it has
fourteen entries.

At 50 or 100 families, hand-maintained mappings remain possible but review and
fixture burden will grow. At hundreds of families, measured error rates or
maintenance time may justify repository-owned manifest tooling or generated
indexes. That is a future tooling trigger, not evidence for a universal
registry or generator now.

## Evidence-binding pattern

M5.3 demonstrates a repeated architectural chain:

```text
domain evidence artifact
    → independent validation
    → exact task-specific Context projection
    → minimal immutable provider projection
    → independently validated inert semantic output
```

This is `REPEATED_PATTERN_WORTH_DOCUMENTING`. It is applicable in principle to
rights/source eligibility and future camera or emotion observations, but
domain identities, qualification, and compatibility remain domain-owned. It
is not ready for a shared framework; one more independent domain should test
whether the repetition is genuinely stable.

## Semantic-engine taxonomy

Implementation evidence supports a descriptive distinction:

- **Evidence Interpretation / Semantic Observation engines** qualify bounded
  observations from admitted evidence. Scene Breakdown and Character
  Continuity fit here. “Observation” never means objective truth.
- **Option Generation engines** produce bounded inert alternatives. Generate
  Options and Scene Production Options fit here. An option is not a rank,
  recommendation, approval, or plan.

Every result remains non-authorizing. This taxonomy is useful vocabulary for
future architecture documents (`DOCUMENT_ONLY`), but it does not justify base
classes, a universal engine API, or a new registry today.

## Probabilistic and multimodal readiness

The existing architecture is structurally ready for a probabilistic provider:
exact task/Context compatibility, minimized evidence, provider identity,
provenance, confidence fields, qualifications, unknowns, limitations,
independent output validation, audit, and inert results already exist.
However, those primitives do not yet define:

| Gap | Classification | Required decision |
|---|---|---|
| Confidence calibration and comparability | `MUST_BE_DECIDED_IN_CINEMATIC_ADR` | Meaning, calibration evidence, thresholds, abstention, and model/version scope |
| Probabilistic observation taxonomy | `MUST_BE_DECIDED_IN_CINEMATIC_ADR` | Closed observation families, uncertainty, disagreement, and non-truth wording |
| Model/provider provenance | `MUST_BE_DECIDED_IN_CINEMATIC_ADR` | Model identity/version/digest, runtime/config where material, license, and qualification |
| Multimodal evidence binding | `BLOCKS_CINEMATIC_ADR` only if omitted from that ADR | Exact source/time-range/track/frame bindings without routing bytes through Runtime |
| AI implementation selection | `CAN_BE_DECIDED_DURING_IMPLEMENTATION` after an ADR admits the class | Component Admission, measured quality/cost, security, and local-first evidence |

These gaps do not require redesign of M3–M5, but probabilistic implementation
must not precede their architectural treatment.

The Cinematic Observation ADR must answer the confidence gate explicitly:

1. which observation domain a confidence value qualifies;
2. what calibration evidence and population support it;
3. how unknown and abstain differ from low confidence;
4. whether values are comparable across models, versions, or observation
   families;
5. that no threshold grants truth, authorization, approval, or execution;
6. whether and under what qualification low-confidence output may enter a
   task-specific Context; and
7. how deterministic and probabilistic observations coexist or disagree
   without one silently overwriting the other.

Model confidence is not automatically system confidence. A future model-backed
observation must remain attributable, where material, to exact model identity
and version, weights digest and licensing/provenance qualification,
implementation/runtime version, preprocessing pipeline/version, inference
policy/configuration version, input evidence identity, output observation
identity, calibration metadata, and known limitations. This is a conceptual
provenance obligation, not a frozen model schema.

## Source rights, withdrawal, and reference influence

Knowledge provenance, source identity, purpose, classification, retention,
revocation, and lineage are sufficient primitives to build upon. They do not
prove copyright, license, consent, analytical eligibility, or permitted
derivative use. The next ADR must explicitly own:

- rights basis and source eligibility for the declared analytical purpose;
- retention and treatment of derived observations after source withdrawal;
- exact lineage from source/time range to observation, pattern, lesson, and
  later Context;
- separation of factual provenance from legal/rights qualification;
- reference influence, aggregation/diversity constraints, and prevention of
  silent source-specific imitation or provenance loss.

Admission should fail closed when required rights/source validity is unknown.
YouTube or another hosting platform is transport/discovery, never an implicit
license. Suitable conceptual source tiers are VSS-owned/generated, explicitly
licensed, public domain, compatible Creative Commons, then other material only
after explicit review. This checkpoint makes no legal determination.

The next ADR must define withdrawal propagation separately for raw media,
derived observations, aggregated patterns, lessons, cached Contexts, future
option/recommendation inputs, and historical audit. It must not assume every
derivative is necessarily deleted: retention, quarantine, continued historical
evidence, and prohibition on future use are rights/policy decisions. Exact
lineage must at least make every affected derivative identifiable. Source
accessibility never establishes source eligibility, and eligibility must bind
purpose, classification, permitted retention, derivative-metadata treatment,
redistribution restrictions, revocation, and provenance.

## Film Learning readiness and initial slice

The proposed flow—eligible source → observations → patterns → lessons →
task-specific Context → Shot Design—is architecturally plausible if each arrow
preserves exact provenance, qualification, withdrawal behavior, and bounded
compatibility. It should not be one universal cinematic observation object.
Cinematography, editing, performance, emotion, humor, sound, lighting/color,
and blocking have different evidence and confidence semantics.

Observation, pattern, and lesson should have independently reviewable contract
meanings and lifecycles: an observation records what was detected or
interpreted from exact evidence; a pattern qualifies repetition or association
across observations; a lesson is a bounded qualified generalization eligible
for a particular future task. Pattern frequency is not artistic truth, and a
lesson is not a recommendation, approval, or authority. The next ADR should
start with a narrow federation rather than either a Movie/Cinematic God Object
or one registry per individual property.

Start with **narrow Shot/Cinematography Observation**: shot boundaries and
duration, framing/shot-scale category, subject count, approximate camera-angle
category, movement category, and a bounded composition category. Begin with
original synthetic/manual fixtures. This slice is relatively observable,
directly useful to later Shot Design, and can establish qualified multimodal
contracts without first solving culturally subjective emotion, humor,
performance, music, or dialogue interpretation.

External reference learning, project-specific learning, and studio feedback
learning must remain separate provenance and policy domains. They may share
qualified observation contracts only through explicit compatibility; they
must not silently pool evidence, rights, retention, or influence. A future
human/director feedback loop needs its own meaning for acceptance/rejection,
reason, outcome, and authority.

## Data Plane and Compute Plane implications

Cinematic Observation introduces large video/audio bytes. ADR-0021 and
ADR-0022 remain sufficient constitutional boundaries:

- Runtime carries bounded authority, identities, digests, purpose, and
  references—not a two-hour film payload.
- A governed Data Plane eventually transports or resolves exact media bytes.
- Semantic outputs are bounded derived observations, not proof of source truth.
- Operation classification follows workload. Manual/deterministic fixtures and
  small metadata extraction may be local Semantic Plane work; decode, computer
  vision, GPU inference, or long-running media analysis may require a
  Compute/Execution operation with Runtime admission and direct governed Data
  Plane access.

The domain must not be classified wholesale into one plane. The future ADR
must define the boundary and stop before implementing heavy media if the Asset
and Worker/Durable Execution ADR gates become applicable.

## Minimal components, AI, and pattern learning

ADR-0023 holds under all reviewed next-domain scenarios. No video database,
vector database, embeddings, broker, Redis, Kubernetes, GPU cluster, search
service, or model server is justified now. The evidence-led sequence is:

```text
manual/original structured fixtures
    → deterministic metadata extraction
    → optional open-source vision tools/models behind stable interfaces
    → measured small local model
    → larger/shared inference only when quality and workload justify it
```

Begin by deriving governed structured observations and a provenance-preserving
pattern library, not by fine-tuning a large video model. Structured patterns
are more inspectable, withdrawable, testable, locally queryable, and cheap.
They may lose nuance and require careful normalization; future evidence can
justify models where deterministic/structured approaches do not meet quality.
Cost must be measured per quality-approved observation or downstream artifact,
including review and rejection, rather than per inference call.

## Plan IR reassessment

Verdict: **STILL_PREMATURE**.

M5 implements sequence positions, semantic transition evidence, provider calls,
and audit lifecycle. It does not implement executable steps, dependency graphs,
resource reservations, scheduling, retries, compensation, durable state,
recovery, approval gates, or effect transitions. A continuity transition is
semantic evidence, not a plan edge. Cinematic Observation should add evidence,
not execution planning. Reassess only after a domain produces concrete,
repeated orchestration semantics—likely after Shot Design and before effectful
Compute—not merely after another semantic family.

## Performance, concurrency, and cost

The 419-test baseline passes. M3 performance profiles exercise the real
Gateway with bounded concurrency; M4 and M5 tests prove deterministic repeated
runs, dry-run gates, exact audit association, and shared-Gateway concurrency.
M5.3's reported in-memory analysis timing is sanity evidence, not an end-to-end
production SLO. Current scenes (8), characters (8), observations (128),
transitions/comparisons, result bytes, provider calls (1), and iterations (1)
are bounded. Comparison is grouped rather than unrestricted pairwise work.

Canonicalization, registry construction, Context assembly, and independent
validation add governance cost but show no measured local-first bottleneck.
Exact versions chiefly add maintenance and regression cost, not meaningful
runtime lookup cost at current scale. Do not weaken binding or digest checks
for speculative speed.

CI should retain four layers: focused domain tests, public integration paths,
architecture/security evidence, and complete regression. Repeated CI steps may
be consolidated only when timing and failure-localization data show value. The
past flaky/performance history reinforces keeping performance evidence
qualified rather than using timing as an unstable correctness gate.

## Architecture evidence and governance

The ADR Evidence Matrix accurately records M5.1/M5.2/M5.3 Character Continuity,
ADR-0021 Semantic Plane scope, ADR-0022 Asset/Compute deferrals, and ADR-0023
no-component evidence. It contains no false `IMPLEMENTED` claim discovered by
this review, so no matrix correction is required.

The governance process demonstrated value:

- M5.2 precondition review prevented mutation of validation-only task v1 and
  caused explicit task v2 evolution.
- M5.3 expressiveness review prevented smuggling transition evidence into
  Context v1 and caused exact task v3, Context v2, and catalogue 1.1 evolution.
- Independent acceptance found and corrected transition reassociation and
  duplicate-identity weaknesses before merge.

Continue Milestone Boards for material semantic increments. Run a
Constitutional Board for the Cinematic Observation ADR and whenever large media,
probabilistic/external providers, new persistent state, a new plane, or
effectful execution is proposed. Do not impose constitutional review on every
small implementation PR.

## What important production property currently has no architectural owner?

| Property | Classification | Future owner/trigger |
|---|---|---|
| Confidence calibration | `NEEDS_NEXT_ADR` | Cinematic Observation ADR before probabilistic output |
| Probabilistic observation taxonomy | `NEEDS_NEXT_ADR` | Cinematic Observation ADR |
| Model/config provenance | `NEEDS_NEXT_ADR` | Before first model-backed observation |
| Reference rights and analytical eligibility | `NEEDS_NEXT_ADR` | Before external persistent source analysis |
| Reference influence and withdrawal propagation | `NEEDS_NEXT_ADR` | Film Learning architecture |
| Human review semantics | `FUTURE_DOMAIN` | Before review state becomes workflow/authority |
| Learning feedback and quality measurement | `FUTURE_DOMAIN` | Project/studio learning ADR |
| Source/raw-media retention | `NEEDS_NEXT_ADR` | Cinematic Observation source-eligibility policy |
| Media sanitization and parser isolation | `NEEDS_NEXT_ADR` | Before any non-fixture media decoding |
| Malicious-media handling | `NEEDS_NEXT_ADR` | Cinematic Observation threat boundary; implementation follows admitted workload |
| Model update/replacement policy | `NEEDS_NEXT_ADR` | Before model-backed observations; exact versions and no implicit migration |
| Production media lineage and output admission | `PRODUCTION_ONLY` | Asset/Output Admission architecture |
| Worker isolation, durable recovery, scheduling | `PRODUCTION_ONLY` | Worker/Durable Execution ADR |

Current exact semantic identity, qualification, provenance, Context lifecycle,
and non-authorizing results are `OWNED_ALREADY`; the table identifies the
missing specialized semantics rather than assigning them implicitly to
Runtime, Gateway, Knowledge, or audit.

## Constitutional workload stress

| Stress | Conclusion |
|---|---|
| Deterministic semantic request | Current bounded local reference path remains sound. |
| Probabilistic multimodal request | Architecture shape holds; calibration, model provenance, and epistemic contracts are next-ADR requirements. |
| Two-hour film / thousands of shots | Bytes cannot traverse Gateway; use references, bounded observation batches, and likely Data/Compute gates. |
| One workstation / no network | Manual fixtures and deterministic metadata can remain local with no service. |
| GPU-assisted observation | GPU availability is not authority; measured work may require Compute admission and isolation. |
| External licensed media | Exact rights/source admission, retention, lineage, and withdrawal are mandatory. |
| Revoked source | Derived observations/patterns need exact reverse lineage and defined quarantine/withdrawal behavior. |
| Changing model version | Model/config identity must be exact and outputs remain historically attributable; no `latest`. |
| Many references / repeated learning | Bounded families and provenance-preserving aggregation are needed; no God observation or hidden mixing. |
| Distributed future compute | Runtime routes admission/references, Data Plane moves bytes, workers cannot self-authorize, and output remains subject to admission. |

ADR-0021/0022/0023 remain coherent under these stresses. The gaps are explicit
future gates, not contradictions in the current platform.

The next ADR's security projection must cover malformed media and decoder
vulnerabilities, decompression bombs, hidden streams and metadata, adversarial
frames/audio, source spoofing, rights-metadata tampering, model poisoning and
replacement, transcript/metadata prompt injection if an AI boundary exists,
privacy and biometric processing, real-person inference, and sensitive-trait
claims. The ADR must assign trust, validation, isolation, size/compute bounds,
and fail-closed eligibility boundaries; it need not prematurely implement all
production mitigations. Manual/original structured fixtures avoid—not solve—
these media risks during the first semantic slice.

## Recommended roadmap

The reviewed candidate roadmap is preferred over immediate Shot Design, Asset
Management, Plan IR, AI integration, or Music:

```text
M5 checkpoint
    → Cinematic Observation / Film Learning ADR
    → source eligibility, provenance, withdrawal, confidence, and influence decisions
    → narrow Shot/Cinematography Observation contracts
    → deterministic/manual original-fixture implementation
    → optional measured open-source CV experiments
    → provenance-preserving pattern/lesson architecture
    → Shot Design architecture
```

Shot Design now would lack governed cinematic evidence. Asset Management is
important but is not required for original bounded semantic fixtures; it
becomes mandatory before persistent/heavy external media. Plan IR has no
execution evidence. AI integration before epistemic and rights contracts would
invert governance. Music is more subjective and less direct as the first bridge
to Shot Design.

## Validation and scope

The pre-change baseline passed 419 Python `unittest` cases across configuration,
commands, Runtime, SDK, providers, workflows, architecture boundaries,
reasoning contracts/Gateway, performance, Knowledge, Movie and Character
contracts, M4 services, Context, M5.2/M5.3, infrastructure contracts, and
security. The public M4/M5 Gateway, CLI, dry-run, determinism, and concurrency
paths are included in those suites. Full repository validation after this
report is recorded in the checkpoint PR.

The unrelated untracked
`.local/secrets/development.auto.tfvars.example` remains untouched.

No Cinematic Observation, Film Learning, Shot Design, Plan IR, AI, retrieval,
embedding, media ingestion, Asset/Data implementation, Compute/Execution
implementation, database, broker, worker, queue, scheduler, rendering,
distributed infrastructure, or dependency is introduced by this checkpoint.
