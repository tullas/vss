#!/usr/bin/env bash
# Runtime secret presence checks. Never print or return secret values.

_secrets_lib_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=logging.sh
source "$_secrets_lib_dir/logging.sh"

require_secret() {
  if (( $# != 1 )) || [[ ! $1 =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    printf '%s\n' 'usage: require_secret SECRET_VARIABLE_NAME' >&2
    return 64
  fi

  local name=$1
  if [[ ! -v $name || -z ${!name} ]]; then
    log_error "required secret is not available: $name"
    return 78
  fi
}
