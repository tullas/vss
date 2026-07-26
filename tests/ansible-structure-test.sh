#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ansible_dir="$project_root/ansible"

required_files=(
  playbooks/site.yml
  roles/baseline/defaults/main.yml
  roles/baseline/tasks/main.yml
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

printf '%s\n' 'Ansible structure tests passed'
