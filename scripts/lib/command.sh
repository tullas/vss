#!/usr/bin/env bash
# Shared command execution helpers. Source this file from Bash entry points.

_command_lib_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=logging.sh
source "$_command_lib_dir/logging.sh"

# Run a command, logging a shell-escaped representation to stderr. The command
# is passed as separate arguments so no shell parsing or evaluation occurs.
run_command() {
  if (( $# == 0 )); then
    printf '%s\n' 'error: run_command requires a command' >&2
    return 64
  fi

  local rendered_command
  printf -v rendered_command '%q ' "$@"
  log_debug "executing: $rendered_command"

  local status=0
  "$@" || status=$?

  if (( status != 0 )); then
    log_error "command failed with exit code $status: $rendered_command"
  fi

  return "$status"
}
