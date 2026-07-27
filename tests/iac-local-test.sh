#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
status=0
DOCKER_BIN=__vss_missing_docker__ "$project_root/scripts/iac-local.sh" health >/tmp/vss-iac-health.out 2>&1 || status=$?
(( status == 69 ))
grep -Fq 'Docker is unavailable' /tmp/vss-iac-health.out

grep -Eq 'init .*input=false' "$project_root/scripts/iac-local.sh"
grep -Eq 'plan .*input=false' "$project_root/scripts/iac-local.sh"
grep -Eq 'apply .*input=false' "$project_root/scripts/iac-local.sh"
grep -Eq 'destroy .*input=false' "$project_root/scripts/iac-local.sh"

printf '%s\n' 'local IaC workflow tests passed'
