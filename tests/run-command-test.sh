#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
runner="$project_root/scripts/run-command.sh"

assert_status() {
  local expected=$1
  shift
  local actual=0
  "$@" || actual=$?
  if (( actual != expected )); then
    printf 'expected exit code %d, got %d\n' "$expected" "$actual" >&2
    return 1
  fi
}

assert_status 0 env LOG_LEVEL=DEBUG "$runner" -- printf 'hello\n'
assert_status 23 "$runner" -- bash -c 'exit 23'
assert_status 64 "$runner"

printf '%s\n' 'run-command tests passed'
