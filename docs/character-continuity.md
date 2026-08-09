# M5.2 Character Continuity Reasoning

M5.2 implements the first bounded cross-scene semantic path governed by
[ADR-0020](adr/ADR-0020-character-continuity-architecture.md). It remains a
local, deterministic, inert Semantic Plane capability. Runtime authority is
unchanged.

## Exact contracts and Context

`analyze_character_continuity/1` remains the supported M5.1 validation-only
contract. `analyze_character_continuity/2` is the executable M5.2 task. The
version advance preserves historical artifact meaning; neither version is
silently upgraded or downgraded. Executable task v2 expects exactly
`character_continuity_context/1` and returns the unchanged
`character_continuity_observation_set/1`.

Context Assembly accepts only independently validated v2 task, continuity
sequence, character identities, and character observations. It binds one
project, one explicit linear sequence of 2–8 scenes, 1–8 exact character IDs,
the three M5.1 categories, and at most 128 observations. Raw self-consistent
dictionaries cannot substitute for validated dependencies. Its immutable
Assembly Report contains counts and digest bindings, never observation values
or source prose. One terminal audit attempt is made; audit failure is fatal.

Digest domains are distinct: Movie Registry, Context Registry, task, input
set, selection, Context semantic content, complete Context, Assembly Report,
rule catalogue, provider view, invocation binding, semantic result, payload,
and complete result. They prove integrity and binding only—not identity,
chronology, continuity truth, artistic correctness, approval, or authority.

## Provider view and deterministic rules

ReasoningGateway extracts a deeply immutable
`CharacterContinuityProviderView` containing only exact project, sequence,
scenes/positions, character IDs, selected categories, explicit typed
observations, qualifications, and rule-catalogue bindings. Providers receive no
full Context, report, registry, Runtime, audit, policy object, path, callback,
workflow, capability, asset, or execution handle.

The repository-owned catalogue is
`vss.character-continuity.rules.deterministic/1.0.0`. The strategy is
`vss.analyze-character-continuity.deterministic/1.0.0`; the provider is
`vss.reasoning.character-continuity.deterministic/1.0.0` with API v1. The
catalogue admits only presence, possession, and physical state, uses explicit
continuity positions, caps comparisons at 128, and fixes persistence to off.
Execution makes exactly one provider call. Dry-run performs all readiness,
expiry, revocation, extraction, and binding work but makes zero calls and
fabricates no result.

## Semantic boundary

Identity is exact character-ID equality; display labels, aliases,
capitalization, transliteration, similarity, and NLP are never used.
Chronology comes only from explicit continuity positions, never Scene Breakdown
ordinal, array order, filename, or title. Every observation remains scene-local.

Non-mention is not absence. A lantern explicitly possessed in scene 1 and not
mentioned in scene 2 produces no loss, removal, negative possession,
transition, contradiction, disappearance, or persistence inference. Repeated
explicit values are qualified as repeated evidence, not proof of persistence.
Different explicit values are not generically contradictory. M5.2 discovers no
transition or contradiction; unsupported comparison remains unknown.

The result is independently validated and inert. `review_suggested` remains a
boolean semantic hint, never severity, priority, approval, scheduling, or an
execution trigger. There are no fixes, recommendations, actions, reshoots,
workflows, Plan IR, or Shot Design.

## Gateway lifecycle, security, and limits

The path validates exact task v2 and Context, checks compatibility and
correlation, verifies integrity, expiry and current immutable revocation,
extracts the provider view, computes provider-view and invocation-binding
digests, invokes once, validates the result independently, checks semantic
honesty and size, audits once, and returns. Invalid task v1, invalid Context,
expiry, revocation, substitution, or any pre-provider failure produces zero
provider calls. There is no fallback, retry, alternate provider, or weaker
context-free mode.

Implementation is Python-only and bounded by 8 scenes, 8 characters, 128
observations/comparisons, 64 KiB Context/result, one iteration, and one provider
call. Iteration is grouped and canonically ordered by exact character,
category, and explicit position. No network, filesystem provider access,
database, service, daemon, AI, model, prompt, retrieval, search, embedding,
asset plane, compute worker, or persistent state exists.

M5.3 remains responsible for stronger bounded contradiction or transition
analysis. Production artifact snapshots and dynamic compute admission remain
deferred under ADR-0022. The implementation follows ADR-0021’s Semantic Plane
boundary and ADR-0023’s minimal-component strategy.
