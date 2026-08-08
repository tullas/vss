# ADR-0020: Character Continuity Architecture

## Status

Accepted

## Context

ADR-0019 and M4 established a governed chain from a validated Story Fragment to
deterministic Scene Breakdown and inert Scene Production Options. The M4
Architecture and Integration Checkpoint accepted that chain and recommended
Character Continuity before Plan IR because continuity is the smallest next
capability that introduces persistent semantic identity, evidence across
multiple scenes, possible state change, and contradiction detection without
introducing effects.

M4 is intentionally scene-local after breakdown: production options bind one
exact scene. It does not establish whether two character references denote the
same narrative entity, whether scenes share a story-world chronology, whether a
state should persist, or whether incompatible claims are actually
contradictory. Treating display names or scene ordinals as answers would turn
convenient heuristics into false identity and chronology claims.

VSS needs a bounded, provider-neutral way to examine independently validated
scenes and return traceable continuity observations, contradictions, unknowns,
and qualifications. The output must remain advisory and inert. This ADR defines
that architecture only; it implements no contract, Context family, rule,
provider, schema, storage, workflow, or feature.

## Decision

VSS will define a future narrow Character Continuity semantic capability:

```text
validated scene_breakdown/1
  -> exact selection of 2–8 scenes
  -> exact governed character identities
  -> explicit continuity-sequence qualification
  -> character_continuity_context/1
  -> existing Reasoning Gateway
  -> deterministic continuity rules/provider
  -> character_continuity_observation_set/1
```

The conceptual task is `analyze_character_continuity/1`. Its narrow purpose is
`character_continuity_local_validation`. The first result contains inert
observations, explicit transitions, unresolved transitions, contradictions,
unknowns, review-suggested flags, provenance, confidence qualifications, and
limitations. It does not repair content, decide which claim is true, rank
alternatives, approve continuity, order a reshoot, or create a plan.

Scene Breakdown remains the primary structured input. Exact evidence references
back to governed Story Fragment material are retained, but complete source text
is not blindly re-ingested. A missing structured claim remains unknown; the
continuity provider cannot retrieve more material.

The first implementation will be deterministic, local, bounded, and based only
on explicitly represented identities and typed claims. It performs no semantic
name matching, NLP entity resolution, prose inference, image/costume/actor
recognition, or external AI call.

## Why Character Continuity follows M4

Character Continuity provides the first evidence across semantic units:

- an identity persists independently of display text and scene position;
- observations from multiple scenes accumulate without becoming truth;
- state claims may differ, transition, remain unknown, or conflict;
- contradiction requires compatible scope and explicit evidence;
- provenance must connect every conclusion to multiple exact scenes;
- chronology must be governed separately from presentation order;
- cross-scene bounds expose real performance and contract-evolution pressure.

This offers more architectural learning than broadening deterministic scene
segmentation. It is safer than Shot Design because it does not introduce camera
hierarchy or plan-like ordering, and safer than Plan IR because no action graph
has yet been evidenced. It exercises the existing M3/M4 governance boundaries
without adding effects or external dependencies.

## Relationship to M4

Character Continuity consumes validated M4 movie artifacts; it does not replace
or reinterpret their ownership:

```text
Story Fragment --validated source claims--> Scene Breakdown
Scene Breakdown --exact selected scenes--> Character Continuity
Scene Breakdown --one exact scene--> Production Options
```

Scene Breakdown owns deterministic narrative-unit boundaries and scene-local
structured observations. Character Continuity owns only cross-scene comparison
of admitted character observations. Production Options remains an independent
single-scene advisory path. Continuity does not require Production Options in
v1, and Production Options does not become continuity state.

The capability consumes no raw project directory, complete movie project,
unvalidated screenplay, actor record, or media asset. It cannot mutate the
Scene Breakdown or Story Fragment from which evidence came.

## Authority boundary

Runtime remains the sole authorization and execution authority. Character
Continuity Context assembly, registries, rules, strategy, provider, validation,
result, confidence, evidence, revocation, and audit are non-authorizing.

- a continuity observation is not approval;
- a contradiction is not a production instruction;
- a continuity risk is not a blocker, priority, task, or reshoot order;
- confidence grants no authority and does not prove artistic error;
- evidence and provenance grant traceability, not truth or permission;
- registration means structurally known, not authorized or executable;
- the continuity path cannot invoke Runtime capabilities or workflows;
- the continuity path cannot alter scenes, story text, assets, or state;
- the Reasoning Gateway may invoke only the admitted inert reasoning provider;
- no result can expand its input purpose, classification, trust, or authority.

CommandRunner may load bounded files, validate outer correlation, route to
Context/Reasoning owners, and map typed outcomes to the existing VSS envelope.
It must not own character identity, chronology, persistence, contradiction,
rule selection, provider selection, digests, semantic honesty, or audit policy.

## No Character God Object

VSS will not introduce a universal Character Object. A single mutable aggregate
covering biography, appearance, costume, performance, dialogue, voice,
relationships, emotions, physical condition, legal data, actor data,
scheduling, assets, and production instructions would conflate distinct
sources, owners, lifecycles, classifications, and authorities.

ADR-0020 uses separate bounded concepts only:

1. a source-declared character reference;
2. a governed character semantic identity;
3. a scene-local typed observation;
4. a continuity-sequence binding;
5. a cross-scene observation or contradiction.

Costume, emotional, relationship, performance, actor, asset, schedule, and
production-instruction models remain separate future decisions. A later family
may reference the same semantic character identity without expanding this
result into a universal record.

## Character identity model

Five identities are distinct:

1. **Source-declared character reference:** the exact identifier or declaration
   carried by governed source material. It remains a source claim.
2. **Character semantic identity:** a stable, project-scoped movie-domain ID
   explicitly admitted by a governed binding. It denotes the narrative entity
   analyzed by continuity.
3. **Scene-local character observation:** an occurrence or state claim binding
   the semantic identity to one exact scene and evidence.
4. **Cross-scene continuity identity:** the semantic character identity plus
   the continuity-sequence scope in which observations may be compared.
5. **Performer/actor identity:** future, separately governed personal or
   production data. It is never inferred from character identity.

The first implementation requires explicit stable semantic character IDs from
governed source declarations or a separately validated identity-binding
artifact. Identity does not derive solely from display name, capitalization,
scene ordinal, array position, or occurrence order. Project identity is part of
the binding domain.

Display names are labels only. “Guard” in two scenes is not automatically one
person. Two people with the same name remain distinct. Aliases, titles,
transliteration, renaming, anonymous roles, groups, and multiple roles remain
unresolved unless an exact governed binding explicitly relates them. The first
implementation has no heuristic alias table or fuzzy match. Unknown or
ambiguous identity fails closed for cross-scene comparison.

The precise lexical format and digest construction for a semantic character ID
are deferred to M5.1, but the format must be bounded, opaque to display-name
semantics, stable across event time/process/path, project-bound, and protected
against caller substitution.

## Character observation

A character observation is a bounded typed assertion with:

- observation identity/version;
- exact character semantic identity;
- exact Scene Breakdown identity/version/digest;
- exact scene ID/content digest;
- source binding and inert evidence references;
- observation category and typed state category/value where applicable;
- provenance category: source-declared, source-observed, rule-derived, or
  unresolved;
- continuity-sequence identity and qualified position/relationship;
- confidence and basis;
- assumptions, ambiguity, unknowns, conflicts, and limitations;
- rule identity/version when derived.

The first implementation admits only:

- **presence:** explicit presence of the exact character in one scene;
- **possession:** an explicit claim that the character possesses or does not
  possess an exactly identified narrative item;
- **physical state:** an explicit value from a small closed taxonomy whose
  meaning is defined by the contract.

Explicit location claims are deferred from the first automatic comparison
slice. Location commonly changes without contradiction and needs stronger
chronology/transition evidence. Scene/location evidence may remain inert
provenance or unknown, but the first rules do not derive location continuity.
Costume, emotion, relationship, narrative status, and dialogue are likewise
deferred.

Presence is positive evidence only. Non-mention never creates an absence
observation. A negative state must be an explicit admitted claim, not an
inference from omitted text.

This rule applies uniformly: a character, object, injury, location, costume, or
other property not mentioned in a later scene does not establish absence,
recovery, relocation, costume change, state reversal, or contradiction.

## Continuity state

The architecture distinguishes:

- **declared state:** explicitly supplied as a governed source claim;
- **observed state:** directly represented by an admitted scene observation;
- **rule-derived state:** derived only by an identified continuity rule;
- **unknown state:** insufficient compatible evidence;
- **contradictory state:** incompatible explicit claims in comparable scope;
- **superseded state:** a prior claim explicitly replaced within governed
  chronology, without asserting that either claim was true;
- **unresolved transition:** states differ but no admitted transition or
  comparable chronology explains the relationship.

There is no universal state machine. State is category-specific and closed.
Physical-state and possession values cannot be compared across categories. A
state assertion does not persist forever. Persistence is **off by default** and
exists only where a versioned rule explicitly declares its scope, prerequisites,
and terminating transition.

A later category may explicitly classify a state as scene-local/instantaneous,
persistent-until-explicit-transition, or unknown-persistence, but there is no
universal persistence mode. Such a rule must bind exact identity, sequence and
known chronology, and must stop at an admitted removal/change transition or
scope boundary.

The deterministic v1 should prefer direct comparison of explicit claims over
state propagation. Presence never persists beyond its scene. Possession and
physical state may be compared only when the exact character, category,
continuity sequence, chronology relationship, and rule prerequisites match.
Unknown chronology produces unknown comparison, not inferred persistence.

Example: a character explicitly holds a sword in one scene and the sword is not
mentioned in another. The second scene supplies no negative claim, so no
contradiction exists. The result records missing evidence or unknown state if
that information is material to the admitted rule.

## Contradiction semantics

A contradiction requires all of the following:

1. the same exact governed character semantic identity;
2. the same exact typed state category and compatible value domain;
3. scenes in the same continuity sequence with an admitted comparable
   chronology scope;
4. two or more explicit or admitted rule-derived claims whose values are
   declared incompatible by a versioned rule;
5. no explicit admitted transition, scope boundary, or chronology qualification
   that explains the change;
6. exact evidence for every involved claim.

The following are not automatically contradictions:

- an item is mentioned once and omitted later;
- a character appears in one scene and not another;
- two scenes use the same display name without identity binding;
- a character is in different locations;
- costume or state differs across an unknown time jump;
- an explicit transition explains a state change;
- scenes belong to different or unresolved continuity sequences.
- a dream, flashback, flashforward, montage, retelling, nested story, or
  parallel timeline lacks an explicit comparable relationship to the primary
  sequence.

A contradiction record contains a deterministic contradiction identity,
category, exact character and sequence identities, involved observation and
scene identities/digests, evidence references, rule identity/version,
qualification, unresolved status, confidence/basis, unknowns, and limitations.
It never selects a true claim, edits source material, or orders corrective work.

## Transition semantics

A transition is reported only when source-supported or explicitly declared
structured evidence connects compatible before/after states within known
chronology. A change in values is not itself proof of a transition. A rule may
classify an explicit transition, preserve its evidence, and state its limits;
it may not invent the missing event.

An explicit transition can explain an otherwise incompatible pair and prevent
classification as contradiction. If chronology is known but the connecting
evidence is missing, the result may report an unresolved transition. If
chronology is unknown, both transition and contradiction remain unknown.

“Superseded” means that an admitted sequence relationship identifies a later
claim in that scope; it does not mean the earlier source was false or corrected.

## Scene order and story chronology

Scene ordinal is presentation/source order, not story-world chronology. The
continuity engine must not infer chronological progression from array position
or `scene 1 → scene 2 → scene 3`. Flashbacks, flashforwards, parallel timelines,
dreams, retellings, montage, nested stories, and intercuts make that inference
unsafe.

The first implementation requires an explicit `continuity_sequence_id`. This
identifies a governed narrative continuity scope; it is not screenplay order,
shooting order, production schedule, or real-world time. Every selected scene
binds its exact scene identity/digest to that sequence and to either a bounded
explicit sequence position or an explicit relationship such as before, after,
same interval, or unknown, as later standardized by M5.1.

Only one continuity sequence is analyzed per task. Unknown or incompatible
relationships remain unknown and disable propagation/contradiction rules that
require chronology. ADR-0020 does not create a general timeline engine.

## Task and result contracts

The conceptual task is `analyze_character_continuity/1`. It binds:

- exact project, environment, purpose, request, and correlation;
- exact `scene_breakdown/1` identity/version/digest;
- exact selected scene IDs/content digests;
- exact selected character semantic identities;
- one exact continuity-sequence identity and qualified relationships;
- expected `character_continuity_context/1` and
  `character_continuity_observation_set/1` versions;
- exact policy/rule-catalogue/strategy/provider compatibility;
- classification, trust, expiry, retention, and numeric bounds.

It contains no raw replacement scenes, display-name selection, caller rule or
provider override, prompt, model, ranking request, approval, correction,
workflow, capability, or execution command.

The conceptual result `character_continuity_observation_set/1` binds the exact
request, Scene Breakdown, selected scenes, characters, continuity sequence,
Context, policy/rule catalogue, strategy/provider/API, and distinct semantic
and complete-result digest domains. It may contain observations, explicit
transitions, unresolved transitions, contradictions, unknowns, review-suggested
flags, evidence, confidence, and limitations. It contains no corrected scene,
winner, recommendation, production task, schedule, worker, actor mapping,
budget, Plan IR, approval, or executable step.

Every observation and contradiction is independently digestible and exactly
bound. Stable result order is canonical presentation, not rank or priority.

## Character Continuity Context

The conceptual `character_continuity_context/1` uses the established Context
Object envelope and federated Context Registry. It is typed, bounded,
recursively immutable, purpose-limited, independently versioned, expiring,
revocation-aware, provider-neutral, and non-authorizing.

Its minimized typed payload may contain only:

- exact Scene Breakdown and selected scene identities/digests;
- exact selected character semantic identities and source references;
- one continuity-sequence identity and qualified scene relationships;
- relevant source-supported observations and explicit typed state claims;
- source bindings, provenance categories, and inert evidence references;
- chronology ambiguity, assumptions, conflicts, unknowns, and limitations;
- rights and cultural qualifications as claims;
- exact rule-catalogue identity/version and analysis bounds.

It excludes unrelated scenes/characters, the complete movie project, complete
Story Fragments unless separately proven necessary, production options in v1,
complete Knowledge Packages, reports, registries, schemas, Runtime,
capabilities, workflows, paths/files, audit, approvals, execution data, prompts,
provider-native messages, and arbitrary metadata.

Context Assembly validates each source artifact independently, resolves exact
compatibility and scene/character/sequence selection, verifies purpose/project/
classification/trust, evaluates expiry/revocation, minimizes deterministically,
enforces bounds, independently validates the Context, creates a governance
report, and writes exactly one terminal safe Context audit attempt. It cannot
analyze continuity or invoke reasoning.

## Purpose limitation

The purpose is `character_continuity_local_validation`. It binds project,
development environment, task, Context/result families, selected scene and
character sets, continuity sequence, classification, trust, policy, expiry,
retention, and bounds.

Purpose may narrow but cannot expand to public release, production execution,
training, external-AI submission, media generation, actor management, casting,
legal determination, cultural authority, or correction approval. Invalid
Context never falls back to a context-free or different reasoning path.

## Knowledge and provenance relationship

Scene Breakdown is the primary structured source because it already preserves
scene identity, source binding, observations, claims, boundary interpretation,
ambiguity, unknowns, conflicts, limitations, and evidence references. Character
Continuity retains exact references back to governed Story Fragment identity
and digest where the Scene Breakdown carries them.

The provider cannot reopen source files, resolve evidence, query Knowledge
Packages, or retrieve omitted material. If existing scene observations do not
justify a continuity claim, the result says unknown. Future admission of prior
continuity observations requires a separately versioned inert input family,
exact lineage/digest compatibility, and current revocation; callers cannot
inject arbitrary prior state in v1.

Every result observation and contradiction traces to:

- Story Fragment identity/digest where available;
- Scene Breakdown identity/version/digest;
- exact scene ID/content digest and source span/evidence reference;
- character semantic identity and continuity sequence;
- provenance category and rule identity/version;
- Context content/full digests and result semantic/full digests.

Provenance proves traceability, not factual, artistic, legal, or cultural truth.

## Provider-neutral reasoning architecture

Continuity contracts contain no prompts, chat messages, token counts, model IDs,
temperature, embeddings, similarity scores, tool definitions, or vendor
settings. The existing Reasoning Gateway owns request/Context validation,
compatibility, expiry/revocation, bounds, provider-view extraction, immutable
invocation binding, exact strategy/provider admission, result validation,
semantic honesty, terminal audit, and response mapping.

The provider receives one dedicated deeply immutable minimal view containing
only the selected scene/character/sequence evidence and admitted rules needed
for comparison. It receives no full Context, full project, report, registry,
schema, revocation snapshot, Runtime, capability, workflow, audit, path/file,
connector, network/subprocess client, callback, approval, or execution object.

A deterministic provider is required first. A future external provider may fit
the same semantic contracts, but probabilistic alias/entity resolution must
remain qualified and can never silently become exact identity.

## Deterministic rule catalogue

The first implementation should define an immutable repository-owned catalogue:

`vss.character-continuity.rules.deterministic/1.0.0`

It declares exact admitted observation categories, closed value domains,
compatibility, explicitly limited persistence, contradiction and transition
rules, chronology prerequisites, canonical order, and numeric bounds. It is
deterministic, independently versioned, bounded, non-authorizing, and not caller
configurable. It is not a universal story-logic or timeline engine.

Initial deterministic rules may recognize only:

- repeated occurrence of the same explicit character ID;
- explicit typed presence, possession, and physical-state claims already
  represented structurally;
- explicit transitions with exact evidence;
- incompatible explicit values under one admitted comparable scope;
- missing or non-comparable evidence as unknown.

No rule performs semantic name matching, prose inference, NLP entity
resolution, image analysis, costume/actor recognition, or hidden AI-like
inference.

## Cross-scene selection and bounds

The first task analyzes exactly one project and continuity sequence, 2–8 exact
scenes, 1–8 exact characters, a bounded number of typed observations per scene,
and bounded contradictions/transitions/evidence references. M5.1 owns exact
byte, node, depth, observation, and result limits after fixture measurement.

Selection requires exact Scene Breakdown identity/digest, scene IDs/content
digests, character semantic IDs, and continuity-sequence identity. It rejects
scene title, display name alone, ordinal alone, array position, caller-supplied
scene replacement, unknown character, mixed project, duplicate selection, and
mixed or incompatible sequence scope.

Implementations should group/index observations by
`(character_id, sequence_id, category, comparable_scope)` and compare only
bounded compatible groups. They must not perform an unbounded all-scenes ×
all-characters × all-observations pairwise scan. No production SLO is asserted.

## Confidence and continuity risk

Confidence follows existing semantic discipline: a small closed qualitative
level, explicit basis, qualifications, and limitations. Numeric pseudo-precision
is prohibited unless a later contract supplies validated meaning. High
confidence means the configured rule found strongly supported incompatible
claims; it does not mean the story is wrong or production must change.

V1 should not introduce severity levels. A single qualified
`review_suggested` semantic flag is sufficient when an explicit contradiction
or materially unresolved transition may benefit from human attention. It is not
an approval gate, issue priority, blocker, schedule item, or executable task.
The underlying evidence and qualification, rather than the flag, remain the
meaningful result.

## Rights, privacy, and cultural qualification

Rights and cultural qualifications flow from governed evidence without
promotion. Continuity analysis cannot infer real-person or actor identity,
protected or sensitive traits, legal status, historical truth, cultural
authority, ownership, permission, or clearance. It cannot silently canonicalize
one historical, literary, legendary, religious, or adapted account.

For later Vikramaditya material, disagreements among historical, literary,
legendary, and adapted sources remain explicit provenance/conflict, not defects
to resolve. Public or high-impact use remains subject to separately governed
human legal/cultural review; this ADR creates no such workflow.

## Security and trust boundaries

| Threat | Trust boundary and mitigation | Deferred control |
|---|---|---|
| Character God Object/arbitrary metadata | closed task-specific contracts and separate families | future families remain separate |
| name collision/alias confusion | explicit semantic IDs; no display-name matching | governed probabilistic binding |
| character/scene substitution | exact project, breakdown, character, scene and content digests | authenticated signatures |
| state injection | independently validated typed observations and closed categories | richer extraction governance |
| chronology/sequence substitution | explicit sequence ID and relationship binding; no ordinal inference | richer timeline contract |
| contradiction suppression/fabricated transition | mandatory evidence, unknown/conflict preservation, independent result validation | human adjudication |
| absence treated as contradiction | positive explicit evidence only; omission remains unknown | none needed for v1 |
| provenance promoted to truth | semantic honesty and mandatory qualifications | external verification |
| classification downgrade/trust promotion | exact request/Context/policy binding; classification may not downgrade and trust may not promote | authenticated policy assertions |
| rights/cultural promotion | claims remain qualified; no clearance/authority fields | legal/cultural review |
| unbounded combinatorics | fixed scene/character/observation/group/result bounds | measured long-film profiles |
| provider overexposure | Gateway-owned immutable minimal view | process isolation |
| Context/result/digest substitution | distinct content/view/invocation/result domains and exact validation | signing/authentication |
| mutation after validation | recursive immutable snapshots | process isolation |
| invalid Context fallback | task-specific fail-closed Gateway path | none |
| audit leakage/false success | minimized one-terminal-attempt fatal audit | durable production audit |
| CommandRunner policy drift | routing-only boundary and domain-owner tests | dispatch refactor if repeated |

Trusted repository Python remains in-process and is not a malicious-code
sandbox. Persistent revocation, durable tamper-evident audit, authenticated
artifacts, privacy/residency enforcement, and process isolation are required
before external providers, production effects, or sensitive material.

## Local-first and performance

The first implementation runs on a laptop with original deterministic fixtures
and no network, cloud, AI API, database, vector store, search engine, embedding
service, GPU, paid service, or external identity provider. It uses bounded
regular files only at the CLI boundary and the established strict JSON/schema
loading and immutable canonicalization.

Complexity dimensions—scenes, characters, observations, categories,
comparability groups, transitions, contradictions, evidence, Context bytes,
result bytes, provider calls, and deadline—must all be explicit policy bounds.
Grouped comparison is preferred to unbounded quadratic comparison. M5 evidence
may justify a movie workload in the Performance Laboratory, but this ADR defines
no SLO or feature-film scaling claim.

## Plan IR evidence and boundary

Continuity may expose persistent semantic identity, qualified before/after
state, explicit transition, unresolved transition, narrative-state dependency,
and contradiction that suggests human review. These are valuable evidence for
future planning architecture, but they are not Plan IR.

The continuity result contains no proposed future action, resource allocation,
capability, workflow, retry, compensation, recovery action, approval gate,
schedule, worker, or executable state transition. “State” describes narrative
evidence, not Runtime or workflow state. The M5 checkpoint will ask whether
continuity and at least one other domain capability independently demonstrate
the same planning concepts before Plan IR begins.

## Relationship to Shot Design

Character Continuity remains independent of future Shot Design. Shot Design may
later consume exact inert continuity observations through its own task-specific
Context, but it does not own or mutate continuity state. Continuity contains no
camera, framing, lens, blocking, shot order, render instruction, media asset, or
shot execution field.

## External AI timing

External AI remains deferred. A future AI provider might interpret richer prose,
propose probabilistic alias bindings, identify implied state, or analyze complex
continuity, but its output must fit the same bounded inert contracts and retain
uncertainty, provenance, classification, purpose, and semantic honesty.
Probabilistic identity must never be promoted silently to exact identity.

Before external AI, VSS needs a deterministic benchmark, explicit provider data
governance, prompt/provider-native translation outside semantic contracts,
privacy and rights policy, cost/deadline controls, persistent revocation,
durable audit, output quarantine, and isolation.

## Relationship to prior ADRs

- **ADR-0010 and ADR-0016:** Runtime alone authorizes and executes; continuity
  cannot approve, invoke, or act.
- **ADR-0011:** explicit boundaries, least privilege, provider neutrality,
  deterministic verification, and fail-closed behavior govern the slice.
- **ADR-0012 and ADR-0013:** one existing Reasoning Gateway and independently
  versioned inert task/result contracts; no semantic God Object.
- **ADR-0014:** bounded laptop evidence, no production performance claim.
- **ADR-0015:** provenance, classification, trust, retention, uncertainty,
  conflict, and revocation remain governed.
- **ADR-0017:** a minimized purpose-specific Context is the only provider input.
- **ADR-0018:** Movie, Context, and reasoning registration remain federated,
  immutable, exact, and non-authorizing.
- **ADR-0019:** exact Scene Breakdown identities and qualifications are consumed
  rather than replaced; production options remain independent.

The M4 checkpoint’s accepted recommendation and Plan IR deferral are the direct
decision inputs to ADR-0020.

## Alternatives

1. **Plan IR now:** rejected. M4 has no repeated evidence for action sequencing,
   resources, recovery, compensation, or approval gates.
2. **Shot Design first:** deferred. It offers hierarchy/order learning but risks
   premature plan-like semantics before cross-scene identity/state is known.
3. **External AI first:** rejected. It adds data, privacy, cost, prompt, and
   nondeterminism concerns before a deterministic continuity benchmark exists.
4. **Broad Character Model:** rejected as a Character God Object spanning
   unrelated owners, lifecycles, sensitive data, and production concerns.
5. **Narrow Character Continuity semantics:** selected. It supplies the highest
   cross-scene/state learning with bounded local deterministic risk.

## Consequences

Positive consequences include the first cross-scene semantic state, explicit
identity persistence, contradiction discipline, accumulated provenance,
stronger future Plan evidence, local deterministic verification, and reusable
input for later Shot Design and production planning.

Costs include character-identity and chronology complexity, ownership of a
small typed state taxonomy, stronger provenance and cross-field validation,
bounded combinatorial comparison, and temptation to grow a Character God
Object. Mitigations are explicit IDs, one continuity sequence, three initial
observation categories, persistence off by default, no name heuristics, no
automatic repair, fixed bounds, no Plan IR, and independent review.

## Roadmap

- **ADR-0020:** Character Continuity Architecture (this documentation decision).
- **M5.1:** character semantic identity/reference, continuity-sequence,
  character-observation, `analyze_character_continuity/1`, and
  `character_continuity_observation_set/1` contracts, schemas, validators, and
  fixtures only; no Context Assembly or reasoning.
- **M5.2:** Character Continuity Context Assembly, deterministic rule catalogue,
  and existing-Gateway reasoning path.
- **M5.3:** bounded cross-scene contradiction/transition analysis and direct
  concurrency/performance evidence where required.
- **M5 checkpoint:** reassess Plan IR readiness using implemented evidence.

These milestones are recommendations, not implementation performed by this ADR.

## Unresolved questions

- exact semantic character ID format and identity-binding artifact;
- aliases, titles, display names, transliteration, renaming, character families,
  multiple roles with one name, anonymous characters, and groups/crowds;
- exact continuity-sequence representation and relationship vocabulary;
- flashbacks, flashforwards, parallel timelines, montage, dreams, retellings,
  intercuts, and nested stories;
- exact possession and physical-state taxonomies;
- costume, emotional, relationship, narrative-status, death, injury, and
  performance continuity;
- explicit versus implied transitions and category-specific persistence;
- whether contradiction severity ever adds meaning beyond qualification;
- long-form risk representation and source-span aggregation;
- continuity across Scene Breakdown results and multiple Story Fragments;
- multilingual identity and transliteration governance;
- external-AI entity resolution and probabilistic identity contracts;
- exact numeric bounds, long-film scaling, retention, and revocation lifetime;
- future human-review workflow ownership;
- evidence threshold and timing for Plan IR.

These questions are recorded rather than answered through hidden heuristics or
an over-broad v1 contract.

## Independent review perspectives

Independent acceptance must review this decision from Enterprise Architecture,
Movie Continuity/Script Supervision, Character Domain Modeling, Narrative
Timeline Architecture, Semantic Contracts, Context Architecture, Knowledge
Governance, Runtime Authority, Product Security, Data Governance, Copyright and
Licensing Risk, Cultural/Historical Sensitivity, Provider Neutrality,
Local-First Engineering, Performance/Complexity, Contract Evolution, and
Independent Verification perspectives.

Review must specifically challenge name-based identity, chronology inferred
from scene order, absence-as-contradiction, Character God Object growth,
narrative state becoming planning state, observations becoming execution
instructions, unbounded cross-scene comparison, deterministic rules hiding
AI-like inference, and rights/cultural claims promoted to truth or authority.

## Acceptance boundary

ADR-0020 is acceptable only if Runtime remains the sole execution and
authorization authority; continuity artifacts are inert; character, actor, and
display-name identities remain separate; continuity sequence is not scene
order; omission is not contradiction; contradiction requires explicit
incompatible comparable evidence; explicit transitions can explain change;
chronology uncertainty and exact provenance remain visible; claims,
rights/cultural qualification, and confidence remain qualified; Context is
task-specific and provider-neutral; analysis is bounded and locally
deterministic; and the roadmap remains narrow.

This ADR adds no implementation, schema, test, Context implementation,
strategy/provider, Plan IR, Shot Design, external AI, prompt, connector,
retrieval, search, embedding, database, persistent state, approval, execution,
media generation, distributed infrastructure, production audit, process
isolation, or dependency.
