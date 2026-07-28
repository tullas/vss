#!/usr/bin/env bash
set -euo pipefail

readonly project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly environment_root="$project_root/infrastructure/environments/development/local"
readonly work_dir=$(mktemp -d)
readonly state_file="$work_dir/object-storage.tfstate"
readonly vars_file="$work_dir/object-storage.auto.tfvars"

cleanup() {
  tofu -chdir="$environment_root" destroy -auto-approve -input=false \
    -var-file="$vars_file" >/dev/null 2>&1 || true
  rm -rf "$work_dir"
}
trap cleanup EXIT

umask 077
export VSS_CONTRACT_ACCESS_KEY="vss-test-$(openssl rand -hex 8)"
export VSS_CONTRACT_SECRET_KEY="$(openssl rand -hex 24)"
printf 'minio_root_user = "%s"\nminio_root_password = "%s"\n' \
  "$VSS_CONTRACT_ACCESS_KEY" "$VSS_CONTRACT_SECRET_KEY" >"$vars_file"

tofu -chdir="$environment_root" init -input=false -lockfile=readonly -reconfigure \
  -backend-config="path=$state_file" >/dev/null
tofu -chdir="$environment_root" apply -auto-approve -input=false \
  -var-file="$vars_file" >/dev/null

test "$(docker inspect --format '{{.State.ExitCode}}' vss-development-object-storage-init)" = "0"
python3 "$project_root/tests/versitygw-contract.py" seed

docker restart vss-development-object-storage >/dev/null
tofu -chdir="$environment_root" apply -auto-approve -input=false \
  -var-file="$vars_file" >/dev/null
python3 "$project_root/tests/versitygw-contract.py" verify-cleanup

tofu -chdir="$environment_root" plan -detailed-exitcode -input=false \
  -var-file="$vars_file" >/dev/null
printf 'Object-storage lifecycle and S3 contract acceptance passed\n'
