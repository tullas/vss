#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT

cat >"$test_dir/docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $1 == wait ]]; then
  printf '%s\n' "$2"
elif [[ $1 == inspect ]]; then
  printf '%s\n' "${VSS_TEST_EXIT_CODE:?}"
else
  exit 64
fi
EOF
chmod +x "$test_dir/docker"

PATH="$test_dir:$PATH" VSS_INIT_CONTAINER_ID=container-id VSS_TEST_EXIT_CODE=0 \
  "$project_root/scripts/check-container-exit.sh"

status=0
PATH="$test_dir:$PATH" VSS_INIT_CONTAINER_ID=container-id VSS_TEST_EXIT_CODE=17 \
  "$project_root/scripts/check-container-exit.sh" >/dev/null 2>&1 || status=$?
(( status == 1 ))

printf 'Container completion gate tests passed\n'
