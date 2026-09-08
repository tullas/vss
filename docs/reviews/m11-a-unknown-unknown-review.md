# M11.A UNKNOWN_UNKNOWN_REVIEW — External Media Boundary

| risk_or_missing_seam | affected_invariant | scenario | impact | required_decision | owner | disposition | evidence |
|---|---|---:|---|---|---|---|---|
| Provider handling, retention, residency, and compatibility are unknown. | Rights and minimum-disclosure boundaries must be explicit. | 2,4,11,12,13 | rights, tenant, audit | Bind required handling evidence to the provider/model contract and fail closed when absent. | provider/data governance | mitigate_before_acceptance | ADR-0028 exact provider boundary |
| A timeout or ambiguous cost could permit a second attempt. | One approval admits one non-reusable attempt and full ceiling remains consumed. | 10 | cost, authority | Terminally quarantine unresolved attempts; prohibit retry or reservation reuse. | Runtime/resource admission | mitigate_before_acceptance | ADR-0028 spend admission |
| Returned bytes could become an uncontrolled asset. | Output is review-only, same-scope, expiring quarantine evidence. | 3,8,9,13 | rights, recovery, product | Validate bytes/metadata, digest and lineage, and controlled local quarantine; no release or promotion. | media/data governance | mitigate_before_acceptance | ADR-0028 output admission |
| Future provider or storage retirement could strand evidence. | Provider and local-output seams remain bounded and replaceable. | 4,5,8,12 | availability, recovery | Keep the result disposable and defer durable recovery, catalog, and reuse. | architecture | accept_with_bound | ADR-0028 deferred seams |
| Scale or review load could pressure generalized infrastructure prematurely. | No queue, worker, database, or generalized subsystem is introduced. | 1,10 | availability, cost | Limit this decision to one local attempt and reassess before expansion. | architecture | accept_with_bound | ADR-0028 scope |

## Scenario coverage

All thirteen required stress scenarios are represented above; scenarios not
listed separately are covered by the combined findings. Acceptance is bounded
to the decision and grants no execution authority.

## Disposition

`ACCEPT` — the ADR adds the minimum missing seams and records explicit deferral
triggers for unresolved durable platform concerns.
