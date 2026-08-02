# Semantic reasoning contracts

M3.1 implements validation-only contracts derived from ADR-0012 through
ADR-0016. It does not reason, generate options, select or call a provider,
execute a capability or workflow, retrieve knowledge, create plans, approve
actions, or grant authority.

## Registry

`SemanticContractRegistry` is an explicit immutable snapshot built from four
exact repository-owned schema paths. It admits only this mapping:

| Contract | Identity | Version | Lifecycle |
| --- | --- | --- | --- |
| Request envelope | `semantic_request` | `1` | active |
| Task | `generate_options` | `1` | active |
| Result envelope | `semantic_result` | `1` | active |
| Result family | `option_set` | `1` | active |

Registration means that a contract is known. It does not authorize reasoning,
providers, strategies, Knowledge Packages, capabilities, workflows, approval,
or execution. The registry contains no handler, import, plugin, provider, or
execution hook. Unknown identities, versions, combinations, schemas, and
lifecycle states fail closed.

Schemas are regular non-symlink files beneath the repository `schemas/`
directory. Loading rejects path escape, identity mismatch, unsupported dialect,
malformed schema, and external or remote references. The registry retains an
immutable parsed snapshot and SHA-256 digest for each admitted schema, so later
filesystem substitution cannot mutate an existing invocation.

## Envelope and payload boundaries

The request envelope carries stable routing and governance metadata: request
and correlation identities, exact task and required-family versions,
validation lifecycle mode, classification, purpose, budget, and exactly one
typed task payload. `GenerateOptions` v1 contains a bounded objective, typed
constraints, desired option count, and optional evaluation dimensions. It has
no generic context or metadata bag.

The result envelope carries stable contract metadata and exactly one
`OptionSet` payload. It cannot contain multiple payloads or family-specific
optional fields. `OptionSet` owns alternatives and option-comparison semantics;
future families require their own schemas and registry entries rather than
growth of a universal reasoning object.

## OptionSet and common semantic sections

An `OptionSet` has an identity, objective summary, one to eight uniquely
identified alternatives, and bounded common sections. Options contain
descriptions, benefits, drawbacks, risks, constraint references, and inert
evidence identifiers. They contain no plan, executable operation, capability,
workflow, approval, provider tool call, secret, source-access grant, or
implementation path.

Common sections compose typed bounded facts, assumptions, unknowns,
constraints, evidence references, confidence, and limitations. Claimed facts
are not established as truth by schema validation. Evidence references use an
identifier form and grant no access to their sources. Assumptions stay distinct
from facts, and unknowns remain explicit rather than fabricated.

Confidence contains `unknown`, `low`, `medium`, or `high`, a bounded basis, and
bounded qualifications. It is not a probability, is not statistically
calibrated, and grants no authority.

## Bounds and immutability

Central constants bound requests to 16 KiB, results to 64 KiB, strings to 2,048
characters, lists to 64 items, objects to 32 properties, nesting to eight
levels, total nodes to 1,024, JSON integers to the interoperable signed range,
and options to eight. Task and family schemas impose tighter field-specific
bounds. These conservative development-safe limits prevent accidental memory,
serialization, and review amplification. Future profiles require explicit
versioned policy; they do not silently alter v1.

Validated values recursively use immutable mapping proxies and tuples. Registry
records and snapshots use frozen slotted dataclasses and immutable mappings.
Unsupported Python objects, tuples, sets, bytes, file handles, datetimes,
custom objects, recursive/excessively deep content, huge integers, and
non-finite numbers are rejected rather than stringified.

## Compatibility, canonicalization, and errors

M3.1 supports exact versions only. It performs no downgrade, translation,
unknown-field dropping, family substitution, or lifecycle defaulting.
Canonical JSON uses UTF-8, sorted keys, compact separators, and rejects
unsupported objects. SHA-256 digests cover schema bytes, the deterministic
registry snapshot, and validated request/result envelopes. Digests provide
integrity evidence only—not signatures, authenticity, approval, or authority.

Typed internal errors distinguish unknown identity, unsupported version,
incompatible combination, invalid input/schema, unsafe content, disabled
contract, registry integrity, and internal failure. M3.1 adds no exit code and
no public reasoning CLI. Safe errors do not echo payload contents.

## Deterministic acceptance example

From the repository root:

```bash
PYTHONPATH=src python -c 'import json, pathlib; from vss_reasoning_contracts import SemanticContractRegistry, validate_request, validate_result; root=pathlib.Path.cwd(); registry=SemanticContractRegistry.built_in(root); fixtures=root/"tests/fixtures/reasoning"; request=validate_request(json.loads((fixtures/"generate-options-valid.json").read_text()), registry); result=validate_result(json.loads((fixtures/"option-set-valid.json").read_text()), registry); print(request.digest, result.digest, registry.digest)'
```

This validates and prints deterministic integrity digests. It does not generate
or execute anything.

## Known limitations and next step

There is no reasoning provider, strategy, prompt, model selection, option
generator, Knowledge Package, retrieval, Plan IR, approval artifact, or
execution integration. Semantic objects remain inert. M3.2 may add a
deterministic option generator through separately reviewed runtime boundaries;
it must consume these contracts without weakening them.
