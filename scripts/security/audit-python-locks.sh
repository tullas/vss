#!/usr/bin/env bash
set -Eeuo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"

shopt -s nullglob
locks=(requirements/locks/*.lock.txt)
(( ${#locks[@]} > 0 )) || {
  printf 'ERROR: no Python lockfiles found\n' >&2
  exit 1
}

for lock in "${locks[@]}"; do
  printf 'Auditing %s\n' "$lock"
  python -m pip_audit --require-hashes -r "$lock"
done
