#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

for environment in development staging production; do
  [[ -f "$project_root/infrastructure/environments/$environment/main.tf" ]]
done
[[ -f "$project_root/infrastructure/modules/baseline/main.tf" ]]
[[ -f "$project_root/infrastructure/backend.tf.example" ]]

status=0
"$project_root/scripts/iac.sh" unsupported development >/dev/null 2>&1 || status=$?
(( status == 64 ))

printf '%s\n' 'IaC structure tests passed'
