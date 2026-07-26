#!/usr/bin/env bash
# Safe configuration loader for simple KEY=VALUE files.

_config_lib_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
_config_default_dir=$(cd -- "$_config_lib_dir/../.." && pwd)/config

load_config() {
  if (( $# > 1 )); then
    printf '%s\n' 'usage: load_config [environment]' >&2
    return 64
  fi

  local environment=${1:-${CONFIG_ENV:-}}
  local config_dir=${CONFIG_DIR:-$_config_default_dir}
  local file line key value
  local -a files=("$config_dir/default.env")
  local -A values=()

  if [[ -n $environment ]]; then
    files+=("$config_dir/environments/$environment.env")
  fi
  files+=("$config_dir/local.env")
  if [[ -n ${CONFIG_FILE:-} ]]; then
    if [[ ! -f $CONFIG_FILE ]]; then
      printf 'error: CONFIG_FILE is not a regular file: %s\n' "$CONFIG_FILE" >&2
      return 66
    fi
    files+=("$CONFIG_FILE")
  fi

  for file in "${files[@]}"; do
    [[ -e $file ]] || continue
    if [[ ! -f $file ]]; then
      printf 'error: configuration path is not a regular file: %s\n' "$file" >&2
      return 66
    fi
    while IFS= read -r line || [[ -n $line ]]; do
      [[ -z $line || $line == \#* ]] && continue
      if [[ $line != *=* ]]; then
        printf 'error: invalid configuration line in %s: %s\n' "$file" "$line" >&2
        return 65
      fi
      key=${line%%=*}
      value=${line#*=}
      if [[ ! $key =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
        printf 'error: invalid configuration key in %s: %s\n' "$file" "$key" >&2
        return 65
      fi
      values["$key"]=$value
    done < "$file"
  done

  for key in "${!values[@]}"; do
    if [[ ! -v $key ]]; then
      export "$key=${values[$key]}"
    fi
  done
}
