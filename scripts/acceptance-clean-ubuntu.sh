#!/usr/bin/env bash
# Run in a disposable clean Ubuntu VM with an interactive sudo-capable user.
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"
log_dir=.local/bootstrap/acceptance
mkdir -p "$log_dir"
chmod 700 "$log_dir"

run_logged() {
  local name=$1
  shift
  "$@" >"$log_dir/$name.log" 2>&1
}

check_status=0
run_logged 01-check ./scripts/bootstrap-host.sh --check || check_status=$?
(( check_status == 0 || check_status == 69 ))
run_logged 02-bootstrap ./scripts/bootstrap-host.sh
run_logged 03-bootstrap-idempotent ./scripts/bootstrap-host.sh
run_logged 04-secrets vss secrets init --environment development
run_logged 05-plan vss platform plan --environment development
run_logged 06-up vss platform up --environment development --non-interactive
run_logged 07-health vss platform verify --environment development
run_logged 08-up-idempotent vss platform up --environment development --non-interactive
run_logged 09-down vss platform down --environment development --yes --non-interactive
run_logged 10-status vss platform status --environment development
git check-ignore --quiet .local/secrets/development.auto.tfvars .local/state/development/terraform.tfstate
! grep -REi '(minio_root_password[[:space:]]*=|minio_root_user[[:space:]]*=)' "$log_dir"
grep -Fq '"destroyed":true' "$log_dir/09-down.log"
grep -Fq '"managed":false' "$log_dir/10-status.log"
printf 'clean Ubuntu acceptance passed\n'
