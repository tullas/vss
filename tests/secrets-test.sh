#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../scripts/lib/secrets.sh
source "$project_root/scripts/lib/secrets.sh"

APP_TOKEN=available require_secret APP_TOKEN

status=0
require_secret MISSING_TOKEN >/dev/null 2>&1 || status=$?
(( status == 78 ))

status=0
require_secret 'invalid-name' >/dev/null 2>&1 || status=$?
(( status == 64 ))

printf '%s\n' 'secrets tests passed'
