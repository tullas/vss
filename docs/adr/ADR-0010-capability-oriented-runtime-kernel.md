# ADR-0010: Capability-Oriented Runtime Kernel

## Status

Accepted

## Date

2026-07-31

## Context

VSS currently exposes domain operations through a Python command engine. The
engine discovers registered command modules, validates JSON input schemas,
creates a command context, applies timeouts, invokes handlers, and returns a
structured response with a correlation ID and named exit code. Bootstrap,
platform, secrets, and system commands already use this contract. This is a
sound compatibility baseline, but continued growth through command-specific
framework logic would couple domains, execution controls, and providers.

VSS needs a runtime architecture that can add domain functionality without
discarding the existing command engine or embedding vendor-specific behavior
in a privileged core. It must preserve provider independence, local-first
development, secure-by-default execution, reproducibility, deterministic
interfaces, auditable actions, and compatibility with existing commands.
Migration must be gradual rather than a disruptive rewrite.

The existing security foundation requires independently approved components,
immutable identities, exact dependency pins, license and vulnerability review,
validated provenance, least privilege, safe diagnostics, and expiring
exceptions. A capability model must strengthen these controls rather than
create an alternate path around them.

## Decision

VSS will evolve into a capability-oriented runtime. A deliberately small
Runtime Kernel will provide shared validation and execution services;
capabilities will supply domain functionality. The current command engine and
its public CLI remain the initial execution path and compatibility contract.

### Terminology

- **Capability:** A versioned unit of domain functionality discoverable by the
  runtime. It exposes one or more commands through a validated manifest and a
  bounded handler contract.
- **Runtime Kernel:** The minimal trusted core that validates, authorizes, and
  executes capabilities while enforcing runtime-wide contracts.
- **Capability Manifest:** Machine-readable metadata describing a capability's
  identity, version, commands, schemas, permissions, compatibility, integrity,
  and entry points.
- **Provider:** An interchangeable implementation of an external or internal
  service contract. Providers supply effects; they do not define capability
  identity or kernel policy.
- **Workflow:** A declarative sequence or graph of capability invocations. A
  workflow describes orchestration and does not bypass per-execution policy.
- **Execution:** One runtime-controlled invocation with a correlation identity,
  validated input, execution context, state, audit trail, and normalized
  outcome.
- **Policy:** A rule evaluated before or during execution to grant, restrict,
  or deny an operation independently of what a capability requests.

### Architectural boundaries

1. **Runtime Controller** coordinates one execution. It resolves a capability,
   validates input, requests authorization, constructs context, invokes the
   handler, normalizes the result, emits events, records audit data, and maps
   failures to existing response and exit-code contracts. It contains no
   domain or provider-specific logic.
2. **Capability Registry** is the deterministic index of approved capability
   identities, versions, commands, and lifecycle states. Initially it contains
   built-in, repository-owned capabilities only. Registration does not imply
   authorization.
3. **Capability Loader** resolves an approved registry entry to a local handler.
   It accepts only configured repository-owned locations, uses canonical paths,
   verifies integrity before loading, and cannot download code.
4. **Capability Manifest Validator** validates the manifest against its pinned
   schema, rejects unknown or malformed structures, checks identity and command
   uniqueness, verifies runtime API compatibility and integrity metadata, and
   passes declared requirements to policy evaluation. Validation does not grant
   permission.
5. **Execution Context** is an immutable, per-invocation view containing the
   correlation ID, environment, approved configuration, deadline, dry-run and
   diagnostic modes, authorized provider handles, bounded state/checkpoint
   access, event and audit sinks, and the effective permissions. It must not
   expose undeclared ambient credentials or unrestricted host access.
6. **Policy and Permission Evaluator** computes effective authorization from
   the manifest request, caller and environment policy, capability approval,
   and execution parameters. It is deny by default, narrows rather than expands
   requested permissions, and records its decision and rationale for audit.
7. **Provider Interface** defines stable, vendor-neutral contracts for effects
   such as reasoning, object storage, source control, media generation, and
   command execution. Provider implementations are injected after policy
   authorization; the kernel does not import vendor SDKs or hold vendor logic.
8. **Event Publisher** emits ordered, in-process structured lifecycle records
   for an execution. Subscribers observe events but cannot change authorization
   or mutate the execution outcome.
9. **Audit Logger** records security-relevant requests, policy decisions,
   provider use, state transitions, and outcomes without secrets or unsafe raw
   child output. Audit failure is explicit and fails closed where policy
   requires a durable record.
10. **State/Checkpoint Interface** provides capability-scoped state operations
    with explicit ownership and serialization contracts. The interface does not
    promise distributed durability, concurrency, or a database.
11. **Workflow Interface** defines declarative invocation nodes, dependencies,
    inputs, outputs, and failure behavior. Every node is a normal authorized
    execution; workflow orchestration receives no additional privilege.
12. **CLI Adapter** preserves existing CLI forms, translates arguments into
    runtime requests, and renders the existing structured response envelope and
    exit codes. It contains presentation and compatibility logic, not domain
    behavior.

The Controller depends on the other interfaces, but implementations remain
replaceable. Capabilities cannot reach around the Controller to obtain
providers, state, secrets, subprocesses, or audit sinks.

### Minimal trusted kernel

The initial kernel may:

- discover approved local capabilities;
- validate manifests and command input;
- create an execution context;
- enforce declared and independently authorized permissions;
- invoke capability handlers;
- normalize responses;
- emit audit events; and
- return standardized exit codes.

The initial kernel must not include autonomous AI planning, persistent
distributed messaging, complex workflow scheduling, dynamic remote plugin
installation, marketplace behavior, arbitrary downloaded code execution,
multi-agent coordination, production databases, or cloud-provider-specific
logic. These exclusions constrain both implementation and dependency choices.

### Capability identity

The canonical command identity is a stable, lowercase dotted name:

```text
namespace.capability.command
```

Segments use ASCII letters and digits, begin with a letter, and may contain
single hyphens. Names are globally unique within a runtime API version and are
not reassigned to different semantics. A two-segment identity is permitted
when the capability and command are naturally the same operation, preserving
existing names such as `system.info`, `bootstrap.check`, `bootstrap.local`,
`platform.plan`, and `platform.up`; `security.scan` is another valid example.
Aliases belong to the CLI Adapter and do not change canonical identity.
Existing CLI commands are not renamed as part of this decision.

### Capability manifest

A capability manifest conceptually contains:

- `schema_version`: version of the manifest document format;
- `name` and `namespace`: stable capability identity components;
- `version`: immutable capability implementation version;
- `description`: human-readable purpose without executable semantics;
- `runtime_api_version`: supported kernel contract version;
- `entry_point`: a constrained reference to an approved local handler;
- `commands`: canonical command identities and handler mappings;
- input and output schemas for each command;
- `permissions`: requested effect categories and their narrow scopes;
- `required_providers`: provider interface names and compatible contract
  versions, never vendor credentials;
- compatibility constraints for the runtime and supported environments;
- integrity metadata binding the manifest and implementation to reviewed
  provenance; and
- lifecycle status such as experimental, active, deprecated, or retired.

The concrete schema and serialization format are M2.1 implementation details.
They must be deterministic, versioned, reject unknown security-sensitive
fields, and be covered by valid and adversarial fixtures before use.

### Permissions and policy

Permissions are declared with deny-by-default scopes for:

- filesystem reads and writes;
- network destinations or provider access;
- subprocess execution, including executable and argument constraints;
- secret identities and purpose-bound access;
- Docker socket access;
- privileged host operations;
- repository modification; and
- external AI-provider access.

A manifest declaration is necessary but not sufficient. Runtime policy must
independently authorize each request for the caller, environment, capability
version, command, and execution mode. Undeclared access and declared but
unauthorized access are denied. A provider handle conveys only the authorized
operations; raw credentials are not added to capability input, output, logs,
events, checkpoints, or error messages. New permission categories and any
expansion of existing scopes require security review.

### Security boundaries

The kernel and admission process apply the existing security and supply-chain
policies to capabilities:

- untrusted, malformed, ambiguous, or unsupported manifests are rejected
  before loading;
- manifest, implementation, and approved provenance identities are bound to
  prevent plugin substitution;
- canonical repository roots and resolved-path containment checks prevent path
  traversal and symlink escape;
- approved components, exact pins, hashes, namespaces, and provenance mitigate
  dependency confusion and substitution;
- entry points use a constrained registry mapping and are never arbitrary
  import strings, shell fragments, or downloaded executables;
- effective permissions are the intersection of declarations and runtime
  policy, preventing capability privilege escalation;
- secret values are purpose-bound, minimally exposed, redacted from observable
  records, and never accepted through an undeclared ambient channel;
- subprocesses use reviewed executable paths, argument arrays, fixed working
  directories, bounded environments, and timeouts; shell-string evaluation is
  prohibited;
- provider credentials remain within provider implementations, with access
  scoped and audited to prevent credential reuse or confused-deputy behavior;
- audit records exclude secrets, include correlation and integrity context,
  and are written through a kernel-controlled sink inaccessible to capability
  mutation;
- unsupported runtime API versions fail before handler resolution; and
- capability artifacts follow component approval, license, vulnerability,
  integrity, SBOM, provenance, exception, and rollback controls already defined
  by VSS policy.

Dynamic third-party capability installation is explicitly deferred until
signing, provenance verification, trust policy, execution isolation, and
revocation are designed and validated together. A manifest alone is never a
trust assertion. M2 does not authorize marketplace installation or execution
of externally downloaded capability code.

### Provider independence

Capabilities consume abstract provider interfaces rather than importing
vendor-specific SDKs into the kernel. Initial interface families may include
`ReasoningProvider`, `ObjectStorageProvider`, `SourceControlProvider`,
`MediaGenerationProvider`, and `ExecutionProvider`. Each interface specifies
versioned request, response, failure, timeout, and capability semantics.

Implementations may be proprietary or open source, local or remote. They are
selected by configuration and policy, injected through the Execution Context,
and independently admitted by supply-chain policy. Capability contracts remain
stable across provider substitutions. No provider integration is created by
this ADR, and media-production functionality is outside this decision.

### Events, audit, and state

For M2.1, events are ordered in-process structured records. Audit records may
initially be append-only JSON Lines under ignored local state, with restrictive
permissions, stable schemas, correlation IDs, timestamps, policy decisions,
and outcomes. This local implementation is not represented as tamper-proof;
the interface permits a stronger sink later.

State and checkpoint interfaces may initially use in-memory or local-file
implementations. Local files must be capability- and environment-scoped,
schema-versioned, written safely, excluded from source control, and protected
from traversal. Persistent distributed messaging, production databases, and
distributed state coordination are deferred. In every case, the interface is
the architectural contract and the first local implementation is replaceable.

### Failure model

The execution request is a deterministic internal contract containing the
canonical command identity, environment, JSON input object, optional caller-
supplied correlation ID, dry-run mode, deadline or timeout, and approved
diagnostic and interactive flags. M2.1 may version this request explicitly but
must preserve the current `CommandRunner.run` semantics through the
compatibility adapter. Provider credentials, ambient environment values, and
unvalidated objects are not request fields.

Runtime outcomes reuse the current response envelope: `schema_version`,
`command`, `correlation_id`, `started_at`, `status`, `exit_code`,
`completed_at`, `duration_ms`, `output`, and safe `errors`. The envelope may
evolve only through explicit schema versioning. Errors remain bounded and safe
for display; raw exceptions, credentials, environment contents, and unreviewed
provider output are not returned.

The runtime defines the following failure categories and maps them to stable,
named exit codes:

| Category | Required behavior | Initial compatibility mapping |
| --- | --- | --- |
| Invalid manifest | Reject before loading or invocation | `INVALID_CONFIGURATION` |
| Incompatible runtime API | Reject before handler resolution | `INVALID_CONFIGURATION` |
| Capability not found | Return the requested canonical identity | `UNKNOWN_COMMAND` |
| Permission denied | Return a safe denial without attempting the effect | New named code reserved during M2.1 |
| Invalid capability input | Return the first safe schema error | `INVALID_INPUT` |
| Provider unavailable | Return a safe provider identity and retry-neutral outcome | `NOT_READY` |
| Capability execution failure | Normalize an expected or unexpected handler failure | `EXECUTION_FAILURE` |
| Timeout | Stop waiting, cancel where supported, and record the outcome | `TIMEOUT` |
| Internal runtime failure | Hide internals and preserve correlation for diagnosis | `INTERNAL_ERROR` |

M2.1 will assign any new numeric code without changing existing numeric values.
Compatibility tests must prove that legacy commands retain their current
envelopes and exit behavior throughout migration.

### Compatibility and migration

Migration proceeds by vertical slices:

1. **Phase 1:** Existing commands continue to work unchanged through the
   current registry, handlers, CLI forms, response envelope, and exit codes.
2. **Phase 2:** Existing command metadata and handlers are represented
   internally as built-in capabilities through a compatibility adapter. The
   adapter must not change externally observable command behavior.
3. **Phase 3:** New domain functionality is created only through the capability
   SDK and its manifest, testing, policy, and provider contracts.
4. **Phase 4:** Legacy command registration is deprecated only after equivalent
   built-in capability support is stable and compatibility tests demonstrate
   parity. Removal requires a separate decision and communicated lifecycle.

The existing command engine is an implementation asset, not discarded code.
Its registry discovery, input validation, context, execution, timeout, safe
error, envelope, and exit-code behavior inform the first kernel interfaces.

### M2 delivery sequence

1. **M2.1 Runtime Kernel:** Define and test the minimal local registry,
   manifest schema and validator, controller, execution context, policy hooks,
   normalized outcomes, in-process events, and local audit/state interfaces.
2. **M2.2 Workflow Execution:** Add a small declarative workflow interpreter
   over ordinary capability executions, without distributed scheduling.
3. **M2.3 Capability SDK:** Publish the supported authoring, manifest, schema,
   test-fixture, and compatibility contracts for repository-owned capabilities.
4. **M2.4 Provider Abstraction:** Stabilize provider interfaces and introduce
   independently reviewed implementations through configuration and policy.
5. **M2.5 Migration of existing built-in commands:** Adapt current commands in
   vertical slices while retaining CLI and response compatibility.

Each milestone is separately reviewable. Later milestones do not expand the
M2.1 trusted core by implication.

## Alternatives Considered

### Continue expanding hardcoded CLI commands

This has the lowest immediate cost and preserves the current model, but shared
policy, audit, provider, and state behavior would continue to spread across
handlers. Domain growth would increase coupling and make consistent permission
enforcement difficult.

### Build a microservice platform immediately

Services could provide independent scaling and deployment boundaries, but VSS
does not yet require distributed operation. Networking, service identity,
durable messaging, deployment, and production data stores would enlarge the
trusted and operational surface before capability contracts are understood.

### Use a third-party workflow engine as the runtime

A workflow engine could accelerate scheduling and persistence, but its model
would dictate core interfaces and add substantial supply-chain and operational
scope. Workflow orchestration is only one consumer of capability execution and
must not become the security kernel.

### Build an agent-first architecture

Agent planning can select operations dynamically, but it is nondeterministic
and introduces prompt, model, tool-selection, and authorization risks. It does
not replace typed capability contracts or policy enforcement. Autonomous AI
planning and multi-agent coordination are outside the initial kernel.

### Adopt the capability-oriented kernel

This creates one narrow control point for validation, authorization, execution,
audit, and outcomes while keeping domain behavior and provider implementations
outside the core. It supports local-first vertical slices and gradual reuse of
the existing engine. This alternative is selected because it provides the
needed extensibility and security boundaries without prematurely adopting a
distributed platform or autonomous planner.

## Consequences

Positive consequences include common execution controls, provider independence,
improved fixture-based and contract testing, stronger centralized policy
enforcement, gradual extensibility, and reusable domain capabilities. Existing
commands retain a supported migration path and local development remains the
default.

Costs and risks include manifest and runtime API versioning, an ongoing
compatibility burden, plugin security, migration effort, the possibility that
the kernel accumulates domain behavior, and the temptation to overbuild
abstractions before real use cases exist.

These risks are mitigated by keeping the kernel minimal, starting with built-in
capabilities, prohibiting dynamic external plugins initially, versioning APIs
explicitly, requiring security review for every new permission, developing
vertical slices, and maintaining compatibility tests for commands, envelopes,
schemas, and exit codes. New abstractions require evidence from at least one
concrete vertical slice and must not move provider or domain logic into the
kernel.

## Unresolved Questions

The following are intentionally left to M2.1 design and separate review:

- the concrete manifest serialization format, schema identifier, and supported
  runtime API version-negotiation range;
- the exact new numeric exit code for permission denial;
- the approved built-in capability directory and integrity-binding mechanism;
- audit retention, rotation, integrity strengthening, and behavior when the
  local sink is unavailable;
- cancellation guarantees for timed-out handlers and providers; and
- the minimum provider contract needed for the first nontrivial vertical slice.

None of these questions permits dynamic external installation, weakens
deny-by-default authorization, or changes existing command behavior.

## Verification

Validate this decision with:

```bash
./scripts/validate_adr.sh
git diff --check
```

During M2 implementation, add compatibility and adversarial tests for manifest
validation, path containment, identity/integrity substitution, permissions,
safe failures, audit records, response envelopes, and unchanged legacy command
behavior before migrating any command.
