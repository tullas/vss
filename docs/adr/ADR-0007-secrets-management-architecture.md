# ADR-0007: Secrets Management Architecture

## Status

Accepted

## Date

2026-07-25

## Context

Automation needs credentials for applications, databases, infrastructure,
CI/CD, and external services. Exposing them in source control, logs, command
arguments, or long-lived local files creates unacceptable security and
operational risk.

## Decision

Secrets are separate from application configuration and injected only at
runtime. They are classified as application, database, infrastructure, CI/CD,
or external-service secrets. Each secret must have a named owner, least-
privilege scope, documented rotation procedure, and audit trail in its secret
provider.

Use the CI platform's environment-scoped secrets, Ansible Vault, or an approved
external secret manager. Do not commit plaintext secret values, private keys,
certificates, real inventories, unencrypted Vault files, or populated `.env`
files. Templates may document variable names but must not contain values.

`scripts/lib/secrets.sh` provides `require_secret NAME` for Bash automation.
It validates a secret is present without printing its value. Callers must not
put secret values in log messages, command arguments, artifact names, or error
output. Ansible tasks handling secrets must use `no_log: true`.

CI runs Gitleaks on full repository history. For organization repositories,
configure the `GITLEAKS_LICENSE` GitHub secret required by the action. A scan
finding blocks the pipeline. A suspected exposure requires immediate
revocation/rotation and incident review; deleting the value from the current
file is not sufficient because history and logs may retain it.

## Consequences

Deployments require their secret provider configuration before they can run,
but repository access alone does not grant credentials. Runtime secret access
is auditable through the selected provider and GitHub Environment deployment
history. Rotation is performed in the provider, then validated through a
non-production deployment before production promotion.

## Verification

Run:

```bash
bash tests/secrets-test.sh
```
