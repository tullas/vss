# M11.0 UNKNOWN_UNKNOWN_REVIEW — External Moving-Shot Boundary

| risk_or_missing_seam | affected_invariant | scenario | impact | required_decision | owner | disposition | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Provider-side handling, retention, and compatibility of the admitted still and returned video are not owned by the current still-review path. | Rights, provenance, and output admission are explicit rather than inferred from local possession. | 2, 4, 9, 13 | rights, audit, product | Admit a narrow external-media contract with provider handling limits and a controlled output boundary, or defer the external call. | Asset/Data and production-governance architecture | block | docs/architecture/adr-evidence-matrix.md; docs/architecture/vss-constitution.md |
| A one-call ceiling cannot prevent charge ambiguity or duplicate effects after timeout without an accepted request reservation and terminal reconciliation rule. | Runtime effect authority does not substitute for dynamic cost/resource admission. | 7, 10 | cost, recovery, audit | Admit a bounded one-attempt reservation and reconciliation seam before any credentialed transport. | Runtime and production-governance architecture | block | docs/architecture/adr-evidence-matrix.md; docs/runtime-kernel.md |

All other required scenarios were reviewed and add no independent material
finding beyond these two coupled boundary gaps. `REVISE`: do not select a
provider, transmit media, or attempt generation until the required architecture
decision and independent review evidence exist. This review grants no execution
or production authority.
