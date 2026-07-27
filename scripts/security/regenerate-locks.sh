#!/usr/bin/env bash
set -Eeuo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"
generator=${UV_BIN:-uv}
expected='uv 0.10.7'
[[ $($generator --version) == "$expected" ]] || {
  printf 'ERROR: lock generation requires %s\n' "$expected" >&2
  exit 69
}

mkdir -p requirements/locks
common=(--generate-hashes --no-annotate --no-header)
"$generator" pip compile requirements/inputs/runtime.in --python-version 3.12 "${common[@]}" -o requirements/locks/runtime.lock.txt
"$generator" pip compile requirements/inputs/bootstrap.in --python-version 3.11 "${common[@]}" -o requirements/locks/bootstrap-py311.lock.txt
"$generator" pip compile requirements/inputs/bootstrap.in --python-version 3.12 "${common[@]}" -o requirements/locks/bootstrap-py312.lock.txt
"$generator" pip compile requirements/inputs/development.in --python-version 3.12 "${common[@]}" -o requirements/locks/development.lock.txt
python3 scripts/security/update-lock-metadata.py
printf 'deterministic Python locks regenerated; review the complete diff\n'
