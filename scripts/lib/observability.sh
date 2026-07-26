#!/usr/bin/env bash
# Trace correlation and lightweight metric emission for Bash automation.

_observability_lib_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=logging.sh
source "$_observability_lib_dir/logging.sh"

begin_trace() {
  if (( $# != 1 )) || [[ ! $1 =~ ^[a-zA-Z0-9._-]+$ ]]; then
    printf '%s\n' 'usage: begin_trace operation' >&2
    return 64
  fi
  if [[ -z ${TRACE_ID:-} ]]; then
    TRACE_ID=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
    export TRACE_ID
  fi
  log_info "trace started operation=$1"
}

end_trace() {
  if (( $# != 2 )) || [[ ! $1 =~ ^[a-zA-Z0-9._-]+$ ]] || [[ ! $2 =~ ^[a-zA-Z0-9._-]+$ ]]; then
    printf '%s\n' 'usage: end_trace operation status' >&2
    return 64
  fi
  log_info "trace completed operation=$1 status=$2"
}

emit_metric() {
  if (( $# < 2 || $# > 3 )) || [[ ! $1 =~ ^[a-zA-Z_:][a-zA-Z0-9_:]*$ ]] || [[ ! $2 =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    printf '%s\n' 'usage: emit_metric metric_name numeric_value [unit]' >&2
    return 64
  fi

  local name=$1 value=$2 unit=${3:-count}
  if [[ ! $unit =~ ^[a-zA-Z0-9._/-]+$ ]]; then
    printf '%s\n' 'error: metric unit contains invalid characters' >&2
    return 64
  fi
  log_info "metric name=$name value=$value unit=$unit"
  if [[ -n ${METRICS_FILE:-} ]]; then
    printf '%s %s\n' "$name" "$value" >> "$METRICS_FILE"
  fi
}
