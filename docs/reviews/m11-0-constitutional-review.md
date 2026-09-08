# M11.0 Constitutional Review — First Governed Moving Shot

## Boundary under review

Issue #132 proposes VSS's first external effectful media request and first
controlled video artifact. It would consume an admitted still basis, transmit
it to a provider, reserve one bounded paid attempt, and retain a returned media
file with lineage. The current architecture explicitly defers these seams:
ADR-0021's Asset/Data and Compute boundaries, ADR-0022's dynamic
cost/resource admission and production-input snapshot, and output admission
for effectful artifacts. No accepted owner or contract currently admits them.

## Material falsification findings

| Finding | Affected invariant | Stress | Required decision | Disposition |
| --- | --- | --- | --- | --- |
| A content digest alone cannot prove that the exact admitted still is the immutable provider input or that a returned clip belongs to that request. | Exact production-input snapshot and output lineage. | Provider loss/retirement; stale or revoked state; later provenance audit. | Admit an Asset/Data and output-admission boundary with immutable input, request, and output bindings. | `block` |
| Existing Runtime policy authorizes permissions/providers but has no dynamic budget, reservation, pricing, or one-attempt recovery semantics. | Static validation must not masquerade as resource admission. | Cost runaway; partial provider failure; hours-long operation. | Admit bounded cost/resource reservation and terminal-attempt semantics before a paid call. | `block` |
| A local video file has no accepted controlled-media residency, retention, deletion, or quarantine owner. | Heavy bytes remain outside semantic/control paths with explicit rights and recovery handling. | Tenant/rights conflict; customer exit; corrupt media or failed recovery. | Admit the minimal controlled media/output boundary or explicitly reduce the milestone to non-effectful architecture work. | `block` |

## Required stress coverage

Scenarios 1, 2, 3, 4, 5, 7, 9, 10, 12, and 13 expose the three findings above.
Scenarios 6, 8, and 11 are not applicable: this proposal contains no database
migration, operated site/backup system, or multi-region deployment. The
review does not treat those absences as acceptance of an external media path.

## What important production property currently has no architectural owner?

Immutable external-media input admission, controlled output admission,
media retention/deletion, terminal attempt reconciliation, and dynamic spend
reservation have no accepted architectural owner. The evidence matrix names
the applicable future gates rather than implementing these guarantees.

## Disposition

`REVISE`. A narrow architecture decision and independent falsification review
must admit the minimum boundaries before implementation. This review grants no
execution, provider, production, publication, migration, purchase, or workflow
authority.
