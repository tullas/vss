#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
output=${1:-$root/dist/security-evidence}
mkdir -p "$output"
git -C "$root" archive --format=tar HEAD | gzip -n >"$output/vss-source.tar.gz"
python3 "$root/scripts/security/generate-sbom.py" --output "$output/vss.cdx.json"
python3 "$root/scripts/security/validate-sbom.py" "$output/vss.cdx.json"
source_uri="git+https://github.com/tullas/vss@$(git -C "$root" rev-parse HEAD)"
python3 "$root/scripts/security/generate-provenance.py" "$output/vss-source.tar.gz" --source "$source_uri" --output "$output/vss-source.intoto.jsonl"
python3 "$root/scripts/security/validate-provenance.py" "$output/vss-source.tar.gz" "$output/vss-source.intoto.jsonl"
python3 "$root/scripts/security/validate-artifacts.py" "$output"
