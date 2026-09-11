# Film #1 two-day production-path lessons

This record captures the systemic lessons from the two-adjacent-shot Film #1
experiment. It is process-improvement evidence, not production authority.

## Observed failures

- Component and CI success did not establish end-to-end production readiness.
- Semantic identity drift separated planning, authorization, and execution.
- An execution namespace collision consumed attention before provider work.
- Credential lifecycle and provider readiness were not reliable at the irreversible boundary.
- Provider acceptance and local-attempt ledger semantics diverged.
- A successful terminal provider result required recovery before local admission.
- Controller merge-SHA identity created conflicts across valid execution context.
- Producing adjacent shots required excessive human and Codex intervention.

## Required improvement scope

Before any material scale beyond this experiment, prioritize a repeatable,
source-code-repair-free two-adjacent-shot path with:

1. A full provider-lifecycle state machine covering authorization, readiness,
   reservation, submission, operation polling, terminal evidence, local
   admission, recovery, reconciliation, and cost.
2. An end-to-end digital-twin/golden-path rehearsal and failure injection before
   paid execution.
3. Centralized semantic identity shared by plan, request, authorization,
   namespace, operation, ledger, and artifact records.
4. Credential readiness immediately before the irreversible provider boundary.
5. A controller identity design that cannot confuse merge SHA, execution
   identity, and authoritative request identity.
6. Production KPIs: time-to-valid-shot, interventions-per-shot, provider
   submissions, failures, and cost.
7. Complexity and governance-effectiveness measures, including whether each
   control reduces failure or intervention without adding unjustified burden.

The product rule is explicit: do not expand architecture or governance merely
for its own sake. Demonstrate the repeatable adjacent-shot path first; scale
only when the evidence shows that the smallest useful extension is working.

This record does not authorize provider calls, new paid authorization, Runtime
recovery or repair, Attempt 6, production, publication, or workflow activation.
