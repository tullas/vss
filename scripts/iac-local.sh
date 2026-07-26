#!/usr/bin/env bash
# Transparent workflow for the local OpenTofu/Docker provider.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd -- "$script_dir/.." && pwd)
root_dir="$project_root/infrastructure/environments/development/local"
state_dir="$project_root/.local/state/development"
secrets_file="$project_root/.local/secrets/development.auto.tfvars"
iac_bin=${IAC_BIN:-tofu}
docker_bin=${DOCKER_BIN:-docker}

usage() {
  printf 'usage: %s init | validate | plan | apply | health | destroy\n' "${0##*/}" >&2
  exit 64
}

action=${1:-}
[[ $# -eq 1 ]] || usage
case $action in init|validate|plan|apply|health|destroy) ;; *) usage ;; esac
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
  plan)
    [[ -f $secrets_file ]] || { printf 'missing ignored secrets file: %s\n' "$secrets_file" >&2; exit 66; }
    mkdir -p "$state_dir"
    "$iac_bin" -chdir="$root_dir" init
    "$iac_bin" -chdir="$root_dir" plan -var-file="$secrets_file"
    ;;
  apply)
    [[ -f $secrets_file ]] || { printf 'missing ignored secrets file: %s\n' "$secrets_file" >&2; exit 66; }
    mkdir -p "$state_dir"
    "$iac_bin" -chdir="$root_dir" init
    "$iac_bin" -chdir="$root_dir" apply -var-file="$secrets_file"
    ;;
  health)
    command -v "$docker_bin" >/dev/null 2>&1 || { printf 'Docker is unavailable; health check skipped\n' >&2; exit 69; }
    container_name='vss-development-minio'
    status=$("$docker_bin" inspect --format '{{.State.Health.Status}}' "$container_name" 2>/dev/null || true)
    if [[ $status == healthy ]]; then
      printf 'MinIO health: healthy\n'
    else
      printf 'MinIO health: %s\n' "${status:-unavailable}" >&2
      exit 1
    fi
    ;;
  destroy)
    [[ -f $secrets_file ]] || { printf 'missing ignored secrets file: %s\n' "$secrets_file" >&2; exit 66; }
    "$iac_bin" -chdir="$root_dir" init
    "$iac_bin" -chdir="$root_dir" destroy -var-file="$secrets_file"
    ;;
esac
