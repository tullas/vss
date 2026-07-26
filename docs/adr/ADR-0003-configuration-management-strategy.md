# ADR-0003: Configuration Management Strategy

## Status

Accepted

## Date

2026-07-25

## Context

Automation needs environment-specific configuration without hardcoded values,
source-controlled secrets, or inconsistent loading behavior.

## Decision

Configuration is externalized using simple `KEY=VALUE` files and environment
variables. Configuration files are parsed as data; they are never sourced as
Bash code.

The repository structure is:

```text
config/default.env                 # tracked, non-secret defaults
config/environments/<name>.env     # ignored environment-specific values
config/local.env                   # ignored developer overrides
config/*.example                   # tracked templates only
```

Use `scripts/lib/config.sh` and call `load_config [environment]`. Files are
loaded in this order: `default.env`, the named environment file, `local.env`,
then the optional file named by `CONFIG_FILE`. Later files override earlier
files. Values already supplied in the process environment take precedence over
all files, making secret injection through CI, Jenkins, Ansible, or a secret
manager safe and consistent.

Only variable names matching Bash environment-variable syntax are accepted.
Malformed lines cause loading to fail with exit status 65. `CONFIG_FILE` must
refer to an existing regular file when set. The default configuration directory
is the repository's `config` directory and can be overridden with `CONFIG_DIR`
for tests or external automation.

Secrets must be supplied through a CI secret store, Jenkins credentials,
Ansible Vault, or the process environment. They must not appear in tracked
configuration files, examples, logs, or command arguments.

## Consequences

Scripts can have portable defaults while deployments retain independent
configuration. The deliberately limited file syntax does not support shell
expansion, quoting semantics, or multiline values; those features would make
configuration execution-prone and harder to validate.

The schema-driven Python configuration engine is available as
`python -m vss_config validate --environment <name>` and
`python -m vss_config render --environment <name>`. It merges
`config/defaults.yml` with the selected file under `config/environments/` and
validates the result against the versioned schema before rendering.

## Verification

Run:

```bash
bash tests/config-test.sh
```
