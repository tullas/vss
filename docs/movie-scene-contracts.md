# M4.1 Movie Scene Contracts

M4.1 is validation only. It introduces the bounded movie-domain registry and
three inert contracts: `story_fragment/1`, `break_down_scenes/1`, and
`scene_breakdown/1`. It does not implement scene parsing, Context Assembly,
strategies, providers, production options, AI, retrieval, media generation,
Plan IR, approval, or execution.

The Movie Domain Contract Registry is repository-owned, immutable, exact,
non-authorizing, and independent from the Semantic, Knowledge, Context,
Runtime, provider, workflow, and capability registries. Registration means known
only. Existing M3 v1 contracts are unchanged; M4.2 will define explicit
Knowledge/Context admission mappings.

`story_fragment/1` is bounded source data with original fixture text, explicit
declarations, inert citations, rights qualification, and cultural
qualification. Declarations are source claims, not extracted truth. Annotations
are not an extension bag. Unknown shapes fail closed. Rights status is not legal
clearance, and cultural status is not cultural authority.

`break_down_scenes/1` is a validation-only task identity expecting
`scene_breakdown/1`. The result is a typed inert interpretation with bounded
ordered scenes, source spans, explicit boundary basis/rule, closed provenance
categories, ambiguity, assumptions, unknowns, conflicts, confidence, and
limitations. No algorithm exists yet. Scene boundaries are not artistically
definitive; natural-language location/time mentions are not automatically
structural transitions.

Scene identities and payload digests are deterministic and independent of time,
correlation, process, path, provider, and hash seed. Validated models are
recursively immutable. Strict schemas reject unknown fields, oversized values,
duplicate keys, non-finite values, unsafe references, and unsupported types.

Fixtures are original repository test material and use `original` rights
qualification. No third-party screenplay, prose, lyrics, private data, or
cultural/historical claim is included.

M4.2 owns `scene_breakdown_context/1`, Context Assembly, and the deterministic
scene-breakdown implementation. Later milestones may add production-option
contracts and Context. No Plan IR is defined until concrete movie outputs show
repeated sequencing, dependency, resource, effect, or approval requirements.

Trusted Python remains in-process. Any future audit remains development-only;
production rights verification, persistent revocation, isolation, and durable
audit are deferred.

### M4.1 precision notes

The validated Story Fragment `digest` is the complete canonical digest of the
validated artifact; M4.1 does not expose a second declared integrity field.
`fragment_id` and `scene_id` are validated caller-supplied stable identifiers,
not cryptographic identity derivations. Their semantic content is bound by the
complete artifact/payload digests and source bindings.

Scene source spans use Unicode code-point offsets. Standalone M4.1 validation
checks span shape, ordering, overlap, and source-binding references; containment
against source text is deferred to M4.2 Context assembly. Each scene carries an
exact versioned boundary-rule reference, an ambiguity marker, and a
scene-content digest. Fallback boundaries are rule-derived and never imply
artistic certainty.

The task contract has a strict `validate_scene_task` API. Its lifecycle denotes
structural contract admission only; it does not imply an implemented algorithm,
strategy, provider, or executable policy. Registry schema snapshots are
recursively immutable. No annotation extension bag exists in `story_fragment/1`.
