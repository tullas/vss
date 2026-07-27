#!/usr/bin/env bash
# Minimal trusted entry point for Ubuntu and Ubuntu under WSL.
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd -- "$script_dir/.." && pwd)
os_release_file=${VSS_OS_RELEASE_FILE:-/etc/os-release}
python_bin=${VSS_PYTHON_BIN:-python3}
venv_dir=${VSS_VENV_DIR:-$project_root/.venv}
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

if [[ ! -d $venv_dir ]] && ! probe_venv; then
  [[ $mode != check ]] || { log "ERROR: Python venv support is missing; install $venv_package"; exit 69; }
  need_sudo
  run "${SUDO[@]}" apt-get update
  run "${SUDO[@]}" apt-get install -y "$venv_package"
  probe_venv || { log "ERROR: Python venv support is still unavailable after installing $venv_package"; exit 69; }
fi

# Internal phase boundary used by clean-image and command-isolation tests.
if [[ ${VSS_BOOTSTRAP_PHASE0_ONLY:-0} == 1 ]]; then
  printf '{"state":"PHASE0_READY","python_version":"%s","venv_package":"%s"}\n' "$python_version" "$venv_package"
  exit 0
fi

if [[ $mode == check ]]; then
  if [[ -x $venv_dir/bin/vss ]]; then run "$venv_dir/bin/vss" bootstrap check --environment development --dry-run; else log 'CHECK: .venv is absent; bootstrap is required'; fi
  exit 0
fi

[[ -d $venv_dir ]] || run "$python_bin" -m venv "$venv_dir"
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
