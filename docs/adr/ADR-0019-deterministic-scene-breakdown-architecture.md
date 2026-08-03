# ADR-0019: Deterministic Scene Breakdown Architecture

## Status

Proposed

## Context

M3.1–M3.6 establish a governed local chain from Knowledge Packages through
bounded Context and deterministic reasoning to inert OptionSets. The first
domain slice must now demonstrate direct movie-production value without adding
execution, provider coupling, or a universal movie model.

## Decision

VSS will begin with a narrow two-stage slice:

```text
governed story knowledge
  -> Knowledge Package
  -> scene_breakdown_context/1
  -> break_down_scenes/1
  -> scene_breakdown/1
  -> scene_production_options_context/1
  -> generate_scene_production_options/1
  -> scene_production_option_set/1
```

Both results are advisory, inert, bounded, and non-authorizing. Runtime remains
the sole authority for authorization, approval, and execution. No stage invokes
media tools, allocates money, schedules workers, publishes content, or creates
an executable plan.

## Relationship to existing architecture

- **ADR-0010/0016:** movie artifacts cannot authorize, approve, execute, invoke
  capabilities, or invoke workflows.
- **ADR-0011:** explicit contracts, least privilege, provider neutrality,
  local-first operation, deterministic testing, fail-closed behavior, and
  documented limitations apply.
- **ADR-0012/0013:** reasoning remains inert; each envelope has one independently
  versioned typed payload; no semantic God Object is introduced.
- **ADR-0014:** workloads are bounded laptop experiments, not production or
  feature-film performance claims.
- **ADR-0015:** classification, trust, purpose, provenance, freshness,
  retention, conflicts, uncertainty, and revocation remain governed Knowledge
  properties.
- **ADR-0017:** only minimized task-specific Context reaches reasoning.
- **ADR-0018:** movie registries remain federated and independently owned.

M3 registries, v1 contracts, and the M3 integration checkpoint are reused and
not changed by this ADR.

## Movie-domain boundary

The movie domain may own movie Knowledge families, Context families, semantic
tasks/results, compatibility mappings, validation, fixtures, and documentation.
It does not own Runtime authorization, provider selection outside policy,
credentials, connectors, rendering, publishing, scheduling, approval, or
production audit infrastructure.

There is no universal Movie Object or Production Object. Story, screenplay,
scene, character, location, shot, costume, sound, schedule, asset, render,
review, licensing, and release concepts remain independently versioned future
families. A bounded registry may group genuinely aligned movie families, but it
must not become a universal Movie Registry.

## First Knowledge families

The minimum first implementation requires `story_fragment/1`: a bounded title,
fragment text, language, source sequence/type, explicitly supplied character or
location declarations, bounded annotations, inert citations, and source
qualification. It contains no prompts, commands, handles, credentials, assets,
or metadata bag. Instruction-like text is ordinary inert content.

`character_reference/1` and `location_reference/1` are optional future additions;
they are admitted in M4.1 only if they materially improve the first slice.

Source knowledge is distinct from interpretation. Derived output must label
source-supported observations, rule-derived interpretation, assumptions,
unknowns, conflicts, limitations, and evidence references separately.

## Scene semantics and identity

For this slice, a scene is a contiguous narrative unit identified by explicit
headings, location/time changes, separators, sequence markers, or a bounded
deterministic fallback. This is an operational definition, not a universal
artistic definition. Explicit, rule-derived, and ambiguous boundaries remain
distinguishable; material ambiguity is not silently resolved.

Scene identity is derived from source identity/version, source sequence,
normalized boundary index, deterministic ordinal, and scene-content digest. It
does not use time, process, machine, filesystem order, provider, or randomness.
Semantic scene identity, event-bound analysis identity, and future execution
identity are separate.

## Scene Breakdown task and result

The first conceptual task is `break_down_scenes/1`, consuming a validated,
bounded `scene_breakdown_context/1` and producing `scene_breakdown/1`. The
typed result may contain ordered scenes, source spans/evidence, boundary basis,
explicit characters, locations, time indicators, events, qualified dramatic
function where deterministic, constraints, assumptions, unknowns, conflicts,
confidence, and limitations.

Ordering is source order and is deterministic. A conservative single breakdown
is used when alternatives would be unbounded; unresolved alternatives are
recorded as ambiguity or limitation. No NLP model, hidden heuristic drift,
shot list, camera grammar, costume, lighting, music, or acting direction is
selected here. The exact bounded rule grammar is an M4.1 implementation
decision, not frozen by this ADR.

## Scene Production Options task and result

The second conceptual task is `generate_scene_production_options/1`, consuming
one validated scene or bounded scene subset plus
`scene_production_options_context/1`, and producing
`scene_production_option_set/1`.

Options are bounded alternatives, not plans or recommendations. They may
describe broad production approach, visual treatment category, staging
complexity, location/performer/asset requirements, effects and audio
considerations, local prototype suitability, unknown dependencies, and
validation needs. They contain no commands, workflow steps, credentials,
vendor settings, budgets, schedules, capability invocations, or execution
authority.

Creative intent (mood, dramatic purpose, tone, audience effect) remains separate
from production method (live action, animation, virtual production, compositing,
or practical effects). No method is treated as inherently superior. A small
fixed repository-owned profile catalogue may be introduced in implementation;
its exact profiles are not frozen here.

## Context families and mappings

The first Context families are independently versioned:

- `scene_breakdown_context/1` → `break_down_scenes/1` → `scene_breakdown/1`
- `scene_production_options_context/1` →
  `generate_scene_production_options/1` → `scene_production_option_set/1`

Each mapping binds exact Knowledge family, Context family, task/result versions,
purpose, project, environment, classification, policy, lifecycle, and bounds.
Unknown, wildcard, latest, name-only, caller-defined, or implicit semantic
version mappings fail closed. Semantic, Knowledge, Context, and movie-domain
registries remain separate.

Initial purposes are `scene_breakdown_local_validation` and
`scene_production_options_local_validation`. Purpose can narrow, never expand,
into public release, training, external-provider submission, marketing, or
execution.

## Governance and semantic honesty

Initial development supports only `public` and `internal`; `approved_fixture`
may be admitted while `unverified` is represented but rejected by the first
policy. Classification cannot downgrade and trust cannot promote. Story text is
not automatically factual; history, legend, adaptation, and invention remain
distinct qualifications.

Every derived scene retains source item/package identity and digests, source
span/evidence, boundary-rule identity/version, policy identity/version, Context
digest, and result digest. Provenance is traceability, not artistic truth.

Scene output must not claim definitive artistic boundaries, completeness,
objective dramatic purpose, or factual correctness. Production options must not
claim feasibility, cost, timing, quality, legal clearance, performer
availability, asset availability, or that one option is best. Unknowns,
conflicts, uncertainty, and limitations are mandatory and confidence is
qualified and non-authorizing.

## Rights and cultural sensitivity

Future contracts retain known ownership/licensing status, permitted use,
restrictions, attribution requirements, expiry/revocation, and uncertainty.
The first local slice uses original, public-domain, or explicitly authorized
fixtures and does not submit source material externally. Rights validation is a
separate concern.

For historical, literary, religious, legendary, or culturally sensitive
material, preserve attribution and disagreement and distinguish history, legend,
adaptation, and invention. No source is silently canonical. Appropriate human
review is required before public or high-impact use; this ADR does not create a
cultural-policy engine.

## Local-first bounds and determinism

M4 workloads are bounded by story bytes, fragments, scenes, characters,
locations, events, evidence references, conflicts, unknowns, options, Context
bytes, result bytes, and deadline. Numeric profiles belong to versioned
implementation policies; no production SLO or feature-film scalability claim is
made.

Identical semantic inputs and versions produce stable scene identities,
boundaries, evidence ordering, option ordering, and semantic result digests
across processes, working directories, hash seeds, supported concurrency, and
event-bound correlations. Event identities may vary only where explicitly
event-bound. CI uses only authorized non-sensitive fixtures and requires no
network, cloud, database, search, embedding, GPU, or paid service.

## Security boundary

Threats include Movie/Production God Objects, universal registries, instruction-
like story text, source leakage, copyrighted fixture leakage, purpose or
classification changes, trust promotion, source/scene/result substitution,
boundary/order manipulation, identity collisions, evidence substitution,
fabricated people/places/events, unsupported dramatic claims, option-as-plan
interpretation, vendor coupling, oversized input, Unicode/JSON hazards, audit
leakage, expiry/revocation bypass, false success, provider overexposure, and
CommandRunner policy drift.

Mitigations are structural non-authority, strict bounded contracts, exact
identity/digest bindings, repository-owned rules, immutable snapshots, source
evidence, explicit uncertainty, safe audit metadata, and fail-closed validation.
Keyword filtering is not the security boundary. Trusted in-process Python is
not sandboxed; external providers, production credentials, isolation, durable
audit, signing, privacy/residency, and persistent revocation remain deferred.

## Plan IR timing

Universal Plan IR remains deferred. Scene Breakdown and Scene Production Options
are semantic results, not executable step graphs: they contain no capabilities,
workflows, credentials, retries, scheduling authority, worker assignments,
effects, or approvals. Plan IR should be reconsidered only after concrete movie
outputs demonstrate shared sequencing, resource, dependency, and approval
requirements.

## Alternatives

1. Universal Plan IR first — rejected as speculation without domain evidence.
2. Universal Movie/Production Object — rejected for God Object coupling.
3. External AI/prompt first — rejected for provider and data-governance coupling.
4. Media generation/rendering first — rejected because effects and recovery are
   not ready.
5. Narrow deterministic scene breakdown and production options over existing M3
   boundaries — selected for direct mission value, local evidence, low risk,
   provider neutrality, and useful future planning evidence.

## Consequences

Benefits are the first direct movie value, evidence for future planning,
reusable scene identities, early uncertainty discovery, local inexpensive tests,
and preserved authority boundaries. Costs include new ownership and mapping,
narrow initial semantics, source-span complexity, cultural/licensing review,
and temptation toward universal modeling. Mitigations are one source family,
one scene task, one option task, bounded fixtures, explicit limitations, no
execution/AI, independent review, and an integration checkpoint.

## Roadmap

- M4.1: movie Knowledge and Scene Contract Registry, `story_fragment/1`, scene
  task/result contracts, fixtures, and validation.
- M4.2: scene Context assembly, exact mappings, deterministic strategy/provider,
  local CLI and audit.
- M4.3: production-option contracts, Context, bounded profile catalogue, and
  deterministic Context-aware reasoning.
- M4 checkpoint: review the complete movie chain.
- Reconsider Plan IR only after demonstrated scene-production outputs.

Future character continuity, shot design, costume, sound, music, schedule,
budget, asset, rendering, and release families remain separate milestones.

## Unresolved questions

Exact first Knowledge families, source formats, heading grammar, fallback
segmentation, source-span representation, ambiguity and confidence taxonomy,
montage/intercut/flashback/nonlinear handling, multilingual normalization,
rights metadata, cultural-source classification, profile catalogue, option
ranking/human selection, Context/result identifiers, numeric bounds, performance
baselines, movie registry boundaries, approvals, assets, and Plan IR timing all
remain implementation or later-architecture decisions.

## Acceptance boundary

This ADR establishes no schemas, code, tests, providers, registry implementation,
Plan IR, execution, media generation, rendering, infrastructure, or dependency.
It establishes a narrow deterministic movie slice whose artifacts remain inert,
traceable, bounded, purpose-limited, classified, revocable, and locally
testable.
