#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT

git -C "$temporary" init -q
mkdir -p "$temporary/capabilities/movie-m8-3-real-provider-smoke-2"
: > "$temporary/capabilities/movie-m8-3-real-provider-smoke-2/manifest.yaml"
"$repository_root/scripts/validate-experiment-isolation.sh" "$temporary"

mkdir -p "$temporary/docs/experiments"
: > "$temporary/docs/experiments/m8-3-real-provider-smoke-1.md"
if "$repository_root/scripts/validate-experiment-isolation.sh" "$temporary" >/dev/null 2>&1; then
    printf 'Expected mixed experiment identities to fail isolation validation\n' >&2
    exit 1
fi

: > "$temporary/unrelated-local-file"
rm "$temporary/docs/experiments/m8-3-real-provider-smoke-1.md"
"$repository_root/scripts/validate-experiment-isolation.sh" "$temporary"
