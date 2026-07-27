#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
role_dir="$project_root/ansible/roles/local_toolchain"
playbook="$project_root/ansible/playbooks/bootstrap-local.yml"

[[ -f $playbook ]]
grep -Fq 'become: true' "$playbook"
grep -Fq 'ansible.builtin.deb822_repository' "$role_dir/tasks/docker.yml"
grep -Fq 'opentofu-repo.gpg' "$role_dir/tasks/opentofu.yml"
grep -Fq 'opentofu.gpg,/etc/apt/keyrings/opentofu-repo.gpg' "$role_dir/tasks/opentofu.yml"
grep -Fq 'python3-debian' "$role_dir/tasks/docker.yml"
grep -Fq 'local_toolchain_docker_group is changed' "$role_dir/tasks/docker.yml"
! grep -R -n 'apt-key' "$role_dir"
grep -Fq 'force: false' "$role_dir/tasks/local_directories.yml"
grep -Fq 'docker info' "$role_dir/tasks/docker.yml"
grep -Fq 'systemd is not active' "$role_dir/tasks/docker.yml"
grep -Fq "['running', 'degraded']" "$role_dir/tasks/docker.yml"
grep -Fq 'local_toolchain_pid1_is_systemd' "$role_dir/tasks/docker.yml"

printf '%s\n' 'bootstrap structure tests passed'
