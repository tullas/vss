#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../scripts/lib/logging.sh
source "$project_root/scripts/lib/logging.sh"

log_path=$(mktemp)
trap 'rm -f "$log_path"' EXIT

output=$(LOG_LEVEL=DEBUG LOG_FILE="$log_path" log_debug 'diagnostic details' 2>&1)
[[ $output =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\ DEBUG\ diagnostic\ details$ ]]
[[ $(< "$log_path") == "$output" ]]

output=$(LOG_LEVEL=WARN log_info 'hidden message' 2>&1)
[[ -z $output ]]

status=0
LOG_LEVEL=INVALID log_info 'message' >/dev/null 2>&1 || status=$?
(( status == 64 ))

printf '%s\n' 'logging tests passed'
