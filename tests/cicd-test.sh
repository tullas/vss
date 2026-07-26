#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
deploy="$project_root/scripts/deploy.sh"

bash -n "$deploy"

status=0
DEPLOY_SCRIPT= "$deploy" development >/dev/null 2>&1 || status=$?
(( status == 78 ))

adapter_dir=$(mktemp -d)
trap 'rm -rf "$adapter_dir"' EXIT
for adapter in deploy health rollback; do
  printf '%s\n' '#!/usr/bin/env bash' 'test "$1" = staging' > "$adapter_dir/$adapter"
  chmod +x "$adapter_dir/$adapter"
done
DEPLOY_SCRIPT="$adapter_dir/deploy" HEALTHCHECK_SCRIPT="$adapter_dir/health" ROLLBACK_SCRIPT="$adapter_dir/rollback" "$deploy" staging release-1 >/dev/null

printf '%s\n' 'CI/CD tests passed'
