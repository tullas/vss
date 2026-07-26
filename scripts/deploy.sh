#!/usr/bin/env bash
# Invoke a target-specific deployment adapter selected by external configuration.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/config.sh
source "$script_dir/lib/config.sh"
# shellcheck source=lib/logging.sh
source "$script_dir/lib/logging.sh"
# shellcheck source=lib/observability.sh
source "$script_dir/lib/observability.sh"

if (( $# > 2 )); then
  printf 'usage: %s [environment] [release-version]\n' "${0##*/}" >&2
  exit 64
fi

environment=${1:-${CONFIG_ENV:-}}
requested_release=${2:-}
load_config "$environment"
release_version=${requested_release:-${RELEASE_VERSION:-}}

if [[ ! $release_version =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
  log_error 'RELEASE_VERSION must be a non-empty safe release identifier'
  exit 78
fi

for adapter in DEPLOY_SCRIPT HEALTHCHECK_SCRIPT ROLLBACK_SCRIPT; do
  adapter_path=${!adapter:-}
  if [[ ! -x $adapter_path || ! -f $adapter_path ]]; then
    log_error "$adapter must name an executable regular file"
    exit 78
  fi
done

begin_trace deployment
deployment_started=$SECONDS
emit_metric deployment_attempts_total 1 count

rollback() {
  local cause_status=$1
  log_warn "deployment failed; starting rollback for release $release_version"
  emit_metric rollback_attempts_total 1 count
  local rollback_status=0
  "$ROLLBACK_SCRIPT" "${environment:-default}" "$release_version" || rollback_status=$?
  if (( rollback_status == 0 )); then
    log_info "rollback completed for release $release_version"
    emit_metric rollback_success_total 1 count
  else
    log_error "rollback failed with exit code $rollback_status for release $release_version"
  fi
  return "$cause_status"
}

log_info "validating deployment of release $release_version to ${environment:-default}"
status=0
"$DEPLOY_SCRIPT" "${environment:-default}" "$release_version" || status=$?
if (( status != 0 )); then
  log_error "deployment failed with exit code $status for release $release_version"
  emit_metric deployment_failures_total 1 count
  rollback_status=0
  rollback "$status" || rollback_status=$?
  end_trace deployment failed
  exit "$rollback_status"
fi

log_info "verifying release $release_version in ${environment:-default}"
"$HEALTHCHECK_SCRIPT" "${environment:-default}" "$release_version" || status=$?
if (( status != 0 )); then
  log_error "post-deployment verification failed with exit code $status for release $release_version"
  emit_metric deployment_failures_total 1 count
  rollback_status=0
  rollback "$status" || rollback_status=$?
  end_trace deployment failed
  exit "$rollback_status"
fi

log_info "deployment completed for release $release_version"
emit_metric deployment_success_total 1 count
emit_metric deployment_duration_seconds "$(( SECONDS - deployment_started ))" seconds
end_trace deployment succeeded
