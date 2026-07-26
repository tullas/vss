#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
deploy="$project_root/scripts/deploy.sh"

bash -n "$deploy"

status=0
DEPLOY_SCRIPT= "$deploy" development >/dev/null 2>&1 || status=$?
(( status == 78 ))

adapter=$(mktemp)
trap 'rm -f "$adapter"' EXIT
printf '%s\n' '#!/usr/bin/env bash' 'test "$1" = staging' > "$adapter"
chmod +x "$adapter"
DEPLOY_SCRIPT="$adapter" "$deploy" staging >/dev/null

printf '%s\n' 'CI/CD tests passed'
