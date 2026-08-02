# ADR-0013: Semantic Reasoning Contracts

## Status

Proposed

## Date

2026-08-01

## Context

[ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md) establishes the
Runtime Kernel as the single authority for validation, authorization,
execution, normalization, and audit. [ADR-0011](ADR-0011-engineering-principles.md)
requires Runtime-first, provider-neutral, vendor-neutral, explicitly versioned
contracts. [ADR-0012](ADR-0012-evolvable-reasoning-architecture.md) establishes
the permanent rule that reasoning proposes while Runtime validates, authorizes,
approves, and executes.

ADR-0013 defines the language spoken between Runtime-controlled callers and
every present or future reasoning implementation. Reasoning engines, models,
providers, strategies, knowledge sources, evaluation techniques, and contract
implementations may change repeatedly. The stable Runtime boundary must not
encode those choices.

The durable abstraction is semantic intent and semantic result. Runtime never
asks an implementation to use a named model, vendor, local serving product,
prompt, message sequence, or generation parameter. Runtime submits a versioned
semantic task. Reasoning returns a versioned semantic object. The object is
inert, bounded, provider-neutral data and conveys no authority.

This ADR specifies concepts and compatibility rules. It deliberately does not
define serialization schemas, Python types, APIs, implementations, prompts,
providers, workflows, or execution behavior.

## Decision

VSS will define independently versioned Reasoning Tasks and Reasoning Objects
as the permanent semantic boundary between Runtime governance and replaceable
reasoning. The first supported task SHALL be `GenerateOptions`, and its result
family SHALL be `OptionSet`.

The contract boundary follows four rules:

1. Runtime expresses the semantic task and required result family, never an
   implementation technique.
2. Reasoning returns a validated semantic object, never an executable command,
   implementation reference, policy decision, or approval.
3. Task, object-family, and overall reasoning-contract versions evolve
   independently and fail closed when unsupported.
4. Model, Provider, Strategy, Knowledge Source, and Contract Version remain
   independently replaceable without changing Runtime contracts.

## Governing boundary

ADR-0013 is governed by ADR-0011 and refines, without superseding, ADR-0012.
ADR-0012 owns the Reasoning Gateway, policy, budgets, provider and strategy
authorization, Knowledge Package boundary, lifecycle controls, audit, and
proposal-versus-execution rule. ADR-0013 owns only the semantic meaning of task
requests and reasoning results.

The Runtime may route a supported semantic task through the Reasoning Gateway,
but neither the task nor its result selects a provider, strategy, prompt,
knowledge source, capability, workflow, or implementation. Registration and
contract compatibility do not imply authorization.

## Terminology

### Reasoning Task

A **Reasoning Task** is an immutable, versioned semantic request describing the
kind of reasoning requested, the bounded input meaning, applicable constraints,
and the required Reasoning Object family. It states *what* result is needed,
not *how* to produce it. A task contains no prompt, provider selection, model
configuration, execution instruction, or authority.

### Reasoning Object

A **Reasoning Object** is an immutable, versioned, bounded, structured semantic
result conforming to one declared object-family contract. It contains explicit
facts, assumptions, unknowns, constraints, evidence references, confidence,
limitations, version, and contract identity. It is data for validation and
human or Runtime-controlled consumption; it is never an instruction to execute.

### Reasoning Evidence

**Reasoning Evidence** is a stable reference to authorized supporting material
and the claim it is offered to support. A reference carries identity,
provenance, relevance, and integrity context defined by the applicable contract
or future Knowledge Package contract. Evidence is not proof of truth,
authorization to retrieve a source, authorization to disclose content, or
execution authority.

### Reasoning Assumption

A **Reasoning Assumption** is a proposition used to construct an object but not
established as a fact by the available authorized evidence. It is explicit,
scoped, and traceable to the result elements it affects. An assumption cannot
be silently promoted to fact.

### Reasoning Unknown

A **Reasoning Unknown** is material information that is unavailable,
unverified, ambiguous, stale, or outside the authorized context and may affect
interpretation of the result. Unknowns are first-class data, not omitted error
conditions. They identify impact without inventing missing information.

### Reasoning Constraint

A **Reasoning Constraint** is a declared semantic boundary that candidate
results must satisfy or explicitly report as unsatisfied. Constraints may
express required, prohibited, bounded, or preference semantics. A reasoning
engine cannot weaken, reinterpret, or silently discard a constraint.

### Reasoning Confidence

**Reasoning Confidence** is a bounded, explicitly qualified statement about the
support for a claim or object under the declared facts, assumptions, unknowns,
constraints, evidence, and method. It is not necessarily a probability and
must not imply calibration that has not been demonstrated. Confidence never
grants authorization, approval, autonomy, truth, or permission.

The first contract requires confidence to identify its scope and limitations;
the final normalized scale and calibration semantics remain open work.

### Reasoning Risk

A **Reasoning Risk** is a structured description of a possible adverse outcome,
including affected objective or asset, cause or condition, consequence,
uncertainty, and available evidence. A risk assessment informs policy and human
review but cannot accept risk or authorize an action.

### Reasoning Recommendation

A **Reasoning Recommendation** is an inert, reasoned preference among explicit
alternatives under stated criteria, constraints, assumptions, unknowns,
evidence, risk, confidence, and limitations. It is not approval, policy,
provider selection, capability selection, or an execution request.

### Reasoning Alternative

A **Reasoning Alternative** is one distinct candidate response to the semantic
task, described sufficiently for comparison without embedding executable
content. Alternatives preserve material trade-offs and uncertainty and do not
become selected merely by their order or confidence.

### Reasoning Explanation

A **Reasoning Explanation** is a bounded, audience-appropriate summary of the
facts, criteria, evidence, assumptions, unknowns, limitations, and trade-offs
that support a semantic result. It does not expose hidden reasoning or
chain-of-thought and is not a substitute for evidence.

### Reasoning Limitation

A **Reasoning Limitation** is a disclosed restriction on validity, coverage,
freshness, method, data, calibration, generalization, or intended use. A
limitation remains attached to the affected object and cannot be removed by a
translator without explicit, validated semantics.

## Semantic statements carried by every object

Every Reasoning Object family contains the following semantic statements,
even when a field is explicitly empty:

- **Facts:** propositions treated as established within the bounded task
  context, with evidence or authoritative input references where required.
- **Assumptions:** propositions relied upon but not established as facts.
- **Unknowns:** material missing, ambiguous, stale, or unverified information.
- **Constraints:** boundaries applied to the object and any unsatisfied
  constraints.
- **Evidence references:** stable references supporting claims, never ambient
  source access.
- **Confidence:** scoped, qualified support statements without authority.
- **Limitations:** restrictions on interpretation and use.
- **Version:** the independently enforced object-family version.
- **Contract identity:** the stable semantic identity defining the object's
  meaning.

These statements are logically immutable after validation. A later annotation
or evaluation is a new versioned object linked to the original; it does not
rewrite prior evidence. Facts are facts *within the contract context*, not
universal truth. Empty assumptions, unknowns, constraints, evidence, or
limitations must be represented intentionally rather than omitted ambiguously.

## Reasoning Object families

Object families provide distinct semantic meanings rather than optional modes
inside one universal object. A new family may be admitted without changing
Runtime when it follows the common object invariants and is registered through
an independently versioned contract.

### OptionSet

An **OptionSet** contains distinct Reasoning Alternatives responsive to one
bounded question. It records coverage limitations, relevant comparison
criteria, constraints, shared and alternative-specific assumptions and
unknowns, evidence references, and confidence. Ordering does not imply ranking
or recommendation unless a future contract explicitly defines such semantics.

### Evaluation

An **Evaluation** assesses one or more identified objects against explicit,
versioned criteria. It records criterion results, evidence, uncertainty,
limitations, and confidence. It does not choose an operation, approve an
action, or rewrite the evaluated object.

### Classification

A **Classification** assigns one or more labels from a task-defined, versioned
label vocabulary to identified input. It records applicable evidence,
uncertainty, confidence, and limitations. A label is descriptive data and does
not independently trigger policy or execution.

### Recommendation

A **Recommendation** expresses an inert preference among named alternatives
using explicit criteria and trade-offs. It preserves rejected alternatives,
risks, assumptions, unknowns, evidence, confidence, and limitations. Runtime or
a human may disregard it without violating the contract.

### Explanation

An **Explanation** provides a bounded semantic account of an identified object
or conclusion. It references facts and evidence, discloses assumptions,
unknowns, constraints, confidence, and limitations, and excludes hidden
reasoning and provider-native content.

### RiskAssessment

A **RiskAssessment** describes identified Reasoning Risks, affected assets or
objectives, uncertainty, evidence, confidence, limitations, and applicable
constraints. It does not accept risk, assign permission, or approve mitigation.

### ConstraintSet

A **ConstraintSet** groups normalized Reasoning Constraints with provenance,
scope, priority or conflict semantics where the applicable version defines
them, and any known incompatibilities. It cannot modify Runtime policy or
convert a preference into authorization.

### EvidenceBundle

An **EvidenceBundle** groups bounded Reasoning Evidence references and the
claims, provenance, freshness, classification, and limitations associated with
them. It contains no implicit source credential or retrieval authority and is
not a replacement for the Knowledge Package boundary defined by ADR-0012.

## First task contract: GenerateOptions

`GenerateOptions` is the first supported Reasoning Task. It requests a bounded
set of semantically distinct alternatives for a stated question or objective
under declared facts, constraints, assumptions, known unknowns, evidence
references, and output bounds. Its required result is an `OptionSet`.

The task's semantic inputs are conceptually limited to:

- the question or objective to explore;
- facts supplied by the authorized caller or bounded context;
- explicit assumptions and known unknowns;
- constraints and comparison criteria;
- authorized evidence references;
- required coverage and result bounds; and
- the required `OptionSet` contract identity and version.

This list describes meaning, not a serialization schema.

`GenerateOptions` produces alternatives and their trade-offs. It does not:

- generate, validate, or execute a plan;
- select or execute a capability, tool, provider, model, strategy, workflow, or
  knowledge source;
- rank an alternative as an authorized choice;
- approve, schedule, publish, purchase, modify, or delete anything;
- infer permission, autonomy, policy, or acceptance of risk;
- return code, shell commands, executable paths, implementation paths,
  credentials, or provider-native calls; or
- create Plan IR.

`GeneratePlan`, `ExecutePlan`, `ChooseBestProvider`, `ToolSelection`, generic
execution, and autonomy are explicitly not part of the first contract. A later
task cannot acquire these semantics by adding optional fields to
`GenerateOptions`; it requires a separately reviewed task identity and version.

## Prohibited concepts and authority

Semantic Reasoning Contracts contain no prompts, chat messages or roles, system
prompts, temperature, `top_p` or top-p, provider or model names, tokens or token
identifiers and counts, embeddings, vector-database assumptions,
provider-shaped JSON, proprietary tool calls, provider-native responses,
credential references, or arbitrary implementation paths.

They convey no execution, filesystem, provider, workflow, approval, secret,
repository, subprocess, network, or policy authority. Reasoning output cannot:

- approve execution or accept risk;
- elevate or request additional permissions implicitly;
- invoke or select providers, capabilities, tools, or workflows;
- modify Runtime state, policy, configuration, registries, or audit;
- access secrets, filesystems, knowledge sources, or credentials;
- bypass policy, validation, budgets, approval, or the Reasoning Gateway; or
- cause side effects through object interpretation.

Consumers treat every object as untrusted inert data until contract validation
completes. Even a valid object remains inert. Only a separate
Runtime-controlled process may interpret it for a later authorized task, and
that process does not inherit authority from the object.

## Rule of Five

Every reasoning feature must be independently replaceable at five dimensions:

1. **Model:** the internal reasoning mechanism can change without a semantic
   contract change.
2. **Provider:** the implementation supplying reasoning can change without a
   task or object change.
3. **Strategy:** the method used to approach the task can change independently
   of provider and Runtime.
4. **Knowledge Source:** authorized source material can change behind bounded
   Knowledge Packages and evidence references.
5. **Contract Version:** consumers and producers can migrate through explicit
   compatibility windows without changing Runtime execution authority.

If replacing any one dimension requires modification of Runtime's semantic
contract, authorization boundary, capability contract, or workflow contract,
the design is rejected. An adapter may change inside the replaceable layer, but
it cannot weaken semantic meaning or move provider concepts into Runtime.

## Contract identity and independent versioning

Three version dimensions are independent:

- **Reasoning Contract version:** versions the common semantic invariants and
  relationship among task requests, result objects, and validation outcomes.
- **Reasoning Task version:** versions the meaning, required inputs, permitted
  outputs, and failure semantics of one task such as `GenerateOptions`.
- **Reasoning Object version:** versions one object family's meaning and
  invariants, such as `OptionSet`, independently of other families.

A change in one dimension does not silently increment, downgrade, or reinterpret
another. Each supported combination is explicit in a Runtime-owned contract
registry. Provider, model, strategy, Knowledge Package, evidence, audit, and
implementation versions remain separate metadata governed by ADR-0012.

Contract identities are stable textual semantic identifiers. An identity is
never reassigned to incompatible meaning. This ADR does not select concrete
serialized identifier fields or version syntax; ADR implementation work must
do so without altering these semantics.

## Backward compatibility

Future additions must not invalidate an existing supported contract. Compatible
evolution may add a new task, a new object family, or a new independently
negotiated version while preserving the meaning and validation of existing
versions.

The following are incompatible changes and require a new applicable version:

- changing the meaning of a fact, assumption, unknown, constraint, evidence
  reference, confidence statement, or limitation;
- making a previously optional semantic claim mandatory or vice versa when the
  change affects interpretation;
- changing `GenerateOptions` into ranking, recommendation, planning, tool
  selection, or execution;
- changing the result family expected by an existing task version;
- changing bounds, ordering, default, omission, or failure semantics in a way
  that alters meaning; or
- removing information needed to preserve uncertainty, provenance, or
  limitations.

Unknown task identities, object families, contract versions, task versions,
object versions, or unsupported version combinations fail closed before a
reasoning result is accepted. Unknown fields cannot be treated as harmless when
they could affect semantics or authority.

## Compatibility windows and migration

Every new version proposal documents:

- the old and new identities and supported combinations;
- the semantic difference and whether translation is lossless;
- affected producers and consumers;
- the introduction, deprecation, and removal conditions;
- a bounded overlap window with dates or measurable exit criteria;
- an accountable owner;
- conformance, compatibility, rollback, and shadow evidence; and
- behavior when negotiation fails.

Migration follows ADR-0012: introduce and validate versions independently, run
conformance tests and non-influencing shadow comparisons, migrate consumers
incrementally, announce deprecation, retain the explicit compatibility window,
and remove an old version only after all supported consumers migrate.

There is no implicit downgrade, silent field dropping, semantic default
substitution, provider-controlled compatibility, or lossy translation without
explicit policy approval. Compatibility windows cannot be indefinite.

## Contract negotiation

Negotiation is deterministic and fail closed. A Runtime-owned registry compares
the caller's exact supported contract, task, and object versions with the
versions admitted for the selected strategy and provider. It chooses only an
explicitly supported combination under current policy; it never asks a provider
to guess or downgrade.

The exact negotiation algorithm is future work. Until it is defined and
validated, only exact-version matches are safe. Negotiation cannot select an
implementation, expand authority, or override lifecycle and kill-switch state.

## Shadow execution and comparison

A new producer, strategy, provider, translator, or contract version enters
shadow evaluation before it can replace an active semantic path. Shadow
execution receives only an already authorized bounded task and budget. Its
object is validated, audited, and compared using a governed evaluation corpus
or approved live comparison criteria.

A shadow object cannot be returned as the active result, change approval,
influence execution, modify policy, become fallback automatically, or increase
autonomy. Comparisons preserve task/object/version identities and distinguish
semantic validity from subjective quality. Promotion requires conformance,
compatibility, security, data-governance, and regression evidence. Rollback
restores a previously supported semantic combination without changing Runtime
contracts.

## Security properties

Reasoning output is always inert and untrusted. Contract validity means only
that data satisfies known semantic and structural expectations; it does not
mean the content is true, safe to disclose, authorized, approved, or suitable
for execution.

The contract prevents authority confusion by requiring:

- explicit separation of facts, assumptions, unknowns, and limitations;
- evidence references without direct source access;
- bounded object families and result counts;
- rejection of provider-native and executable content;
- exact identity and version validation;
- independent Runtime authorization outside the object;
- safe failure for unknown tasks, families, versions, or semantics; and
- retention of uncertainty and limitations through translation.

Reasoning cannot approve execution, elevate permissions, invoke providers,
select capabilities, modify Runtime state, access secrets, or bypass policy.
Confidence, recommendation, classification, risk, explanation, evidence, or
majority agreement never grants authority.

Built-in reasoning implementations will remain trusted in-process code unless a
later isolation decision changes that boundary. Semantic contracts constrain
data and authority but are not a sandbox for malicious implementation code.
Dynamic third-party reasoning code remains unsupported under ADR-0012.

## Audit and evidence

The semantic audit record for each reasoning result includes:

- Reasoning Contract identity and version;
- Reasoning Task identity and version;
- Reasoning Object family identity and version;
- Reasoning Version;
- execution duration;
- bounded evidence references or an evidence-bundle digest;
- correlation and request identities;
- validation outcome; and
- safe status and failure classification.

**Reasoning Version** identifies the versioned strategy or semantic procedure
that produced the result without changing the task or object meaning. It is
recorded for reproducibility and comparison, not exposed as provider selection
inside the semantic object. Provider and implementation identity, when required
for operational audit, remain separate governance metadata under ADR-0012.

Audit does not retain prompts, provider-native model responses, secrets,
credentials, source content, internal hidden reasoning, or chain-of-thought by
default. Audit references and digests do not grant retrieval permission. Audit
failure follows ADR-0012 and cannot silently produce a successful controlled
operation.

## Determinism and evaluation

The semantic contract is deterministic even when an implementation is not:
identical validated objects have identical meaning, validation, and
compatibility outcomes for the same contract versions. Ordering, omission,
empty-value, confidence, and failure semantics must be explicit for each
version.

Implementations are evaluated through provider-neutral conformance cases and a
stable, non-sensitive corpus. Evaluation distinguishes structural validity,
semantic contract adherence, evidence use, uncertainty disclosure, option
diversity, constraint satisfaction, and reproducibility from provider-specific
quality metrics. A favorable benchmark cannot grant authority or waive a
contract requirement.

## Compatibility test of the abstraction

A future engineer must be able to replace GPT, Claude, Gemini, Llama, Ollama,
DeepSeek, Qwen, human review, a rules engine, graph reasoning, symbolic
reasoning, or a technology not yet invented without modifying Runtime semantic
contracts.

These examples are replaceability tests, not approved providers, dependencies,
integrations, recommendations, or concepts exposed by the Runtime contract.
Any implementation still requires separate admission, policy, security,
licensing, data-governance, and lifecycle review.

## Alternatives Considered

### Provider-native request and response contracts

This would simplify the first adapter but expose models, roles, prompts,
generation parameters, tokens, tool calls, and response objects to Runtime.
Replacement would require contract changes, so this alternative is rejected.

### Prompt text as the universal task

Prompt text is flexible but has no stable task semantics, moves provider and
strategy concerns into callers, weakens validation, and makes compatibility
depend on mutable technique. It is rejected.

### One universal Reasoning Object

A universal object would accumulate optional fields and couple unrelated
semantics and version changes. Independent object families with common
invariants are selected instead.

### Begin with plan generation

Planning introduces operation references, sequencing, approval, and a greater
risk of execution confusion before semantic contracts are proven. It is
deferred in favor of inert option generation.

### Begin with recommendation or classification

Both are bounded but can be mistaken for a decision or policy trigger.
`GenerateOptions` more clearly preserves human and Runtime choice while testing
semantic alternatives, evidence, uncertainty, constraints, and limitations.

### Semantic tasks and independently versioned object families

This design provides stable meaning without coupling Runtime to a reasoning
technique. It supports exact validation, gradual migration, shadow comparison,
and the Rule of Five. This alternative is selected.

## Consequences

### Positive

- Runtime remains independent of providers, models, prompts, and reasoning
  techniques.
- `GenerateOptions` provides useful bounded output without planning or
  execution authority.
- Facts, assumptions, unknowns, evidence, confidence, and limitations remain
  explicit instead of being collapsed into prose.
- Independent task and object families allow narrow evolution.
- Exact compatibility, shadow migration, and rollback reduce internal contract
  lock-in.
- Provider-neutral objects support deterministic validation, comparison, and
  audit.

### Costs and trade-offs

- Multiple version dimensions require a compatibility registry and ownership.
- Strict object families require more semantic design than free-form text.
- Provider adapters may lose implementation-specific features at the public
  boundary.
- Evidence, uncertainty, limitation, and confidence semantics add authoring and
  review burden.
- Exact-version fail-closed behavior may temporarily reduce availability during
  migration.
- `GenerateOptions` deliberately cannot satisfy planning, selection, or
  execution use cases.

### Mitigations

- Admit one task and one primary result family first.
- Keep common invariants small and add families only for demonstrated semantic
  needs.
- Require bounded compatibility windows, shadow evidence, and rollback plans.
- Preserve provider-specific optimizations inside replaceable adapters.
- Record unresolved semantics rather than embedding premature defaults.
- Apply ADR-0011's simplicity-over-cleverness and vertical-slice principles to
  later implementation.

## Open Questions

The following remain future decisions and do not expand current authority:

- What concrete Plan IR semantics and validation boundary will later represent
  plans without making reasoning output executable?
- What final Knowledge Package and evidence-reference contracts will ADR-0014
  define?
- Does a Reasoning Compiler translate only validated semantic objects, and who
  owns its admission and version lifecycle?
- What concrete Reasoning Gateway request and result schemas implement these
  semantics without widening the Runtime Kernel?
- How are strategies and providers selected independently while preserving
  exact contract compatibility?
- Which confidence scale, calibration evidence, and applicability rules work
  across deterministic, human, symbolic, graph, and model-based reasoning?
- Is human reasoning represented as a Strategy, Provider, or both?
- How does hybrid reasoning attribute facts, assumptions, unknowns, evidence,
  confidence, and limitations across contributors?
- Which shadow-evaluation corpus, comparison methods, and promotion thresholds
  are governed and reproducible?
- Which benchmarks measure semantic adherence without becoming provider-specific
  authority signals?
- What deterministic negotiation algorithm and compatibility-window durations
  are appropriate after exact-version matching?
- Can streaming Reasoning Objects preserve immutability, bounds, validation,
  ordering, cancellation, and audit before completion?
- How will multi-stage reasoning link immutable intermediate objects without
  treating intermediate output as authorization or hidden mutable memory?
- Which normalized source/citation reference semantics belong to ADR-0014?
- How are partial results classified after timeout or cancellation?

These questions require separate evidence and decisions. Until resolved, they
must not be filled by provider defaults or implicit Runtime behavior.

## Success Criteria

ADR-0013 may be accepted when:

- the semantic task/object boundary is independent of provider and strategy;
- `GenerateOptions` is the sole first task and returns only an inert
  `OptionSet`;
- all required semantic concepts and object families are unambiguous;
- every object exposes facts, assumptions, unknowns, constraints, evidence
  references, confidence, limitations, version, and contract identity;
- no provider-native or prompt concept appears in the public contract;
- the Rule of Five can be satisfied without Runtime contract modification;
- task, object, and overall Reasoning Contract versions evolve independently;
- unknown identities and versions fail closed;
- migration windows, shadow isolation, deprecation, and rollback are explicit;
- reasoning output carries no execution, authorization, provider, workflow,
  filesystem, secret, approval, or policy authority;
- audit records safe contract, task, object, reasoning, duration, and evidence
  metadata without prompts, raw responses, secrets, or hidden reasoning;
- future Plan IR, knowledge, compilation, selection, calibration, human/hybrid,
  streaming, and multi-stage decisions remain explicitly unresolved; and
- no implementation, schema, provider, workflow, SDK, dependency, test,
  prompt, or integration is added.

## References

- [ADR-0010: Capability-Oriented Runtime Kernel](ADR-0010-capability-oriented-runtime-kernel.md)
- [ADR-0011: Engineering Principles](ADR-0011-engineering-principles.md)
- [ADR-0012: Evolvable and Reversible Reasoning Architecture](ADR-0012-evolvable-reasoning-architecture.md)
- [M2 architecture checkpoint](../reviews/m2-architecture-checkpoint.md)
- [VSS security threat model](../security/threat-model.md)
- [Runtime Kernel documentation](../runtime-kernel.md)
- [Provider Abstraction documentation](../provider-abstraction.md)

## Verification

Verify this documentation-only decision with:

```bash
./scripts/validate_adr.sh
git diff --check
```

Also validate repository-relative references and links, confirm that the ADR is
the only tracked change, and run existing Markdown validation when available.
Do not add a dependency solely to validate this document.
