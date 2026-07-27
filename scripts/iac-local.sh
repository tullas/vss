#!/usr/bin/env bash
# Transparent workflow for the local OpenTofu/Docker provider.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd -- "$script_dir/.." && pwd)
root_dir="$project_root/infrastructure/environments/development/local"
state_dir="$project_root/.local/state/development"
state_file="$state_dir/terraform.tfstate"
secrets_file="$project_root/.local/secrets/development.auto.tfvars"
iac_bin=${IAC_BIN:-tofu}
docker_bin=${DOCKER_BIN:-docker}

usage() {
  printf 'usage: %s init|validate|plan|plan-destroy|apply|status|health|destroy [--non-interactive]\n' "${0##*/}" >&2
  exit 64
}

action=${1:-}
approval_flag=()
if [[ ${2:-} == --non-interactive && $# -eq 2 ]]; then approval_flag=(-auto-approve); elif [[ $# -ne 1 ]]; then usage; fi
case $action in init|validate|plan|plan-destroy|apply|status|health|destroy) ;; *) usage ;; esac
if [[ $action != health ]]; then
  command -v "$iac_bin" >/dev/null 2>&1 || { printf 'OpenTofu executable not found: %s\n' "$iac_bin" >&2; exit 69; }
fi

case $action in
  init)
    mkdir -p "$state_dir"
    "$iac_bin" -chdir="$root_dir" init
    ;;
  validate)
    "$iac_bin" -chdir="$root_dir" init -backend=false
    "$iac_bin" -chdir="$root_dir" validate
    ;;
  plan|plan-destroy)
    [[ -f $secrets_file ]] || { printf 'missing ignored secrets file: %s\n' "$secrets_file" >&2; exit 66; }
    mkdir -p "$state_dir"
    "$iac_bin" -chdir="$root_dir" init
    destroy_flag=()
    [[ $action == plan-destroy ]] && destroy_flag=(-destroy)
    "$iac_bin" -chdir="$root_dir" plan -state="$state_file" -var-file="$secrets_file" "${destroy_flag[@]}"
    ;;
  apply)
    [[ -f $secrets_file ]] || { printf 'missing ignored secrets file: %s\n' "$secrets_file" >&2; exit 66; }
    mkdir -p "$state_dir"
    "$iac_bin" -chdir="$root_dir" init
    "$iac_bin" -chdir="$root_dir" apply -state="$state_file" -var-file="$secrets_file" "${approval_flag[@]}"
    "$iac_bin" -chdir="$root_dir" output -state="$state_file" -json platform_contract
    ;;
  status)
    [[ -f $state_file ]] || { printf '{"managed":false,"resources":{}}\n'; exit 0; }
    if ! "$iac_bin" -chdir="$root_dir" output -state="$state_file" -json platform_contract; then
      printf '{"managed":false,"resources":{}}\n'
    fi
    ;;
  health)
    command -v "$docker_bin" >/dev/null 2>&1 || { printf 'Docker is unavailable; health check skipped\n' >&2; exit 69; }
    container_name='vss-development-minio'
    status=$("$docker_bin" inspect --format '{{.State.Health.Status}}' "$container_name" 2>/dev/null || true)
    if [[ $status == healthy ]]; then
      printf '{"health":{"service":"minio","status":"healthy"}}\n'
    else
      printf 'MinIO health: %s\n' "${status:-unavailable}" >&2
      exit 1
    fi
    ;;
  destroy)
    [[ -f $secrets_file ]] || { printf 'missing ignored secrets file: %s\n' "$secrets_file" >&2; exit 66; }
    "$iac_bin" -chdir="$root_dir" init
    "$iac_bin" -chdir="$root_dir" destroy -state="$state_file" -var-file="$secrets_file" "${approval_flag[@]}"
    printf '{"destroyed":true}\n'
    ;;
esac
