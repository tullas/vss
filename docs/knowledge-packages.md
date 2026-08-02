# M3.4 Knowledge Contracts and Packages

M3.4 is a local, offline validation-and-construction slice implementing the
bounded Knowledge Package boundary from ADR-0015. The Knowledge Layer prepares
inert data; it is not a second Runtime and grants no reasoning, provider,
approval, workflow, capability, execution, source-access, or autonomy authority.

## Contract registry and boundaries

The repository-built registry admits exactly `knowledge_item/1`, typed family
`reference_note/1`, and `knowledge_package/1`. Registration means known, not
authorized. Schemas come from exact repository-owned paths using bounded
no-follow reads and are validated, hashed, and snapshotted. External or dynamic
references, nested schema identities, symlinks, non-regular files, alternate
roots, runtime registration, and dynamic imports are prohibited.

Each item has a small cross-family envelope and exactly one typed payload.
`reference_note/1` contains only a title, inert plain-text body, conservative
topic labels, fixed `en` language, and inert citation identifiers. It has no
extension bag, movie fields, provider data, source handle, or authority.

## Source, policy, and bounds

The only source is `vss.local.reference-fixtures/1`, trust `approved_fixture`,
with exact fixture identity `reference-note-local-validation`. This is not a
filesystem connector: callers cannot provide paths, browse, follow symlinks,
read special files, use environment configuration, or access a network.

Repository policy admits only `development`, purpose
`local_validation_context`, classifications `public` and `internal`, and trust
`approved_fixture`. Classification uses `public < internal`; a package equals
the most sensitive included item. Classification and trust grant neither
disclosure permission nor truth.

The current builder emits one item; contracts bound packages to eight items and
64 lineage steps. Central limits include 16 KiB source/item documents, 64 KiB
packages, 4 KiB bodies, 256-character titles, 16 labels/citations, JSON depth 8,
and 2,048 nodes. Existing bounded-JSON rules reject excessive integers,
non-finite values, unsupported Python objects, and excessive structure.

UTC metadata covers observation, effectiveness, retrieval, staleness,
construction, expiration, and retention. Ordering is validated. Current policy
rejects stale, expired, revoked, disabled, unverified, or purpose-incompatible
items. The committed fixture is recognized by its exact repository-owned event
identity and validated against the fixed `2026-08-02T00:00:00Z` policy clock;
other CLI packages use current UTC, and callers cannot provide a clock. This
keeps CI evidence deterministic without allowing other packages to select
historical time. Retention metadata is validated, while deletion is deferred.

The builder and validator use an immutable policy-owned revocation snapshot.
The M3.4 production snapshot is explicitly known-empty; test snapshots prove
that effective source or item revocation invalidates construction or package
validation, while invalid revocation ordering fails closed. No persistent or
remote revocation service is claimed.

Redaction is represented only by fixed policy `vss.no-redaction-required/1`.
`none_detected` conflicts means none among included items, not none globally.
Uncertainty explicitly records that truth and applicability were not verified.

## Provenance, integrity, and lineage

Provenance names the fixture loader, reference-note normalizer, owner, and the
ordered transformations: strict JSON decode, typed normalization,
classification validation, and canonicalization. Provenance is traceability,
not proof of truth.

SHA-256 evidence covers source bytes, decoded source, normalized payload,
validated item content, package content, complete event-bound package, and the
registry snapshot. Ordered lineage links these values. Digests detect recorded
substitution; they are not signatures, authenticity, authorization, approval,
encryption, trust, or truth.

Canonical JSON uses UTF-8, sorted keys, fixed separators, and no fallback
stringification. Unicode code points are preserved without implicit Unicode
normalization, so canonically equivalent spellings can intentionally have
different digests. Non-finite and unsupported values fail closed.

Source, payload, item-content, and package-content digests remain stable for
identical content and policy/contract versions. Package-content material excludes
correlation and event metadata. Complete-package integrity includes event
metadata while excluding only its self-referential digest slots, so it may vary
between build events.

## CLI

```bash
vss knowledge package build \
  --source reference-note-local-validation \
  --purpose local_validation_context \
  --environment development \
  --correlation-id m3-4-local-build

vss knowledge package validate \
  --input tests/fixtures/knowledge/knowledge-package-valid.json \
  --environment development \
  --correlation-id m3-4-local-validate
```

Build returns the bounded non-sensitive package and digest summary in the
existing response envelope. Validation reads a bounded regular file using
strict duplicate-key and non-finite rejection and returns a safe summary.
Neither retrieves, reasons, approves, or executes. No dry-run is added because
construction is already inert. Each operation writes one payload-free terminal
development audit record; audit failure is fatal. Local JSONL is development
only.

## Limitations

There is no connector, crawler, search, index, embedding, vector/graph store,
database, cache, external source, AI model, prompt, reasoning-package
consumption, Plan IR, approval, workflow/capability execution, or autonomy.
Built-in Python remains trusted in-process. Signing, encryption, production
storage/audit, privacy/residency and deletion enforcement, persistent
revocation, caching, conflict resolution, and broader families are deferred.
