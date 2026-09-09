# ADR-0030: Reproducible Governance and Algorithm-Aware Digest References

## Status

Accepted

## Context

Repository validation previously relied on several independent checks. Secret
baseline scope, test classification, protected generated artifacts, and
isolated execution therefore could drift apart. Digest fields also commonly
used a bare 64-character value, which cannot identify an algorithm or the
canonicalization rules used to produce it.

## Decision

The repository governance manifest is the authoritative local policy for
baseline scope, protected paths, and test classification. `validate-change.sh`
invokes that policy and the deterministic classified suite under an isolated
HOME and temporary directory. Provider, external-media, and host-integration
tests require explicit classification and are excluded from ordinary CI.

New code may use an algorithm-aware `DigestReference` with optional
canonicalization and version metadata. Existing bare SHA-256 strings remain
valid and historical immutable artifacts are not rewritten.

All governance authority remains false. These checks provide validation and
coordination evidence only; they do not authorize Runtime, providers,
production, publication, workflow activation, merge, or push.

## Consequences

Protected changes require a human-readable justification in the validation
environment and must use the sanctioned updater where one exists. Existing
host/provider workflows remain separately classified and are not silently
converted into hermetic CI tests.
