# M3.5 Context Assembly

M3.5 implements a local, deterministic, bounded Context Contract Registry and
one `generate_options_context/1` assembly path. It converts independently
validated M3.4 Knowledge Packages into an inert task-specific Context Object
and a separate governance-facing Assembly Report.

## Authority boundary

Context Assembly is not Runtime and is not authorization. It can only narrow
already admitted package scope. It cannot retrieve, search, invoke reasoning,
invoke capabilities/workflows, select a provider/model, approve, execute, or
grant source access. A valid Context or Report means structural validation and
assembly evidence, not truth, approval, recommendation, or executability.

The Reasoning Gateway does not receive Context Objects in M3.5. M3.6 must make
the identity/version/content-digest and correlation binding explicit before any
delivery path is added.

## Registry and contracts

`vss_context_contracts` owns the immutable repository-built registry and strict
schemas for:

- `context_assembly_request/1`
- `context_object/1`
- `generate_options_context/1`
- `context_assembly_report/1`

The exact mapping is:

`generate_options/1` + `option_set/1` + `knowledge_package/1` +
`reference_note/1` + package purpose `local_validation_context` → context
purpose `generate_options_local_validation` under
`generate_options_context_local/1`.

Unknown identities, versions, roots, schemas, or mappings fail closed. The
registry snapshots schemas during construction and never reopens them during
validation. It is independent from the Semantic, Knowledge, Runtime, Provider,
and Workflow registries.

## Assembly request and selection

The request is bounded and contains exact task/family/policy/purpose,
development environment, project binding, validation time, classification
ceiling, trust requirement, explicit package/item requirements, budgets, and a
finite deadline. It contains no paths, providers, models, prompts, queries,
connectors, tools, callables, or metadata bag.

Packages are independently revalidated through M3.4. Input package order is
normalized; items are ordered by stable item identity and digest. Same identity
and same content digest is included once. Same identity with a different digest
fails. Required content must fit completely; optional content may be omitted
deterministically. There is no clipping, truncation, summarization, excerpting,
or semantic rewriting. Full bounded reference-note title/body content is used
when admitted.

## Governance

Assembly rechecks purpose, project, environment, classification, trust,
freshness, expiry, retention, lifecycle, and the current M3.4 revocation
snapshot. Context classification cannot be lower than selected content and
cannot exceed the request ceiling. Trust remains `approved_fixture`; it is not
truth. Context expiry is the earliest applicable package, item, retention, and
policy deadline.

Conflicts, uncertainty, limitations, inert evidence references, and bounded
provenance references are preserved. Evidence references grant no file, package,
URL, connector, or source access. The Assembly Report records inclusion,
omission, rejection, budgets, digests, and lifecycle without note bodies,
packages, raw provenance, or provider-native data.

## Digest domains

The implementation distinguishes registry, package-set, selection, Context
content, report, and event-bound complete-object evidence. Content and selection
digests are stable for identical content, policy, requirements, and validation
time. Event-bound complete digests may change with event identity or report
identity. Digests provide deterministic substitution evidence only; they are not
signatures, authenticity, truth, trust, approval, or authority.

## Bounds and audit

Requests, packages, aggregate input, notes, references, conflicts, uncertainty,
reports, depth, and serialized bytes are bounded. Validated models are immutable
through supported APIs. The assembler is reusable with request state local to
each invocation. Development JSONL audit contains safe metadata and fails the
operation if it cannot be written; it remains local-only and is not durable,
tamper resistant, rotated, or multi-host ordered.

## Commands

```text
vss context assemble \
  --request tests/fixtures/context/context-assembly-request-valid.json \
  --package tests/fixtures/knowledge/knowledge-package-valid.json \
  --environment development \
  --correlation-id m3-5-local-assemble

vss context validate \
  --input tests/fixtures/context/context-object-valid.json \
  --environment development \
  --correlation-id m3-5-local-validate
```

The existing VSS response envelope and numeric exit codes are preserved.

## M3.6 boundary

M3.6 delivers a validated Context to the existing deterministic GenerateOptions
Gateway through an immutable invocation binding. It rechecks expiry and
current policy-owned revocation immediately before provider delivery and
passes only the minimal typed payload. The provider receives no package,
Assembly Report, registry, source path, or evidence-resolution capability.
The semantic request remains v1; no external provider, prompt, retrieval,
cache, or reuse is introduced.

## Deliberate non-scope

M3.5 adds no Reasoning Gateway integration or semantic schema change, provider,
prompt, AI model, connector, retrieval, search, embedding, database, cache,
Context reuse, Plan IR, approval, execution, distributed infrastructure,
production audit, process isolation, or autonomous behavior. Trusted Python
remains in-process. Persistent revocation, signing/authentication, privacy and
residency enforcement, durable storage, and long-running recovery remain
deferred.

## M4.3 scene production Context

`scene_production_options_context/1` is a federated task-specific Context
family. Its compatibility is exact: validated `scene_breakdown/1`, one scene
ID/content digest, `generate_scene_production_options/1`,
`scene_production_option_set/1`, development,
`scene_production_options_local_validation`,
`scene_production_options_context_local/1`, the deterministic profile
catalogue, and the admitted strategy/provider/API. No latest, wildcard,
name-only, implicit-semver, caller-defined, upgrade, downgrade, or
registration-order fallback exists. Assembly preserves qualifications,
minimizes the selected scene, independently validates the Context, emits a
bounded report, and writes one fatal-on-failure terminal Context audit attempt.
