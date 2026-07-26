#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

for environment in development staging production; do
  [[ -f "$project_root/infrastructure/environments/$environment/main.tf" ]]
done
[[ -f "$project_root/infrastructure/modules/baseline/main.tf" ]]
[[ -f "$project_root/infrastructure/backend.tf.example" ]]
local_root="$project_root/infrastructure/environments/development/local"
for file in main.tf variables.tf outputs.tf versions.tf development.auto.tfvars.example; do
  [[ -f "$local_root/$file" ]]
done
for file in platform-interface.md capabilities.schema.json outputs.md; do
  [[ -f "$project_root/infrastructure/contracts/$file" ]]
done
[[ ! -e "$project_root/.local/state" || -z "$(find "$project_root/.local/state" -type f -print -quit)" ]]

status=0
"$project_root/scripts/iac.sh" unsupported development >/dev/null 2>&1 || status=$?
(( status == 64 ))

printf '%s\n' 'IaC structure tests passed'
