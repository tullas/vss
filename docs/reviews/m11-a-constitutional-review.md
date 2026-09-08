# M11.A Constitutional Review — External Media Admission Seam

## Decision under review

ADR-0028 admits only the smallest architecture seam needed before Issue #132
can implement one human-triggered moving-shot attempt. It does not add a
provider, call, production authority, or reusable media system.

## Invariants and authority flow

Runtime remains the effect boundary; provider adapters remain replaceable;
authoritative visual input is reconstructed and digest-bound; spend is
reserved immediately before credentialed transport; output is validated and
quarantined for same-scope local review only. Human approval remains separate
from architecture acceptance. Credentials and provider bytes stay outside
contracts and audit text.

## Review disposition

`ACCEPT` — the ADR preserves existing Runtime, provenance, rights, tenant,
human-control, and publication boundaries. Its explicit non-goals prevent
silent expansion into provider selection, retries, production, or release.

## Evidence and limitations

Evidence: `docs/adr/ADR-0028-first-external-media-attempt-admission.md`,
`docs/architecture/vss-constitution.md`, `docs/architecture/decisions/DEC-0001-foundation-closure.json`.
This is architecture evidence only; implementation and paid-call admission
remain future, separately reviewed work.
