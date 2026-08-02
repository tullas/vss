# ADR-0016: Autonomy, Approval, and Execution Authority

## Status

Accepted

## Date

2026-08-02

## Context

VSS can represent inert reasoning results and governed knowledge, but future
autonomous behavior requires an explicit authority model. Model quality,
provider selection, workflow structure, confidence, or previous success cannot
become authorization. Approvals must not become durable ambient privileges,
and local development conveniences must not become production policy.

The permanent rule is:

> Reasoning proposes. Policy evaluates. An authorized approver approves when
> required. Runtime validates the approval and remains the sole execution
> authority.

No proposer, provider, strategy, capability, workflow, worker, connector, or
Knowledge Package may approve itself or grant execution authority.

This decision is governed by:

- [ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md), which makes
  Runtime the sole execution and authorization authority;
- [ADR-0011](ADR-0011-engineering-principles.md), especially least privilege,
  explicit authorization, fail-closed behavior, audit, and human approval for
  destructive operations;
- [ADR-0012](ADR-0012-evolvable-reasoning-architecture.md), which establishes
  that reasoning proposes and Runtime executes;
- [ADR-0013](ADR-0013-semantic-reasoning-contracts.md), which makes semantic
  objects inert and provider neutral;
- [ADR-0014](ADR-0014-local-first-scalability-performance-efficiency.md), which
  governs bounded concurrency, budgets, protected critical controls, retries,
  and local-first scale;
- [ADR-0015](ADR-0015-knowledge-architecture.md), which makes knowledge
  purpose-limited and non-authorizing; and
- the [M2 architecture checkpoint](../reviews/m2-architecture-checkpoint.md),
  which identifies production gaps in cancellation and audit durability.

Autonomy never bypasses Runtime, policy, contracts, budgets, approval, audit,
isolation, idempotency, reconciliation, revocation, data classification, or
Knowledge Package purpose restrictions.

## Decision

VSS will use explicit, independently validated roles, bounded autonomy levels,
versioned risk and reversibility classifications, immutable scoped approval
artifacts, mandatory revalidation, kill switches, and protected emergency
controls. Runtime consumes authority; it does not infer authority from
reasoning output, confidence, package contents, provider behavior, or queue
presence.

### Authority model

#### Proposer

A proposer creates a recommendation, candidate plan, or requested action. It
may be a human, deterministic strategy, reasoning strategy, provider-backed
strategy, workflow, or capability. Proposal creates no approval or execution
authority.

#### Policy evaluator

The evaluator considers operation identity and version, environment, risk,
reversibility, blast radius, classification, Knowledge Package purpose,
provider and strategy maturity and lifecycle, budgets, cost, concurrency,
production status, and approval requirements. Evaluation is not approval unless
an explicit versioned policy permits the operation at a bounded autonomy level.
Unknown policy state fails closed.

#### Approver

An approver is an independently authorized principal or mechanism and approves
only within assigned scope. It may be a human, governed group, an explicitly
authorized policy rule for low-risk work, or a future external system behind a
narrow adapter. A model, provider, worker, strategy, or candidate plan cannot
approve itself. Approver authority is independently versioned, scoped,
expiring, revocable, and validated.

#### Executor

Runtime is the sole execution authority. Workers, providers, capabilities, and
workflows act only under validated, bounded authority issued by Runtime. A
worker cannot extend that authority or substitute its own decision.

#### Auditor

The auditor records safe evidence of proposal, policy, approval, denial,
execution, revocation, cancellation, and outcome. Audit never grants authority.

### Separation of duties

Proposer, approver, executor, and auditor are logically distinct. High-risk
operations require an approver independent of the proposer. Critical operations
may later require multiple independently authorized approvers. Low-risk local
operations do not require multi-party approval when explicit policy permits
them.

Conflicts of interest are evaluated against proposer identity, approver
identity and authority, project or tenant, operation ownership, and affected
resources. A conflicted principal cannot satisfy an independence requirement.
The final identity and conflict policy is deferred.

### Autonomy levels

| Level | Name | Authority |
| --- | --- | --- |
| 0 | Disabled | No reasoning or autonomous action; manual operation uses approved Runtime paths. |
| 1 | Advisory | Explain, summarize, classify, or recommend; no executable action or plan is authorized. |
| 2 | Proposal | Produce structured options or candidate plans; results remain inert. |
| 3 | Read-only execution | Runtime executes explicitly classified, capability-specific read-only operations under bounded policy. |
| 4 | Human-approved reversible execution | Runtime executes a reversible, compensatable, or reconcilable change after explicit human approval and with rollback or reconciliation evidence. |
| 5 | Policy-approved bounded reversible execution | Runtime executes a narrowly bounded reversible or reconcilable action without per-action human approval only under an owned, versioned, expiring policy and all production prerequisites. |
| 6 | Reserved high-impact autonomy | Reserved; no current implementation may claim unrestricted autonomy. |

Level 3 may cover system inspection, metadata validation, repository analysis,
continuity checks, and non-mutating knowledge retrieval only when read-only
classification is explicit for that exact operation.

Level 4 may cover draft assets, development-only generated files, temporary
development resources, review media, and budget-capped temporary tests. These
examples grant no authority by themselves.

Level 5 requires an explicitly approved capability and operation version,
environment, bounded and reversible or reconcilable effect, bounded blast
radius and cost, permitted classification, approved provider and strategy,
production prerequisites, policy owner/version/expiry, and active kill
switches.

Irreversible, destructive, public, financial, legal, credential-related,
security-sensitive, privacy-sensitive, or production-critical operations retain
explicit human approval unless a future accepted ADR establishes stronger
governance.

### Risk classification

Risk is explicit, versioned, policy-owned, and evaluated across state mutation,
reversibility, blast radius, financial and public impact, security and
credential impact, privacy, legal and licensing impact, production and data
classification impact, external-system effect, retry ambiguity, confidence in
outcome detection, and recovery complexity.

Conceptual classes are negligible, low, moderate, high, and critical. Numeric
scoring is deferred. Unknown or conflicting classification fails closed and
cannot be downgraded by a proposer, provider, strategy, worker, or capability.

### Reversibility model

- **Reversible:** a tested rollback restores prior state within defined limits.
- **Compensatable:** exact undo is impossible, but an approved compensating
  action restores an acceptable governed state.
- **Reconcilable:** external state can be inspected and corrected after an
  uncertain outcome.
- **Irreversible:** the effect cannot be reliably undone or compensated.
- **Unknown:** reversibility is not established and is treated as irreversible
  for approval.

Likely irreversible or high-impact operations include public publication,
financial purchase, credential disclosure, permanent deletion, legal
submission, production mutation, external notification, release signing, and
destructive infrastructure change. Classification remains operation-specific.

### Approval contract

An approval is an immutable, bounded authorization artifact. Conceptual
metadata includes:

- approval identity and contract version;
- approver identity and authority version;
- proposal or plan digest;
- exact operation identities and versions;
- environment and project or tenant;
- risk and reversibility classifications;
- data classification and permitted purpose;
- resource and cost budgets and maximum attempts;
- valid-from and expiration times;
- conditions, exclusions, and required evidence;
- correlation identity and revocation state;
- approval scope; and
- signature or integrity evidence when later required.

An approval contains no broad ambient permission, unrestricted capability
access, raw secret, arbitrary executable path, provider-native tool call,
indefinite validity, or implied permission for unrelated operations. It is inert
data until Runtime validates its contract, integrity, approver authority,
scope, policy compatibility, lifecycle, and current kill-switch state.

### Scope, expiry, revocation, and reuse

Approval binds to the narrowest practical combination of operation and version,
plan digest, workflow version, project, environment, deployment profile,
classification ceiling, provider or strategy trust class, budget, time window,
attempt count, and affected assets or resources.

Material changes to input, plan, operation version, provider, strategy,
environment, classification, risk, purpose, cost, or blast radius invalidate or
require re-evaluation of approval. Approval for one scope is never silently
reused for another.

Approvals have explicit validity periods and support revocation, suspension,
supersession, one-time use where appropriate, attempt and budget exhaustion,
environment, policy-version and operation-version invalidation, and
incident-response invalidation. Expired, revoked, suspended, superseded,
exhausted, or incompatible approvals fail closed. Runtime revalidates
immediately before execution, including queued and retried work.

Reuse is prohibited by default. An explicitly reusable approval still defines
its operation set and versions, environment, risk ceiling, budget, attempts,
validity, classification, purpose, revocation and evidence requirements. “Approve
all future actions” is invalid.

### Human approval

Human approval is required for destructive or irreversible work, production
mutation, public release, financial commitments, credential operations, legal
or licensing decisions, sensitive personal or regulated data, high-blast-radius
infrastructure, policy or security-control changes, and promotion to a higher
autonomy level.

The interface presents understandable structured evidence: action, purpose,
affected resources, risk, reversibility, expected outcome, cost, involved data,
evidence, alternatives, uncertainty, expiration, and rollback or reconciliation
plan. It does not require hidden chain-of-thought. Approval UI text is
presentation, not the authoritative artifact.

### Self-approval prevention

The following are prohibited:

- a model approving its recommendation or a provider approving its output;
- a strategy raising its autonomy level;
- a workflow approving its steps;
- a capability authorizing undeclared permission;
- a worker authorizing itself;
- a connector expanding data use;
- a Knowledge Package implying approval; and
- a confidence score, benchmark, or history granting authority.

Proposer and approver identities remain distinguishable and are independent for
high-risk work. Provider, model, and strategy maturity may constrain authority
but never create it.

### Policy-approved autonomy

Policy may authorize low-risk or bounded reversible work without per-action
human approval only when explicit, versioned, owned, reviewed, time- and
environment-bounded, capability- and operation-version-specific, risk-,
classification- and cost-bounded, revocable, auditable, testable, and protected
by kill switches. Policy cannot delegate unlimited authority or authorize its
own modification.

### Lifecycle, promotion, suspension, and rollback

Autonomy lifecycle semantics include experimental, shadow, advisory,
approval-required, limited-autonomous, active, suspended, deprecated, and
disabled. Shadow behavior cannot affect approval or execution.

Promotion requires conformance and security tests, deterministic fixtures,
failure/recovery evidence, shadow comparisons, approval accuracy, incident
history, rollback success, budget adherence, latency and reliability, human
review, and data-governance review as applicable. Model quality or confidence
alone is insufficient. Suspension and rollback are immediate and do not require
contract changes.

### Kill switches

VSS requires global, environment, capability, operation, provider, strategy,
project or tenant, approval-system, budget, and production disable switches,
plus an emergency human-approval requirement.

Kill switches are evaluated before proposal use, approval, queue admission,
every execution attempt, retry, and external side effect. Active switches
override all prior approvals. Unavailable or unknown switch state fails closed.

### Budgets and cost

Autonomy is bounded by monetary cost, provider usage, CPU, memory, GPU, storage,
network, elapsed time, executions, retries, concurrency, assets, and external
side effects. Budget approval is explicit. An operation cannot increase its own
budget; retry and fallback consume the original budget unless newly approved.
Unknown cost fails closed when cost governance is required.

### Development and production

Development policy may use deterministic substitutes, reduced-quality media,
local-only changes, temporary resources, low-risk reversible work, and explicit
shorter approval paths. It never weakens authorization, audit meaning, approval
validation, budget enforcement, classification, secret handling, kill switches,
failure handling, idempotency, or reconciliation.

Production autonomy requires process or worker isolation, durable execution
state, durable tamper-resistant audit, incident response, credential governance,
revocation, enforceable cancellation, idempotency or reconciliation,
observability, and recovery evidence. Local JSON Lines audit, cooperative thread
cancellation, deterministic fixtures, and trusted in-process Python do not
satisfy these production prerequisites.

### Local-first testability

The complete authority path is testable on one workstation with deterministic
policy and approver fixtures. Tests cover advisory and proposal flows,
read-only execution, human-approved reversible and policy-approved bounded
execution, denial, expiry, revocation, kill switches, budget exhaustion, stale
approval, plan digest and operation-version mismatch, changed input/provider/
strategy, retry after expiry, duplicate delivery, reconciliation, self-approval,
approver-authority failure, audit failure, and cancellation.

Standard CI requires no identity provider, paid service, AI API, or cloud
account. Fixtures prove contract and governance behavior, not production
identity or isolation.

### Approval evidence and audit

Audit records safe proposal identity/digest, proposer class, policy identity and
version, risk and reversibility, approver identity or authority class, approval
identity/scope/result, safe denial category, validity and expiry, revocation,
operation identity/version, execution and attempt identities, budget,
kill-switch state, execution and reconciliation outcomes, duration, and
correlation identity.

Audit excludes raw secrets, credentials, hidden reasoning, unrestricted
Knowledge Package content, provider-native responses, unnecessary personal
data, and sensitive raw UI content by default. Audit failure cannot be treated
as success. Local JSON Lines remains development-only.

### Approval-system availability

When approval infrastructure is unavailable, actions needing approval fail
closed. Existing approvals may be used only while current, unrevoked,
independently verifiable, in scope, and compatible with current policy and kill
switches. A provider or worker cannot substitute for an approver.

Critical emergency disable and teardown retain deterministic, separately
governed paths independent of reasoning and the normal approval service.

### Emergency operations

Emergency authority may disable autonomy, revoke approvals, cancel queued work,
stop workers, prevent provider calls, tear down temporary infrastructure, or
isolate a compromised project. It is narrow, independently protected,
auditable, incapable of broad normal execution, and usable without AI. Final
break-glass identity technology is deferred.

### Retries and distributed execution

Under ADR-0014, before every attempt Runtime revalidates approval, policy,
operation version, environment, risk, budget, kill switches, revocation,
deadline, and attempt limit. Execution identity is distinct from attempt
identity. At-least-once delivery cannot consume authority beyond approval
scope. Unknown and partial outcomes require reconciliation. A retry cannot
silently enlarge or change an approved effect.

### Security threat assessment

| Threat | Boundary and mitigation | Deferred control |
| --- | --- | --- |
| Self-approval | Proposer/approver boundary; distinct identities, independent approval for high risk | Production identity model |
| Approval spoofing or approver impersonation | Approval/Runtime boundary; integrity, authority version, scope and current identity validation | Signing and identity provider |
| Stale approval, replay, retry after expiry | Lifecycle boundary; expiry, one-time/attempt limits, revocation and pre-attempt validation | Durable approval store |
| Scope expansion or cross-project use | Project/operation boundary; exact scoped fields and fail-closed matching | Final matching language |
| Plan, operation, environment, provider or strategy substitution | Proposal/execution boundary; bound digests, versions and identities | Final digest algorithm |
| Classification or risk downgrade | Governance boundary; policy-owned classifications and independent validation | Final taxonomy/scoring |
| Budget inflation or autonomy escalation | Policy/Runtime boundary; immutable ceilings and explicit promotion | Production policy engine |
| Kill-switch bypass or queue after revocation | Admission/execution boundary; checks before admission, attempt, retry and effect | Distributed propagation mechanism |
| Worker execution without authority | Runtime/worker boundary; bounded execution authority and current validation | Worker isolation and protocol |
| Duplicate or partial effects | Delivery/external boundary; idempotency, attempt identity, reconciliation and non-retryability | Operation-specific contracts |
| Approval outage | Availability boundary; fail closed and independently verifiable existing approvals only | Availability design |
| Audit failure | Execution/evidence boundary; failure cannot become success | Durable audit backend |
| Credential theft | Identity/worker boundary; scoped credentials and no secrets in artifacts | Credential system |
| Confused deputy | Caller/Runtime boundary; bind caller, purpose, project, resource and operation | Production identity claims |
| Malicious or social-engineering proposal content | Data/approval boundary; structured inert evidence, validation and no embedded authority | Approval UX safeguards |

Dynamic third-party approval adapters, policy modules, risk classifiers,
autonomy controllers, and identity integrations remain unsupported. Future
support requires signing, provenance, trust roots, isolation, revocation,
upgrade policy, compatibility, and incident-response architecture.

### Provider and product neutrality

This decision selects no identity provider, approval product, policy engine,
workflow product, notification system, AI provider, database, queue, signing
service, or cloud platform. Approval and autonomy contracts remain open and
provider neutral. Human approval remains possible without a specific SaaS
product.

## Alternatives Considered

### 1. Reasoning model self-approval

Rejected because proposal quality cannot establish authority or separation of
duties.

### 2. Confidence-threshold autonomy

Rejected because confidence is neither calibrated authority nor a complete risk
assessment.

### 3. Workflow-owned approval

Rejected because orchestration cannot expand its own permissions.

### 4. Provider-native tool approval

Rejected because it couples governance to one provider and allows a producer to
shape authorization.

### 5. Human approval for every operation

Rejected as disproportionate for low-risk read-only and tightly bounded local
work; excessive friction encourages unsafe bypasses.

### 6. Separate proposer, policy, approver, Runtime executor, and auditor

Selected. Bounded levels and risk-based approval balance safety, local-first
development, efficiency, human control, provider neutrality, future autonomy,
scale, and auditability.

## Consequences

Positive consequences include explicit authority, prevention of self-approval,
bounded autonomy, human control over high-impact work, safe policy-approved
low-risk execution, immediate suspension, provider neutrality, local testing,
production governance, approval lineage, and safer retries.

Costs and risks include approval friction, policy complexity, identity
integration, expiry handling, operational overhead, false denials, delayed
execution, revocation propagation, evidence storage, classification maintenance,
and over-governance.

Mitigations are risk-based approval, narrow reusable approvals, deterministic
fixtures, explicit low-risk policy autonomy, one operation class at a time,
measurable promotion criteria, periodic review, and simplicity over cleverness.

## Roadmap Impact

1. ADR-0016 Autonomy, Approval, and Execution Authority.
2. M3.1 Semantic Contract Registry and first schemas.
3. M3.2 Deterministic `GenerateOptions` implementation.
4. M3.3 Local concurrency and performance baseline.
5. M3.4 Knowledge Contract Registry and bounded Knowledge Packages.
6. M3.5 Plan IR and validation.
7. M3.6 Approval contract and local deterministic approver.
8. M3.7 First external reasoning provider.
9. Later: production identity, durable approval storage, multi-party approval,
   production audit, worker isolation, and bounded autonomous movie workflows.

This ADR implements none of these items.

## Unresolved Questions

- first risk taxonomy and scoring method;
- approver identity model and human approval interface;
- approval schema and signing method;
- reusable and multi-party approval rules;
- emergency authority and break-glass access;
- production policy engine and language;
- production approval store and notifications;
- approval timeout and escalation;
- revocation propagation;
- plan digest algorithm and scope-matching rules;
- operation-change invalidation;
- cost estimation and unknown-cost handling;
- production identity provider;
- offline and disconnected-laptop approval;
- personal, regulated, legal, release, and publication approvals;
- movie-specific approval gates;
- acceptable approval latency;
- autonomy promotion ownership;
- incident-triggered suspension; and
- audit retention.

## Acceptance Criteria

This ADR is acceptable when:

- Runtime remains the sole executor;
- proposer, approver, executor, and auditor are distinct;
- reasoning cannot self-approve and confidence never grants authority;
- autonomy levels, risk, and reversibility are explicit;
- unknown reversibility is treated as irreversible;
- approvals are immutable, scoped, expiring, revocable, and bounded;
- stale or mismatched approvals fail closed and cannot cross material scope;
- kill switches override approval and retries revalidate authority;
- high-impact actions retain human approval;
- development does not weaken governance;
- complete flows are locally testable without external services;
- no identity, policy, approval, queue, database, cloud, or provider product is
  selected;
- production prerequisites are explicit; and
- no implementation or dependency accompanies this decision.

## Independent Review Perspectives

| Perspective | Conclusion |
| --- | --- |
| Enterprise Software Architecture | Roles and contracts separate governance from replaceable integrations. |
| Runtime Authority | Runtime alone converts validated authority into execution. |
| Product Security | Scope, expiry, revocation, revalidation, kill switches, and separation fail closed. |
| Risk Management | Multidimensional risk and explicit reversibility prevent confidence-only autonomy. |
| Human Factors and Approval UX | Structured evidence supports informed approval without chain-of-thought exposure. |
| AI Governance | Reasoning remains proposer-only and cannot promote itself. |
| Distributed Systems | Attempt-level revalidation and reconciliation address at-least-once delivery. |
| Reliability and Recovery | Emergency controls, cancellation, suspension, and reconciliation preserve recovery. |
| FinOps | Cost and resource ceilings bind approval, retry, and fallback. |
| Privacy and Legal Governance | Classification, purpose, legal and regulated-data impacts drive human approval. |
| Local-First Developer Experience | Deterministic fixtures exercise the full authority path without SaaS or cloud. |
| Media Production Governance | Draft/review work may be bounded; release and high-impact actions remain human-approved. |
| Provider Neutrality | No identity, approval, policy, provider, queue, database, signing, or cloud product is selected. |
| Independent Verification | No contradiction with ADR-0010 through ADR-0015 was identified; implementation choices remain deferred. |

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [ADR-0012: Evolvable and Reversible Reasoning Architecture](ADR-0012-evolvable-reasoning-architecture.md)
- [ADR-0013: Semantic Reasoning Contracts](ADR-0013-semantic-reasoning-contracts.md)
- [ADR-0014: Local-First Scalability, Performance, and Resource Efficiency](ADR-0014-local-first-scalability-performance-efficiency.md)
- [ADR-0015: Knowledge Architecture and Bounded Knowledge Packages](ADR-0015-knowledge-architecture.md)
- [M2 Architecture Checkpoint](../reviews/m2-architecture-checkpoint.md)
- [Threat Model](../security/threat-model.md)
- [Secure Development](../security/secure-development.md)
- [Security Exceptions](../security/security-exceptions.md)

## Verification

Acceptance requires ADR validation, repository-relative reference validation,
documentation-only scope verification, whitespace validation, and existing
Markdown validation when available. This decision adds no runtime code, test,
schema, workflow, approval or identity service, agent, AI integration, provider,
queue, database, dependency, or infrastructure.
