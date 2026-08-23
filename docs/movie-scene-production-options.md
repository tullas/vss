# M4.3 Governed Scene Production Options

M4.3 admits `generate_scene_production_options/1`, `scene_production_option_set/1`, and `scene_production_options_context/1` as repository-owned structural contracts. Registration means structurally known only. Runtime remains the sole authorization and execution authority.

The Context assembler independently validates one `scene_breakdown/1` and selects exactly one scene by both scene ID and scene-content digest. It rejects ordinal-, title-, position-, replacement-body-, cross-breakdown-, and digest-based substitution. The minimized Context preserves source observations and claims, boundary basis and rule, ambiguity, assumptions, unknowns, conflicts, limitations, inert evidence identifiers, rights and cultural qualifications as claims, local constraints, and the exact profile catalogue. It contains no complete breakdown, story text, registry, schema, path, audit, Runtime, capability, workflow, provider configuration, approval, or execution material. Assembly produces an immutable Context, bounded governance report, and exactly one safe terminal development audit record. Audit failure is fatal.

The immutable catalogue `vss.scene-production-profiles.deterministic/1.0.0` contains exactly `minimal_stage`, `location_live_action`, `stylized_2d`, and `stylized_3d` in stable ordinal order. Each record declares bounded performer, location, asset, effects, audio, prototype, unknown, external-validation, and limitation qualifications. Stable order is not ranking. The catalogue is not caller configurable and grants no authority.

The existing Reasoning Gateway admits strategy `vss.generate-scene-production-options.deterministic/1.0.0` and provider `vss.reasoning.deterministic-scene-production-options/1.0.0` using provider API v1. The Gateway validates the task and Context, exact request/scene/Context binding, project, environment, purpose, classification and trust, lifecycle, catalogue, bounds, and implementations. It then creates the deeply immutable `SceneProductionOptionsProviderView`, computes its digest and an immutable invocation binding, and immediately rechecks expiry and the known-empty local `vss.movie.revocation.snapshot/1` before the sole provider call. Invalid, expired, revoked, or substituted material never falls back and causes zero calls. There is no retry.

The provider receives only project and scene digests, minimized observations and claims, boundary qualifications, uncertainty and limitations, evidence identifiers, rights/cultural claims, local constraints, immutable profile records, and the option limit. It does not receive the Context, breakdown, Assembly Report, policy object, revocation snapshot, registries, schemas, audit, Runtime, capabilities, workflows, paths, files, connectors, callbacks, network, subprocess, credentials, approval, or execution data. Trusted Python remains in-process; it is not process isolation.

Each inert option binds the project, exact breakdown and scene, profile, Context content, policy, and option content. Validation enforces unique IDs/profiles, contiguous catalogue order, per-option content digests, payload and semantic-result digests, and a complete event-bound result digest. It rejects ranking, score, recommendation, preference, winner, selection, approval, plan, workflow, capability, execution, model, and prompt fields. Semantic honesty preserves ambiguity, conflicts, unknowns, limitations, external-validation requirements, rights/cultural qualifications, and low qualified confidence. Validation does not prove feasibility, cost, duration, quality, availability, rights or permit clearance, artistic correctness, or cultural authority.

Dry-run traverses the full admission, expiry, revocation, provider-view, and invocation-binding path, calls zero providers, produces no OptionSet or result digest, and writes safe reasoning audit evidence. Normal execution calls the provider exactly once and the terminal audit binds request, scene, Context, provider view, invocation, catalogue, strategy/provider/API, call count, revocation, dry-run, and result digest without bodies or private paths.

Public development commands are:

```text
vss movie context-assemble-scene-production-options --request <task.json> --scene-breakdown <breakdown.json> --environment development --correlation-id <exact-correlation>
vss context validate --input <context.json> --environment development --correlation-id <exact-correlation>
vss movie generate-scene-production-options --request <task.json> --context <context.json> --environment development --correlation-id <exact-correlation>
vss movie generate-scene-production-options --request <task.json> --context <context.json> --environment development --correlation-id <exact-correlation> --dry-run
```

M4.3 introduces no Plan IR, ranking, recommendation, automatic selection, approval, execution, scheduling, budgeting, external AI, prompt, connector, retrieval, search, embedding, database, cache, media generation, rendering, distributed infrastructure, production audit, process isolation, or autonomous behavior. Local JSONL audit remains development-only.

## M7.1 governed Knowledge-informed options

`scene_production_options_context/2`, `generate_scene_production_options/2`,
and `scene_production_option_set/2` are the exact v2 boundary for optional
M6.5 Shot/Cinematography Knowledge. The v1 contracts and behavior remain
unchanged. At most two supplied Knowledge artifacts are independently
revalidated immediately before the deterministic provider call, including
project/domain, local manual or synthetic provenance, admission lineage, and
active lifecycle eligibility.

Knowledge is used only as bounded informational context. It cannot select,
rank, score, recommend, approve, authorize, or establish truth. The v2 result
records exact Knowledge and admission/source lineage with the closed
`informational_context_only` designation. Invalid supplied Knowledge fails
closed; it is never silently discarded. No Knowledge follows the existing
fixed, stable-order, non-ranking option path. Runtime remains the sole
execution authority and no automatic promotion or external learning exists.

## M7.2 deterministic option-review preparation

The development command below independently revalidates an M7.1 v2 Option Set
and produces `scene_option_review_packet/1`:

```text
vss movie prepare-option-review --input <option-set-v2.json> --request-id <request-id> --environment development --correlation-id <correlation-id>
```

The packet binds the complete source Option Set, preserves every option in its
original stable non-ranking order, carries exact Knowledge lineage and declared
informational influence, and presents structured considerations, unresolved
checks, and common human-review prompts. Packet, entry, payload, and complete
result digests make omission, substitution, and resealing detectable by the
domain validator.

This is review preparation, not a review decision. It does not rank, score,
recommend, select, approve, schedule, budget, create a plan or workflow, grant
authority, or execute anything. Human review outcomes and any later selection
or approval boundary remain separate future milestones.

## M7.3 accountable option-review decisions

`record_scene_option_review_decision/1` and
`scene_option_review_decision/1` record exactly one accountable human
assessment—`accept`, `reject`, or `defer`—against an exact M7.2 packet entry.
The development command requires both authoritative source artifacts:

```text
vss movie record-option-review-decision --review-packet <review-packet-v1.json> --option-set <option-set-v2.json> --option-id <option-id> --reviewer-id <reviewer-id> --outcome <accept|reject|defer> --rationale <human-rationale> --request-id <request-id> --environment development --correlation-id <correlation-id>
```

Use one or more `--deferred-condition <condition>` arguments when the outcome
is `defer`; deferred outcomes require at least one unresolved reason or
next-review condition, while other outcomes reject deferred conditions. The
validator independently reconstructs the selected option and inherited
Knowledge lineage from the validated packet and Option Set. Task, decision,
payload, packet, source, option-content, and complete-result bindings make
fully resealed substitution or mutation fail closed.

An `accept` outcome is only a review-stage human assessment. The result
explicitly grants no production approval, production plan, scheduling,
workflow activation, capability, or Runtime execution authority. M7.3 adds no
ranking, recommendation, selection workflow, planning, scheduling, or
execution behavior.

The caller-supplied reviewer ID is integrity-bound accountability metadata; it
is not authenticated, identity-verified, authorization-checked, or digitally
signed by this local milestone. Consumers must not treat the identifier as
proof of reviewer identity or authority.

## M7.4 deterministic shot-plan draft POC

### Local terminal demo

Run the complete existing POC from one story file with no intermediate-file
management:

```text
vss movie demo --story tests/fixtures/movie/story-fragment-valid.json --reviewer-id local.reviewer
```

The command performs the real scene-breakdown, v2 production-option, review,
accepted-decision, and shot-plan services. It prints the four production
options, asks the user to choose one, and writes one JSON bundle with the
validated intermediate artifacts, review decision, and `draft_only` shot plan
to standard output. `--option-id` provides the same
path non-interactively. The reviewer ID remains caller-supplied accountability
metadata, not authenticated identity or production authority.

The demo intentionally continues with the first scene in the deterministic
breakdown. It does not provide scene selection or multi-scene shot planning.

`create_scene_shot_plan_draft/1` consumes an independently validated accepted
M7.3 decision together with its exact review packet, v2 Option Set, and scene
breakdown. Through the Reasoning Gateway it makes exactly one call to the local
deterministic shot-plan provider and emits `scene_shot_plan_draft/1`. Reject and
defer assessments fail closed. Dry-run completes admission and binding but
calls no provider and emits no draft.

The draft contains three stable structural cards: scene orientation, primary
action, and detail or transition. Their order describes narrative structure;
it is not ranking or recommendation. Each card preserves source evidence,
assumptions, unknowns, limitations, and exact cinematography Knowledge
influence when present. Composition qualifications use declared scene
locations, characters, time indicators, events, and unknowns; missing angle,
elevation, movement, or screen-direction evidence is reported as unspecified
rather than invented.
The validator independently reconstructs every card from the authoritative
upstream artifacts, so resealing cannot legitimize substitution, omission,
addition, reordering, or content mutation.

```text
vss movie create-shot-plan-draft --decision <decision-v1.json> --review-packet <review-packet-v1.json> --option-set <option-set-v2.json> --scene-breakdown <scene-breakdown-v1.json> --request-id <request-id> --environment development --correlation-id <correlation-id>
vss movie create-shot-plan-draft --decision <decision-v1.json> --review-packet <review-packet-v1.json> --option-set <option-set-v2.json> --scene-breakdown <scene-breakdown-v1.json> --request-id <request-id> --environment development --correlation-id <correlation-id> --dry-run
```

The artifact is structurally `draft_only`. It provides no production
approval, final shot selection, production-plan authority, scheduling,
workflow activation, capability grant, provider execution authority, or
Runtime execution authority. It does not establish feasibility and performs
no media generation, external model call, storage, orchestration, or Runtime
operation.

## M8.0 provider-neutral storyboard specifications

`create_scene_storyboard_specification/1` consumes the exact accepted review
decision, review packet, production option set, scene breakdown, and validated
`scene_shot_plan_draft/1`. Admission reconstructs the complete upstream chain,
including the selected option and inherited informational Knowledge lineage.
`scene_storyboard_specification/1` contains exactly one deterministically ordered
frame specification for each shot card.

Each frame carries its source shot identity and digest, supported subject, action,
environment, and time cues, qualified framing and camera fields, accepted-option
style direction, continuity constraints, explicit assumptions and unknowns, a
provider-neutral prompt, negative constraints, and its own semantic digest. Literal
time cues use only a closed set found in validated source observations when the
scene contract has no declared time indicator. Other missing facts remain explicit
unknowns; the derivation does not invent appearance, blocking, lens, palette, set
dressing, weather, or architecture.

The artifact is `specification_only`. It grants no production approval, final frame
selection, scheduling, workflow activation, capability, provider execution,
Runtime execution, or media-generation authority. The built-in deterministic
provider is an internal governed transformation only; no external image provider
is configured or called. Dry-run validates the authoritative chain with zero
provider calls.

```text
vss movie create-storyboard-specification --decision <decision-v1.json> --review-packet <review-packet-v1.json> --option-set <option-set-v2.json> --scene-breakdown <scene-breakdown-v1.json> --shot-plan <shot-plan-v1.json> --request-id <request-id> --environment development --correlation-id <correlation-id>
vss movie demo --story tests/fixtures/movie/story-fragment-valid.json --reviewer-id local.reviewer --storyboard-specification
```

Add `--dry-run` to the standalone command for readiness only. Without
`--storyboard-specification`, the demo retains its M7.4 behavior and stops after
the shot-plan draft.

## M8.1 governed deterministic local storyboard rendering

`movie.render-storyboard` independently reconstructs the complete accepted
review, option, scene, shot-plan, storyboard, semantic-digest, and Knowledge
lineage before admitting a minimized immutable request to Runtime. Runtime
authorizes the repository-owned `movie.storyboard-render` capability's exact
`provider_access` and `filesystem_write` permissions and statically selects the
built-in `movie.storyboard-render.local/1.0.0` provider.

The standard-library provider produces a deterministic 1200×1500 SVG review
sheet with three ordered schematic panels. Runtime atomically publishes it at
`.local/movie/storyboards/<storyboard-specification-digest>/storyboard.svg`.
Callers cannot supply a path. Identical content is idempotent; conflicts,
symlinks, escapes, and special destinations fail closed.

```console
vss movie render-storyboard --decision <decision.json> --review-packet <packet.json> --option-set <options.json> --scene-breakdown <breakdown.json> --shot-plan <shot-plan.json> --storyboard <storyboard.json> --environment development --correlation-id <correlation-id>
vss movie demo --story tests/fixtures/movie/story-fragment-valid.json --reviewer-id local.reviewer --render-storyboard
```

The demo flag implies storyboard specification generation and uses the same
public adapter and Runtime capability. Dry-run performs admission and policy
checks but calls no render provider and writes no media. The output is only
`development_review_media`: not pictorial AI generation, production approval,
asset admission, final selection, publication, scheduling, workflow activation,
or autonomous authority. External providers, raster output, production
rendering, asset catalogs, revisions, queues, and workers remain unimplemented.
