# M8.3 real-provider smoke-3 pre-paid checkpoint

Smoke-3 preserves smoke-2 and reuses its fixed M8.3 Mira frame, depiction-only projection,
OpenAI endpoint, `gpt-image-2-2026-04-21` snapshot, 1280x720 medium-quality PNG request, one-call
maximum, and US$0.07 ceiling. It has a new disposable create-once state root:
`.local/movie/m8-3-real-provider-smoke-3`. Smoke-1/smoke-2 evidence and state are not inputs and
are never modified.

Runtime remains execution authority. The pre-paid checkpoint reconstructs the authoritative
request, checks unused state/output readiness, and runs `ExternalExecutionPreflight` for exact
request binding, credential-variable presence, proxy absence, and bounded DNS readiness. It reads
no credential value, makes no provider request, persists no DNS result, and reserves no attempt.
Readiness reports `provider_call_count: 0` and `attempt_reserved: false`.
The CLI and command runner require the closed mode to be explicit; omission, contradiction with
Runtime dry-run state, or any caller-added mode is rejected before admission.

Run the zero-call checkpoint with the six governed artifacts:

```text
vss movie m8-3-real-provider-smoke-3 --decision <decision.json> --review-packet <packet.json> --option-set <options.json> --scene-breakdown <breakdown.json> --shot-plan <shot-plan.json> --storyboard <storyboard.json> --environment development --correlation-id <checkpoint-id> --preflight
```

After separate explicit authorization, changing only the mode and correlation ID would execute the
single paid attempt:

```text
vss movie m8-3-real-provider-smoke-3 --decision <decision.json> --review-packet <packet.json> --option-set <options.json> --scene-breakdown <breakdown.json> --shot-plan <shot-plan.json> --storyboard <storyboard.json> --environment development --correlation-id <authorized-attempt-id> --generate
```

The generation path reruns the same authoritative Runtime preflight after SDK/handler readiness
checks and immediately before create-once reservation. Only then may credential retrieval and the
single transport occur. There is no retry, fallback, second candidate, A/B path, or regeneration.
Success stops at a reviewer record with exactly `USE`, `REGENERATE`, or `REJECT`; `REGENERATE`
does not authorize another call. All production, asset, final-selection, publication, workflow,
autonomous, and reusable-execution authority flags remain false.

## Outcome

Exactly one provider call succeeded and produced the fixed 1280x720 PNG review candidate. The
sanitized estimated cost was US$0.030140 and provider latency was 28,913 ms. Human review recorded
`USE`. This disposition applies only to the generated review candidate, grants no production,
publication, workflow, autonomous, or reusable provider authority, and authorizes no second call.
