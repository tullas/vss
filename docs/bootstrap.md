# Local toolchain bootstrap

The bootstrap commands prepare an Ubuntu or Ubuntu-under-WSL workstation for
the ADR-0009 local provider. Git, Python 3.11+, and Ansible are trusted
prerequisites. Ansible installs Docker Engine and OpenTofu only when needed;
OpenTofu remains responsible for creating the local MinIO platform.

## Commands

```bash
vss bootstrap check --environment development
vss bootstrap local --environment development
vss bootstrap local --environment development --verbose --ask-become-pass
vss bootstrap verify --environment development
```

`check` is read-only. It reports WSL and systemd detection, Docker CLI and
daemon status, OpenTofu version, and conflicts on ports 9000 and 9001.

`local` invokes `ansible/playbooks/bootstrap-local.yml`. It reuses an already
working Docker daemon. If Docker is unavailable, it requires active systemd;
on WSL without systemd it stops and explains how to enable systemd in
`/etc/wsl.conf` and restart WSL. It uses signed APT keyrings for the official
Docker and OpenTofu repositories. It never installs or controls Docker Desktop
on Windows, adds users to privileged groups, runs OpenTofu apply/destroy, or
prints credentials.

On failure, the JSON response includes only a short sanitized Ansible summary
(failed task, safe error message, and return code). `--verbose` additionally
writes sanitized Ansible diagnostics to stderr while preserving the response
envelope on stdout. `--ask-become-pass` lets Ansible prompt interactively; the
password is never stored or included in output.

The role creates `.local/state/development` and `.local/secrets`, and copies
the safe secrets example only when the destination does not exist. Existing
local secrets are not overwritten.

`verify` checks `docker info`, `tofu version`, repository paths and ignored
state/secrets configuration, then runs `scripts/iac-local.sh validate`. It does
not apply infrastructure.

## Assumptions and privilege boundaries

The playbook targets Ubuntu and uses `become: true` for package and service
operations. A user must have working privilege escalation; otherwise Ansible
reports the failure and no bootstrap completion is claimed. WSL Docker Engine
installation requires systemd. Docker Desktop with WSL integration is treated
as an already accessible daemon and is reused without attempting Windows-side
changes.
