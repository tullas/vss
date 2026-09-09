# ADR-0029: Existing-Media Revalidation Against Current Lineage

## Status

Accepted with guardrail

## Context

The accepted M11.0 bounded path has immutable review media and historical
admission evidence, but current source reconstruction can differ from the
historical candidate lineage. Reusing historical grounding evidence would
silently convert stale review into current evidence.

# Decision

VSS may revalidate one immutable, already-retained review image against a
newly reconstructed current scene/shot/storyboard/frame/option lineage. The
revalidation record verifies the exact bytes by `media_sha256`, carries the
historical candidate, grounding review, promotion, admission, catalog, and
lineage digests in an explicitly historical-only section, and separately binds
the current authoritative lineage. Historical evidence never becomes evidence
that the media was produced from the current lineage.

Revalidation is initially a pending human-review request. Completion requires a
new sealed human grounding review whose scene, shot, frame, and option IDs and
candidate digest are current and distinct from the historical review. Only a
completed revalidation may create the separate current-shot binding transition;
the existing historical `grounded_storyboard_shot_binding/1` contract and checks
are unchanged.

The evidence and transition are development review references only. Their
authority fields are closed false: they grant no canon, publication,
production, Runtime, provider, deployment, regeneration, ranking,
recommendation, workflow, or autonomous authority. They copy no media bytes and
do not invoke providers, generate media, create Candidate 3, or execute video.

## Guardrail and stop

The implementation reconstructs current source through the real deterministic
movie path and verifies the existing PNG bytes locally. It prepares a pending
artifact and stops at the new human grounding review boundary. M11.0 is not
admissible until that review and the separate current-shot binding are recorded.
