# Upgrade and lifecycle policy

Supported components must be upstream-maintained and reviewed at least every
180 days, or more often near EOL. Unsupported/EOL software blocks new release
candidates unless an independently approved exception exists.

Dependabot opens dedicated ecosystem branches. Every update PR must link
release notes and relevant advisories, identify breaking changes, regenerate
locks/SBOM/provider locks, record old and new pins, explain rollback, and pass
all tests/security gates. Major upgrades remain isolated and never auto-merge.

The Upgrade Steward owns scheduled vulnerability, outdated, EOL, expired
exception, failed scan, and stale security-PR reports. Automation may prepare
PRs/issues but may not waive, approve, weaken, or merge critical changes.
