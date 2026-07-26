#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
status=0
DOCKER_BIN=__vss_missing_docker__ "$project_root/scripts/iac-local.sh" health >/tmp/vss-iac-health.out 2>&1 || status=$?
(( status == 69 ))
grep -Fq 'Docker is unavailable' /tmp/vss-iac-health.out

printf '%s\n' 'local IaC workflow tests passed'
