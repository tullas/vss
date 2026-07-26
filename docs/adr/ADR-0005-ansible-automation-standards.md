# ADR-0005: Ansible Automation Standards

## Status

Accepted

## Date

2026-07-25

## Context

The project needs maintainable infrastructure automation for configuration,
deployment, provisioning, and operational tasks without mixing environment
data, secrets, and reusable automation logic.

## Decision

Ansible automation uses a role-based layout:

```text
ansible/
  ansible.cfg
  playbooks/                 # workflow orchestration
  roles/<role>/{defaults,tasks,handlers,templates}/
  inventories/<environment>/ # environment-specific, ignored hosts files
  group_vars/                # non-secret shared variables
```

Playbooks orchestrate roles and do not duplicate role task logic. Roles must
be idempotent: use Ansible modules and declarative `state` values instead of
unconditional shell commands. A task may use `command` only when no suitable
module exists, with explicit `changed_when` and `failed_when` semantics.

Real inventory files and `vault.yml` files are excluded from source control.
Tracked `.example` files document their shape. Secrets are supplied through
Ansible Vault, CI secret injection, or the approved secret manager, and tasks
handling secrets must set `no_log: true`.

Run playbooks with an explicit inventory, for example:

```bash
cd ansible
ansible-playbook -i inventories/development/hosts.yml playbooks/site.yml
```

The baseline playbook uses privilege escalation because it manages a
system-owned workspace; its inventory user must therefore have approved
`become` access.

Task names provide execution-flow logs, and normal Ansible stdout is retained
for CI and operational troubleshooting. Set `ANSIBLE_LOG_PATH` when a durable
log file is required by the execution environment.

## Consequences

Reusable roles reduce duplication and environment-specific inventories remain
separate from code. Every environment must provision its inventory and secrets
before a playbook can run. The included `baseline` role is deliberately small;
application, middleware, and deployment automation should be added as separate
roles.

## Verification

Run:

```bash
bash tests/ansible-structure-test.sh
```

The CI validation stage also installs `ansible-core` and performs the same
playbook syntax check against the development inventory example.

When Ansible is available, also run:

```bash
cd ansible && ansible-playbook --syntax-check -i inventories/development/hosts.yml playbooks/site.yml
```
