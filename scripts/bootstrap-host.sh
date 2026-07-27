#!/usr/bin/env bash
# Minimal trusted entry point for Ubuntu and Ubuntu under WSL.
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd -- "$script_dir/.." && pwd)
os_release_file=${VSS_OS_RELEASE_FILE:-/etc/os-release}
python_bin=${VSS_PYTHON_BIN:-python3}
if [[ -n ${VSS_VENV_DIR+x} ]]; then venv_dir=$VSS_VENV_DIR; else venv_dir="$project_root/.venv"; fi
sudo_bin=${VSS_SUDO_BIN:-sudo}
SUDO=()
sudo_keeper_pid=
sudo_preauthenticated=false
tmp_file=
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
run_privileged() {
  if (( EUID == 0 )); then run "$@"; else run "${SUDO[@]}" -n "$@"; fi
}
stop_sudo_keeper() {
  [[ -n $sudo_keeper_pid ]] || return 0
  kill "$sudo_keeper_pid" 2>/dev/null || true
  wait "$sudo_keeper_pid" 2>/dev/null || true
  sudo_keeper_pid=
}
cleanup() {
  stop_sudo_keeper
  if $sudo_preauthenticated; then
    "${SUDO[@]}" -k >/dev/null 2>&1 || true
    sudo_preauthenticated=false
  fi
  [[ -z $tmp_file ]] || rm -f -- "$tmp_file"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
need_sudo() {
  if (( EUID == 0 )); then SUDO=(); return; fi
  command -v "$sudo_bin" >/dev/null 2>&1 || { log 'ERROR: sudo is required for host changes'; exit 77; }
  if [[ ${VSS_BOOTSTRAP_ALLOW_NONINTERACTIVE_SUDO:-0} != 1 && ( ! -t 0 || ! -t 1 ) ]]; then
    log 'ERROR: host changes require interactive sudo, but no terminal is attached'; exit 77
  fi
  SUDO=("$sudo_bin")
}
sudo_keeper() {
  local sleep_pid=
  trap '[[ -z $sleep_pid ]] || kill "$sleep_pid" 2>/dev/null || true; wait "$sleep_pid" 2>/dev/null || true; exit 0' TERM INT
  while "${SUDO[@]}" -n true >/dev/null 2>&1; do
    sleep "${VSS_SUDO_KEEPALIVE_SECONDS:-45}" &
    sleep_pid=$!
    wait "$sleep_pid" || exit 0
    sleep_pid=
  done
}
preauthenticate_sudo() {
  if (( EUID == 0 )); then return 0; fi
  if [[ ! -t 0 || ! -t 1 || ! -t 2 ]]; then
    log 'ERROR: bootstrap requires an interactive terminal for sudo authentication'
    exit 77
  fi
  need_sudo
  if ! run "${SUDO[@]}" -v; then
    log 'ERROR: sudo authentication failed; bootstrap stopped before Ansible'
    exit 77
  fi
  if ! "${SUDO[@]}" -n true >/dev/null 2>&1; then
    log 'ERROR: sudo authentication could not be validated; bootstrap stopped before Ansible'
    exit 77
  fi
  sudo_preauthenticated=true
  sudo_keeper &
  sudo_keeper_pid=$!
}

derive_developer_identity() {
  local passwd_entry repository_uid
  developer_repository_root=$(realpath -e -- "$project_root")
  repository_uid=$(stat -c '%u' -- "$developer_repository_root")

  if (( EUID == 0 )); then
    developer_uid=$repository_uid
  else
    developer_uid=$(id -u)
    [[ $repository_uid == "$developer_uid" ]] || {
      log 'ERROR: repository ownership does not match the invoking developer'
      exit 77
    }
  fi
  [[ $developer_uid =~ ^[0-9]+$ ]] || { log 'ERROR: unable to validate the developer uid'; exit 77; }
  passwd_entry=$(getent passwd "$developer_uid" || true)
  [[ -n $passwd_entry && $(grep -c '^' <<<"$passwd_entry") -eq 1 ]] || {
    log 'ERROR: unable to resolve the repository owner in the local passwd database'
    exit 77
  }
  IFS=: read -r developer_user _ passwd_uid developer_gid _ developer_home _ <<<"$passwd_entry"
  [[ $passwd_uid == "$developer_uid" && $developer_gid =~ ^[0-9]+$ ]] || {
    log 'ERROR: local passwd identity does not match the repository owner'
    exit 77
  }
  [[ $(id -u "$developer_user") == "$developer_uid" && $(id -g "$developer_user") == "$developer_gid" ]] || {
    log 'ERROR: developer identity validation failed'
    exit 77
  }
  [[ $developer_home == /* && $developer_home != / && -d $developer_home ]] || {
    log 'ERROR: developer home directory is invalid'
    exit 77
  }
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
case $python_version in
  3.11) selected_ansible_version=2.19.9; bootstrap_lock=requirements/locks/bootstrap-py311.lock.txt ;;
  3.12|3.13|3.14) selected_ansible_version=2.21.2; bootstrap_lock=requirements/locks/bootstrap-py312.lock.txt ;;
  *) log "ERROR: Python $python_version is unsupported by the VSS Ansible compatibility policy; supported versions are 3.11 through 3.14"; exit 69 ;;
esac
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
  local candidate=$1 candidate_python="$1/bin/python" candidate_version
  if [[ ! -x $candidate_python ]]; then venv_health_reason=missing-python; return 1; fi
  if ! "$candidate_python" -c 'pass' >/dev/null 2>&1; then venv_health_reason=python-failed; return 1; fi
  if ! "$candidate_python" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    venv_health_reason=unsupported-python
    return 1
  fi
  candidate_version=$("$candidate_python" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
  if [[ $candidate_version != "$python_version" ]]; then venv_health_reason=python-version-mismatch; return 1; fi
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

# VSS commands discover their managed tools (including Ansible) through PATH.
# Export the validated environment before invoking any VSS entry point so users
# never need to activate the virtual environment themselves.
export PATH="$venv_dir/bin:$PATH"

# Internal boundary for managed-venv recovery and clean-image acceptance tests.
if [[ ${VSS_BOOTSTRAP_VENV_ONLY:-0} == 1 ]]; then
  printf '{"state":"VENV_READY","python_version":"%s"}\n' "$python_version"
  exit 0
fi

if [[ $mode == check ]]; then
  if [[ -x $venv_dir/bin/vss ]]; then run "$venv_dir/bin/vss" bootstrap check --environment development --dry-run; else log 'CHECK: .venv is absent; bootstrap is required'; fi
  exit 0
fi

installed_ansible_version=$("$venv_dir/bin/python" -c 'from ansible.release import __version__; print(__version__)' 2>/dev/null || true)
ansible_combination_supported=false
[[ $installed_ansible_version == "$selected_ansible_version" ]] && ansible_combination_supported=true
printf '{"state":"ANSIBLE_COMPATIBILITY","python_version":"%s","installed_ansible_core":"%s","selected_ansible_core":"%s","supported":%s}\n' \
  "$python_version" "${installed_ansible_version:-not-installed}" "$selected_ansible_version" "$ansible_combination_supported" >&2

run "$venv_dir/bin/python" -m pip install --disable-pip-version-check --require-hashes -r "$bootstrap_lock"
run "$venv_dir/bin/python" -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e .

installed_ansible_version=$("$venv_dir/bin/python" -c 'from ansible.release import __version__; print(__version__)' 2>/dev/null || true)
[[ $installed_ansible_version == "$selected_ansible_version" ]] || {
  log "ERROR: ansible-core compatibility verification failed for Python $python_version"
  exit 69
}

verify_venv_executable() {
  local executable=$1 expected="$venv_dir/bin/$1" discovered
  [[ -x $expected ]] || { log "ERROR: required VSS virtual environment executable is unavailable: $executable"; exit 69; }
  discovered=$(command -v -- "$executable" 2>/dev/null || true)
  [[ $discovered == "$expected" ]] || {
    log "ERROR: required executable does not resolve from the VSS virtual environment: $executable"
    exit 69
  }
}
for executable in python pip vss ansible-playbook; do
  verify_venv_executable "$executable"
done
run "$venv_dir/bin/ansible-playbook" --version >/dev/null

# Internal boundary used by clean-image and command-isolation tests.
if [[ ${VSS_BOOTSTRAP_INSTALL_ONLY:-0} == 1 ]]; then
  printf '{"state":"TOOLCHAIN_READY","python_version":"%s","ansible_core_version":"%s","ansible_compatible":true}\n' \
    "$python_version" "$installed_ansible_version"
  exit 0
fi

preauthenticate_sudo

# Internal boundary used by sudo lifecycle and clean-image acceptance tests.
if [[ ${VSS_BOOTSTRAP_SUDO_ONLY:-0} == 1 ]]; then
  printf '{"state":"SUDO_READY","preauthenticated":%s}\n' "$([[ $EUID == 0 ]] && printf false || printf true)"
  exit 0
fi

derive_developer_identity

if [[ ! -L /usr/local/bin/vss || $(readlink -f /usr/local/bin/vss 2>/dev/null || true) != "$venv_dir/bin/vss" ]]; then
  run_privileged ln -sfn "$venv_dir/bin/vss" /usr/local/bin/vss
  run_privileged chown -h root:root /usr/local/bin/vss
fi
run "$venv_dir/bin/vss" bootstrap check --environment development
developer_extra_vars=$("$venv_dir/bin/python" -c \
  'import json,sys; print(json.dumps(dict(zip(("local_toolchain_developer_user", "local_toolchain_developer_uid", "local_toolchain_developer_gid", "local_toolchain_developer_home", "local_toolchain_project_root"), sys.argv[1:]))))' \
  "$developer_user" "$developer_uid" "$developer_gid" "$developer_home" "$developer_repository_root")
if ! run_privileged "$venv_dir/bin/ansible-playbook" \
  -i "$project_root/ansible/inventories/development/hosts.yml" \
  "$project_root/ansible/playbooks/bootstrap-local.yml" \
  --extra-vars "$developer_extra_vars"; then
  log 'ERROR: privileged local toolchain bootstrap failed'
  exit 70
fi
printf '{"schema_version":"1","command":"bootstrap.local","status":"success","environment":"development"}\n'

docker_group_entry=$(getent group docker 2>/dev/null || true)
developer_listed_in_docker_group=false
docker_group_active=false
docker_info_accessible=false
process_uid=$EUID
if [[ -n ${VSS_BOOTSTRAP_TEST_ROOT:-} && -n ${VSS_TEST_EFFECTIVE_UID:-} ]]; then
  process_uid=$VSS_TEST_EFFECTIVE_UID
fi
if [[ -n $docker_group_entry && $(grep -c '^' <<<"$docker_group_entry") -eq 1 ]]; then
  IFS=: read -r docker_group_name _ docker_group_gid docker_group_members <<<"$docker_group_entry"
  if [[ $docker_group_name == docker && $docker_group_gid =~ ^[0-9]+$ ]] &&
    tr ',' '\n' <<<"$docker_group_members" | grep -Fxq "$developer_user"; then
    developer_listed_in_docker_group=true
  fi
  # Supplementary groups belong to the current process. Querying `id USER`
  # would only re-read the group database and would hide the login boundary.
  if (( process_uid == developer_uid )) && id -G | tr ' ' '\n' | grep -Fxq "$docker_group_gid"; then
    docker_group_active=true
  fi
fi
if $developer_listed_in_docker_group && ! $docker_group_active; then
  restart_required docker_group
fi
if (( process_uid == developer_uid )) && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker_info_accessible=true
fi
printf '{"state":"POSTINSTALL_CHECK","developer_in_docker_group":%s,"docker_group_active":%s,"docker_info_accessible":%s}\n' \
  "$developer_listed_in_docker_group" "$docker_group_active" "$docker_info_accessible"
run "$venv_dir/bin/vss" bootstrap verify --environment development
printf 'state=COMPLETE\n' >"$progress_file"
chmod 600 "$progress_file"
printf '{"state":"COMPLETE","environment":"development"}\n'
