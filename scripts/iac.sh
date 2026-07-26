#!/usr/bin/env bash
# Controlled OpenTofu workflow for environment roots.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/logging.sh
source "$script_dir/lib/logging.sh"

usage() {
  printf 'usage: %s validate <environment> | plan <environment> | apply <environment> <plan-file>\n' "${0##*/}" >&2
  exit 64
}

action=${1:-}
environment=${2:-}
[[ -n $action && -n $environment && $environment =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || usage
case $action in validate|plan|apply) ;; *) usage ;; esac

root_dir=$(cd -- "$script_dir/.." && pwd)
environment_dir="$root_dir/infrastructure/environments/$environment"
[[ -d $environment_dir ]] || { log_error "unknown infrastructure environment: $environment"; exit 66; }

iac_bin=${IAC_BIN:-tofu}
command -v "$iac_bin" >/dev/null 2>&1 || { log_error "OpenTofu executable not found: $iac_bin"; exit 69; }

init_and_validate() {
  "$iac_bin" -chdir="$environment_dir" init -backend=false
  "$iac_bin" -chdir="$environment_dir" validate
}

init_with_backend() {
  "$iac_bin" -chdir="$environment_dir" init
  "$iac_bin" -chdir="$environment_dir" validate
}

case $action in
  validate)
    (( $# == 2 )) || usage
    log_info "validating infrastructure environment: $environment"
    init_and_validate
    ;;
  plan)
    (( $# == 2 )) || usage
    plan_file=${IAC_PLAN_FILE:-"$environment_dir/$environment.tfplan"}
    log_info "planning infrastructure environment: $environment"
    init_with_backend
    "$iac_bin" -chdir="$environment_dir" plan -out="$plan_file"
    ;;
  apply)
    (( $# == 3 )) || usage
    plan_file=$3
    [[ -f $plan_file ]] || { log_error "plan file not found: $plan_file"; exit 66; }
    [[ ${IAC_CONFIRM_APPLY:-} == "$environment" ]] || {
      log_error "set IAC_CONFIRM_APPLY=$environment before applying"
      exit 77
    }
    log_warn "applying reviewed infrastructure plan for environment: $environment"
    init_with_backend
    "$iac_bin" -chdir="$environment_dir" apply "$plan_file"
    ;;
esac
