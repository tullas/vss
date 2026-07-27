#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ansible_dir="$project_root/ansible"

required_files=(
  playbooks/site.yml
  playbooks/bootstrap-local.yml
  roles/baseline/defaults/main.yml
  roles/baseline/tasks/main.yml
  roles/local_toolchain/defaults/main.yml
  roles/local_toolchain/tasks/main.yml
  roles/local_toolchain/tasks/docker.yml
  roles/local_toolchain/tasks/opentofu.yml
  roles/local_toolchain/tasks/local_directories.yml
  roles/local_toolchain/handlers/main.yml
  inventories/development/hosts.yml
  group_vars/all/vault.yml.example
)

[[ -f $project_root/ansible.cfg ]]

for file in "${required_files[@]}"; do
  [[ -f $ansible_dir/$file ]]
done

grep -Eq 'ansible\.builtin\.file:' "$ansible_dir/roles/baseline/tasks/main.yml"
grep -Eq 'state: directory' "$ansible_dir/roles/baseline/tasks/main.yml"
grep -Eq 'no_log: true' "$project_root/docs/adr/ADR-0005-ansible-automation-standards.md"
grep -Eq 'ansible\.builtin\.deb822_repository:|ansible\.builtin\.apt_repository:' "$ansible_dir/roles/local_toolchain/tasks/docker.yml"
grep -Eq 'force: false' "$ansible_dir/roles/local_toolchain/tasks/local_directories.yml"
grep -Eq 'state: started' "$ansible_dir/roles/local_toolchain/tasks/docker.yml"

printf '%s\n' 'Ansible structure tests passed'
