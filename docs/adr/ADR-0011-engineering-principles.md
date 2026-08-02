# ADR-0011: Engineering Principles

## Status

Accepted

## Date

2026-08-01

## Context

VSS has completed its second architecture milestone. The platform now has a
Runtime Kernel, sequential Workflow Engine, Capability SDK, provider
abstraction, a migrated legacy command, security review, supply-chain
governance, and infrastructure expressed as code. These components establish
useful boundaries, but those boundaries will remain coherent only if future
work follows a common set of engineering principles.

Feature pressure, operational urgency, and new technology can otherwise create
parallel execution paths, implicit authority, vendor coupling, unversioned
contracts, or controls applied only after implementation. Such divergence
would reduce the value of the M2 architecture and increase the cost of every
later change.

This ADR is the engineering constitution for VSS. Future ADRs MUST reference
it and explain any deliberate exception. Future code reviews MUST evaluate
compliance with it. An exception requires documented rationale, bounded scope,
risk ownership, and a removal or review condition; convenience alone is not
sufficient.

## Decision

VSS will apply the following principles to architecture, implementation,
operations, security, and review. The terms MUST, MUST NOT, SHOULD, SHOULD NOT,
and MAY express descending levels of obligation. A deviation from a MUST or
MUST NOT requires an ADR that identifies the affected principle and records
the compensating controls.

## 1. Executive Summary

VSS exists to provide a dependable, extensible platform for executing domain
operations through explicit contracts and controlled infrastructure effects.
It separates business capabilities from execution authority, orchestration,
and provider implementations so that each can evolve without silently
changing the trust model of the others.

Long-term architectural consistency is more valuable than rapid feature
delivery because every shortcut in an execution platform becomes a precedent
and a potential bypass. Consistent boundaries allow features to be tested,
replaced, audited, and operated predictably. Delivery speed remains important,
but it is achieved through small vertical slices and reusable contracts, not by
creating alternate paths around validation, authorization, or audit.

## 2. Guiding Principles

### Runtime First

- **Purpose:** Keep one authoritative path for controlled execution.
- **Rationale:** Centralized execution controls prevent capabilities, commands,
  workflows, and providers from applying inconsistent policy.
- **Examples:** A migrated CLI command invokes the Runtime Controller; each
  workflow step is a normal runtime invocation.
- **Trade-offs:** Runtime changes require careful compatibility review and may
  add modest overhead to otherwise simple operations.

### Capability First

- **Purpose:** Package domain behavior as small, versioned units.
- **Rationale:** Capabilities provide a consistent authoring, validation, and
  testing boundary without expanding the kernel.
- **Examples:** New domain behavior is expressed through a manifest and the
  Capability SDK rather than a new privileged CLI execution path.
- **Trade-offs:** Authors must maintain manifests and explicit input and output
  contracts.

### Provider Neutral

- **Purpose:** Separate capability intent from infrastructure implementation.
- **Rationale:** Stable provider contracts make implementations replaceable and
  keep infrastructure decisions out of business logic.
- **Examples:** A capability requests an authorized clock contract rather than
  constructing a clock implementation.
- **Trade-offs:** Neutral contracts expose only common, intentional semantics
  and may not surface every implementation-specific feature.

### Vendor Neutral

- **Purpose:** Prevent any vendor from becoming part of the kernel contract.
- **Rationale:** Vendor choice must remain an operational and policy decision,
  not an architectural dependency.
- **Examples:** Provider interfaces use VSS-owned types and named failures;
  vendor SDK objects do not cross runtime boundaries.
- **Trade-offs:** Adapters may be required, and vendor-specific optimizations
  need explicit optional extensions.

### Local First Development

- **Purpose:** Make core development and verification possible on a controlled
  local workstation.
- **Rationale:** Local reproducibility shortens feedback loops and reduces
  dependence on remote services and credentials.
- **Examples:** Built-in discovery uses repository-controlled paths; deterministic
  fakes replace remote services in tests.
- **Trade-offs:** Local implementations do not claim production-scale
  durability or distribution.

### Infrastructure as Code

- **Purpose:** Make infrastructure changes reviewable, repeatable, and
  recoverable.
- **Rationale:** Declarative, version-controlled infrastructure reduces manual
  drift and supports validation before deployment.
- **Examples:** Environments and automation are defined through reviewed
  OpenTofu and Ansible sources.
- **Trade-offs:** Provider state and tool versions require disciplined lifecycle
  management.

### Security by Construction

- **Purpose:** Embed security properties in interfaces and execution paths.
- **Rationale:** Controls added after implementation are easier to omit or
  bypass.
- **Examples:** Manifests reject unknown fields; capability context omits ambient
  secrets and unrestricted host objects.
- **Trade-offs:** Secure contracts require more design work before feature code
  begins.

### Fail Closed

- **Purpose:** Deny or fail when trust, validation, authorization, or required
  audit evidence is unavailable.
- **Rationale:** Ambiguous security state must not be interpreted as permission
  or success.
- **Examples:** An unsupported API version or failed audit write fails the
  operation.
- **Trade-offs:** Availability may be reduced during control-plane failures.

### Least Privilege

- **Purpose:** Grant only the authority required for one operation.
- **Rationale:** Narrow authority reduces both accidental damage and exploit
  impact.
- **Examples:** Provider access is scoped to an exact provider identity;
  executable probes use fixed arguments and approved paths.
- **Trade-offs:** New legitimate effects require explicit policy and security
  review.

### Immutable Runtime

- **Purpose:** Keep runtime registrations, policy views, and execution context
  stable during execution.
- **Rationale:** Mutation creates time-of-check/time-of-use ambiguity and makes
  behavior difficult to reproduce or audit.
- **Examples:** Registries and provider handles are frozen after construction;
  execution context is immutable.
- **Trade-offs:** Configuration changes require constructing a new runtime
  instance rather than modifying a live one.

### Explicit Authorization

- **Purpose:** Separate requested permissions from granted permissions.
- **Rationale:** A declaration describes need; it does not establish trust.
- **Examples:** Runtime policy independently approves every declared permission
  and provider requirement before a handler receives access.
- **Trade-offs:** Policy configuration and denial diagnostics require ongoing
  maintenance.

### Explicit Contracts

- **Purpose:** Make every boundary machine-checkable and reviewable.
- **Rationale:** Implicit conventions drift and fail unpredictably.
- **Examples:** JSON Schemas define manifests, commands, and workflows; provider
  protocols define safe operations and errors.
- **Trade-offs:** Contract evolution carries a compatibility burden.

### Version Everything

- **Purpose:** Make compatibility decisions deliberate.
- **Rationale:** Independently versioned contracts distinguish compatible
  evolution from accidental breakage.
- **Examples:** Manifest schema, Runtime API, SDK API, Provider API, workflow
  schema, capability, provider, and workflow versions are enforced separately.
- **Trade-offs:** Version matrices and migration policy add maintenance work.

### Deterministic Testing

- **Purpose:** Produce repeatable evidence independent of host or clock state.
- **Rationale:** Nondeterministic tests conceal regressions and erode confidence.
- **Examples:** Fakes control providers and host inspection; fixed fixtures cover
  success and failure classifications.
- **Trade-offs:** Test seams must be designed without leaking test-only behavior
  into production contracts.

### Deterministic CI

- **Purpose:** Ensure the same source and locked inputs produce the same
  validation outcome.
- **Rationale:** A green build must be meaningful and reproducible.
- **Examples:** Actions and artifacts use immutable identities; dependencies and
  tool versions are locked.
- **Trade-offs:** Pin maintenance and controlled upgrades require scheduled
  effort.

### Open Standards

- **Purpose:** Prefer portable formats and protocols with multiple viable
  implementations.
- **Rationale:** Open standards improve interoperability, inspection, and
  replacement options.
- **Examples:** YAML authoring, JSON Schema validation, JSON Lines audit records,
  and standard infrastructure formats.
- **Trade-offs:** A standard may evolve more slowly than a proprietary feature
  set.

### OSS First with Enterprise Governance

- **Purpose:** Prefer suitable open-source components while managing legal,
  security, provenance, and maintenance risk.
- **Rationale:** Source availability is valuable but does not itself establish
  fitness or trust.
- **Examples:** Admission requires approved licensing, vulnerability review,
  immutable resolution, SBOM coverage, and provenance evidence.
- **Trade-offs:** Some components will be rejected or upgrades delayed until
  governance evidence is complete.

### Human Approval for Destructive Operations

- **Purpose:** Keep irreversible or high-impact decisions under accountable
  human control.
- **Rationale:** Automation can validate and propose actions but cannot infer
  authorization for destructive effects.
- **Examples:** Deletion, destructive infrastructure changes, credential
  rotation, and production mutation require an explicit approval gate.
- **Trade-offs:** Approval increases lead time and requires clear operational
  ownership.

### Observable Systems

- **Purpose:** Make state transitions, health, and failures understandable.
- **Rationale:** Operations cannot safely manage behavior they cannot observe.
- **Examples:** Correlation IDs connect CLI, workflow, capability, provider, and
  audit records; failures use named classifications.
- **Trade-offs:** Telemetry must be bounded and governed to avoid cost and data
  exposure.

### Audit Everything

- **Purpose:** Record every security-relevant execution and decision.
- **Rationale:** Accountability and incident analysis require durable evidence
  of what was requested, authorized, and completed.
- **Examples:** Runtime and workflow lifecycle events record identities,
  authorization outcomes, status, and correlation without raw input or output.
- **Trade-offs:** Audit storage, integrity, retention, and availability become
  operational responsibilities.

### Small Composable Components

- **Purpose:** Keep responsibilities narrow and independently testable.
- **Rationale:** Composition reduces coupling and limits trusted code size.
- **Examples:** Workflow orchestration, provider selection, host inspection,
  policy, and result normalization remain separate components.
- **Trade-offs:** Composition introduces interfaces and requires disciplined
  dependency direction.

### Simplicity over Cleverness

- **Purpose:** Prefer direct, inspectable designs over hidden automation.
- **Rationale:** Security and compatibility depend on behavior that reviewers
  can understand and verify.
- **Examples:** Explicit registries are preferred to dynamic import discovery;
  fixed adapters are preferred to reflective dispatch.
- **Trade-offs:** Some repetitive wiring is accepted until evidence justifies a
  reusable abstraction.

## 3. Runtime Principles

The Runtime Controller is the single execution authority for capabilities. The
runtime owns execution coordination, validation, authorization, policy
evaluation, audit, provider selection, result normalization, and mapping to
named outcomes. It constructs the minimum execution context required for one
authorized invocation.

No CLI adapter, workflow, capability, provider, compatibility layer, or future
interface may bypass the runtime for a capability execution. Registration,
manifest declaration, discovery, caller identity, workflow inclusion, and
provider availability never imply authorization. Runtime presentation concerns
remain outside the controller, and domain behavior remains outside the kernel.

## 4. Capability Principles

Capabilities contain bounded business logic behind versioned manifests and
input/output contracts. They receive only runtime-authorized context and return
SDK-defined safe results or errors.

Capabilities MUST NOT:

- own or reinterpret runtime policy;
- select, enumerate, or instantiate provider implementations;
- access secrets directly or discover ambient credentials;
- launch arbitrary subprocesses or accept executable command strings;
- perform unrestricted filesystem access;
- construct the external VSS response envelope;
- mutate runtime registries or execution context; or
- bypass normalization, authorization, or audit.

Trusted built-in Python capability code executes in process and is not
sandboxed. SDK contracts and policy reduce accidental authority; they do not
make malicious built-in code safe. Admission and review therefore remain part
of the trust boundary.

## 5. Provider Principles

Providers expose bounded infrastructure or service effects through versioned,
provider-neutral contracts. They MUST NOT contain business workflow or domain
decision logic. Implementations are replaceable and selected statically by the
runtime according to policy; capabilities cannot select implementation paths.

Runtime policy owns provider authorization and exposes only the exact approved
contract handle. Credentials, implementation configuration, and vendor-native
objects remain inside the provider boundary and MUST NOT enter capability
inputs, outputs, audit records, or errors. Built-in in-process providers are
trusted code, not isolation boundaries.

## 6. Workflow Principles

Workflows declaratively orchestrate capability operations. They define order,
bounded inputs, timeouts, and failure semantics; they do not implement business
logic, policy, provider selection, Python dispatch, shell execution, or secret
resolution.

Every capability step is executed through the Runtime Controller with its own
validation, authorization, normalization, and audit. Workflow authorization
cannot increase step authority. Workflow formats use schemas and explicit
operation allowlists and cannot select arbitrary modules, executables,
environment variables, implementation paths, or unrestricted arguments.

## 7. Security Principles

VSS applies zero-trust reasoning to every boundary: identity and data are
validated at use, authority is explicit and minimal, and trust is never
inherited merely because a request originates inside another component.

Security requirements are:

- deny by default for operations, permissions, providers, paths, and inputs;
- explicit, independently authorized permissions with narrow scopes;
- secure defaults that require an intentional review to expand authority;
- fail-closed handling of validation, authorization, provider initialization,
  execution-control, and required-audit failures;
- safe normalization of outputs, errors, metadata, and diagnostic text;
- bounded input and output size, depth, type, duration, and cardinality;
- minimum authority in every context, handle, filesystem scope, executable
  probe, and network destination;
- secret isolation from capability input, environment access, output, logs,
  audit, state, and raw exceptions;
- canonical-path, integrity, ownership, permission, and version validation at
  trust boundaries; and
- explicit documentation of trusted-code assumptions and the absence of a
  Python process sandbox.

Threat models MUST distinguish policy enforcement from process isolation and
trusted-but-defective code from unsupported malicious third-party code.

## 8. OSS Governance

External components require documented admission under the repository's
component and supply-chain policies. Only licenses on the approved policy list
may be used without an explicit, current security exception. Every shipped
dependency MUST be represented by its immutable resolved identity and covered
by dependency review, license review, vulnerability scanning, SBOM generation,
and available provenance controls.

Dependencies are added only when their value exceeds their security,
maintenance, legal, and reproducibility cost. Standard-library or existing
components are preferred when they satisfy the contract. Upgrades are regular,
reviewed changes: update locks and integrity evidence, review release and
security impact, regenerate the SBOM and provenance, run compatibility and
security suites, and preserve a rollback path. Continuous review includes
automated scanning plus time-bound human ownership of findings and exceptions.

## 9. AI Principles

AI is a Provider. AI is not the Runtime, policy, authorization, or the source
of truth. An AI implementation cannot receive implicit authority, decide its
own permissions, bypass deterministic controls, or replace authoritative
repository, configuration, state, and policy records.

Any future reasoning operation MUST be:

- **audited:** identity, authorization, bounded request metadata, outcome, and
  correlation are recorded without exposing protected content;
- **bounded:** input, output, time, cost, tools, data access, and side effects
  have explicit limits;
- **authorized:** runtime policy approves both the capability operation and the
  exact provider access before invocation;
- **replaceable:** capability contracts do not depend on implementation-native
  types or behavior; and
- **vendor neutral:** selection occurs behind a VSS-owned, versioned provider
  interface with portable failures and semantics.

AI output is untrusted data until validated. It cannot directly authorize or
perform a destructive operation. Any proposed effect follows the same runtime
policy, human approval, validation, normalization, and audit requirements as a
non-AI request.

## 10. Documentation Principles

Architecture precedes implementation. A change begins with documented
boundaries, contracts, trust assumptions, failure behavior, compatibility, and
operational ownership at a depth proportionate to its risk.

An ADR is required before an incompatible public or internal platform-contract
change. Every future ADR MUST reference ADR-0011 and describe how its decision
conforms or which principle it deliberately supersedes. A threat-model update
precedes implementation of a sensitive feature, new authority, secret path,
external provider, destructive effect, or trust-boundary change.

Documentation is reviewed with code, uses stable terminology, and distinguishes
an interface from its initial implementation and a current guarantee from
deferred intent.

## 11. Testing Principles

Every feature requires evidence at the appropriate boundaries:

- unit tests for isolated behavior and contract edge cases;
- negative tests for malformed, unsupported, missing, and denied inputs;
- security tests for bypass, substitution, traversal, injection, leakage,
  excessive resource use, and fail-closed behavior;
- compatibility tests for existing commands, schemas, envelopes, exit codes,
  correlation, and migration paths; and
- acceptance tests that invoke the same production path used by callers.

Tests use deterministic fixtures for time, host state, providers, failures, and
external effects. They MUST NOT weaken production validation or depend on
mutable network state where a controlled fixture can establish the same
contract. A regression correction includes a test that fails without it.

## 12. Review Process

Every material change receives independent review appropriate to its impact.
One reviewer may cover multiple perspectives when qualified, but authorship
alone is not approval for security-sensitive or architectural findings.

- **Architecture:** validates boundaries, dependency direction, contracts,
  versioning, simplicity, and conformity with this ADR.
- **Security:** validates threat-model changes, authorization, least privilege,
  safe failure, isolation assumptions, and adversarial evidence.
- **Supply Chain:** validates component admission, licenses, locks, integrity,
  SBOM, provenance, vulnerabilities, and exceptions.
- **Compatibility:** validates public behavior, migration, version support,
  named failures, and existing callers.
- **Operations:** validates observability, audit, failure recovery, resource
  limits, deployment, rollback, and ongoing ownership.

Pull requests MUST state which perspectives apply, provide validation evidence,
and identify unresolved risks. Destructive operations and exceptions require
the accountable human approval defined by policy. Critical and High findings
block release. Medium findings block when they undermine an explicit contract
or lack a documented mitigation and owner.

## 13. Deferred Principles

Dynamic plugins, distributed runtime coordination, multi-agent orchestration,
remote execution, and self-modifying systems remain intentionally deferred.
They are not implied extension points and MUST NOT be introduced incrementally
through configuration, workflow syntax, package discovery, or hidden execution
paths.

Each requires a dedicated ADR, threat model, isolation and identity design,
authorization model, supply-chain and revocation plan, resource controls,
failure semantics, operational ownership, and deterministic acceptance
evidence before implementation begins.

## 14. Success Criteria

Engineering quality is measured against the following goals:

- zero known paths that confer authority through implicit trust;
- every capability execution passes runtime validation, authorization,
  normalization, and required audit exactly once;
- all public contracts and independently evolving platform contracts are
  explicitly versioned;
- compatible behavior is retained until an approved migration and deprecation
  plan is complete;
- provider contracts contain no implementation-specific types and every
  provider implementation is replaceable behind the same approved contract;
- shipped external dependencies are minimal, approved, locked, scanned, and
  represented in SBOM and provenance evidence;
- CI is reproducible and deterministic for identical source and locked inputs,
  with a target of 100 percent deterministic required checks;
- security-relevant executions and decisions are correlated and auditable
  without raw inputs, outputs, secrets, environment values, or exceptions;
- bounded inputs, outputs, timeouts, and resource limits exist at every exposed
  execution boundary;
- destructive effects require explicit, attributable human approval; and
- every accepted risk has an owner, impact statement, review condition, and
  time-bounded exception where applicable.

These criteria are release gates or tracked engineering objectives, not claims
that local first implementations already provide distributed durability,
tamper-proof audit, or process isolation.

## 15. References

- [ADR-0001: Establish Bash Command Execution Framework](ADR-0001-bash-command-execution-framework.md)
- [ADR-0002: Standardize Logging and Error Reporting](ADR-0002-standardize-logging-and-error-reporting.md)
- [ADR-0003: Configuration Management Strategy](ADR-0003-configuration-management-strategy.md)
- [ADR-0004: CI/CD Pipeline Architecture](ADR-0004-cicd-pipeline-architecture.md)
- [ADR-0005: Ansible Automation Standards](ADR-0005-ansible-automation-standards.md)
- [ADR-0006: Deployment and Rollback Strategy](ADR-0006-deployment-and-rollback-strategy.md)
- [ADR-0007: Secrets Management Architecture](ADR-0007-secrets-management-architecture.md)
- [ADR-0008: Monitoring and Observability Strategy](ADR-0008-monitoring-and-observability-strategy.md)
- [ADR-0009: Infrastructure as Code Standards](ADR-0009-infrastructure-as-code-standards.md)
- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [VSS security threat model](../security/threat-model.md)
- [M2 architecture checkpoint](../reviews/m2-architecture-checkpoint.md)

## Consequences

### Positive

- Future decisions share a stable vocabulary and review baseline.
- Runtime authority, provider neutrality, and capability boundaries remain
  consistent as the platform grows.
- Security, compatibility, and supply-chain requirements are applied before
  implementation rather than added selectively afterward.
- Explicit exceptions make architectural risk visible and time-bound.

### Costs and risks

- Up-front architecture, threat modeling, and cross-functional review increase
  the lead time of sensitive or incompatible changes.
- Versioned contracts and compatibility commitments require sustained
  maintenance.
- Principles can become ceremonial if pull requests do not include concrete
  compliance evidence.
- Overly literal application could create unnecessary abstraction for small
  changes.

### Mitigations

- Apply review depth in proportion to authority, compatibility impact, and
  operational risk.
- Prefer small vertical slices and the simplest design satisfying current
  contracts.
- Record exceptions explicitly rather than weakening principles globally.
- Revisit this ADR through a superseding ADR when evidence shows a principle is
  no longer effective.

## Verification

Compliance is verified through ADR validation, architecture and threat-model
review, deterministic unit and acceptance tests, compatibility and adversarial
tests, dependency and license policy checks, SBOM and provenance generation,
artifact inspection, secret scanning, and required CI gates.

Future ADRs verify that they reference ADR-0011. Future code reviews verify the
applicable principle, the evidence supporting compliance, and any approved
exception. Documentation checks confirm that this ADR retains the repository's
required title, Status, Context, Decision, Consequences, and Verification
sections.
