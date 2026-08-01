# Workflow Engine M2.2

VSS M2.2 adds a minimal sequential interpreter for trusted, repository-owned
workflows. It builds on the M2.1 Runtime Kernel without changing existing
commands or migrating another command into a capability.

## Trusted workflow model

Authored workflows are safe-loaded YAML files discovered only as direct
`*.yaml` children of `workflows/builtin/`. Requested names use a constrained
lowercase identifier and cannot select paths. Resolved workflow files must stay
inside that fixed root; path traversal and symlink escape fail closed. The
validated workflow SHA-256 is rechecked immediately before execution.

Workflows conform to `schemas/workflow-v1.schema.json`. M2.2 supports workflow
schema version `1` and runtime API version `1`. The schema rejects unknown
fields, more than 32 steps, duplicate or unsafe step IDs, nonsequential policy,
`continue_on_error: true`, and timeouts outside 0.001 through 300 seconds.
Validation also rejects unsafe YAML tags, expression/interpolation syntax,
embedded shell fragments, recursive workflow invocation, and operations
outside the fixed allowlist.

## Operation allowlist

M2.2 supports exactly:

- `system.info`, executed through the M2.1 Runtime Controller;
- `bootstrap.check`, executed through a narrow adapter over the existing
  `CommandRunner`.

Workflow YAML cannot select Python functions, modules, executables, command-line
arguments, environment variables, external files, or remote sources. The
operation registry is code-owned and independently checked after schema
validation.

## Sequential execution

Steps execute in authored order on the caller's process. Each step begins as
pending, transitions to running, and finishes as succeeded or failed. The first
failure stops execution; remaining steps are represented deterministically as
skipped. There are no conditions, interpolation, parallelism, retries,
rollback, or compensation.

The workflow result contains its version, generated execution ID, preserved or
generated correlation ID, timestamps, duration, final status, safe step
summaries, and safe errors. Raw workflow inputs, process environment, raw child
output, and unfiltered exceptions are excluded. A command timeout becomes the
named workflow timeout result; other failed operations become a named workflow
execution failure.

## Audit

The workflow engine appends structured records to the existing ignored
`.local/runtime/audit/executions.jsonl` sink. Successful `runtime-smoke`
execution emits, in order:

1. `workflow_started`
2. `step_started` and `step_completed` for `system.info`
3. `step_started` and `step_completed` for `bootstrap.check`
4. `workflow_completed`

Failures use `step_failed` and `workflow_failed`; skipped steps receive a
`step_completed` record with status `skipped`. Records contain workflow and
step identity, workflow execution and correlation IDs, authorization result,
status, exit code, duration, and manifest digest. They do not contain raw step
input. The existing directory mode `0700`, file mode `0600`, append-only write,
containment, and no-follow protections remain in effect. Audit failure cannot
produce a successful workflow result.

## Reference workflow

Inspect and execute the built-in workflow with:

```bash
vss workflow list
vss workflow describe runtime-smoke
vss workflow run runtime-smoke --environment development
vss workflow run runtime-smoke --environment development --correlation-id example-id
```

`runtime-smoke` invokes `system.info` and then `bootstrap.check`, exactly once
each and in that order.

## Deferred functionality

M2.2 does not include DAG scheduling, parallelism, retries, rollback,
compensation, conditions, variable interpolation, cron, remote workers,
distributed state or events, workflow editing or installation, dynamic
plugins, marketplaces, user-authored Python or shell, external providers, AI
planning, or movie-production workflows.
