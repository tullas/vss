# ADR-0002: Standardize Logging and Error Reporting

## Status

Accepted

## Date

2026-07-25

## Context

ADR-0001 establishes a Bash command execution framework. As automation grows,
operators and CI systems need consistent messages that identify the execution
flow and failures without contaminating command output.

## Decision

Project-owned Bash automation will use `scripts/lib/logging.sh`. It provides
`log_debug`, `log_info`, `log_warn`, and `log_error` functions.

Every log line uses this format:

```text
2026-07-25T12:34:56Z INFO message text
```

The timestamp is UTC in ISO 8601 format. Log lines are written to standard
error so standard output remains available to calling scripts and pipelines.

Set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARN`, or `ERROR` to suppress lower-priority
messages; it defaults to `INFO`. Set `LOG_FILE` to append the same formatted
messages to a file. Invalid log levels are rejected with a usage-style error.

`run_command` logs command execution at `DEBUG` and command failures at
`ERROR`, then returns the command's original exit status.

## Consequences

Automation has uniform, machine-parseable diagnostics while preserving command
output and exit-code semantics. Scripts must source the logging helper before
emitting framework log messages; `scripts/lib/command.sh` does this itself.

## Verification

Run:

```bash
bash tests/run-command-test.sh
bash tests/logging-test.sh
```
