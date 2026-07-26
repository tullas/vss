#!/usr/bin/env bash
# Shared, timestamped logging helpers. Logs are intentionally sent to stderr.

_log_level_value() {
  case $1 in
    DEBUG) printf '10\n' ;;
    INFO)  printf '20\n' ;;
    WARN)  printf '30\n' ;;
    ERROR) printf '40\n' ;;
    *) return 64 ;;
  esac
}

log_message() {
  if (( $# < 2 )); then
    printf '%s\n' 'error: log_message requires a level and message' >&2
    return 64
  fi

  local level=$1
  shift
  local configured_level=${LOG_LEVEL:-INFO}
  local level_value configured_value
  level_value=$(_log_level_value "$level") || {
    printf 'error: invalid log level: %s\n' "$level" >&2
    return 64
  }
  configured_value=$(_log_level_value "$configured_level") || {
    printf 'error: invalid LOG_LEVEL: %s\n' "$configured_level" >&2
    return 64
  }

  if (( level_value < configured_value )); then
    return 0
  fi

  local timestamp line
  timestamp=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
  printf -v line '%s %s %s' "$timestamp" "$level" "$*"
  printf '%s\n' "$line" >&2
  if [[ -n ${LOG_FILE:-} ]]; then
    printf '%s\n' "$line" >> "$LOG_FILE"
  fi
}

log_debug() { log_message DEBUG "$@"; }
log_info() { log_message INFO "$@"; }
log_warn() { log_message WARN "$@"; }
log_error() { log_message ERROR "$@"; }
