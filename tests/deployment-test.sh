#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
deploy="$project_root/scripts/deploy.sh"
workspace=$(mktemp -d)
trap 'rm -rf "$workspace"' EXIT

make_adapter() {
  local name=$1
  local body=$2
  printf '#!/usr/bin/env bash\n%s\n' "$body" > "$workspace/$name"
  chmod +x "$workspace/$name"
}

make_adapter deploy 'printf "deploy:%s:%s\\n" "$1" "$2" >> "$TRACE_FILE"'
make_adapter health 'printf "health:%s:%s\\n" "$1" "$2" >> "$TRACE_FILE"; exit 42'
make_adapter rollback 'printf "rollback:%s:%s\\n" "$1" "$2" >> "$TRACE_FILE"'

trace_file="$workspace/trace"
status=0
TRACE_FILE="$trace_file" DEPLOY_SCRIPT="$workspace/deploy" HEALTHCHECK_SCRIPT="$workspace/health" ROLLBACK_SCRIPT="$workspace/rollback" "$deploy" staging release-1 >/dev/null 2>&1 || status=$?
(( status == 42 ))
expected=$'deploy:staging:release-1\nhealth:staging:release-1\nrollback:staging:release-1'
[[ $(< "$trace_file") == "$expected" ]]

status=0
DEPLOY_SCRIPT="$workspace/deploy" HEALTHCHECK_SCRIPT="$workspace/health" ROLLBACK_SCRIPT="$workspace/rollback" "$deploy" staging 'invalid release' >/dev/null 2>&1 || status=$?
(( status == 78 ))

printf '%s\n' 'deployment tests passed'
