#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../scripts/lib/config.sh
source "$project_root/scripts/lib/config.sh"

config_path=$(mktemp -d)
trap 'rm -rf "$config_path"' EXIT
mkdir -p "$config_path/environments"
printf '%s\n' 'REGION=default' 'MODE=default' > "$config_path/default.env"
printf '%s\n' 'MODE=development' 'FEATURE_ENABLED=true' > "$config_path/environments/development.env"
printf '%s\n' 'MODE=local' > "$config_path/local.env"
printf '%s\n' 'MODE=external' > "$config_path/external.env"

export REGION=injected
export CONFIG_DIR="$config_path"
export CONFIG_FILE="$config_path/external.env"
load_config development
[[ $REGION == injected ]]
[[ $MODE == external ]]
[[ $FEATURE_ENABLED == true ]]

printf '%s\n' 'BAD-KEY=value' > "$config_path/invalid.env"
status=0
CONFIG_FILE="$config_path/invalid.env" load_config >/dev/null 2>&1 || status=$?
(( status == 65 ))

printf '%s\n' 'configuration tests passed'
