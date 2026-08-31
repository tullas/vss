# Domain-neutral production visual grounding

M10.0 provides one inert, production-owned visual-grounding profile and a sealed
versioned route into the controlled storyboard-frame projection. The mechanism
does not contain or infer historical, cultural, geographic, wardrobe,
architecture, technology, brand, genre, or other domain knowledge. Group IDs and
constraint text are opaque production data.

`production_visual_grounding_profile/1` binds exact tenant, universe, and
production scope; optional scene and declared-character applicability; mode;
ordered constraint groups; uncertainty, conflicts, limitations, evidence
references, lifecycle, reviewer accountability metadata, and a canonical seal.
`required` profiles must be active, conflict-free, applicable, and contain at
least one complete group. `not_required` profiles contain no groups and preserve
the existing generic M8/M10 semantics.

M10.1 adds `production_visual_grounding_profile/2` for one bounded revision
cycle. A human authors the complete next opaque profile; VSS never derives or
mutates it from review evidence. The sealed revision binds the immediately prior
same-profile revision and one sealed `REGENERATE` or `REJECT` grounding review,
including its candidate and frame digests. The existing v3 route carries the
revised profile digest unchanged, so every separately approved candidate binds
the exact human-authored revision and its predecessor evidence. This adds no
profile, prompt, approval, reservation, Runtime, provider, product, canon, or
rights authority.

The grounded route is additive and versioned:

```text
production_visual_grounding_profile/1
  -> creative_decision_revision/2
  -> canon_snapshot/2
  -> production_canon_binding/2
  -> scene_shot_plan_draft/2 grounding overlay
  -> scene_storyboard_specification/2 grounding overlay
  -> controlled_storyboard_frame_generation_request/3
```

The shot-plan and storyboard v2 artifacts are strict overlays over independently
reconstructed v1 artifacts. Each item binds the exact base shot or frame digest,
applicable group IDs, opaque positive constraints, exclusions, unresolved facts,
limitations, and a content seal. The base draft/specification remains
authoritative for narrative and camera content. The overlays add no render,
production, provider, Runtime, workflow, rights, or publication authority.

The v3 request independently reconstructs the v1 path and every grounded overlay.
Its provider projection contains only the selected base frame depiction fields
and the applicable positive constraints, exclusions, and unresolved limits. It
does not send group IDs, curator/reviewer identities, evidence references,
rights records, unrelated groups, or unrelated frames. The request binds the
profile and exact frame-grounding digests. All existing one-use approval,
preflight, reservation, provider, cost, output-admission, quarantine, and
no-retry controls remain unchanged.

The CLI accepts the grounded route only when all of these optional arguments are
present together:

```text
--visual-grounding-profile
--grounded-creative-decision
--grounded-canon-snapshot
--grounded-canon-binding
--grounded-shot-plan
--grounded-storyboard
```

`production_visual_grounding_review/1` records a bounded production-defined
defect code, optional group reference, rationale, reviewer accountability
metadata, and exact candidate/frame/profile digests. It is evidence for a later
profile revision, not truth by itself. Its authority fields are structurally
false: it cannot mutate a profile or prompt, issue approval, reserve an attempt,
call Runtime or a provider, or trigger regeneration.

External asset ingestion, automated retrieval, embeddings, model-authored
grounding facts, asset catalogs, domain-specific validation, and reusable-asset
admission remain separate future capabilities.
