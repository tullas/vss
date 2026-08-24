# UNKNOWN_UNKNOWN_REVIEW

Use this bounded review before accepting a **major architecture boundary**: a
new durable authority boundary, tenant/data isolation boundary, authoritative
state technology, cross-plane protocol, irreversible migration mechanism,
external platform dependency, or material change to recovery/security/rights
semantics.

Do not require it for ordinary pull requests, compatible domain extensions,
routine dependency updates, or implementation inside an already accepted
boundary. It is a material-risk gate, not recurring ceremony and not a feature
brainstorm.

## Review input

Record only:

- boundary/decision and owning ADR or proposal;
- exact scope, assumptions, invariants, authority and data flows;
- expected scale/lifetime and current evidence;
- known failure/recovery model and deferred seams; and
- reviewer perspectives needed for the material risks.

## Required stress scenarios

Challenge applicable assumptions against:

1. 10x productions, 100x assets, and multi-year history;
2. external tenants with conflicting contracts or policies;
3. customer exit plus deletion, retention, export, and legal-hold obligations;
4. provider/model retirement or loss of compatibility;
5. OS, database, language, runtime, dependency, or platform end-of-life;
6. failed database major upgrade, partial migration, or ambiguous cutover;
7. compromised human, agent, service, or provider credential;
8. region/site loss, corrupt backup, or failed disaster recovery;
9. rights discovered invalid after derivatives, promotion, or publication;
10. cost runaway, capacity exhaustion, or human-review bottlenecks;
11. tenant-specific residency, encryption, isolation, or audit requirements;
12. loss of an infrastructure, database, storage, or other critical vendor;
13. regulatory, contractual, provenance, or audit request years later.

Mark a scenario `not_applicable` only with a short boundary-specific reason.
Unknown required validity fails closed.

## Output contract

Output is a bounded table containing only material new risks or missing seams:

| Field | Requirement |
| --- | --- |
| `risk_or_missing_seam` | Concrete failure or coupling exposed by stress; no feature wish list. |
| `affected_invariant` | Existing or proposed invariant at risk. |
| `scenario` | One or more required stress-scenario numbers. |
| `impact` | Security, rights, tenant, availability, recovery, cost, audit, or product consequence. |
| `required_decision` | Smallest seam, constraint, experiment, or explicit deferral needed before acceptance. |
| `owner` | Accountable architecture/policy domain, not an unauthenticated identity claim. |
| `disposition` | `block`, `mitigate_before_acceptance`, `accept_with_bound`, or `defer_with_trigger`. |
| `evidence` | Bounded references to tests, measurements, contracts, incidents, or accepted decisions. |

Maximum 20 findings. Combine duplicates. Do not include implementation ideas
that do not change risk, missing seams, acceptance, or deferral triggers. Do not
invent services, products, schemas, or platform features solely to fill the
table.

## Acceptance

The decision owner records:

- every required scenario as reviewed or justified `not_applicable`;
- each material finding's disposition and owner;
- changes made to the proposal and unresolved bounded risks;
- explicit evidence/trigger for any deferral; and
- `ACCEPT`, `REVISE`, or `REJECT`.

Review acceptance is architecture evidence only. It grants no Runtime,
provider, production, publication, migration, purchase, deployment, or
workflow authority.
