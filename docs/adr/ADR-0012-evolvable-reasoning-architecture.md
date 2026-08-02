# ADR-0012: Evolvable and Reversible Reasoning Architecture

## Status

Accepted

## Date

2026-08-01

## Context

VSS has an accepted capability-oriented Runtime Kernel, sequential Workflow
Engine, Capability SDK, provider abstraction, and an initial legacy-command
migration. The M2 architecture establishes the Runtime Controller as the
authority for validation, authorization, execution, normalization, and audit.
It also records two constraints relevant to future reasoning: cooperative
thread cancellation cannot stop effectful in-process work, and the local JSON
Lines audit implementation does not provide production retention, durability,
or tamper resistance.

VSS may later add reasoning and bounded autonomous behavior. The architecture
must assume that models, provider APIs, provider capabilities, prompt
techniques, planning and evaluation methods, confidence representations,
retrieval methods, storage systems, and autonomy policies will change. Some
early decisions will prove incorrect. Therefore, intelligence must be an
evolutionary subsystem outside the stable execution kernel rather than a new
source of platform authority.

The objective is not to make mistakes impossible. It is to make mistakes
detectable, contained, reversible, migratable, auditable, testable, inexpensive
to replace, and unable to bypass Runtime authority. This ADR defines
responsibilities, trust boundaries, lifecycle rules, and conceptual contracts.
It does not define final schemas or implement any M3 component.

## Decision

VSS will use an evolvable, reversible, provider-neutral reasoning architecture.
The permanent architectural rule is:

> Reasoning proposes. Runtime validates, authorizes, approves, and executes.

Reasoning output is inert structured data. No reasoning provider, strategy,
planner, model, prompt, agent, or knowledge source may directly execute a
capability, mutate the platform, or grant authority.

Consistent with ADR-0011, AI is one possible Reasoning Provider implementation.
It is not the Runtime, policy, authorization, approval, or source of truth.

The architecture consists of:

1. a stable governance and execution layer;
2. a sole controlled Reasoning Gateway;
3. independently versioned reasoning envelopes and task contracts;
4. replaceable reasoning strategies;
5. replaceable provider adapters;
6. provider-neutral intermediate representations;
7. bounded, authorized Knowledge Packages;
8. Runtime-owned validation, authorization, budgets, audit, approval,
   cancellation, and execution; and
9. explicit lifecycle, shadow, promotion, rollback, feature-flag, and
   kill-switch controls.

## Relationship to ADR-0011

ADR-0012 is governed by
[ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md). It
applies those principles as follows:

| ADR-0011 principle | Application in this decision |
| --- | --- |
| Runtime First | Runtime remains the only execution and authorization authority; reasoning returns inert data. |
| Capability First | Capabilities request semantic, versioned tasks and never embed prompts or provider APIs. |
| Provider Neutral | Providers implement narrow reasoning contracts and cannot expose native objects across the adapter. |
| Vendor Neutral | Public contracts contain portable VSS concepts, not model names, credentials, or proprietary request structures. |
| Local First Development | The first implementation sequence begins with deterministic local fakes and preserves non-reasoning recovery. |
| Security by Construction | Validation, policy, data minimization, budgets, approval, and audit are architectural boundaries rather than provider options. |
| Fail Closed | Unsupported requirements, versions, tasks, disabled components, failed validation, and unavailable controls deny or fail safely. |
| Least Privilege | Providers receive bounded Knowledge Packages and exact task authority, never ambient source, credential, or execution access. |
| Immutable Runtime | Registries, lifecycle selections, budgets, and policy decisions are fixed for an invocation and evidenced. |
| Explicit Authorization | Task, strategy, provider, knowledge, budget, autonomy, approval, and operation decisions are independently authorized. |
| Explicit Contracts | Envelopes, task payloads, Knowledge Packages, Plan IR, provider/strategy APIs, translators, compilers, evidence, and audit are defined contracts. |
| Version Everything | Each independently evolving contract has its own version, compatibility window, owner, and retirement plan. |
| Deterministic Testing | Deterministic fakes, governed corpora, conformance suites, simulation, and replay validate behavior without external mutable state. |
| Deterministic CI | Contract fixtures, versions, evaluation corpora, and tool inputs are immutable and reproducible. |
| Open Standards | JSON-compatible values, JSON Schema, stable identifiers, and cryptographic digests form portable boundaries. |
| Human Approval for Destructive Operations | High-impact actions retain explicit human approval regardless of provider confidence or autonomy history. |
| Observable Systems | Correlation, lifecycle state, named outcomes, versions, budgets, and evidence make reasoning decisions inspectable. |
| Audit Everything | Security-relevant decisions and lifecycle transitions are audited without sensitive raw reasoning content. |
| Small Composable Components | Gateway, strategy, provider, knowledge, translator, validator, compiler, approval, and execution responsibilities remain separate. |
| Simplicity over Cleverness | Initial work is one narrow task with a deterministic fake; no speculative framework or dynamic discovery is authorized. |

This decision introduces no deliberate deviation from ADR-0011. A future
deviation requires its own ADR and the exception process defined by ADR-0011.

## Stable and replaceable layers

### Stable governance layer

The stable layer defines controls that must remain independent of any reasoning
technique or provider. It may contain:

- the Reasoning Gateway;
- request-envelope and task-contract validation;
- a task-contract registry and explicit version negotiation;
- Knowledge Package validation and authorization;
- data-classification and purpose enforcement;
- policy and budget evaluation;
- strategy and provider authorization;
- provider, strategy, and task lifecycle validation;
- normalized result and output validation;
- evidence and audit interfaces;
- cancellation and approval interfaces;
- Plan IR validation and registered-operation resolution;
- feature flags and emergency kill switches; and
- promotion and rollback controls.

The stable layer defines governance semantics, not intelligence. It depends on
versioned interfaces and portable data, never on the internal design of a
strategy, provider, prompt, model, retrieval method, or knowledge store.

### Replaceable intelligence layer

The replaceable layer may contain:

- reasoning strategies;
- prompt and message construction;
- provider adapters and model-specific translation;
- planning algorithms;
- confidence and evaluation approaches;
- context assembly strategies and Knowledge-Layer-owned retrieval strategies;
- symbolic reasoning and deterministic rules;
- human-authored or human-mediated reasoning;
- hybrid reasoning; and
- future implementation-specific optimizations.

A replaceable component receives only the authority and bounded data granted
for one invocation. Selection, review, maturity, or historical success does not
confer execution, approval, policy, credential, or source-system authority.
Retrieval strategies operate only within the separately governed Knowledge
Layer and produce bounded Knowledge Packages; they do not give a Reasoning
Provider or Strategy direct source access.

### Stable core exclusions

The Runtime Kernel and common reasoning contracts must not contain prompt
templates, system prompts, chat message roles, vendor SDK objects, vendor model
names, vendor-native tool calls, model parameters such as temperature or top-p,
vendor token identifiers, proprietary finish reasons or safety settings,
chain-of-thought methods, hidden-reasoning extraction, planning algorithms,
memory-retrieval strategies, embedding or database details, knowledge-store
implementation details, domain instructions, agent personalities, or arbitrary
implementation paths.

## Common reasoning envelope

VSS will not define one universal schema containing every possible reasoning
task. A small common envelope supplies routing, governance, and evidence
metadata; an independently versioned task payload supplies semantic data.

Conceptual common-envelope fields may include:

- `schema_version`;
- `request_id` and `correlation_id`;
- `task_type` and `task_contract_version`;
- `data_classification` and `permitted_purpose`;
- a bounded `budget`;
- `required_output_contract`;
- `allowed_operations`;
- `autonomy_level` and `lifecycle_mode`;
- bounded `policy_context`;
- `knowledge_package_references`; and
- the task-specific `payload`.

These are conceptual responsibilities, not a final field schema. ADR-0013 will
define the first concrete envelope and task contract. Policy context contains
portable decision inputs, not executable policy, credentials, provider-native
configuration, or ambient environment state.

## Task-specific contracts

Potential future task types include classification, summarization, structured
option generation, information-gap analysis, risk assessment, plan generation,
plan evaluation, and result evaluation. Each task contract is independently
versioned, validated, lifecycle managed, tested, deprecated, migrated, and
disabled.

Providers need not support every task or version. A provider, strategy, or
translator cannot declare a task compatible on its own. Compatibility is
verified by the stable contract registry and policy. An unsupported task,
version, or required semantic fails closed.

## Open and provider-neutral formats

Public reasoning boundaries use open, inspectable, serializable formats:
JSON-compatible values, JSON Schema, stable textual identifiers, and
cryptographic digests where integrity evidence is required.

Public Runtime reasoning contracts must not expose model names, prompts,
message roles, temperature, top-p, vendor token identifiers, proprietary
function/tool-call formats, provider-native responses, proprietary safety
objects, provider-native finish reasons, or provider-native credential
references.

Portable requirements may include maximum duration, response size, context
size, iterations, determinism preference, data classification, privacy and
retention restrictions, required output schema, allowed operations, confidence
requirement, cost or resource ceiling, and cancellation requirement. Adapters
may translate portable requirements into provider-specific behavior. If an
implementation cannot honor a requirement, it must fail safely and identify
the unsupported portable semantic; it must not silently ignore or weaken it.

## Reasoning Gateway

The Reasoning Gateway is the sole controlled entry point to reasoning. It is a
governance boundary used by Runtime-controlled executions, not an alternate
execution kernel.

### Responsibilities

For every request the Gateway must:

1. validate the common envelope and task-specific payload;
2. verify contract and API-version compatibility;
3. verify task, strategy, and provider lifecycle state;
4. evaluate global, provider, strategy, task, source, and environment kill
   switches;
5. apply data-minimization and classification policy;
6. validate and authorize Knowledge Package identity, purpose, freshness,
   classification, digest, and expiration;
7. enforce context, duration, iteration, call, response, evidence, and cost
   budgets;
8. resolve an authorized strategy and an independently authorized provider;
9. invoke the provider through a narrow provider-neutral contract;
10. normalize the result and reject provider-native or unbounded data;
11. validate the result against the required output contract;
12. record safe evidence and emit correlated audit records; and
13. return inert structured output to the Runtime-controlled caller.

### Prohibited responsibilities

The Gateway must not execute capabilities, execute or modify workflows, mutate
infrastructure, compile executable code, approve operations, modify policy,
infer authorization from provider output, expose provider or source-system
credentials, grant direct source access, accept arbitrary implementation paths,
accept provider-native configuration from capabilities or workflows, interpret
confidence as authority, or automatically execute a candidate plan.

## Strategy and provider separation

### Reasoning Strategy

A Reasoning Strategy determines how a versioned task is approached. A strategy
may eventually be deterministic, rule based, template based, symbolic, model
assisted, human authored, human mediated, or hybrid. It may prepare a
provider-neutral request but does not own Runtime authorization, approval,
execution, credentials, budgets, capability invocation, or arbitrary provider
selection.

### Reasoning Provider

A Reasoning Provider supplies a bounded implementation capable of returning a
reasoning result. It may eventually be deterministic, local, remote, symbolic,
human mediated, open source, proprietary, model based, or non-model based. It
does not contain VSS business policy, execute capabilities, authorize itself,
choose autonomy, expose native objects beyond its adapter, retain or disclose
data beyond approved policy, or increase its budget.

A strategy must not be permanently coupled to one provider, and a provider
must not be permanently coupled to one strategy. Runtime policy resolves both
identities independently. Any compatibility constraint between them is
explicit, versioned, narrow, and replaceable rather than encoded in capability
or workflow contracts.

## Prompt isolation

Prompts, messages, templates, model parameters, and provider-native request
construction exist only inside replaceable provider adapters or
strategy-specific translation components. They never appear in the Runtime
Kernel, capability public contracts, workflow schemas, Plan IR, authorization
policy, common reasoning envelope, Knowledge Package contract, or approval
contract.

Capabilities request semantic reasoning tasks and do not construct prompts.
Workflows reference reasoning task contracts and do not construct prompts.
Prompt changes therefore do not require changes to the Runtime Kernel,
capability contract, or workflow schema.

## Proposal versus execution

The controlled path is:

```text
reasoning request
→ request and task validation
→ policy, strategy, provider, budget, and knowledge authorization
→ bounded reasoning invocation
→ normalized reasoning result
→ response-schema validation
→ Plan IR validation when applicable
→ registered-operation resolution
→ approval when required
→ Runtime execution
```

Reasoning output never directly invokes a capability or workflow, runs a
subprocess, modifies infrastructure or provider configuration, accesses
secrets, writes to a repository, changes Runtime policy, approves itself,
spends money, publishes content, rotates credentials, performs destructive
operations, creates executable implementation references, bypasses workflow
validation, or bypasses operation registration.

## Plan Intermediate Representation

VSS will define a provider-neutral Plan Intermediate Representation (Plan IR)
in a later contract ADR. Plan IR may reference only registered, versioned VSS
operations. Conceptual plan fields may include:

- `plan_schema_version` and `plan_id`;
- goal, assumptions, uncertainties, and constraints;
- risk classification and reversibility classification;
- steps and dependencies;
- required approvals and expected outputs; and
- validity or expiration metadata.

A step may conceptually include a stable step identifier, registered operation,
operation contract version, safe structured input, dependencies, timeout,
approval requirement, reversibility classification, and expected safe output
contract.

Plan IR must not contain Python or shell code, arbitrary executables or paths,
arbitrary URLs, provider-native tool calls, module or implementation paths,
environment-variable references, credentials, raw secrets, unregistered
operations, implicit provider selection, or direct workflow implementation
references.

A provider may produce a candidate plan, but that candidate is not valid Plan
IR merely because a provider emitted it.

## Plan compilation and execution

Authorities remain separate:

1. A provider or strategy produces a candidate structured result.
2. A validated, versioned translator may convert it into candidate Plan IR.
3. An independent Plan IR validator validates structure and references.
4. Runtime policy independently authorizes every referenced operation.
5. An independent approval mechanism approves actions when required.
6. A later, versioned workflow compiler may convert approved Plan IR into a VSS
   workflow.
7. Runtime remains the only execution authority for every operation.

Providers and strategies own none of Plan IR validation, operation
authorization, approval, workflow compilation authority, or execution
authority. Translator and compiler versions are independently versioned and
recorded as evidence. Compilation should be deterministic for identical
validated input and compiler version where practical. A compiler output remains
subject to workflow schema validation and per-step Runtime controls.

## Knowledge Layer boundary

Reasoning does not retrieve repository content, documents, source-control
content, execution history, platform state, tickets, logs, assets, memory,
prior conversations, or other project material directly.

A future Knowledge Layer owns source registration and identity, retrieval,
access control, purpose limitation, data classification, freshness,
provenance, redaction, context selection and limits, retention, source
revocation, integrity evidence, and connector governance. The Reasoning Gateway
may receive only a bounded, normalized Knowledge Package prepared and
authorized by that layer.

Storage, indexing, search, retrieval, embeddings, vector databases, graph
databases, memory implementations, repository and document connectors, and
retrieval algorithms remain outside ADR-0012 and will be defined separately by
ADR-0014. This boundary prevents a provider or strategy from coupling the
platform to a knowledge store, database, search engine, embedding model,
connector, source-control system, document format, or memory implementation.

## Knowledge Package

A Knowledge Package may conceptually contain:

- package schema version and stable package identity;
- source references, source types, and provenance metadata;
- data classification and freshness or effective-date metadata;
- selected, bounded content and redaction metadata;
- integrity digest;
- permitted purpose and retention restrictions;
- expiration metadata; and
- authorization metadata.

It grants no direct access to original sources. The Gateway treats all package
content as untrusted input. Inclusion does not imply truth, correctness,
freshness, completeness, authorization to act or disclose, authorization to
retain, or authorization to access the original source. Package authorization
is purpose-, task-, provider-, environment-, and time-specific and does not
survive replay or migration implicitly.

## Version evolution

The common reasoning envelope, each task contract, Knowledge Package, Plan IR,
strategy API, provider API, translator API, compiler API, evidence format, and
applicable audit-event format evolve independently. Each has an owner,
lifecycle status, supported compatibility window, and retirement plan.

An explicit migration may use:

```text
v1 request
→ validated and authorized v1-to-v2 translator
→ v2 strategy or provider
```

Migration follows this sequence:

1. introduce a new version without reinterpreting the old version;
2. validate old and new versions independently;
3. run conformance and regression tests;
4. run non-influencing shadow comparisons;
5. migrate consumers incrementally;
6. announce deprecation and its owner;
7. retain an explicit compatibility window; and
8. remove the old version only after supported consumers migrate.

Implicit or provider-controlled downgrade, silent field dropping, semantic
default substitution, lossy translation without policy approval, unbounded
compatibility windows, and ownerless deprecated versions are prohibited.

## Lifecycle, shadow mode, promotion, and rollback

Reasoning task, strategy, and provider implementations use explicit lifecycle
states:

- `experimental`;
- `shadow`;
- `advisory`;
- `approval_required`;
- `limited_autonomous`;
- `active`;
- `deprecated`; and
- `disabled`.

Lifecycle state does not itself grant authority. Runtime policy separately
defines where a state is eligible.

In shadow mode, an implementation receives an approved bounded request,
produces a result, is audited, and may be compared with the active
implementation. Its result cannot affect execution, approval, policy, fallback
selection, or autonomy. Shadow output is stored only according to approved
evidence and retention policy.

Promotion requires governed evidence, which may include conformance and
regression results, safety results, schema validity, budget adherence, latency,
failure classification, data-handling and security review, comparison against a
governed corpus, and human review. Promotion authority is independent of the
provider and strategy.

Rollback disables or returns selection to a previously approved compatible
implementation immediately through Runtime-owned lifecycle controls. It must
not require changes to capability or workflow public contracts. Rollback does
not reuse expired authorization or bypass compatibility checks.

## Autonomy levels

Autonomy is explicit and policy granted:

| Level | Permitted behavior |
| --- | --- |
| 0 | No reasoning. |
| 1 | Explain or advise; no executable proposal. |
| 2 | Produce structured recommendations or candidate plans; no execution authority. |
| 3 | Execute read-only plans only after policy and any required approval. |
| 4 | Execute reversible changes only after explicit human approval. |
| 5 | Execute bounded reversible changes under explicit policy and approved environment, operation, provider, strategy, classification, and blast-radius limits. |
| 6 | Reserved; grants no current behavior. |

High-impact, irreversible, destructive, financial, public-release,
credential-related, security-sensitive, legal, privacy-sensitive, or
production-critical operations still require explicit human approval.

Runtime policy determines autonomy from the task, environment, operation, risk,
provider trust, strategy maturity, data classification, permitted purpose,
Knowledge Package classification, approval policy, reversibility, blast radius,
budget, and lifecycle stage. Provider intelligence, confidence, model
capability, popularity, or historical success never grants authority. ADR-0015
will define the detailed autonomy and approval policy.

## Budgets and limits

Every reasoning request has explicit maximum duration, response size, context
size, Knowledge Package size, iterations, provider calls, provider units,
estimated cost, Plan IR steps, evidence size, and retry count if retries are
later supported. A value is bounded even when the permitted value is zero.

Budget exhaustion fails safely. Provider-specific accounting may be translated
into normalized portable evidence, including uncertainty in the estimate. A
provider cannot increase its budget; a strategy cannot silently retry; and a
fallback cannot bypass or reset the original authorization and aggregate
budget.

## Data minimization

Providers never receive broad project context automatically. Runtime and the
future Knowledge Layer construct context from the task and input contract,
permitted purpose, data and provider trust classifications, retention policy,
required user approval, legal and license restrictions, provider data-use
restrictions, environment, and minimum necessary information.

Providers receive no direct repository filesystem, environment variables,
secrets, audit files, unrestricted memory or conversations, Docker socket,
provider registry, command execution interface, source credentials, connectors,
or original source sessions. Context is selected, minimized, normalized,
redacted where required, size bounded, classified, purpose limited, integrity
checked, freshness annotated, and audited by digest and metadata.

## Evidence, replay, and comparison

Safe evidence records may include request and task contract identities and
versions, provider and strategy identities and versions, request digest, policy
version, budget, classification, permitted purpose, Knowledge Package identity
and digest, output digest, validation outcome, candidate-plan and Plan IR
digests, translator and compiler versions, approval decision, execution outcome,
lifecycle mode, autonomy level, and kill-switch state.

Sensitive raw prompts, Knowledge Package content, provider responses, hidden
reasoning, chain-of-thought, credentials, source content, and context are not
retained by default. A separately approved policy must define purpose, access,
retention, deletion, and provider behavior before retaining any such data.

Replay uses approved immutable fixtures or approved retained data and defaults
to validation, simulation, or shadow mode. It never silently executes side
effects, reuses expired authorization or approval, contacts an external
provider, reveals redacted data, bypasses current policy, exceeds the current
budget, or uses a disabled implementation.

## Conformance suites

Every strategy and provider must pass a common, provider-neutral conformance
suite covering:

- valid structured and malformed responses;
- unsupported task and version;
- timeout, cancellation, budget exhaustion, and excessive output or context;
- invalid operation references and fabricated capabilities;
- unsafe candidate plans and Plan IR;
- prompt-injection-like input and indirect injection through knowledge;
- secret-like input and output-schema violation;
- provider unavailable/failure and strategy failure;
- a deterministic fake implementation;
- audit failure and kill-switch activation;
- contract downgrade attempts;
- unauthorized or expired Knowledge Packages;
- provider and strategy substitution;
- shadow-result isolation;
- unexpected provider-native data; and
- unsafe fallback.

A stable, non-sensitive evaluation corpus supports regression testing. It
contains no production secrets, unrestricted personal data, unauthorized
proprietary material, unrestricted conversation history, mutable external
dependencies, or provider credentials. Corpus versions and expected evaluation
semantics are immutable inputs to deterministic CI.

## Feature flags and kill switches

Runtime-owned controls include a global reasoning disable switch, provider and
strategy disable switches, task-contract and Knowledge Package source disable
switches, environment restrictions, autonomy ceilings, cost and resource
ceilings, an emergency approval requirement, and deterministic fallback
selection.

Kill switches are evaluated before provider invocation and again before
promotion or execution of resulting proposals. A disabled implementation fails
closed or uses only a compatible fallback explicitly authorized for the same
task, data, budget, lifecycle, and environment. Selection never becomes an
automatic provider-controlled fallback.

Reasoning failure or disablement must not disable bootstrap, recovery, security
scanning, manually authored workflows, platform teardown, audit inspection,
emergency controls, or other non-reasoning capabilities.

## Fallback and recovery

Critical operations retain a non-AI path where practical: deterministic
workflows, rule-based strategies, human-authored plans, manual capability
invocation, and approved operational runbooks. Reasoning is not a mandatory
dependency for bootstrap, recovery, incident or security response, platform
teardown, audit inspection, or emergency disablement.

A fallback is selected by deterministic Runtime policy, not by a failing
provider. It must satisfy the original contract, authorization, classification,
purpose, budget, lifecycle, and approval constraints. Otherwise the request
fails closed.

## Cancellation and isolation

The M2 architecture checkpoint found that cooperative thread cancellation
cannot stop an already running handler. That property is insufficient for
effectful, sensitive, or externally connected reasoning work.

Future reasoning and provider boundaries must support termination without
uncontrolled side effects. No production-sensitive provider, effectful
planning, or autonomous execution may be enabled until a separate isolation
and cancellation design defines process or worker boundaries, termination,
timeout enforcement, resource limits, network controls, credential scope,
cleanup, orphan prevention, and safe failure evidence.

This ADR requires the security property but intentionally does not prescribe a
process, worker, container, or other final implementation.

## Audit and integrity

The M2 checkpoint also found that local JSON Lines audit lacks production
retention, rotation, size limits, durable flush guarantees, tamper resistance,
and independent integrity verification. Development reasoning may initially use
that facility, but no production autonomy may be claimed until production
audit requirements are defined and implemented.

Reasoning audit must distinguish request acceptance/rejection, task validation,
Knowledge Package authorization, strategy/provider selection, budget
authorization, provider invocation start/completion/failure, result
validation/rejection, candidate-plan and Plan IR validation/rejection, approval
request/grant/denial, execution start/completion/failure, ignored shadow result,
kill-switch application, and rollback. Events share correlation and request
identity and do not store sensitive raw content by default.

Audit failure for a required event fails the controlled operation. An audit
record is evidence of a decision, not authorization and not proof that external
data is true.

## Security threats and controls

| Threat | Trust boundary | Architectural mitigation | Deferred control |
| --- | --- | --- | --- |
| Provider substitution | Registry/selector to provider adapter | Repository-controlled identities, digests, exact policy grants, static approved selection, and evidence | External signing, isolation, and revocation |
| Strategy substitution | Registry/selector to strategy | Exact identity/version authorization, immutable selection, digest evidence, and lifecycle controls | External strategy admission |
| Contract downgrade | Caller/translator/provider to contract registry | Independent negotiation, no implicit downgrade, conformance tests, policy-approved translation | Concrete compatibility windows in ADR-0013 |
| Malformed or malicious output | Provider to Gateway | Bounded normalization, JSON-safe types, task/output schema validation, and inert results | Per-task semantic validators |
| Fabricated operations or capabilities | Candidate result to Plan IR | Registered exact operation identities and contract versions; independent Plan IR validation | Concrete Plan IR schema and registry integration |
| Prompt injection | Task/translation to provider | Treat content as untrusted, isolate prompts, constrain outputs and allowed operations | Task-specific injection evaluations |
| Indirect prompt injection | Knowledge Package to provider | Authorized bounded packages, provenance, classification, redaction, content treated as untrusted | Knowledge ingestion controls in ADR-0014 |
| Stale or poisoned knowledge | Source/Knowledge Layer to package | Freshness, provenance, digest, revocation, uncertainty, purpose, and source references | Source scoring and retrieval governance in ADR-0014 |
| Context exfiltration | Gateway/provider boundary | Data minimization, provider trust classification, no direct source access, retention restrictions, and safe evidence | External-provider contractual and technical controls |
| Credential misuse | Runtime/provider boundary | Narrow provider handles, scoped credentials, no credential fields in public contracts, and audit | Credential broker and process isolation design |
| Hidden provider retention | Provider policy boundary | Retention classification, permitted purpose, provider admission, minimization, and disclosure policy | Provider-specific assurance and deletion verification |
| Budget abuse | Strategy/provider to budget authority | Runtime-owned aggregate ceilings, no self-increase, bounded calls/iterations, and fail-closed exhaustion | Portable accounting units |
| Denial of service | Caller/provider to Gateway | Size/count/time limits, cancellation requirement, kill switches, and quotas | Production isolation and scheduling controls |
| Output injection | Provider output to consumers/audit | Structured schemas, safe normalization, bounded diagnostics, inert rendering, and digests | Presentation-context escaping requirements |
| Approval bypass | Plan/Gateway to execution | Independent approval authority, approval bound to exact plan digest/version/expiry | ADR-0015 approval implementation |
| Autonomy escalation | Provider/strategy to policy | Runtime-owned ceiling and explicit level; intelligence/confidence grants no authority | Detailed autonomy policy in ADR-0015 |
| Shadow result becomes active | Shadow implementation to selection/execution | Separate non-influencing sink, explicit lifecycle state, comparison-only path, and tests | Shadow infrastructure implementation |
| Replay causes side effects | Evidence/replay to Runtime | Simulation default, fresh authorization, no approval reuse, and no implicit external calls | Replay tooling and retained-data policy |
| Audit tampering | Runtime to local audit sink | Restricted append interface, safe deterministic events, required-write failure | Production durable integrity backend |
| Provider lock-in | Public contract to adapter | Provider-neutral task contracts and portable normalized outcomes | Conformance across multiple implementations |
| Internal contract lock-in | Consumer to first schema | Independent versions, translators, compatibility windows, shadow migration, and retirement ownership | First concrete versions in ADR-0013 |
| Knowledge-store lock-in | Knowledge Layer to Gateway | Bounded portable Knowledge Package; no retrieval/storage details in reasoning contracts | Knowledge architecture in ADR-0014 |
| Translator compromise | Old contract to new contract/Plan IR | Trusted versioned translators, validation before and after, digests, deterministic tests | Isolation if translators become external |
| Compiler compromise | Plan IR to workflow | Trusted versioned compiler, deterministic output, workflow validation, operation authorization, and evidence | Compiler ownership and implementation review |
| Unsafe fallback | Failure/selector to alternate implementation | Explicit compatible policy selection under original limits; otherwise fail closed | Concrete fallback policy |
| Policy-version mismatch | Gateway/Runtime policy boundary | Bind decisions and approvals to policy identity/version and reject unsupported combinations | Policy migration tooling |
| Data-classification mismatch | Knowledge/caller/provider boundary | Independent classification validation, provider trust policy, and fail-closed mismatch | Classification taxonomy details |
| Permitted-purpose violation | Package/task/provider boundary | Purpose-bound authorization, minimization, evidence, expiry, and no source access | Purpose enforcement in ADR-0014/0015 |
| Provider retention mismatch | Runtime/provider governance | Declared retention capability, admission review, task policy, and safe failure when unmet | External verification and contractual enforcement |

These mitigations define architecture requirements, not claims that deferred
controls already exist. Threat-model changes must precede implementation of a
new provider, knowledge source, autonomy level, or execution effect.

## Dynamic third-party code

Dynamic third-party capabilities, providers, strategies, planners,
translators, compilers, and knowledge connectors remain unsupported. Future
support requires separate architecture for signing, provenance, trust roots,
isolation, revocation, upgrade policy, compatibility, and incident response.

Built-in Python remains trusted in-process code and is not sandboxed. Contract
validation and policy reduce accidental misuse but cannot contain deliberately
malicious reviewed Python. No manifest or lifecycle label changes that fact.

## Alternatives Considered

### 1. Direct model SDK use inside capabilities

This offers fast initial integration but couples business logic to provider
APIs, credentials, prompts, data handling, and failures. It creates multiple
reasoning and authorization paths and is rejected.

### 2. Prompt-centric Runtime API

A prompt API appears generic but exposes one interaction technique as a stable
contract and pushes provider concepts into capabilities and workflows. It makes
prompt evolution disruptive and is rejected.

### 3. One universal reasoning schema

A universal schema centralizes validation but accumulates unrelated task fields,
couples versioning, and encourages lowest-common-denominator semantics. A small
envelope with independent task contracts is selected instead.

### 4. Provider-generated executable workflows

Directly executable provider output reduces translation work but allows an
untrusted result to cross the execution boundary and risks fabricated
operations and approval bypass. Candidate output must pass Plan IR, policy,
approval, workflow, and Runtime controls, so this alternative is rejected.

### 5. Agent-first autonomous design

An autonomous design optimizes for delegation before authority, recovery,
contracts, and evidence are stable. It conflates reasoning with execution and
is rejected. Autonomous behavior may only be layered over the controls in this
ADR and ADR-0015.

### 6. Provider-specific planning contracts

Provider-specific contracts expose native tool calls and planning semantics,
locking capabilities, workflows, and evidence to one adapter. Provider-neutral
task contracts and Plan IR are selected instead.

### 7. Reasoning providers with direct source-system access

Direct repository or source access simplifies retrieval but expands provider
authority, weakens purpose limitation, and couples reasoning to connectors and
storage. Bounded authorized Knowledge Packages are selected instead.

### 8. Evolvable Gateway, task contracts, Knowledge Packages, and Plan IR

This option separates stable governance from replaceable intelligence,
preserves Runtime authority, supports independent contract evolution, and makes
provider, strategy, and knowledge implementations replaceable. Its additional
contracts are justified by explicit trust and migration boundaries. This is the
selected alternative.

## Consequences

### Positive

- Providers and strategies can be replaced independently.
- Contracts can evolve through explicit, observable migrations.
- Structured proposals, independent approval, and Runtime execution support
  safer autonomy.
- Shadow comparison and immediate rollback do not alter capability or workflow
  public contracts.
- Approved replay and regression testing improve detectability.
- Vendor, internal-contract, and knowledge-store lock-in are reduced.
- Runtime authority and provider-neutral capability/workflow contracts are
  preserved.
- Deterministic non-reasoning recovery remains available.

### Costs and risks

- More contracts and independently managed versions require ownership.
- Translators and compatibility windows require maintenance.
- Evidence storage and knowledge governance add operational cost.
- Policy, lifecycle, budget, and approval composition is complex.
- Conformance infrastructure and review delay initial feature delivery.
- The architecture could become over-general before concrete task evidence
  exists.

### Mitigations

- Begin with a narrow first contract and one task type.
- Implement a deterministic fake before any external provider.
- Add no executable reasoning output.
- Introduce explicit deprecation and measurable promotion criteria.
- Conduct periodic architecture checkpoints.
- Build no speculative generic framework beyond accepted use cases.
- Apply simplicity over cleverness and require a concrete vertical slice before
  generalizing.

## Roadmap

This ordering expresses prerequisites; it authorizes no implementation.

### M3A — Reasoning Platform

- ADR-0012 Evolvable and Reversible Reasoning Architecture;
- ADR-0013 Versioned Reasoning Contracts;
- ADR-0014 Knowledge Architecture;
- M3.1 Reasoning contract foundation;
- M3.2 deterministic reasoning provider;
- M3.3 Plan IR and planning validation; and
- M3.6 shadow comparison and provider promotion.

### M3B — Autonomous Platform

- ADR-0015 Autonomy and Approval Policy;
- approval engine;
- reversible execution controls;
- bounded autonomy;
- first external reasoning provider;
- production audit and cancellation prerequisites; and
- promotion and rollback evidence.

The implementation numbering remains:

1. M3.1 Reasoning contract foundation.
2. M3.2 Deterministic reasoning provider.
3. M3.3 Plan IR and planning validation.
4. M3.4 Approval and autonomy policy.
5. M3.5 First external reasoning provider.
6. M3.6 Shadow comparison and provider promotion.

No M3 implementation is part of ADR-0012.

## Unresolved Questions

The following decisions require concrete evidence or later ADRs:

- Which first task contract should ADR-0013 define?
- What normalized confidence semantics are portable across deterministic,
  human, symbolic, and model-based reasoning?
- How is uncertainty represented without false precision?
- Which portable units represent provider, cost, and resource budgets?
- What are evidence-retention periods by classification and purpose?
- How is external-provider data-retention capability classified and verified?
- Which process-isolation and termination mechanism meets cancellation needs?
- Which production audit backend and integrity model are required?
- What are the maximum Knowledge Package and context sizes by task and
  environment?
- Who owns Plan IR compilation and translator admission?
- How long is each compatibility window, and who approves extensions?
- Which safety, validity, latency, budget, and quality metrics govern shadow
  promotion?
- Which criteria govern selection of the first external provider?
- Is human reasoning represented as a strategy, a provider, or both?
- How are citations and source references normalized without coupling to a
  knowledge store?
- What provider cancellation semantics are portable and verifiable?
- How does deterministic fallback selection rank otherwise compatible options?
- Which independent authority approves lifecycle promotion and rollback?

None of these questions permits direct execution, weakens fail-closed policy,
or authorizes an external provider.

## Acceptance Criteria

ADR-0012 may be accepted when:

- stable and replaceable layers are clearly separated;
- Runtime remains the only execution authority;
- no provider-specific concept enters the public Runtime contract;
- reasoning cannot execute directly;
- capability and workflow contracts remain prompt independent;
- Plan IR is provider neutral;
- reasoning contracts are independently versioned;
- Knowledge Packages isolate reasoning from source systems;
- shadow mode and immediate rollback are defined;
- autonomy levels are explicit;
- data minimization is mandatory;
- budgets and kill switches are required;
- deterministic non-reasoning recovery remains supported;
- M2 audit and cancellation limitations are acknowledged;
- dynamic third-party code remains unsupported;
- ADR-0011 principles are explicitly applied without deviation;
- unresolved questions are recorded honestly; and
- no M3 implementation code or dependency is added.

## Independent Review Perspectives

Before acceptance, review must cover these perspectives independently from
implementation authorship:

1. **Enterprise Software Architect:** component responsibilities, dependency
   direction, governance stability, and unnecessary complexity.
2. **Computer Science Evolvability Reviewer:** independent versioning,
   substitutability, migration, rollback, and semantic-loss risks.
3. **Runtime Architect:** sole execution authority, operation resolution,
   cancellation, and compatibility with ADR-0010.
4. **Product Security Reviewer:** threat boundaries, least privilege, failure
   behavior, isolation assumptions, and approval bypass.
5. **AI Governance Reviewer:** bounded reasoning, data purpose, evidence,
   autonomy, human approval, and false-confidence risks.
6. **Provider-Neutrality Reviewer:** absence of provider-native concepts and
   independent strategy/provider replacement.
7. **Knowledge Architecture Reviewer:** package/source separation, provenance,
   classification, freshness, revocation, and storage independence.
8. **Operational Recovery Reviewer:** kill switches, fallback, replay safety,
   audit integrity, cancellation, and deterministic non-reasoning recovery.
9. **Compatibility Reviewer:** unchanged capability, workflow, response, and
   Runtime contracts plus explicit future compatibility windows.
10. **Independent Verification Reviewer:** acceptance criteria, traceability,
    conformance evidence, and absence of implementation changes.

Reviewers must record material contradictions, unclear authority, unsupported
assumptions, and deferred controls. Completeness is not a reason to invent an
implementation choice without evidence.

### Draft review findings

The ten-perspective draft review identified no deviation from ADR-0011 and no
change to an existing public contract. It confirmed these cross-cutting
conclusions:

- Architecture and evolvability: governance contracts are stable in purpose
  but independently versioned; strategy, provider, translator, compiler, and
  knowledge implementations remain replaceable.
- Runtime and compatibility: reasoning has no direct execution path, and
  existing capability, workflow, command, response, and provider contracts are
  unchanged.
- Security and AI governance: output is inert and untrusted; data, budget,
  policy, approval, autonomy, evidence, and kill-switch decisions remain
  independent of provider confidence.
- Provider and knowledge neutrality: no provider-native concept crosses the
  public boundary, and retrieval remains behind authorized Knowledge Packages
  rather than provider source access.
- Recovery and verification: non-reasoning operations remain available;
  production-sensitive use is gated on unresolved cancellation and audit
  controls; conformance and shadow isolation are mandatory.

The review corrected one wording ambiguity by assigning retrieval strategies
explicitly to the future Knowledge Layer. All implementation-specific choices
without current evidence remain in Unresolved Questions or later ADRs.

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [M2 architecture checkpoint](../reviews/m2-architecture-checkpoint.md)
- [VSS security threat model](../security/threat-model.md)
- [Runtime Kernel documentation](../runtime-kernel.md)
- [Capability SDK documentation](../capability-sdk.md)
- [Provider Abstraction documentation](../provider-abstraction.md)
- [Workflow Engine documentation](../workflow-engine.md)
- [Secure development policy](../security/secure-development.md)
- [Component approval policy](../security/component-approval.md)
- [Security exceptions](../security/security-exceptions.md)
- [Dependency upgrade policy](../security/upgrade-policy.md)
- [Vulnerability-management policy](../security/vulnerability-management.md)
- [License policy](../../security/license-policy.yml)
- [Component inventory](../../security/components.yml)
- [Dependency inventory](../../security/dependency-inventory.yml)

## Verification

Verify this decision with the repository ADR validator, repository-relative
reference and link checks, available Markdown lint, documentation-only scope
inspection, and whitespace validation. Future implementation must add
contract, conformance, adversarial, compatibility, shadow-isolation, replay,
kill-switch, audit-failure, cancellation, and deterministic recovery evidence
before any reasoning component is promoted.
