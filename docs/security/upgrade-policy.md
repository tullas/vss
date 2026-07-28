# Upgrade and lifecycle policy

Supported components must be upstream-maintained and reviewed at least every
180 days, or more often near EOL. Unsupported/EOL software blocks new release
candidates unless an independently approved exception exists.

Dependabot opens dedicated ecosystem branches. Every update PR must link
release notes and relevant advisories, identify breaking changes, regenerate
locks/SBOM/provider locks, record old and new pins, explain rollback, and pass
all tests/security gates. Major upgrades remain isolated and never auto-merge.

Dependabot updates declared Python, Action, Terraform-provider, and Dockerfile
manifests but is not authorized to make a change mergeable by itself. The
Dependency Upgrade Steward reviews its release/advisory links, records breaking
and rollback analysis, updates `security/components.yml`, and runs
`scripts/security/regenerate-locks.sh`; CI rejects any manifest/lock/review
evidence drift and regenerates the candidate SBOM and diff. Provider upgrades
use `tofu init -upgrade` followed by review of `.terraform.lock.hcl`. Action
updates must resolve to the release's full commit SHA. OCI digests embedded in
Terraform or shell are refreshed manually from the authenticated upstream
registry because Dependabot cannot discover those non-Dockerfile references;
the registry record, old digest, rollback digest, and scan results are required.
Bot-only PRs therefore remain incomplete and unmergeable. No update automation
has write authority to policy, exception, or approval records.

The Upgrade Steward owns scheduled vulnerability, outdated, EOL, expired
exception, failed scan, and stale security-PR reports. Automation may prepare
PRs/issues but may not waive, approve, weaken, or merge critical changes.
