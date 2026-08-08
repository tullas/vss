# M4.2 Deterministic Scene Breakdown

M4.2 connects the validation-only movie contracts to a bounded local Context
and the existing reasoning boundary. A validated `story_fragment/1` is copied
into the task-specific `scene_breakdown_context/1`; the deterministic
`vss.break-down-scenes.deterministic/1.0.0` implementation then emits a
validated `scene_breakdown/1`.

The source-artifact path is deliberately narrow: one validated Story Fragment
is admitted directly, without changing the M3 Knowledge Package schemas. The
Context preserves the source text and qualifications but contains no package,
registry, schema, path, audit, or execution material.

The rule catalogue is repository-owned (`vss.scene-boundary-rules.deterministic/1.0.0`).
This slice recognizes only exact `SCENE: <identifier>` line markers and a
bounded fallback. Ordinary prose mentions are not structural transitions.
Fallback scenes are low-confidence, explicitly ambiguous, and qualified as
rule-derived rather than artistic truth. Source spans use Unicode code-point
offsets and scene IDs/digests are deterministic.

The provider view is immutable and contains only the minimized Story Fragment,
source qualifications, rule identity, bounds, uncertainty, and limitations. It
cannot retrieve more data or access files, network, Runtime, capabilities,
workflows, registries, or audit. Trusted Python remains in-process and is not a
sandbox.

`vss movie context-assemble-scene-breakdown` and `vss movie break-down-scenes`
are routing-only CLI commands. Dry-run validates readiness and invokes zero
providers. There is no external AI, prompt, screenplay parser, production
option, Plan IR, approval, execution, media generation, or production audit.
Local JSONL audit remains development-only where applicable. M4.3 owns scene
production options through an independently validated exact scene ID/digest
binding; it does not reinterpret or mutate Scene Breakdown.
