# M5.1 Character Continuity Contracts

M5.1 implements the validation-only contract slice of
[ADR-0020](adr/ADR-0020-character-continuity-architecture.md). It establishes
strict schemas, deterministic canonicalization and digests, recursively
immutable validated artifacts, exact Movie Registry admission, original
fictional fixtures, and adversarial tests. Registration means structurally
known only. Runtime remains the sole authorization and execution authority.

## Identity boundaries

`character_reference/1` records an explicit source declaration. Its
`display_label` is presentation only. Exact reference IDs use
`character-ref-<lowercase ASCII token>`. Labels, capitalization, spelling,
Unicode normalization, aliases, honorifics, transliterations, ordinals, array
positions, and text similarity never merge references.

`character_identity/1` is a project-scoped semantic identity with an exact
`character-<lowercase ASCII token>` ID. It admits only
`explicit_source_identity` or `explicit_project_binding`, exact reference IDs
and reference-content digests, and governed evidence. Ambiguous candidates cannot validate as an exact
identity. Performer and actor identities are absent and separate. Neither
contract is a biography, Character God Object, asset record, or mutable store.

## Chronology and observations

`continuity_sequence/1` represents one explicitly declared linear narrative
scope of two through eight exact scenes. Each scene binds the exact Scene
Breakdown digest, scene ID, scene-content digest, and an explicit unique,
contiguous continuity position. Scene ordinal, screenplay order, shooting
order, schedule, and real-world time are not chronology. V1 does not model
parallel, branching, nested, cyclic, dream, flashback, or montage timelines.

`character_observation/1` admits only three positive, explicit categories:

- `presence` with `present`;
- `possession` with `possesses` and a bounded inert object reference; and
- `physical_state` with `injured`, `restrained`, or `unconscious`.

The payloads are category-specific and closed. Location, costume, emotion,
relationship, dialogue, role, performance, actor, and arbitrary state fields
are rejected. Provenance is limited to `source_declared` and
`source_observed`; rule-derived observations are deferred because no rules
exist in M5.1. Confidence is qualitative and qualified, not truth, severity,
approval, or authority.

Non-mention creates no observation. A lantern mentioned in one scene and
omitted later is not absent, removed, transitioned, or contradictory. M5.1 has
no persistence and never carries state forward.

## Task and result

`analyze_character_continuity/1` binds one exact sequence, one through eight
exact characters, selected admitted categories, conservative bounds, the
future `character_continuity_context/1`, and the exact
`character_continuity_observation_set/1` result. Its lifecycle is
`defined_validation_only` and implementation availability is
`not_implemented`. It contains no source body, Context, provider, strategy,
model, prompt, correction, ranking, action, or execution request.

M5.2 advances the task contract intentionally rather than changing this
historical meaning. `analyze_character_continuity/2` is the executable local
deterministic semantic task: its lifecycle is `active`, implementation
availability is `required`, and it binds exactly to
`character_continuity_context/1` and
`character_continuity_observation_set/1`. Both task versions remain registered
and each has an explicit exact mapping to result v1. There is no latest,
wildcard, range, automatic upgrade, downgrade, or nearest-version selection.
Context Assembly and ReasoningGateway accept task v2 only; task v1 remains a
valid supported validation-only artifact.

`character_continuity_observation_set/1` is an inert semantic result. It binds
independently validated observation IDs/content digests to the exact project,
sequence, scenes, characters, categories, and positions. Its nested transition
and contradiction shapes are structural only: transitions require an explicit
source-transition basis, and contradictions bind two distinct resolved
observations while remaining `unresolved`. M5.1 neither discovers logical
incompatibility nor infers transitions. These shapes are not separately
registered contract families.

`review_suggested` is a boolean semantic hint only. It is not severity,
priority, blocker, approval gate, scheduling effect, workflow trigger, or
execution instruction. Repair, recommendation, action, approval, Plan IR,
workflow, capability, and execution fields fail closed.

## Integrity, immutability, bounds, and provenance

Canonical SHA-256 domains are distinct for registry, reference content,
identity content, sequence content, observation content, task content,
transition content, contradiction content, semantic result, payload, and
complete result. Digests provide integrity, not identity or chronology truth,
rights clearance, actor identity, approval, or authority. ID equality is exact
ASCII byte equality. IDs are not Unicode-normalized and have no URL or
filesystem semantics.

Validated values are recursively immutable snapshots. Mutations to source
objects or exported JSON copies cannot alter them. Strict repository-owned
schemas reject unknown fields, remote/dynamic references, duplicate keys at
hardened JSON loading, non-finite values, custom mappings, booleans as
integers, excessive depth/nodes/bytes, and unsupported types.

M5.1 validator APIs use one unambiguous guarantee: an artifact whose semantics
depend on another artifact is returned as validated only after every dependency
has been supplied as an independently validated immutable artifact and all
identity, project, and digest bindings resolve exactly. Identity requires its
complete reference set; a sequence requires its Scene Breakdown; an
observation requires its character identity and sequence; a task requires its
sequence and complete character set; and a result requires its exact
observations, sequence, and task. Omitted, raw, incomplete, duplicate, or extra
dependencies fail closed. There is no structurally-only validated-object mode.

Content digests exclude their own digest field. The semantic-result digest uses
the complete semantic payload with `semantic_result_digest` replaced by JSON
`null`; the complete-result digest excludes itself by retaining only the
already-verified payload digest in `integrity`. These domains remain distinct:
a content, semantic, payload, complete-result, or registry digest cannot
substitute for another.

Limits include 2–8 scenes, 1–8 selected characters, 1–3 categories, at most
128 observations, 32 transitions, 32 contradictions, 32 evidence references
per observation, and a 64 KiB result. Validation never truncates and performs
no pairwise continuity analysis.

Fixtures use an original fictional character, Arin, and original structured
scene claims. Evidence references preserve traceability but do not prove truth.
Rights, cultural, legal, historical, sensitive-person, and performer
determinations remain outside this slice.

## Milestone boundary

No continuity analysis, Context implementation or Assembly, rules catalogue,
strategy, provider, Gateway path, contradiction discovery, persistence engine,
NLP/entity resolution, name matching, external AI, actor identity, Plan IR,
Shot Design, approval, execution, or media generation exists in M5.1. M5.2 may
separately propose a task-specific Context and governed deterministic reasoning
path; M5.3 may propose bounded transition and contradiction analysis. Neither
is implied by structural registration here.
