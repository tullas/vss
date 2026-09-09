#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
scope="$root/config/secrets-baseline-scope-v1.json"
mapfile -t paths < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["paths"]))' "$scope")
if (( ${#paths[@]} == 0 )); then exit 1; fi
cd "$root"
if [[ ${1:-} != --apply ]]; then
  printf 'Refusing baseline mutation. Re-run with --apply; scope is %s\n' "$scope" >&2
  exit 2
fi
exec .venv/bin/detect-secrets scan --baseline .secrets.baseline "${paths[@]}"
