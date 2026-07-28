#!/usr/bin/env bash
set -euo pipefail

: "${VSS_INIT_CONTAINER_ID:?initializer container ID is required}"
docker wait "$VSS_INIT_CONTAINER_ID" >/dev/null
readonly exit_code=$(docker inspect --format '{{.State.ExitCode}}' "$VSS_INIT_CONTAINER_ID")
if [[ $exit_code != 0 ]]; then
  printf 'Object-storage volume initialization failed (exit %s)\n' "$exit_code" >&2
  exit 1
fi
