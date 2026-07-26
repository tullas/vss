#!/usr/bin/env bash
# Execute one command through the project's standard command runner.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib/command.sh
source "$script_dir/lib/command.sh"

if [[ ${1:-} == -- ]]; then
  shift
fi

if (( $# == 0 )); then
  printf 'usage: %s [--] command [argument ...]\n' "${0##*/}" >&2
  exit 64
fi

run_command "$@"
