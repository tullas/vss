# ADR-0001: Establish Bash Command Execution Framework

## Status

Accepted

## Date

2026-07-25

## Context

The project runs Bash commands as part of automation workflows. Without a
shared pattern, scripts can disagree about error handling, exit statuses, and
diagnostic output, making local automation and CI results unreliable.

## Decision

All project-owned Bash entry points must:

1. Use `#!/usr/bin/env bash` and `set -euo pipefail`.
2. Treat a command's exit code as the authoritative success or failure signal.
3. Invoke commands as argument arrays (`"${command[@]}"`), never by passing
   interpolated input to `eval` or `bash -c`.
4. Use `run_command` from `scripts/lib/command.sh` when a command needs a
   consistent log line and failure diagnostic.
5. Return the underlying command's exit code unchanged.

`scripts/run-command.sh` is the standard command-line entry point. It accepts
a program and its arguments after an optional `--` delimiter.

## Consequences

Automation gets consistent stderr diagnostics while preserving useful stdout
for piping or CI annotations. The framework intentionally does not interpret
a shell command string; callers needing shell syntax must put that syntax in a
reviewed script rather than relying on runtime evaluation.

The strict-mode policy means scripts must explicitly handle expected non-zero
statuses (for example, `if ! grep ...; then ...; fi`).

## Verification

Run:

```bash
bash tests/run-command-test.sh
```

