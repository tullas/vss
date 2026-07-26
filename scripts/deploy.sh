#!/usr/bin/env bash
# Invoke a target-specific deployment adapter selected by external configuration.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/config.sh
source "$script_dir/lib/config.sh"
# shellcheck source=lib/logging.sh
source "$script_dir/lib/logging.sh"

if (( $# > 1 )); then
  printf 'usage: %s [environment]\n' "${0##*/}" >&2
  exit 64
fi

environment=${1:-${CONFIG_ENV:-}}
load_config "$environment"

if [[ -z ${DEPLOY_SCRIPT:-} ]]; then
  log_error 'DEPLOY_SCRIPT must name an executable deployment adapter'
  exit 78
fi
if [[ ! -x $DEPLOY_SCRIPT || ! -f $DEPLOY_SCRIPT ]]; then
  log_error "DEPLOY_SCRIPT is not an executable regular file: $DEPLOY_SCRIPT"
  exit 78
fi

log_info "starting deployment for environment: ${environment:-default}"
"$DEPLOY_SCRIPT" "${environment:-default}"
