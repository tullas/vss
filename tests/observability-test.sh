#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../scripts/lib/observability.sh
source "$project_root/scripts/lib/observability.sh"

metrics_path=$(mktemp)
trace_log=$(mktemp)
trap 'rm -f "$metrics_path" "$trace_log"' EXIT

begin_trace deploy 2> "$trace_log"
trace_output=$(< "$trace_log")
[[ $TRACE_ID =~ ^[a-f0-9]{32}$ ]]
[[ $trace_output == *"trace_id=$TRACE_ID" ]]

METRICS_FILE="$metrics_path" emit_metric deployment_attempts_total 1 count >/dev/null 2>&1
[[ $(< "$metrics_path") == 'deployment_attempts_total 1' ]]

status=0
emit_metric 'invalid metric' 1 >/dev/null 2>&1 || status=$?
(( status == 64 ))

printf '%s\n' 'observability tests passed'
