# Dependency policy

Direct dependencies require a purpose, owner, exact version or immutable
identity, upstream-risk review, license decision, rollback method, review date,
and approval in `security/components.yml`. New undeclared dependencies fail CI.

Python lock consumption uses `pip --require-hashes`; lock generation is a
separate maintainer operation. GitHub Actions use full commit SHAs, container
images use registry digests, and OpenTofu providers use exact constraints plus
committed checksum locks. APT repositories require signed metadata and recorded
key fingerprints; initial APT package versions remain a documented residual
risk until snapshot pinning is implemented.

Artifact verification is fail closed: compare SHA-256 subjects to provenance,
validate CycloneDX structure, provider checksum locks, OCI digests, Action
commits, Python hashes, and APT key fingerprints before consumption. Preserve
the prior lock, digest, provider checksum file, host package record, and source
commit as rollback evidence. Releases require successful tests/security scans,
component approvals/exceptions, SBOM and diff, immutable artifact digest,
provenance validation, and an identified rollback revision.

Patch/minor upgrades may be grouped after full testing. Major upgrades are
isolated, identify breaking changes, retain the old pin/digest for rollback,
and never auto-merge. Failed security gates are not suppressible by update
automation.
