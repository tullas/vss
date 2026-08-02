# Deterministic Reasoning Gateway

M3.2 implements one bounded, local reasoning path:

```text
GenerateOptions/1 request
  -> M3.1 validation
  -> fixed policy and implementation resolution
  -> deterministic strategy
  -> deterministic provider
  -> candidate OptionSet
  -> independent M3.1 result validation
  -> inert OptionSet/1 result
```

The Gateway is not an execution or approval authority. It cannot invoke a
capability or workflow, retrieve knowledge, select tools, access secrets, or
turn an option into an action. Runtime remains the sole execution and
authorization authority. Registration, lifecycle `active`, confidence,
evidence identifiers, request budgets, policy admission, and successful
validation grant no execution authority. The result is inert Autonomy Level 2
proposal data under ADR-0016.

## Fixed implementations

Repository-owned policy admits only the `development` environment, `public` or
`internal` classifications, and the `generate_options` purpose. It statically
selects these trusted built-ins:

| Role | Identity | Version | API | Lifecycle |
| --- | --- | --- | --- | --- |
| Strategy | `vss.generate-options.deterministic` | `1.0.0` | `1` | active |
| Provider | `vss.reasoning.deterministic-options` | `1.0.0` | `1` | active |

The immutable implementation registry admits no request, CLI, environment,
configuration, workflow, plugin, path, entry-point, or dynamic-import override.
The provider receives an immutable context containing only semantic routing,
the validated payload, approved identities, environment, purpose,
classification, deadline, budgets, and an audit correlation identity. It
receives no Runtime registry, audit sink, filesystem or network handle,
subprocess launcher, environment variables, secrets, connectors, approvals, or
execution interface. Built-in Python remains trusted in-process code; this is
API immutability, not a sandbox.

## Deterministic profiles and semantic honesty

The provider selects the first requested profiles from this stable order:

1. `strict_constraints`
2. `required_first`
3. `minimal_complexity`
4. `phased`
5. `conservative`
6. `balanced`
7. `efficiency_focused`
8. `validation_first`

Exactly one provider call produces from one to eight bounded primitives. The
strategy composes them into `OptionSet/1`; the provider never creates a Runtime
command envelope. Option IDs are stable profile identities. The OptionSet ID
is derived from the semantic request content and fixed contract identities,
excluding request and correlation IDs.

The output reports no facts or evidence. Confidence is `low`, explicitly based
on a structural deterministic method without external evidence. Unknowns cover
feasibility, cost, timing, and quality. Limitations state that the alternatives
are neither validated recommendations nor plans. In `OptionSet/1`, a
`constraints_satisfied` reference from this implementation means that the
request-declared constraint was structurally incorporated; it does not claim
real-world satisfaction. All submitted v1 constraints are treated as required
because the request contract does not classify them as preferred.

Determinism does not imply truth, correctness, feasibility, approval, or
authority. Prompt-injection-like and executable-looking text is ordinary inert
semantic text; keyword filtering is not a security boundary.

## Validation, budgets, deadlines, and dry-run

The Gateway validates the request before provider invocation and validates the
candidate result independently afterward. It checks exact request/result
identity and correlation binding. Unknown contracts, unsupported versions,
policy mismatches, inactive or substituted implementations, malformed provider
output, and unsupported fields fail closed.

M3.1's v1 `validation` lifecycle mode identifies the only admitted contract
use; it does not mean CLI dry-run and cannot enable execution authority.

M3.2 honors the v1 maximum-duration and maximum-result-size budgets. It allows
exactly one provider call, at most eight statically bounded iterations, no
retry, and no fallback. It checks the effective deadline before and after the
side-effect-free generation. No partial result succeeds after timeout. The
trusted in-process deadline checks are appropriate only to this bounded local
implementation and are not production isolation.

CLI `--timeout` is an optional finite positive duration in seconds, capped at
300 seconds to match the v1 request-contract ceiling. Zero, negative,
non-finite, boolean, or larger values fail closed as invalid input.

Dry-run performs contract validation, policy authorization, and fixed
implementation resolution. It does not invoke the provider and returns only
safe readiness metadata—never a fabricated `OptionSet`.

## Digests and audit

The full M3.1 result digest binds request and correlation identities. M3.2 also
reports `semantic_content_sha256`, the SHA-256 digest of the validated OptionSet
payload. Thus changing only correlation metadata changes the full envelope
digest but not the semantic-content digest. Digests are deterministic integrity
evidence, not signatures, trust, approval, truth, or authorization.

Every invocation attempts exactly one final local audit record containing safe
metadata: identities and versions, registry and request/result digests, policy
outcome, lifecycle, duration, deadline/budget outcomes, correlation, and status.
It contains no objective, constraints, options, full payload, secrets, prompts,
hidden reasoning, or provider-native data. Audit failure is fatal. The current
append-only JSONL facility is development-only and does not establish
production durability or tamper resistance.

## Local acceptance

From the repository root after installing the project:

```bash
vss reasoning generate-options \
  --environment development \
  --input tests/fixtures/reasoning/generate-options-runtime-valid.json \
  --correlation-id m3-2-local-acceptance
```

The command preserves the VSS outer response envelope. Its `output` contains a
validated `semantic_result` and `semantic_content_sha256`. Repeated invocations
produce the same semantic result content and content digest; timestamps,
command duration, execution identity, and audit timestamps may differ.
Normal laptop execution is expected to be sub-second, but that observation is
not a contractual SLO.

Add `--dry-run` to validate readiness without generation. Input is strict JSON:
duplicate object keys and non-finite values are rejected. The CLI reads at most
the 16 KiB v1 request limit from a regular file before decoding. FIFO, device,
directory, and other special-file inputs fail closed. A user-selected symlink
to a regular input file is treated as user data and is permitted; schema and
implementation paths remain fixed and do not use this behavior.

## Limitations

There is no AI model, prompt, external provider, network call, Knowledge
Package, retrieval, Plan IR, approval, capability execution, workflow
execution, or autonomous behavior. No external facts, citations, costs,
timelines, or feasibility claims are produced. M3.3 may establish a local
concurrency and performance baseline without changing these authority
boundaries.
