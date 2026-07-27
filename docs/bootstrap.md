# Local toolchain bootstrap

The bootstrap commands prepare an Ubuntu or Ubuntu-under-WSL workstation for
the ADR-0009 local provider. Git and Python 3.11 through 3.14 are trusted
prerequisites. The bootstrap installs a compatible Ansible version, then
Ansible installs Docker Engine and OpenTofu only when needed;
OpenTofu remains responsible for creating the local MinIO platform.

## Commands

```bash
./scripts/bootstrap-host.sh
vss bootstrap check --environment development
vss bootstrap verify --environment development
```

`check` is read-only. It reports WSL and systemd detection, Docker CLI and
daemon status, OpenTofu version, and conflicts on ports 9000 and 9001.

`local` invokes `ansible/playbooks/bootstrap-local.yml`. The supported
`bootstrap-host.sh` path first lets native `sudo -v` authenticate directly on
the controlling terminal, validates the resulting ticket, and keeps it alive
only for the lifetime of bootstrap. It then runs the dedicated local playbook
itself through `sudo -n`. The playbook is already root and performs no nested
Ansible privilege escalation. The password is never captured, stored, piped,
inspected, or included in VSS output. The command reuses an already working
Docker daemon. If Docker is unavailable, it requires active systemd;
on WSL without systemd it stops and explains how to enable systemd in
`/etc/wsl.conf` and restart WSL. It uses signed APT keyrings for the official
Docker and OpenTofu repositories. It never installs or controls Docker Desktop
on Windows, adds users to privileged groups, runs OpenTofu apply/destroy, or
prints credentials.

The dedicated playbook is an implementation detail of `bootstrap-host.sh`.
Direct non-root playbook execution fails before role changes; the supported
entry point preserves terminal progress and emits a safe structured completion
or a generic failure after Ansible exits.

## Python and ansible-core compatibility

Bootstrap uses deterministic environment-marked pins based on the official
[ansible-core control-node support matrix](https://docs.ansible.com/projects/ansible-core/devel/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix):

| Control-node Python | ansible-core | VSS policy |
| --- | --- | --- |
| 3.11 | 2.19.9 | Supported |
| 3.12–3.14 | 2.21.2 | Supported |
| 3.15 or newer | None selected | Rejected until explicitly validated |

Before dependency installation, phase 0 reports safe compatibility metadata:
the detected Python version, installed ansible-core version (or
`not-installed`), selected version, and whether the existing combination is
supported. An incompatible ansible-core is upgraded in place without replacing
an otherwise healthy virtual environment. Bootstrap then verifies the installed
version and starts `ansible-playbook --version` before invoking VSS.

The role creates `.local/state/development` and `.local/secrets`, and copies
the safe secrets example only when the destination does not exist. Existing
local secrets are not overwritten.

`verify` checks `docker info`, `tofu version`, repository paths and ignored
state/secrets configuration, then runs `scripts/iac-local.sh validate`. It does
not apply infrastructure.

## Assumptions and privilege boundaries

The dedicated playbook targets Ubuntu, requires root at entry, and validates
the original developer identity and repository ownership before making changes.
Repository-local files are assigned to that developer explicitly; APT, package,
service, and `/usr/local/bin/vss` resources remain root-owned. A user must have
working interactive sudo authentication; phase 0 stops before Ansible if
`sudo -v` fails or no terminal is attached.
WSL Docker Engine
installation requires systemd. Docker Desktop with WSL integration is treated
as an already accessible daemon and is reused without attempting Windows-side
changes.
