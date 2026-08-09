# Post-ADR-0022 Source-Conformance Checkpoint

## 1. Review metadata

- Review date: 2026-08-08
- Authoritative reviewed `main`: `c3c91b4e81fd600131b4ff03b8e19303ba4ce98d`
- Review branch: `review/post-adr-0022-source-conformance`
- Scope: Python/source architecture through M5.1 and constitutional review
  governance immediately before M5.2
- Method: source and AST import inspection, public-path traces, registry/audit/
  freshness/resource review, future-workload stress, negative-space review, and
  complete repository validation

This is a point-in-time checkpoint, not an ADR.

## 2. Executive verdict and M5.2 readiness

**Checkpoint verdict: Accepted with non-blocking guardrails.** ADR-0021 and
ADR-0022 constrain future generalization but do not invalidate current source.
No current authority, registry, freshness, resource, or plane violation was
found. No source correction was required.

**Is M5.2 safe to proceed without architectural redesign?**

`YES_WITH_NON_BLOCKING_GUARDRAILS`

M5.2 must remain a bounded, non-effectful Semantic Plane capability using the
existing task-specific Context and semantic Reasoning Gateway patterns. It may
not add assets, workers, heavy data, workflow/capability execution, dynamic
resource authority, Plan IR, or a second control path.

## 3. Findings

| Severity | Secondary classification | Evidence and impact | Disposition |
|---|---|---|---|
| Medium | CURRENT_TEST_GAP | Accepted dependency directions had no direct automated guard; regressions could silently couple contracts/providers to CLI or effects. | Corrected with four standard-library AST tests and focused CI wiring. |
| Low | SAFE_SCOPED_IMPLEMENTATION | `vss_workflows.operations` uses `CommandRunner` as the explicit ADR-0010 legacy compatibility adapter. It is bounded and Runtime-authorized, but must not become the general domain pattern. | Quarantined by an exact dependency test; retain until a separately justified migration. |
| Low | DEFERRED_FUTURE_GUARDRAIL | `vss_reasoning` composes built-in providers/strategies while those packages import reasoning models, creating package-level mutual dependencies. There is no authority cycle or effect access, but repeated providers may increase modularity debt. | Reassess before external provider classes or a separate provider deployment boundary; do not refactor M5.2 speculatively. |
| Observation | SAFE_SCOPED_IMPLEMENTATION | Runtime capability execution is synchronous-from-caller over a bounded thread pool with cooperative cancellation. This is correct for current local bounded work, not a durable Compute model. | Do not generalize it to workers, queues, or hours-long effects. |
| Observation | DEFERRED_FUTURE_GUARDRAIL | Dynamic cost, hardware capacity, reservation, production snapshots, cache validation, output admission, and worker isolation do not exist. | Correctly deferred to the ADR-0021/22 gates in the evidence matrix. |

There are no Critical or High findings, no `CURRENT_VIOLATION`, and no M5.2
blocker.

## 4. Dependency graph and boundaries

The inspected first-party graph has contract packages at the foundation;
Knowledge, Context, and movie services build above contracts; Reasoning composes
semantic contracts, Context, movie adapters, strategies/providers, and Runtime
audit; CommandRunner routes public domain APIs; Runtime composes capability and
provider admission; workflows retain the documented legacy command adapter.

Direct automated constraints now prove:

- contract packages do not import Runtime, CommandRunner, Reasoning Gateway,
  providers/strategies, capabilities, or workflows;
- semantic provider/strategy packages do not import Runtime, CommandRunner,
  capabilities, or workflows;
- the Reasoning layer does not import CommandRunner, capabilities, or workflows;
- direct `CommandRunner` use is confined to the known workflow adapter.

There is no domain-to-CLI reverse dependency outside that explicit adapter and
no current cycle that creates authorization or effect authority. The package
composition cycles noted above are emerging modularity debt, not a
constitutional violation.

## 5. Runtime conclusion

Runtime remains the sole current capability authorization and invocation
authority. Capability resolution, declared permissions, provider access, and
execution are distinct checks. Registry presence and provider handles confer
no authority. Runtime has no Asset Catalog, queue, worker, scheduler, render,
storage, or cache semantics and does not currently proxy production bytes.

The generic dictionary handler and bounded thread-pool interface are
`SAFE_SCOPED`: safe for today's local bounded operations, but not a permanent
API prescription for heavy data or durable work. It neither assumes
exactly-once execution nor establishes a future worker protocol.

## 6. Reasoning Gateway conclusion

All public paths—Context-free/context-aware GenerateOptions, Scene Breakdown,
and Scene Production Options—were traced. The Gateway owns semantic request and
Context validation, exact compatibility, expiry/revocation, minimized provider
views, strategy/provider admission and invocation, semantic result validation,
binding, and terminal reasoning audit.

It owns no capability/workflow invocation, worker placement, scheduling,
storage, asset transport/resolution, rendering, queue, resource reservation, or
effect recovery. Movie-specific methods are healthy domain adapters today;
continued method growth is a review trigger. M5.2 is acceptable only as another
semantic adapter, not as a general execution route.

## 7. CommandRunner conclusion

CommandRunner performs CLI-oriented bounded loading, correlation, public API
routing, and response/exit mapping. Domain services own validation, binding,
revocation, provider policy, and digests; Runtime owns authorization. Its
branching surface remains an emerging routing-maintenance risk identified by
earlier checkpoints, but it contains no Asset/Compute topology or dynamic
resource policy.

## 8. Registry inventory

| Registry | Owner/content | State and authority | Digest/evidence |
|---|---|---|---|
| Capability | Runtime/capability types and manifests | Repository discovered; registrations known-only; policy authorizes separately | Runtime registry tests |
| Provider | Runtime provider kinds/manifests | Repository discovered; policy-scoped handles; no live capacity/pricing | Provider tests |
| Workflow | Workflow types/manifests | Repository owned; Runtime invokes as capability; no queue instances | Workflow tests |
| Semantic Contract | Semantic task/result kinds and exact compatibility | Frozen/static/non-authorizing | `d3621af9feb67661ae065ef53a80971f76767f4b1ee25372b155e95afdb4f2e7` |
| Knowledge Contract | Knowledge kinds/lifecycle compatibility | Frozen/static/non-authorizing | `6e3b1941fddadade8480d30d717ad799bf1aaf13f729e1f4411769ea0a3e2f81` |
| Context Contract | Context families and exact task/result mappings | Frozen/static/non-authorizing | `a075fe561946cb4fc1101099fdb40013e0efbbaa33a2de7516cceaa3ef1970de` |
| Movie Contract | Movie/continuity contract kinds and compatibility | Frozen/static/non-authorizing | `7038570898b930aaea1193b7434b0781b303b9dc0a9022b1d03881be122213ab` |
| Reasoning implementation | Exact trusted semantic strategies/providers | Repository-owned immutable admission; no workers | Source and reasoning tests |

No registry contains asset instances, live capacity, current budget/pricing,
queue state, caches, or mutable project data. Registries describe kinds and
static compatibility; none is an Asset Catalog or dynamic policy engine.

## 9. Knowledge and Context freshness

Knowledge validation proves bounded schema/integrity, exact semantic lineage,
domain lifecycle, staleness, and revocation eligibility at its validation time.
Context Assembly revalidates applicable Knowledge, constructs a purpose-limited
snapshot, labels currency at assembly, and binds expiry/revocation. Context
validation proves only semantic delivery eligibility for its exact family.

Neither API resolves physical assets, inspects caches, proves worker data
availability, or claims production asset currency. Knowledge freshness,
Context delivery eligibility, and production artifact eligibility remain
distinct domains.

## 10. Budgets, resources, and performance

Current schemas impose hard bytes/cardinality/depth bounds. Reasoning policies
separately impose deadlines, iterations, and provider-call limits; Runtime
separately authorizes declared permissions and providers. Performance profiles
measure bounded local workloads. Schema validity, registration, and resource
availability do not authorize an operation.

Runtime does not yet implement cost, quota, GPU capacity, pricing, physical
reservation, or production overrun policy. The evidence matrix therefore does
not claim those ADR-0022 future guarantees are implemented.

## 11. Audit, telemetry, and lineage

Runtime, Knowledge, Context, and Reasoning audit records are minimized local
governance evidence associated by bounded identifiers. Audit failure is fatal
where required. Performance reports and metrics are operational evidence and
are not authorization. Current Knowledge lineage describes semantic source
derivation; it is not media lineage or output admission. Shared correlations do
not create a God Event, and no audit record grants artifact eligibility.

## 12. Provider versus future worker

Current providers consume recursively immutable, bounded semantic views and
return inert semantic candidates. Dependency tests prove providers cannot
reach Runtime, CommandRunner, capabilities, or workflows. They are not workers
and expose no scheduler, queue, storage, network, subprocess, rendering, or
large-artifact protocol. Reusing provider API v1 for an effectful worker would
contradict ADR-0021 and requires a Constitutional Board.

## 13. Evidence classification summary

The persistent [ADR evidence matrix](../architecture/adr-evidence-matrix.md)
records 26 material invariants:

- `IMPLEMENTED_TESTED`: 14
- `IMPLEMENTED_NEEDS_EVIDENCE`: 2
- `NOT_APPLICABLE_CURRENT_SEMANTIC_SCOPE`: 2
- `DEFERRED_ASSET_PLANE`: 3
- `DEFERRED_COMPUTE_PLANE`: 3
- `DEFERRED_PRODUCTION`: 2
- `VIOLATION`: 0

Machine-enforceable present boundaries now have focused dependency coverage.
Absent-worker, asset snapshot, cache, isolation, and output-admission rules wait
for their owning subsystem. Topology, workload classification, and premature
distribution remain recurring constitutional-review questions.

## 14. Future-workload stress conclusions

Bounded deterministic semantic requests remain healthy. Probabilistic AI would
require new epistemic/provider governance. Million-fold payload growth must
move bytes to the Data Plane; long duration requires durable attempts and safe
gates; fan-out requires immutable snapshots/backpressure; partial failure
requires reconciliation; in-flight revocation requires operation-specific
handling; cost exhaustion requires dynamic re-admission; disconnected caches
require exact digest resolution; untrusted plugins require hard worker
isolation; and mixed deployment must preserve identical authority and identity
meaning. None of these future properties should be retrofitted into M5.2.

## 15. What important production property currently has no architectural owner?

The following are deliberately absent from implementation, not silently owned:

| Property | Status and future trigger |
|---|---|
| Artifact promotion and output admission | Deferred; decide before first effectful artifact |
| Media delivery and production rollback | Deferred; decide before production publishing |
| Human-review queue | Deferred; decide when an approved workflow is evidenced |
| Model/media provenance | Deferred; decide before external AI or generated media |
| Persistent revocation | Deferred; required before production/external-provider use |
| Asset deletion and storage residency | Deferred; Asset Architecture ADR |
| Worker isolation | Deferred; mandatory Worker/Durable Execution ADR |
| Durable state, recovery, and reconciliation | Deferred; first queue/worker gate |

Deferral is acceptable for the current local, inert Semantic Plane. Each item is
a mandatory future decision trigger, not an implicit Runtime, Gateway, audit,
or registry responsibility.

## 16. Governance changes

The new [Architecture Review Governance](../architecture/architecture-review-governance.md)
defines Milestone and Constitutional Boards, independent falsification review,
the twelve-workload stress matrix, assumption-attack questions, negative-space
ownership, and present/future/review-only evidence classes. It avoids a giant
CI pipeline and requires no product-specific reviewer.

## 17. Corrections and validation

No production source was changed. Four focused AST dependency tests and one CI
step were added. They use only the standard library and encode accepted current
boundaries rather than speculative future packages.

Validation covers the dependency tests, M5.1 and Movie contracts, M4.2/M4.3,
Context, all M3 suites, the complete Python suite, Bash/shell, Ansible,
OpenTofu, ADR/references/JSON/JSON Schema, supply-chain/license/vulnerability,
secrets/baseline, SBOM/provenance, release/sensitive-content, and whitespace.
Final command results and GitHub checks are recorded in the pull request and
completion report for the reviewed commit.

Local validation passed 375 Python tests, 13 Bash suites, shell syntax, scoped
Ansible inventory/playbook syntax/lint, all OpenTofu environments, ADR and
repository-relative references, JSON parsing and schema-backed suites,
supply-chain policy, runtime dependency vulnerability audit, Python licenses,
secret scanning of every changed file, SBOM/provenance, release artifact and
sensitive-content checks, and whitespace. An additional non-required audit of
the bootstrap Python 3.12 lock reported `PYSEC-2026-3552` in
`cryptography==49.0.0`; the required runtime lock is unaffected and clean. This
pre-existing bootstrap-toolchain advisory is outside this documentation/test
checkpoint's permitted dependency scope and is recorded for separate
supply-chain remediation rather than hidden or misclassified as an
architecture failure.

## 18. Final decision

ADR-0021/22 clarify permanent limits around current interfaces rather than
requiring a redesign. M5.2 may proceed under the constraints in section 2.
Before Asset/Data, Compute/Execution, external AI, or effectful output work,
the named Constitutional Board triggers and deferred ADR gates are mandatory.
