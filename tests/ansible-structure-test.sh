#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ansible_dir="$project_root/ansible"

required_files=(
  ansible.cfg
  playbooks/site.yml
  roles/baseline/defaults/main.yml
  roles/baseline/tasks/main.yml
  inventories/development/hosts.yml.example
  group_vars/all/vault.yml.example
)

for file in "${required_files[@]}"; do
  [[ -f $ansible_dir/$file ]]
done

rg -q 'ansible\.builtin\.file:' "$ansible_dir/roles/baseline/tasks/main.yml"
rg -q 'state: directory' "$ansible_dir/roles/baseline/tasks/main.yml"
rg -q 'no_log: true' "$project_root/docs/adr/ADR-0005-ansible-automation-standards.md"

printf '%s\n' 'Ansible structure tests passed'
