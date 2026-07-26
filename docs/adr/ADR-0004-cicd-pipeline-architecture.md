# ADR-0004: CI/CD Pipeline Architecture

## Status

Accepted

## Date

2026-07-25

## Context

The project has standardized command execution, logging, and configuration.
It needs repeatable validation, testing, and controlled deployments with clear
failure signals and an audit trail.

## Decision

GitHub Actions provides the staged CI/CD architecture:

1. **Validate** runs shell syntax checks and `git diff --check` for every push
   and pull request.
2. **Test** runs the project Bash test suite only after validation passes.
3. **Deploy** runs only through a manually dispatched workflow after tests
   pass. It targets a selected GitHub Environment, so environment protection
   rules and deployment history provide approval and audit controls.

The workflows use a pinned major version of `actions/checkout`, minimal
`contents: read` permissions, and Ubuntu runners. Deployment is delegated to
`scripts/deploy.sh`, which loads configuration using ADR-0003 and requires a
configured `DEPLOY_SCRIPT`. This avoids embedding environment-specific
deployment commands or secrets in the workflow.

## Consequences

Every pull request and push receives consistent validation and test results.
Production deployment requires an explicit operator action and any GitHub
Environment reviewers configured by repository administrators.

To enable a deployment target, provide a non-secret `DEPLOY_SCRIPT` through
the selected environment's variables or approved configuration source. The
script receives the environment name as its first argument and is responsible
for the target-specific deployment and rollback behavior. A missing or invalid
deployment script fails clearly; it is never treated as a successful deploy.

## Verification

Run locally:

```bash
bash tests/cicd-test.sh
```

In GitHub, open a pull request to exercise validation and tests. Use **Run
workflow** on the deployment workflow only after configuring the target GitHub
Environment and its `DEPLOY_SCRIPT` variable.
