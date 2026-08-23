#!/usr/bin/env bash
set -euo pipefail

repository_root=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
cd "$repository_root"

status=$(git status --porcelain=v1 --untracked-files=all)
mapfile -t identities < <(
    printf '%s\n' "$status" \
        | sed -E 's/^.. //' \
        | grep -Eo 'm8-[0-9]+-real-provider-smoke-[0-9]+' \
        | sort -u \
        || true
)
if (( ${#identities[@]} > 1 )); then
    printf 'Multiple experiment identities are present in the working tree:\n' >&2
    printf '  %s\n' "${identities[@]}" >&2
    exit 1
fi
