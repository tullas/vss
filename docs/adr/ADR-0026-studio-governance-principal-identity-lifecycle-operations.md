# ADR-0026: Studio Governance, Principal Identity, and Lifecycle Operations

## Status

Accepted

## Date

2026-08-24

## Context

[ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md) makes Runtime the
execution authority. [ADR-0016](ADR-0016-autonomy-approval-execution-authority.md)
separates proposal, policy, approval, execution, and audit. [ADR-0021](ADR-0021-studio-workload-planes-specialized-execution.md)
defines logical workload planes without requiring services. VSS also needs
stable governance and maintenance seams before production operation expands.

Autonomous detection can improve safety and efficiency, but it cannot become
ambient administration. Platform maintenance affects active productions,
tenants, rights, cost, credentials, durability, and recovery. Treating it as
out-of-band shell access would bypass the same controls required for creative
effects.

This ADR refines governance and lifecycle boundaries. It does not redefine
Runtime, select an identity/policy/workflow/SRE product, implement maintenance,
or require physical control/data-plane separation.

## Decision

VSS adopts auditable principal identities, explicit policy domains and
separation of duties, bounded control/data exchange, and a governed lifecycle
protocol for platform changes.

### Control Plane and Data Plane

The Control Plane owns bounded state and decisions for policy, workflow and
admission, authority, cost, rights, approvals, cancellation, lifecycle, and
audit association. Runtime remains the sole execution and execution-admission
authority.

The Data Plane owns heavy media/object payloads, immutable physical storage,
caches, and resolution under exact governed references. It does not authorize
access, promotion, reuse, or execution. Agents and services exchange exact
identities, references, and bounded purpose-specific projections rather than
unnecessary media copies. Bytes may bypass Runtime as transport but never its
authorization boundary, as required by ADR-0022.

These are logical responsibilities and may coexist in one process, filesystem,
or workstation. Deployment topology grants no authority.

### Principal identity and least privilege

Auditable principal classes are `human`, `agent`, `service`, `provider`, and
`organization`. A principal identity is distinct from:

- authentication method or assurance strength;
- role, group, employment, or customer relationship;
- capability, credential, delegation, approval, or Runtime authorization;
- provider/model identity; and
- accountability metadata supplied by an unauthenticated caller.

Every governed action records the acting/requesting principal, delegated
principal where applicable, capability/operation scope, policy and approval
references, and outcome without exposing secrets. Authentication and
authorization are independently validated at the applicable boundary.

Agents analyze, detect, recommend, and propose only within explicit capability
and data scopes. Services and providers receive least-privilege, purpose-bound,
expiring access. No principal may infer authority from identity, registration,
confidence, previous success, queue placement, asset access, or another
principal's delegation. Runtime authorizes effects; workers/providers cannot
extend the admitted scope.

Human attention, economic budget, time, compute, storage, and blast radius are
governed scarce resources. Automation must bound review volume and cost rather
than converting overload into implicit approval.

### Policy domains and separation of duties

VSS distinguishes these governance domains:

| Domain | Owns | Does not independently grant |
| --- | --- | --- |
| Creative authority | canon, selections, creative acceptance within scope | Runtime effects, rights, publication |
| Runtime/effect authority | operation admission and execution authorization | creative truth, ownership |
| Rights/legal policy | machine-enforceable rights facts, restrictions, review requirements | legal certainty from AI output, payment |
| Commercial/budget policy | spend, pricing, royalties, allocations, ceilings | rights or creative approval |
| Platform/SRE change authority | maintenance policy, environments, recovery requirements | self-authorized execution |
| Security authority | security policy, credentials, incident controls, exceptions | unrelated creative/commercial authority |
| Data governance | retention, deletion, residency, classification, export constraints | ownership or unrestricted reuse |
| Audit/break-glass | evidence integrity, emergency procedure and review | silent standing administration |

One physical person or service may hold several roles only when explicit policy
permits it. High-impact actions require independent duties appropriate to risk.
Conflicts, missing owners, or ambiguous policy fail closed.

Policy is versioned policy-as-code where facts and decisions are deterministic.
Legal ambiguity, creative judgment, novel security risk, irreversible change,
and other high-impact uncertainty require an authorized human gate. AI output
alone cannot grant irreversible, legal, financial, production, publication,
security, credential, or platform-change authority.

### Governed lifecycle protocol

Maintenance is a first-class capability with this mandatory lifecycle:

```text
detect / recommend
  -> plan
  -> preflight
  -> approval or explicitly applicable pre-approved policy
  -> Runtime-authorized execution
  -> verification
  -> evidence
  -> tested rollback, reconciliation, restore, or forward recovery
```

Detection and recommendation are inert. A plan is not authority. Preflight is
read-only and performs cheap closed readiness checks without providers or
secrets where possible. Approval binds exact inputs; Runtime revalidates
immediately before any effect. Execution uses the normal capability/provider
boundary. Verification compares the exact intended and observed state.
Evidence records bounded outcomes. Recovery is selected explicitly rather than
assumed.

The protocol applies, when introduced, to:

- OS patches and OS upgrades;
- base images, runtimes, languages, libraries, and dependencies;
- database engine minor/major upgrades and schema/data migrations;
- storage formats and object layouts;
- queue and workflow-engine versions;
- model/provider deprecation and replacement;
- certificate, key, credential, and secret rotation;
- infrastructure and dependency CVE remediation;
- backup, restore, disaster-recovery tests, and regional recovery;
- capacity changes and cost optimization; and
- deprecation and end-of-life management.

Admission binds the exact target version/change set, source version, environment
and deployment identity, tenant/workload scope, policy version, maintenance
window, risk/reversibility, expected state, compatibility/prerequisite evidence,
backup and restore proof where applicable, cost/resource ceiling, SLA,
residency/rights/retention constraints, verification, and recovery plan. Drift
in any material binding invalidates approval and requires re-evaluation.

### Risk-tiered automation

Future routine, bounded, tested, reversible changes may execute within an
explicitly owned, versioned, expiring pre-approved policy window. That policy
is scoped authority evaluated by Runtime; it is not agent self-authorization,
historical precedent, or a blanket maintenance permission.

Irreversible, destructive, major-version, security/credential-sensitive,
rights/residency-affecting, high-blast-radius, or recovery-uncertain changes
require an explicit human gate. Unknown reversibility is treated as
irreversible. Approval for one environment, version, tenant scope, or change
set cannot be replayed for another.

Direct mutable production administration that bypasses governed paths is
prohibited except audited break-glass. Break-glass is narrow, time-limited,
independently accountable, minimally privileged, monitored, and followed by
mandatory reconciliation, evidence, credential review/rotation where needed,
and retrospective review. Emergency access never becomes normal automation.

### Deployment and migration safety

Desired-state and Infrastructure as Code drive change where practical. Canary,
rolling, and blue-green strategies are preferred when supported and safer;
their availability does not make a change reversible. Active production load,
tenant SLAs, locality/residency, rights, retention, security, and cost ceilings
constrain maintenance windows and rollout.

Application/schema evolution uses compatibility windows and
expand/migrate/contract where appropriate. Destructive database or storage
migration requires backup plus demonstrated restore proof before the
irreversible gate. Database rollback is never presumed possible: every plan
names tested rollback, reconciliation, restore, and/or forward recovery, and
defines the safe point beyond which each remains valid.

Partial, timed-out, or ambiguous outcomes are inspected before retry. A retry
cannot reserve new authority or repeat a possibly committed external effect
without reconciliation and fresh admission.

## UNKNOWN_UNKNOWN_REVIEW findings

The bounded major-boundary review produced three material missing seams:

| Risk or missing seam | Required decision | Disposition |
| --- | --- | --- |
| A compromised agent/service credential can leave queued work and delegated authority apparently valid. | Credential/principal suspension invalidates pending admission and forces current policy/identity revalidation; rotation does not erase accountable historical identity or audit. | `mitigate_before_acceptance` — incorporated as a later identity/Runtime contract requirement. |
| Maintenance may be safe globally but violate one active tenant's SLA, residency, rights, retention, or encryption constraints. | Effective maintenance admission intersects every affected tenant constraint; inability to prove an applicable constraint defers or denies that tenant's change. | `mitigate_before_acceptance` — incorporated in admission bindings. |
| Cost runaway or reviewer overload can turn grouped automation into accidental approval. | Attention/cost ceilings stop or narrow work; batching cannot merge unrelated authority scopes or interpret silence/timeout as approval. | `mitigate_before_acceptance` — permanent policy/UI requirement. |

No additional service or autonomous authority was introduced.

## Consequences

Platform operations use the same governed authority architecture as production
capabilities while allowing autonomous detection and bounded future routine
maintenance. Principals, policy domains, evidence, and recovery become explicit
without requiring new services.

Costs include more planning, compatibility evidence, recovery testing, and
human gates for high-risk work. These costs prevent silent privilege expansion
and unrecoverable maintenance.

## Deferred

- authentication, SSO/RBAC, workload identity, credential broker, and delegation schemas;
- policy engine, approval service, commercial/rights systems, and durable audit;
- maintenance capabilities, workflows, schedulers, agents, providers, and dashboards;
- concrete risk tiers, pre-approved windows, break-glass implementation, HA/DR infrastructure;
- database/storage/queue selections and executable migration plans.

Later implementations must follow ADRs 0010, 0016, 0021, 0022, 0023 and
[ADR-0027](ADR-0027-portable-authoritative-state-storage-evolution.md), deliver
an executable vertical slice with tests, and complete an applicable bounded
[UNKNOWN_UNKNOWN_REVIEW](../architecture-boundary-review.md).

## Acceptance criteria

- detect/recommend/plan are structurally distinct from authorize/execute;
- Runtime remains sole execution authority and pre-approved windows are scoped policy;
- principal identity never implies role, approval, authentication strength, or capability;
- all eight governance domains and their non-authorities are explicit;
- lifecycle classes and plan/preflight/approval/execution/verification/evidence/recovery stages are complete;
- drift invalidates approval and database rollback is not presumed;
- break-glass is exceptional, audited, reconciled, and never ambient administration;
- no infrastructure, identity, policy, database, queue, or orchestration product is selected.
