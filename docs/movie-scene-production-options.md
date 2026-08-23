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
