# ADR-0009: Infrastructure as Code Standards

## Status

Accepted

## Date

2026-07-25

## Context

Infrastructure changes need the same repeatability, review, validation, and
auditability as application changes. Manual changes cause drift and make
recovery and environment recreation unreliable.

## Decision

Infrastructure is defined with OpenTofu-compatible HCL under `infrastructure/`:

```text
infrastructure/
  modules/                 # reusable provider-neutral or provider-specific units
  environments/<name>/     # reviewed roots for each environment
  backend.tf.example        # external remote-state template
```

Every infrastructure change must be reviewed through a pull request and pass
formatting, initialization without a backend, and validation in CI. Plans are
created per environment and applied only through controlled deployment
automation after review. Production apply requires explicit confirmation.

State is remote, encrypted, access-controlled, locked, and backed up by the
chosen cloud or platform backend. State files, plans, backend configuration,
credentials, and provider secrets are never committed. Backend details are
environment-owned and supplied at runtime.

Use `scripts/iac.sh validate <environment>`, `plan <environment>`, or
`apply <environment> <plan-file>`. Apply requires
`IAC_CONFIRM_APPLY=<environment>`, and only consumes a previously generated
plan file. The initial baseline module is deliberately provider-neutral; cloud
resources must be introduced as explicit reviewed modules, not guessed by this
framework.

## Consequences

Infrastructure definitions are versioned and testable without exposing state
or secrets. Teams must provision an approved remote backend before real plans
or applies. Provider authentication and disaster-recovery requirements belong
to environment configuration and the selected cloud module.

## Verification

Run:

```bash
bash tests/iac-structure-test.sh
```
