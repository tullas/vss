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

object_storage="$project_root/infrastructure/modules/local/object_storage/main.tf"
grep -Fq 'user      = "65532:65532"' "$object_storage"
grep -Fq 'user     = "0:0"' "$object_storage"
grep -Fq 'read_only = true' "$object_storage"
grep -Fq 'drop = ["ALL"]' "$object_storage"
grep -Fq 'security_opts = ["no-new-privileges:true"]' "$object_storage"
grep -Fq 'ip       = "127.0.0.1"' "$object_storage"
grep -Fq 'CAP_CHOWN", "CAP_FOWNER' "$object_storage"
grep -Fq 'resource "terraform_data" "volume_permissions_complete"' "$object_storage"
grep -Fq 'scripts/check-container-exit.sh' "$object_storage"
grep -Fq 'depends_on = [terraform_data.volume_permissions_complete]' "$object_storage"
grep -Fq 'ghcr.io/tullas/vss/versitygw@sha256:619ffa71548c6128dc52e53846a0f2178f8fe69fd083ae3c9d72982b50e1bd5c' "$project_root/infrastructure/modules/local/object_storage/variables.tf"
! grep -Rqs 'docker.io/minio/minio' "$project_root/infrastructure" "$project_root/.github/workflows"
python3 -m py_compile "$project_root/tests/versitygw-contract.py"
grep -Fq 'run: scripts/acceptance-object-storage.sh' "$project_root/.github/workflows/ci.yml"
! grep -Eq -- '--(access|secret)' "$project_root/tests/versitygw-contract.py"

status=0
"$project_root/scripts/iac.sh" unsupported development >/dev/null 2>&1 || status=$?
(( status == 64 ))

printf '%s\n' 'IaC structure tests passed'
