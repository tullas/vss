# ADR-0006: Deployment and Rollback Strategy

## Status

Accepted

## Date

2026-07-25

## Context

Deployments across multiple environments require repeatable releases, clear
traceability, failure detection, and a recovery path that does not depend on
ad-hoc manual commands.

## Decision

Deployments use a controlled, versioned lifecycle:

1. Validate the selected environment, release version, and deployment adapters.
2. Run the configured deployment adapter.
3. Run the configured post-deployment health-check adapter.
4. If deployment or verification fails, run the configured rollback adapter.
5. Return a non-zero status for the failed deployment even if rollback succeeds.

`scripts/deploy.sh` implements the lifecycle. It requires a release version
matching `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` and the following executable,
externally configured adapters:

```text
DEPLOY_SCRIPT       # receives: environment release-version
HEALTHCHECK_SCRIPT  # receives: environment release-version
ROLLBACK_SCRIPT     # receives: environment release-version
```

The GitHub deployment workflow requires both an environment and release
version. GitHub Environment protection rules, workflow history, structured
logs, and adapter arguments form the deployment audit trail.

Adapters are responsible for the target-specific implementation. They should
use immutable artifacts and choose a low-disruption strategy appropriate to
the service (for example rolling, blue/green, or canary deployment). A
rollback adapter must restore the last known-good version or another explicitly
documented stable release.

## Consequences

No unversioned deployment can run through the standard entry point, and a
failed verification automatically attempts recovery. Operators must configure
and test all three adapters for each environment before deployment. The
framework cannot infer application-specific health criteria or a safe previous
release; those remain explicit adapter responsibilities.

## Verification

Run:

```bash
bash tests/deployment-test.sh
```
