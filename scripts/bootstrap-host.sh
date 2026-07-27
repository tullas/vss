#!/usr/bin/env bash
# Minimal trusted entry point for Ubuntu and Ubuntu under WSL.
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd -- "$script_dir/.." && pwd)
os_release_file=${VSS_OS_RELEASE_FILE:-/etc/os-release}
python_bin=${VSS_PYTHON_BIN:-python3}
if [[ -n ${VSS_VENV_DIR+x} ]]; then venv_dir=$VSS_VENV_DIR; else venv_dir="$project_root/.venv"; fi
sudo_bin=${VSS_SUDO_BIN:-sudo}
mode=run
verbose=false

usage() { printf 'usage: %s [--check|--resume] [--verbose]\n' "${0##*/}" >&2; exit 64; }
for argument in "$@"; do
  case $argument in
    --check) mode=check ;;
    --resume) mode=resume ;;
    --verbose) verbose=true ;;
    *) usage ;;
  esac
done

[[ $PWD -ef $project_root && -f pyproject.toml && -d .git ]] || {
  printf 'ERROR: run ./scripts/bootstrap-host.sh from the VSS repository root\n' >&2; exit 64;
}
[[ -r $os_release_file ]] || { printf 'ERROR: unsupported operating system; Ubuntu is required\n' >&2; exit 69; }
# shellcheck disable=SC1091
source "$os_release_file"
[[ ${ID:-} == ubuntu ]] || { printf 'ERROR: unsupported operating system: %s; Ubuntu is required\n' "${PRETTY_NAME:-unknown}" >&2; exit 69; }

is_wsl=${VSS_IS_WSL:-false}
if [[ -z ${VSS_IS_WSL+x} ]] && grep -Eqi '(microsoft|wsl)' /proc/sys/kernel/osrelease 2>/dev/null; then is_wsl=true; fi
pid1=${VSS_PID1:-$(tr -d '[:space:]' </proc/1/comm 2>/dev/null || true)}
progress_dir="$project_root/.local/bootstrap"
progress_file="$progress_dir/progress"
mkdir -p "$progress_dir"
chmod 700 "$progress_dir"

log() { printf '%s\n' "$*" >&2; }
run() { if $verbose; then printf '+ %q ' "$@" >&2; printf '\n' >&2; fi; "$@"; }
need_sudo() {
  if (( EUID == 0 )); then SUDO=(); return; fi
  command -v "$sudo_bin" >/dev/null 2>&1 || { log 'ERROR: sudo is required for host changes'; exit 77; }
  if [[ ${VSS_BOOTSTRAP_ALLOW_NONINTERACTIVE_SUDO:-0} != 1 && ( ! -t 0 || ! -t 1 ) ]]; then
    log 'ERROR: host changes require interactive sudo, but no terminal is attached'; exit 77
  fi
  SUDO=("$sudo_bin")
}
restart_required() {
  printf 'state=RESTART_REQUIRED\nreason=%s\n' "$1" >"$progress_file"
  chmod 600 "$progress_file"
  printf '{"state":"RESTART_REQUIRED","reason":"%s","resume":"./scripts/bootstrap-host.sh --resume"}\n' "$1"
  if $is_wsl; then
    printf 'Run from Windows PowerShell:\n'
    printf 'wsl --shutdown\n'
  else
    printf 'Start a new login session, then run ./scripts/bootstrap-host.sh --resume\n'
  fi
  exit 24
}

if $is_wsl && [[ $pid1 != systemd ]]; then
  if [[ $mode == check ]]; then
    restart_required systemd
  fi
  need_sudo
  tmp_file=$(mktemp)
  trap 'rm -f "$tmp_file"' EXIT
  if [[ -f /etc/wsl.conf ]]; then
    awk '
      BEGIN { in_boot=0; saw_boot=0; wrote=0 }
      /^\[boot\][[:space:]]*$/ { if (in_boot && !wrote) print "systemd=true"; in_boot=1; saw_boot=1; wrote=0; print; next }
      /^\[/ { if (in_boot && !wrote) print "systemd=true"; in_boot=0 }
      in_boot && /^[[:space:]]*systemd[[:space:]]*=/ { if (!wrote) print "systemd=true"; wrote=1; next }
      { print }
      END { if (in_boot && !wrote) print "systemd=true"; if (!saw_boot) print "\n[boot]\nsystemd=true" }
    ' /etc/wsl.conf >"$tmp_file"
  else
    printf '[boot]\nsystemd=true\n' >"$tmp_file"
  fi
  run "${SUDO[@]}" install -m 0644 "$tmp_file" /etc/wsl.conf
  restart_required systemd
fi

command -v "$python_bin" >/dev/null 2>&1 || { log 'ERROR: Python 3.11 or newer is required'; exit 69; }
"$python_bin" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || {
  log 'ERROR: Python 3.11 or newer is required'; exit 69;
}
python_version=$("$python_bin" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
[[ $python_version =~ ^[0-9]+\.[0-9]+$ ]] || { log 'ERROR: unable to determine the Python version'; exit 69; }
venv_package="python${python_version}-venv"

validate_venv_path() {
  local root_real target_real test_root_real
  [[ -n $venv_dir ]] || { log 'ERROR: VSS virtual environment path is empty'; exit 64; }
  root_real=$(realpath -e -- "$project_root")
  target_real=$(realpath -m -- "$venv_dir")
  [[ $target_real != / && $target_real != "$root_real" ]] || {
    log 'ERROR: refusing dangerous VSS virtual environment path'; exit 64;
  }
  if [[ -L $venv_dir ]]; then
    log 'ERROR: refusing symbolic-link VSS virtual environment path'; exit 64
  fi
  case $target_real in
    "$root_real"/*) ;;
    *)
      [[ -n ${VSS_BOOTSTRAP_TEST_ROOT:-} ]] || {
        log 'ERROR: VSS virtual environment must be inside the repository'; exit 64;
      }
      test_root_real=$(realpath -m -- "$VSS_BOOTSTRAP_TEST_ROOT")
      case $target_real in
        "$test_root_real"/*) ;;
        *) log 'ERROR: VSS virtual environment must be inside the repository'; exit 64 ;;
      esac
      ;;
  esac
  venv_dir=$target_real
}

venv_health_reason=unknown
venv_healthy() {
  local candidate=$1 candidate_python="$1/bin/python"
  if [[ ! -x $candidate_python ]]; then venv_health_reason=missing-python; return 1; fi
  if ! "$candidate_python" -c 'pass' >/dev/null 2>&1; then venv_health_reason=python-failed; return 1; fi
  if ! "$candidate_python" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    venv_health_reason=unsupported-python
    return 1
  fi
  if ! "$candidate_python" -m pip --version >/dev/null 2>&1; then venv_health_reason=pip-missing; return 1; fi
  venv_health_reason=healthy
  return 0
}

probe_venv() {
  local probe_dir
  probe_dir=$(mktemp -d)
  if "$python_bin" -m venv "$probe_dir" >/dev/null 2>&1; then
    rm -rf -- "$probe_dir"
    return 0
  fi
  rm -rf -- "$probe_dir"
  return 1
}

ensure_system_venv_support() {
  probe_venv && return 0
  need_sudo
  run "${SUDO[@]}" apt-get update
  run "${SUDO[@]}" apt-get install -y "$venv_package"
  probe_venv || { log "ERROR: Python venv support is still unavailable after installing $venv_package"; exit 69; }
}

replace_venv() {
  local parent base replacement backup=
  parent=$(dirname -- "$venv_dir")
  base=$(basename -- "$venv_dir")
  mkdir -p -- "$parent"
  replacement=$(mktemp -d "$parent/.${base}.replacement.XXXXXX")
  if ! "$python_bin" -m venv "$replacement" >/dev/null 2>&1; then
    rm -rf -- "$replacement"
    log 'ERROR: failed to create replacement VSS virtual environment'
    exit 69
  fi
  if ! venv_healthy "$replacement" && [[ $venv_health_reason == pip-missing ]]; then
    "$replacement/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi
  if ! venv_healthy "$replacement"; then
    rm -rf -- "$replacement"
    log "ERROR: replacement VSS virtual environment is unhealthy ($venv_health_reason)"
    exit 69
  fi
  if [[ -e $venv_dir ]]; then
    backup="$parent/.${base}.backup.$$"
    [[ ! -e $backup ]] || { rm -rf -- "$replacement"; log 'ERROR: temporary VSS venv backup path already exists'; exit 69; }
    if ! mv -- "$venv_dir" "$backup"; then
      rm -rf -- "$replacement"
      log 'ERROR: failed to preserve unhealthy VSS virtual environment'
      exit 69
    fi
  fi
  if ! mv -- "$replacement" "$venv_dir"; then
    [[ -n $backup && -e $backup && ! -e $venv_dir ]] && mv -- "$backup" "$venv_dir"
    rm -rf -- "$replacement"
    log 'ERROR: failed to activate replacement VSS virtual environment'
    exit 69
  fi
  [[ -z $backup ]] || rm -rf -- "$backup"
}

validate_venv_path
venv_was_healthy=false
if venv_healthy "$venv_dir"; then
  venv_was_healthy=true
elif [[ -e $venv_dir ]]; then
  log "VSS virtual environment is unhealthy ($venv_health_reason); rebuilding safely"
fi

if ! $venv_was_healthy; then
  if [[ $mode == check ]]; then
    if [[ ! -e $venv_dir ]] && ! probe_venv; then
      log "ERROR: Python venv support is missing; install $venv_package"
    else
      log "ERROR: VSS virtual environment is not ready ($venv_health_reason)"
    fi
    exit 69
  fi
  ensure_system_venv_support
fi

# Internal phase boundary used by clean-image and command-isolation tests.
if [[ ${VSS_BOOTSTRAP_PHASE0_ONLY:-0} == 1 ]]; then
  printf '{"state":"PHASE0_READY","python_version":"%s","venv_package":"%s"}\n' "$python_version" "$venv_package"
  exit 0
fi

if ! $venv_was_healthy; then
  replace_venv
fi
venv_healthy "$venv_dir" || { log "ERROR: VSS virtual environment verification failed ($venv_health_reason)"; exit 69; }

# Internal boundary for managed-venv recovery and clean-image acceptance tests.
if [[ ${VSS_BOOTSTRAP_VENV_ONLY:-0} == 1 ]]; then
  printf '{"state":"VENV_READY","python_version":"%s"}\n' "$python_version"
  exit 0
fi

if [[ $mode == check ]]; then
  if [[ -x $venv_dir/bin/vss ]]; then run "$venv_dir/bin/vss" bootstrap check --environment development --dry-run; else log 'CHECK: .venv is absent; bootstrap is required'; fi
  exit 0
fi

run "$venv_dir/bin/python" -m pip install --disable-pip-version-check -r requirements-bootstrap.txt
run "$venv_dir/bin/python" -m pip install --disable-pip-version-check --no-deps -e .
if [[ ! -L /usr/local/bin/vss || $(readlink -f /usr/local/bin/vss 2>/dev/null || true) != "$venv_dir/bin/vss" ]]; then
  need_sudo
  run "${SUDO[@]}" ln -sfn "$venv_dir/bin/vss" /usr/local/bin/vss
fi
run "$venv_dir/bin/vss" bootstrap check --environment development
bootstrap_args=(bootstrap local --environment development)
if (( EUID != 0 )); then
  [[ -t 0 && -t 1 ]] || { log 'ERROR: bootstrap requires interactive sudo, but no terminal is attached'; exit 77; }
  bootstrap_args+=(--ask-become-pass)
fi
run "$venv_dir/bin/vss" "${bootstrap_args[@]}"

current_user=${SUDO_USER:-$USER}
if getent group docker >/dev/null 2>&1 && id -nG "$current_user" | tr ' ' '\n' | grep -Fxq docker; then :
elif getent group docker | cut -d: -f4 | tr ',' '\n' | grep -Fxq "$current_user"; then
  restart_required docker_group
fi
run "$venv_dir/bin/vss" bootstrap verify --environment development
printf 'state=COMPLETE\n' >"$progress_file"
chmod 600 "$progress_file"
printf '{"state":"COMPLETE","environment":"development"}\n'
