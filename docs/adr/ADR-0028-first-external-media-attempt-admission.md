# ADR-0028: First External Media Attempt Admission

## Status

Accepted

## Date

2026-09-07

## Context

Issue #132 seeks one human-triggered moving-shot review candidate. Its M11.0
Strategic, Constitutional, and UNKNOWN_UNKNOWN reviews stopped that work:
the accepted architecture had deferred the first external production input and
output, dynamic spend reservation, and controlled generated-media admission.

[ADR-0010](ADR-0010-capability-oriented-runtime-kernel.md) makes Runtime the
effect authority. [ADR-0021](ADR-0021-studio-workload-planes-specialized-execution.md)
and [ADR-0022](ADR-0022-cross-plane-admission-resource-bounds-artifact-consistency.md)
reserve exact input, dynamic admission, and output-lineage rules.
[ADR-0025](ADR-0025-scoped-studio-resources-rights-canon-provenance.md) keeps
scoped artifact provenance and output admission distinct from possession or
reuse. This decision admits only the smallest local, controlled seam needed to
implement one external moving-shot attempt later; it implements nothing.

## Decision

VSS may introduce one future Runtime-authorized `external_media_attempt` for a
single human-triggered moving-shot review candidate when all rules below are
implemented and independently tested. The seam admits three bounded concerns:
an exact external production input/output boundary, one-attempt dynamic spend
admission, and controlled local review-media output admission. It does not
admit provider selection, an external call, a generic asset system, a queue,
a database, a retry policy, or production/publication authority.

### Exact input and provider boundary

The future capability receives only bounded control data. Its production input
must reconstruct—not trust a caller claim—and bind the tenant, production, and
selected-shot scope; authoritative visual-basis logical identity, immutable
revision, and exact content digest; classification, rights, purpose, lifecycle,
freshness, and revocation eligibility; relevant source lineage; provider/model
contract identity; bounded generation parameters; applicable Runtime admission
identity; and expiry. The provider adapter receives the minimum required
projection. Provider handling, processing/retention, residency, and
compatibility evidence must be bound to that adapter/model contract and to the
admitted rights, purpose, and classification. Unknown or incompatible required
provider evidence fails closed. Credentials stay in the provider/runtime
environment and never appear in contracts, audit payloads, review media, Git,
or provenance text.

Runtime validates the exact capability, provider registration, policy,
permission, human-triggered request evidence, and input binding. Cheap closed
readiness checks occur before a reservation and make no provider call or
credentialed transport. Immediately before credentialed transport, Runtime
revalidates the material bindings and creates the single attempt reservation.
The adapter may transmit the admitted visual input through the governed
data/media path, but Runtime routes authority and references rather than video
bytes. A provider request ID is evidence only; it never becomes VSS identity,
approval, or authority.

No fallback, fan-out, autonomous regeneration, or retry is admitted. Timeout,
ambiguous transport, malformed response, unavailable provider, or unknown
request status yields a terminal quarantined/failed attempt pending explicit
human reassessment; it cannot reserve or send another request.

### One-attempt spend admission

Before reservation, the future capability requires an exact currency, explicit
non-negative ceiling, provider/model price evidence or an explicitly bounded
estimate, and a remaining spend authority sufficient for the ceiling. Unknown,
stale, malformed, negative, incompatible-currency, or insufficient evidence
fails closed. Contract limits remain static; the spend decision is dynamic
Runtime admission and must not be placed in a contract registry.

The reservation is created immediately before credentialed transport and is
bound to one exact, non-reusable attempt identity and the admitted request. It
may never silently increase. Provider request/response evidence and any
returned bytes bind to that attempt identity. The terminal evidence records
reservation outcome and actual cost when the provider makes it available. Until
terminal reconciliation, the full ceiling remains consumed; unavailable,
malformed, timed-out, or ambiguous cost/request evidence is explicitly
qualified as unresolved and blocks every later attempt under the exact
approval/authority. A reservation is not payment, production approval,
provider authorization, or permission to retry. Paid-call authorization
remains a separately explicit human decision bound to the exact attempt.

### Controlled local output admission

A successful provider response is not an admitted VSS asset or released media.
The future output-admission step accepts at most one returned video artifact
only after bounded media/metadata validation, digesting the exact bytes, and
binding its tenant/production/shot scope, provider/model/request evidence,
production-input identity, derivative lineage, applicable Media BOM/provenance
fields, disposable local-review preservation class, controlled availability
expiry, and retention/deletion/residency eligibility reference owned by Data
Governance. It stores the bytes in local controlled quarantine, accessible only
for same-scope, purpose-limited local review until that expiry. It grants no
discovery, reuse, publication, promotion, or workflow-activation authority. A
local path, provider URL, matching digest, or storage possession grants none of
those rights.

Malformed, oversized, unsupported, mismatched, provenance-incomplete, or
scope/governance-incomplete output fails closed and remains unavailable for
review use. Unknown required data-governance evidence also fails closed. The
retained record is bounded evidence, not a generalized media catalog or
asset-management system. Later reuse, promotion, retention/deletion execution,
sharing, or publication requires its own governed decision and implementation.

### Ownership and implementation boundary

The existing Runtime controller/policy own effect admission and the immediate
pre-transport reservation; the existing provider abstraction owns the
replaceable provider transport; the movie visual-basis path owns source
reconstruction; and a narrowly local controlled-output adapter owns byte
validation and quarantine. These may coexist in the current local process and
filesystem. They do not introduce persistent services, databases, queues,
workers, a universal admission object, or a parallel authority path.

The first implementation must use strict bounded contracts, reconstruct
authoritative source bindings rather than trust caller-supplied digests, and
test validly resealed substitutions, malformed spend/provenance/media evidence,
preflight zero-call behavior, exact one-attempt behavior, and no-output
admission on failed/ambiguous transport. Unit and contract tests make zero paid
calls. The only paid call is a separately authorized smoke attempt after this
architecture and the implementation have passed their gates.

## Consequences

Issue #132 may submit a fresh mission assessment once this decision and its
review evidence are accepted. Its implementation remains constrained to one
review candidate and must prove the above rules through the existing Runtime,
provider, movie, integrity, audit, and review mechanisms.

The decision adds future contract and test obligations. It deliberately does
not claim that local quarantine solves general retention, deletion, residency,
multi-tenant storage, billing, or durable recovery.

## Deferred

- provider selection or integration, credentials, paid calls, and generated video;
- retries, fallback, fan-out, asynchronous worker/queue behavior, and billing;
- asset catalog/database, generalized cost system, media management, or publication;
- reusable-asset promotion, cross-production reuse, retention/deletion execution,
  sharing, release, and production approval.

## Acceptance criteria

- one Runtime-authorized, human-triggered request binds exact source and provider inputs;
- preflight is closed and makes zero provider calls; reservation occurs immediately before transport;
- one ceiling-bound attempt has terminal, fail-closed spend and provenance evidence;
- one validated output is controlled local quarantine only, with exact digest and lineage;
- no result grants retry, provider, production, publication, reuse, or workflow authority;
- no provider, paid call, persistent service, or generalized subsystem is added by this ADR.
