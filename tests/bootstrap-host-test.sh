#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
script="$root/scripts/bootstrap-host.sh"
[[ -x $script ]]
bash -n "$script"
grep -Fq -- '--resume' "$script"
grep -Fq -- '--check' "$script"
grep -Fq 'RESTART_REQUIRED' "$script"
grep -Fq 'wsl --shutdown' "$script"
grep -Fq 'python3-venv' "$script"
grep -Fq 'pip install --disable-pip-version-check --no-deps -e .' "$script"
grep -Fq 'bootstrap verify' "$script"
grep -Fq 'no terminal is attached' "$script"
printf 'phase-0 bootstrap tests passed\n'
