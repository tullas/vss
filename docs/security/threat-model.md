# VSS security threat model

## Scope, assets and adversaries

Assets include source/review history, workflow identities, credentials,
developer/root boundaries, Docker socket, IaC state, dependency locks,
approvals/exceptions, release artifacts, SBOMs and provenance. Adversaries
include compromised upstreams/accounts/actions/images/providers, malicious PRs
or dependencies, local unprivileged users, and mistaken or over-privileged
operators/agents.

## Trust boundaries and abuse cases

- Developer shell to bootstrap, then validated developer identity across sudo
  to root Ansible. Abuse: repository/path substitution or malicious package
  scripts. Mitigation: owner/passwd validation, single sudo boundary, signed
  repositories, recorded key fingerprints and independent review.
- Repository/PR to GitHub-hosted runner and third-party Actions. Abuse: tag
  retargeting, token exfiltration, gate deletion. Mitigation: SHA pins,
  read-only permissions, CODEOWNERS, policy invariants and external required
  rulesets.
- PyPI/APT/registries to build/bootstrap. Abuse: dependency confusion or
  compromised release/key. Mitigation: exact hashed Python locks, component
  admission, provider/image digests, vulnerability/license scans. APT snapshot
  reproducibility remains deferred.
- OpenTofu core to executable provider, then Docker socket. Abuse: provider or
  container obtains host-root-equivalent control. Mitigation: checksum lock,
  exact provider pin, approved image digest, named local developer only, never
  expose the socket to untrusted CI workloads.
- Secrets to process/OpenTofu/container/state/log/artifact. Abuse: diagnostics
  or generated evidence leaks values. Mitigation: ignored state/tfvars, fixed
  summaries, artifact allowlist and secret-canary tests.
- VSS agent/command execution and future plugins/workflows. Abuse: shell/argv
  injection, capability escalation or autonomous risk acceptance. Mitigation:
  argv execution, schemas, timeouts, explicit capability authorization,
  independent approval and deny-by-default future plugin admission.
- Repository-controlled capability manifest to the M2.1 Runtime Kernel and
  built-in handler. Abuse: unsafe YAML construction, malformed or substituted
  manifests, path/symlink escape, arbitrary module import, permission
  escalation, secret disclosure, or audit injection/tampering. Mitigation:
  safe YAML loading, strict versioned schemas, fixed built-in discovery root,
  canonical containment checks, constrained local entry points, manifest
  digest revalidation before import, deny-by-default runtime policy, input
  schemas, append-only structured audit records, and adversarial tests. Local
  audit files are not tamper-proof and remain a residual risk.
- Repository-controlled workflow YAML to the M2.2 sequential interpreter and
  operation adapters. Abuse: unsafe YAML construction, path or symlink escape,
  expression/shell injection, arbitrary operation selection, recursive or
  excessive execution, secret-bearing audit data, or bypass of per-operation
  controls. Mitigation: safe YAML loading, a strict versioned schema, fixed
  built-in discovery root, canonical containment and digest revalidation, a
  two-operation code allowlist, bounded step counts and timeouts, no
  interpolation/includes/conditions, stop-on-failure semantics, M2.1 policy
  enforcement for both allowlisted capabilities, bounded result normalization,
  and structured input-free audit events.
- Repository-controlled SDK-authored capability code to the in-process M2.3
  handler contract. Trusted code may still be defective: it can return unsafe
  objects, raise exceptions, accidentally disclose data, or assume permissions
  it was not granted. Mitigation: immutable bounded contexts, an empty safe
  configuration view by default, typed results and errors, strict JSON size and
  depth limits, input/output schemas, manifest-to-handler identity/version
  binding, deny-by-default policy, controller-only acceptance tests, filtered
  exceptions, and input-free audit records. These contracts reduce accidental
  privilege and disclosure; they are not process isolation and cannot contain
  malicious built-in Python.
- Repository-controlled provider metadata and implementation code to the M2.4
  provider boundary. Abuse: provider substitution, malicious or defective
  implementation code, compromised dependencies, credential misuse, overbroad
  capability access, unsafe provider output, or direct implementation
  instantiation. Mitigation: strict safe-loaded manifests, fixed built-in roots,
  path and symlink containment, manifest and implementation digests, approved
  implementation identity and source classification, static selection, exact
  provider requirements, independent deny-by-default authorization,
  non-enumerable narrow handles, output normalization, input-free provider audit
  metadata, and adversarial tests. The local clock has no dependencies or
  credentials. Built-in Python providers remain trusted in-process code and are
  not sandboxed; these controls do not contain a malicious reviewed provider or
  capability that deliberately imports implementation modules.
- Runtime-owned M2.5 host inspection to approved local executable and socket
  probes. Abuse: arbitrary executable or argument selection, shell injection,
  PATH substitution, permission inflation, raw subprocess disclosure, or
  capability bypass of audit. Mitigation: a single non-enumerable
  `bootstrap_check()` context method, exact capability-scoped permissions,
  fixed executable and argument allowlists, resolved approved system paths,
  empty subprocess environments, fixed loopback ports, bounded normalized
  version output, controller-only invocation, and input/output-free audit
  records. This boundary constrains defective trusted code; in-process Python
  remains unsandboxed.
- Repository-owned M3.1 semantic schemas and fixed registry metadata to inert
  validated request/result objects. Abuse: contract or schema substitution,
  version downgrade, universal-object growth, extension-bag or multiple-payload
  injection, identity/payload mismatch, dynamic registration or arbitrary
  schema/module loading, provider-native or prompt-field injection, oversized
  or recursive objects, post-validation mutation, false confidence authority,
  evidence references treated as source access, registration treated as
  authorization, or sensitive error disclosure. Implemented mitigation: four
  exact repository-contained non-symlink schema paths; Draft 2020-12 schema and
  identity checks; no caller-selected schema root; no external or cyclic
  references, duplicate JSON keys, imports, plugins, environment or CLI schema
  overrides; immutable registry/schema snapshots and validated values;
  exact-version task/family resolution; one typed payload; strict unknown-field,
  size, depth, node, integer and JSON-type bounds; deterministic canonical
  digests; qualified non-authorizing confidence; inert evidence identifiers;
  safe payload-free errors; and adversarial tests. Schema and registry digests
  prove recorded integrity, not signatures, authenticity, authorization, or
  truth. Provider invocation, Knowledge Package resolution, Plan IR, approval,
  execution, signing, third-party registration and production audit are not
  implemented and remain governed by later milestones and accepted ADRs.
- Validated M3.1 requests to the M3.2 deterministic Reasoning Gateway, strategy,
  provider, candidate result and local audit. Abuse: strategy or provider
  substitution, implementation-path injection or self-selection, result
  validation bypass, request/result or correlation substitution, fabricated
  facts/evidence, false confidence, constraint misrepresentation, budget or
  deadline bypass, mutable invocation state, environment-dependent output,
  provider exception or semantic-payload leakage, duplicate audit outcomes,
  audit-write failure, output injection, instruction-like input treated as
  authority, or hidden capability/workflow invocation. Implemented mitigation:
  one immutable repository-built registry and exact trusted identities; no
  dynamic imports, plugins or caller-selected implementations; narrow immutable
  context without Runtime internals, secrets, filesystem/network/subprocess or
  audit handles; exact repository policy; one bounded provider call and at most
  eight iterations; pre/post deadline and result-size checks; independent M3.1
  request and result validation; exact request/correlation binding; stable
  content digests independent of machine state; empty facts and external
  evidence; qualified low confidence and explicit limitations; safe typed
  errors; and one final payload-free audit record whose write failure is fatal.
  The CLI bounds reads before JSON decoding, rejects special input files, and
  rejects non-finite, non-positive, boolean, or over-ceiling timeout values;
  unsafe outer correlation identities are not copied into audit records.
  Instruction-like text remains inert data, and neither successful validation
  nor deterministic output grants authority. Built-in Python remains trusted
  in-process code, local JSONL audit remains development-only, and process
  isolation, durable production audit, Knowledge Packages, Plan IR, approvals,
  external providers and all execution remain deferred.
- Repository-owned M3.3 performance profiles and fixed fixture to the shared
  M3.2 Gateway, development audit reader, metrics, and local report writer.
  Abuse: profile or arbitrary-command injection, report path escape or symlink
  overwrite, unbounded submission or benchmark denial of service,
  request/result or audit association mix-up, correlation collision, partial
  completion reported as success, semantic payload or environment leakage,
  malformed/non-finite metrics, divide-by-zero or wall-clock misuse, executor
  and descriptor leaks, failure contamination, and laptop results presented as
  production evidence. Implemented mitigation: three exact immutable profiles;
  hard request, concurrency, outstanding-work, duration, stress and endurance
  ceilings; no numeric, provider, strategy, command, network or implementation
  override; independent per-request data and identities; the real Gateway and
  normal validation/policy/audit path; monotonic durations; tested nearest-rank
  percentiles and measured-phase throughput; bounded offset-based audit
  selection with rotation/truncation/partial-tail detection and exact terminal
  event, implementation, status, execution and request association; serialized
  complete in-process JSONL appends; allowlisted environment
  and approximate resource metadata; strict 256 KiB payload-free report schema;
  fixed ignored output root, restrictive modes, symlink rejection and atomic
  no-clobber placement; safe errors; and structural CI gates without brittle
  latency SLOs.
  The report digest is integrity evidence only and successful measurement grants
  no authority or production certification. Production admission control,
  multi-process audit locking, durable audit/state, process isolation,
  distributed workers, autoscaling, cloud validation, external-provider and
  movie-media performance remain deferred.
- Repository-owned M3.4 Knowledge Contract Registry, fixed local fixture source,
  `reference_note/1`, and bounded `knowledge_package/1`. Abuse: arbitrary path
  or source selection, traversal and symlink/special-file reads, oversized or
  duplicate-key input, schema/item/package substitution, dynamic references or
  registration, identity/payload mismatch, classification downgrade, trust
  inflation, purpose expansion, stale/expired/revoked replay, lineage or digest
  forgery, conflict/uncertainty suppression, prompt injection, mutation after
  validation, audit leakage, and false truth or authority inference.
  Implemented mitigation: exact source and schema mappings; bounded no-follow
  regular-file reads; strict JSON and immutable schema snapshots; typed payload
  and fail-closed cross-field validation; explicit classification, trust,
  purpose, freshness, lifecycle, retention, an immutable policy-owned
  revocation snapshot, conflict and uncertainty metadata; independent
  item/package integrity and ordered lineage checks; and one safe terminal audit
  attempt whose failure is fatal. The committed deterministic fixture's fixed
  validation time is admitted only when its exact event identity and complete
  digest match; other packages use the current validation time.
  Instruction-like text remains inert. Registration, provenance, trust, freshness, classification and
  integrity grant no truth, disclosure, source access, reasoning, approval, or
  execution authority. Connectors and credentials, production storage/audit,
  signing/encryption, privacy/residency/deletion enforcement, persistent
  revocation, cache invalidation, search/indexing, external providers, reasoning
  consumption, Plan IR, approvals and execution remain deferred.
- Repository-owned M3.5 Context Contract Registry and deterministic Context
  Assembly. Abuse: package substitution, arbitrary request/path input, purpose
  expansion, classification downgrade, trust inflation, stale or revoked
  replay, required/optional manipulation, nondeterministic ordering, duplicate
  identity conflict, budget bypass, digest confusion, conflict or uncertainty
  suppression, evidence references treated as access, payload leakage, or
  CommandRunner drift into a second control plane. Implemented mitigation:
  exact repository schemas and compatibility mappings, bounded no-follow input,
  independent M3.4 package revalidation, exact policy/task/family/project/
  environment checks, current freshness and revocation validation, immutable
  request/policy/registry snapshots, deterministic identity ordering, explicit
  required/optional semantics, complete-note-only minimization, preserved
  conflict/uncertainty/provenance qualifications, distinct content/selection/
  event digest domains, independently validated Context and Assembly Report,
  payload-free audit, safe errors, and routing-only CLI integration. Context and
  reports grant no provider/source/execution authority and are not delivered to
  the Reasoning Gateway in M3.5. Context caching, reuse, persistent revocation,
  provider translation, production audit, process isolation, and M3.6 delivery
  remain deferred.

Residual risks include hosted-runner administration, repository ruleset
configuration, mutable APT repository contents, Docker group privilege,
scanner-database availability, and unsigned provenance consumer verification.
Signed capability bundles, revocation, external trust roots, isolation for
third-party code, and third-party capability provenance remain deferred;
dynamic third-party capability installation is prohibited until those controls
are designed and validated.
### M3.6 governed Context delivery

The reasoning boundary revalidates Context integrity, exact request/correlation
binding, lifecycle, expiry, and the deterministic fixture revocation snapshot
before delivery. The provider receives only a bounded typed view and no package,
source, registry, audit, or evidence-resolution capability. Invalid Context does
not fall back to context-free reasoning. Persistent revocation, authenticated
Context artifacts, durable audit, and process isolation remain deferred.
### M4.1 movie contract threats

The bounded movie registry, strict schemas, closed declarations, original
fixtures, source/interpretation provenance categories, exact digests, and
immutable models mitigate Movie God Objects, arbitrary annotations, source or
fixture leakage, identity substitution, fabricated interpretation, and
instruction-like story text. Rights and cultural qualifications remain claims
requiring separate legal or human review; no provider, Context, parser,
execution, or media capability exists in M4.1. Persistent revocation, durable
audit, and production isolation remain deferred.
## M4.2 scene breakdown boundary

M4.2 adds a repository-owned, versioned structural marker catalogue and a
task-specific immutable scene Context. Marker processing is bounded and does
not interpret ordinary prose as a command or scene transition. Context and
source substitutions are bound by project, request, correlation, family,
purpose, and digests. Fallback segmentation remains qualified and ambiguous;
it is not artistic or historical truth. The provider receives no package,
filesystem, network, Runtime, capability, workflow, or audit handle. Advanced
screenplay parsing, persistent revocation, rights verification, cultural expert
review, process isolation, production options, and Plan IR remain deferred.

## M4.3 governed production-options boundary

M4.3 treats every option as an inert alternative, never a plan, ranking,
recommendation, selection, approval, or executable instruction. Strict schemas
and recursive field rejection prevent hidden ranking, winner, workflow,
capability, model, prompt, and execution fields. Catalogue order is explicitly
labelled non-ranking.

Exact breakdown, scene ID/content digest, Context, catalogue, policy,
strategy/provider/API, option-content, payload, semantic-result, and
complete-result bindings mitigate scene, Context, catalogue/profile, option,
and result substitution. Purpose expansion, classification downgrade, trust
promotion, invalid-Context fallback, excessive option generation, and mutation
after validation fail closed. Expiry and current revocation are checked
immediately before the sole provider call; pre-provider failure has zero calls
and no retry or fallback.

The Gateway-owned provider view limits overexposure and contains no full
Context/breakdown, report, policy object, revocation snapshot, registry, schema,
audit, Runtime, capability, workflow, path, file, connector, callback, network,
subprocess, approval, or execution object. Rights and cultural values remain
qualified claims, never clearance or authority. Ambiguity, conflicts, unknowns,
limitations, and external-validation requirements cannot be suppressed.
Independent semantic-honesty checks reject fabricated feasibility, verified
cost/duration, guaranteed quality, availability, clearance, conflict
resolution, or artistic understanding. Safe audit metadata excludes scene and
option bodies; audit failure prevents false success. CommandRunner only loads
bounded files and routes calls, preventing policy drift.

Implemented here are local structural contracts, Context/reasoning audit
association, deterministic in-process provider isolation by interface, and
known-empty local revocation. Deferred are ranking, selection, approval, Plan
IR, execution, scheduling, budgeting, external AI, media generation, durable
audit, persistent revocation, and process isolation. Local JSONL is
development-only and trusted Python remains in-process.

## M5.1 character continuity contract threats

M5.1 treats character references, identities, chronology sequences,
observations, and results as untrusted inert data until strict validation.
Exact ASCII IDs, project/source/breakdown/scene/sequence bindings, content
digests, closed category payloads, conservative bounds, immutable schema and
registry snapshots, recursively immutable validated values, and independent
cross-field resolution mitigate character or scene substitution, display-name
collision, alias confusion, actor/character conflation, chronology or sequence
substitution, observation injection, arbitrary state/category fields, Unicode
identity confusion, digest substitution, mutation after validation, and
unbounded observation sets.

Positive-only v1 observation states prevent silence from becoming absence.
There is no persistence inheritance, contradiction discovery, repair,
recommendation, Plan, approval, or execution field. Nested transition and
contradiction records require exact resolved observations and remain explicit,
qualified, inert structures. Provenance and confidence establish traceability
and qualification only; they do not establish truth, rights clearance,
cultural authority, performer identity, or Runtime authority.

The future Context name is structural expectation only. No Context family,
provider, rule engine, Gateway route, fallback, retrieval, or audit path exists
in M5.1, preventing future-implementation confusion and CommandRunner policy
drift. Deferred to M5.2/M5.3 are Context expiry/revocation, provider-view
minimization, governed rule admission, contradiction discovery, and bounded
analysis performance. Persistent revocation, durable audit, process isolation,
external AI, alias/entity resolution, and production controls remain deferred.

Cross-artifact dependencies are mandatory at the M5.1 validator boundary.
Raw dictionaries, omitted dependencies, incomplete or extra reference sets,
and artifacts of the wrong validated family cannot be promoted into a returned
validated identity, sequence, observation, task, or result. Public validation
errors use stable Movie-domain messages and do not concatenate jsonschema
messages that could echo source-controlled values or schema details.

## M5.2 governed character continuity reasoning threats

M5.2 admits only exact executable task v2; historical validation-only task v1
fails before provider invocation. Independently validated sequence, identity,
and observation artifacts plus project, scene, position, category, and digest
bindings mitigate character, sequence, chronology, observation, Context,
provider-view, result, and digest substitution. Context expiry and immutable
semantic revocation are checked at assembly and immediately before the sole
provider call. Invalid, expired, revoked, mismatched, or downgraded input has
zero calls and no fallback.

Gateway eligibility uses its policy-owned UTC clock; exact expiry is ineligible
and the final gate is independently rechecked. Fixture time cannot be selected
without the exact committed fixture identity and digest. The Movie-domain
immutable revocation snapshot is federated input, not a universal registry;
Character Continuity queries exact target types and digests only. Audit records
retain the actual expiry, revocation, and provider-attempt outcomes even when a
later stage fails.

The minimal immutable provider view excludes Runtime, CommandRunner, registry,
audit, report, policy objects, filesystem/network handles, capabilities,
workflows, assets, and execution objects. Closed categories and positive-only
payloads prevent actor/performance injection, arbitrary provider fields, and
silence becoming negative state. Exact IDs prevent display-name, alias,
Unicode, transliteration, or similarity-based identity inference. Explicit
positions prevent scene ordinal or input order from becoming chronology.
Persistence remains off, and M5.2 discovers neither transitions nor
contradictions; supplied structural claims remain qualified and inert.

Canonical ordering, bounded scenes/characters/observations/comparisons/bytes,
per-request immutable state, and independently bound audit records mitigate
denial through excessive observations and concurrent request mix-up. Safe
audits contain counts and digests rather than observations, labels, or evidence
content; one terminal attempt is made and audit failure is fatal. M5.3
contradiction discovery, persistent revocation/audit, external AI, process
isolation, and all Asset/Compute production controls remain deferred.

Semantic-honesty enforcement examines only closed semantic prose fields. It
does not scan Python object representations or evidence identifiers, avoiding
identifier-controlled denial while the closed result schema and independent
validator reject provider-native, action, Plan, approval, and execution fields.

## M5.3 bounded continuity-analysis threats

M5.3 prevents transition fabrication and rule substitution through independently
validated transition evidence, exact endpoint IDs/digests and positions,
Context-v2 binding, catalogue-1.1 digest binding, and independent result
validation. Caller-selected rules/providers, prior-result substitution,
chronology substitution, duplicate transition IDs, and forged endpoints fail
before provider execution. Result provenance binds the transition-evidence
identity and digest without carrying its governance object into the provider.

The closed catalogue has no incompatible pair for the positive-only vocabulary,
so differing values and non-mention cannot fabricate contradictions, absence,
loss, recovery, or persistence. `review_suggested` remains inert semantic-review
metadata, never severity, approval, scheduling, or execution authority. Future
negative-state vocabularies or incompatibility rules require explicit contract
and catalogue evolution.

## M6.1 manual/synthetic shot observation threats

M6.1 treats every Shot Cinematography Observation as untrusted inert data.
Exact contract dispatch, bounded JSON validation, closed attribute values,
explicit unavailable states, fixed manual/synthetic provenance pairings, and
content digests mitigate field injection, version fallback, provenance
substitution, fabricated precision, and silent inference. Evidence references
are identities only and grant no file, network, media, rights, truth, promotion,
recommendation, Runtime, or execution authority. No decoder, model, provider,
Gateway route, storage, retrieval, Pattern, Lesson, or Knowledge path exists.

## M6.2 bounded shot observation Context threats

M6.2 independently revalidates every raw M6.1 observation at set admission and
again at Context Assembly. Exact identity/version/digest/shot bindings,
single-project/single-scene/single-classification scope, unique identities, and
canonical unordered representation reject substitution, duplicates, caller
resealing, purpose/version fallback, classification downgrade, and order-based
chronology. The 2–8 bound limits Context nodes and caps any future pairwise work
at 28 comparisons without performing comparisons now.

The immutable Context projects only qualified attributes, bounded evidence
identity, manual/synthetic provenance, and limitations. It contains no media,
path, callback, Runtime capability, registry, provider, execution resource, or
promotion artifact. Assembly performs no filesystem, network, subprocess,
model, reasoning, recommendation, Pattern, Lesson, or Knowledge operation.

## M6.3 deterministic shot-pattern threats

M6.3 revalidates the exact Context and task before its sole provider call and
binds the Context, catalogue, provider view, implementation identities, and
observation IDs/content digests into the invocation digest. Independent result
validation recomputes the closed rules from the admitted Context; fabricated
recurrence, omitted or duplicated evidence, resealed Context projections,
provider-result substitution, incomplete bindings, catalogue substitution, and
pattern amplification from duplicated observations fail closed.

Only `observed` values participate. Exact exclusion records retain uncertain
and unavailable qualifications, preventing qualification erasure or absence
inference. Occurrence counts are never represented as probability, confidence,
truth, authority, recommendation, Lesson, or Knowledge. The 2–8 Context bound,
eight fixed attributes, two pattern types, threshold two, and 40-pattern result
cap bound work and output. There are no combinations, pairwise scans, retries,
fallbacks, files, network, subprocesses, dynamic imports, raw media, models, or
Runtime capabilities. Dry-run performs all admission and binding work but calls
no provider and fabricates no result.

## M6.4 deterministic cinematic Lesson Candidate threats

M6.4 independently revalidates the M6.3 Pattern Set against its exact source
task, Context, and invocation binding before the sole provider call. The M6.4
task, provider view, invocation binding, candidate, and result bind the source
Pattern Set and Context digests. Each candidate additionally binds the exact
Pattern identity, Pattern digest, and supporting-evidence digest. Independent
result recomputation rejects Pattern substitution, forged or omitted Lessons,
evidence omission, duplicate amplification, scope expansion, qualification
removal, outer-hash resealing, and catalogue or provider substitution.

There is no caller-supplied prose: closed structured propositions prevent
recommendation, causal, effectiveness, truth, and persuasive-language
injection. Fixed limitations preserve exact Context scope, observed-only source
semantics, non-generalization, and non-admission to Knowledge. One Pattern maps
to at most one candidate, with no cross-Pattern synthesis. Bounds cap both
source Patterns and candidates at 40. The provider has no files, network,
subprocess, dynamic import, raw media, model, Knowledge store, Runtime
capability, retry, or fallback. Dry-run calls no provider and creates no result.

## M6.5 admitted cinematic Knowledge threats

M6.5 accepts only a validated M6.4 Lesson Candidate whose Pattern Set and
Context lineage are independently revalidated. Admission requires a closed,
human-attributable decision and exact project/domain scope; actor, decision,
candidate, Pattern, Context, and digest substitution therefore fail closed.
There is no automatic promotion, provider admission path, recommendation text,
external source, or cross-project generalization.

Knowledge content is immutable and storage-neutral. Lifecycle events are
versioned and human-attributable; malformed or ambiguous chains, challenge,
withdrawal, revocation, and supersession make current-use eligibility fail
closed while preserving historical artifacts. This prevents stale Knowledge,
evidence laundering, scope escalation, duplicate admission, and lifecycle
resealing from becoming current input. No persistence service, Runtime authority,
or Knowledge promotion workflow is introduced.
