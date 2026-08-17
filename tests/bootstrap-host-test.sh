#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
script="$root/scripts/bootstrap-host.sh"
fixtures="$root/tests/fixtures/bootstrap"
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

[[ -x $script ]]
bash -n "$script"
grep -Fq 'ansible-core==2.19.11; python_version >= "3.11" and python_version < "3.12"' "$root/requirements-bootstrap.txt"
grep -Fq 'ansible-core==2.21.2; python_version >= "3.12" and python_version < "3.15"' "$root/requirements-bootstrap.txt"

bootstrap_env() {
  local version=$1 venv_path=$2 phase=$3
  shift 3
  env \
    PATH="$fixtures:$PATH" \
    VSS_OS_RELEASE_FILE="$fixtures/ubuntu-os-release" \
    VSS_IS_WSL="${VSS_IS_WSL:-false}" \
    VSS_PID1=systemd \
    VSS_PYTHON_BIN="$fixtures/fake-python" \
    VSS_TEST_PYTHON_VERSION="$version" \
    VSS_TEST_COMMAND_LOG="$test_dir/commands.log" \
    VSS_TEST_VENV_MARKER="$test_dir/venv.available" \
    VSS_TEST_VENV_PYTHON_FIXTURE="$fixtures/fake-venv-python" \
    VSS_VENV_DIR="$venv_path" \
    VSS_BOOTSTRAP_TEST_ROOT="$test_dir" \
    VSS_SUDO_BIN="${VSS_SUDO_BIN:-$fixtures/fake-sudo}" \
    VSS_BOOTSTRAP_ALLOW_NONINTERACTIVE_SUDO=1 \
    VSS_TEST_NEW_VENV_PIP_MISSING="${VSS_TEST_NEW_VENV_PIP_MISSING:-0}" \
    VSS_TEST_NEW_VENV_ENSUREPIP_FAILS="${VSS_TEST_NEW_VENV_ENSUREPIP_FAILS:-0}" \
    "$phase"=1 \
    "$@" "$script"
}

host_env() {
  env \
    PATH="$fixtures:$PATH" \
    VSS_OS_RELEASE_FILE="$fixtures/ubuntu-os-release" \
    VSS_IS_WSL="${VSS_IS_WSL:-false}" \
    VSS_PID1=systemd \
    VSS_PYTHON_BIN="$fixtures/fake-python" \
    VSS_TEST_PYTHON_VERSION=3.14 \
    VSS_TEST_COMMAND_LOG="$test_dir/commands.log" \
    VSS_TEST_VENV_MARKER="$test_dir/venv.available" \
    VSS_TEST_VENV_PYTHON_FIXTURE="$fixtures/fake-venv-python" \
    VSS_VENV_DIR="$sudo_venv" \
    VSS_BOOTSTRAP_TEST_ROOT="$test_dir" \
    VSS_SUDO_BIN="${VSS_SUDO_BIN:-$fixtures/fake-sudo}" \
    VSS_SUDO_KEEPALIVE_SECONDS=0.02 \
    "$@"
}

run_host_tty() { host_env script -qec "$script" /dev/null; }

run_phase0() { bootstrap_env "$1" "$test_dir/.venv" VSS_BOOTSTRAP_PHASE0_ONLY "${@:2}"; }
run_venv() { bootstrap_env "$1" "$test_dir/.venv" VSS_BOOTSTRAP_VENV_ONLY "${@:2}"; }
run_install() { bootstrap_env "$1" "$2" VSS_BOOTSTRAP_INSTALL_ONLY "${@:3}"; }
reset_case() { rm -rf -- "$test_dir/.venv"; : >"$test_dir/commands.log"; touch "$test_dir/venv.available"; }
make_existing_venv() {
  mkdir -p "$test_dir/.venv/bin"
  cp "$fixtures/fake-venv-python" "$test_dir/.venv/bin/python"
  chmod +x "$test_dir/.venv/bin/python"
}

# Missing interpreter-matched package is installed and venv creation is retried.
: >"$test_dir/commands.log"
rm -f "$test_dir/venv.available"
output=$(run_phase0 3.14)
grep -Fq 'apt-get update' "$test_dir/commands.log"
grep -Fq 'apt-get install -y python3.14-venv' "$test_dir/commands.log"
[[ $(grep -Fc 'venv 3.14' "$test_dir/commands.log") -eq 2 ]]
grep -Fq '"venv_package":"python3.14-venv"' <<<"$output"

# Already usable system support performs no package operation.
: >"$test_dir/commands.log"
touch "$test_dir/venv.available"
run_phase0 3.14 >/dev/null
! grep -Fq 'apt-get' "$test_dir/commands.log"

# Unsupported future Python fails before dependency installation rather than guessing.
for version in 3.15 3.16; do
  status=0
  run_phase0 "$version" >"$test_dir/future-python.out" 2>&1 || status=$?
  (( status == 69 ))
  grep -Fq 'unsupported by the VSS Ansible compatibility policy' "$test_dir/future-python.out"
done

# No managed venv exists: create and verify it.
reset_case
run_venv 3.14 >/dev/null
[[ -x $test_dir/.venv/bin/python ]]
"$test_dir/.venv/bin/python" -m pip --version

# A healthy managed venv is reused unchanged, including on a second run.
: >"$test_dir/commands.log"
before=$(stat -c '%i' "$test_dir/.venv")
run_venv 3.14 >/dev/null
run_venv 3.14 >/dev/null
after=$(stat -c '%i' "$test_dir/.venv")
[[ $before == "$after" ]]

# Every supported control-node Python selects its deterministic Ansible pin.
for version in 3.11 3.12 3.13 3.14; do
  compatibility_venv="$test_dir/compatibility-$version"
  rm -rf -- "$compatibility_venv"
  output=$(run_install "$version" "$compatibility_venv" 2>"$test_dir/compatibility-$version.err")
  if [[ $version == 3.11 ]]; then expected=2.19.11; else expected=2.21.2; fi
  grep -Fq "\"selected_ansible_core\":\"$expected\"" "$test_dir/compatibility-$version.err"
  grep -Fq "\"ansible_core_version\":\"$expected\"" <<<"$output"
done

# An incompatible Ansible is upgraded in place; a supported pin is unchanged.
compatibility_venv="$test_dir/existing-ansible"
rm -rf -- "$compatibility_venv"
run_venv 3.14 VSS_VENV_DIR="$compatibility_venv" >/dev/null
printf '2.19.2\n' >"$compatibility_venv/.ansible-version"
before=$(stat -c '%i' "$compatibility_venv")
: >"$test_dir/commands.log"
run_install 3.14 "$compatibility_venv" >/dev/null 2>"$test_dir/incompatible.err"
after=$(stat -c '%i' "$compatibility_venv")
[[ $before == "$after" ]]
grep -Fq 'ansible-core 2.19.2 -> 2.21.2' "$test_dir/commands.log"
grep -Fq '"supported":false' "$test_dir/incompatible.err"
: >"$test_dir/commands.log"
run_install 3.14 "$compatibility_venv" >/dev/null 2>"$test_dir/supported.err"
! grep -Fq 'ansible-core ' "$test_dir/commands.log"
grep -Fq '"supported":true' "$test_dir/supported.err"
! grep -Fq 'venv 3.14' "$test_dir/commands.log"

# Installed venv tools are discovered without global Ansible or activation.
custom_venv="$test_dir/custom/managed-venv"
rm -rf -- "$custom_venv"
system_path=/usr/bin:/bin
output=$(PATH="$system_path" run_install 3.14 "$custom_venv")
grep -Fq '"state":"TOOLCHAIN_READY"' <<<"$output"
for executable in python pip vss ansible-playbook; do
  [[ -x $custom_venv/bin/$executable ]]
done
[[ $(PATH="$custom_venv/bin:$system_path" command -v ansible-playbook) == "$custom_venv/bin/ansible-playbook" ]]
before=$(stat -c '%i' "$custom_venv")
PATH="$system_path" run_install 3.14 "$custom_venv" >/dev/null
after=$(stat -c '%i' "$custom_venv")
[[ $before == "$after" ]]

# Existing directory without Python is recovered automatically.
reset_case
mkdir -p "$test_dir/.venv/bin"
run_venv 3.14 >"$test_dir/recovery.out" 2>&1
grep -Fq 'unhealthy (missing-python)' "$test_dir/recovery.out"
"$test_dir/.venv/bin/python" -m pip --version

# Python without pip and an interrupted partial venv are both repaired.
reset_case; make_existing_venv; touch "$test_dir/.venv/.pip-missing"
run_venv 3.14 >/dev/null 2>&1
"$test_dir/.venv/bin/python" -m pip --version
reset_case; mkdir -p "$test_dir/.venv/bin"; touch "$test_dir/.venv/pyvenv.cfg"
run_venv 3.14 >/dev/null 2>&1
"$test_dir/.venv/bin/python" -m pip --version

# Unsupported venv Python is replaced with the supported system interpreter.
reset_case; make_existing_venv; touch "$test_dir/.venv/.unsupported"
run_venv 3.14 >/dev/null 2>&1
[[ ! -e $test_dir/.venv/.unsupported ]]

# An executable that cannot start is also replaced.
reset_case; make_existing_venv; touch "$test_dir/.venv/.python-fails"
run_venv 3.14 >/dev/null 2>&1
[[ ! -e $test_dir/.venv/.python-fails ]]

# A new venv missing pip is repaired with ensurepip before activation.
reset_case
VSS_TEST_NEW_VENV_PIP_MISSING=1 run_venv 3.14 >/dev/null
grep -Fq 'venv-python -m ensurepip --upgrade' "$test_dir/commands.log"
"$test_dir/.venv/bin/python" -m pip --version

# Ensurepip failure stops safely and leaves an existing broken venv recoverable.
reset_case; mkdir -p "$test_dir/.venv/bin"; touch "$test_dir/.venv/partial"
status=0
VSS_TEST_NEW_VENV_PIP_MISSING=1 VSS_TEST_NEW_VENV_ENSUREPIP_FAILS=1 run_venv 3.14 >"$test_dir/ensurepip.out" 2>&1 || status=$?
(( status == 69 ))
grep -Fq 'replacement VSS virtual environment is unhealthy (pip-missing)' "$test_dir/ensurepip.out"
[[ -e $test_dir/.venv/partial ]]

# Dangerous and unrelated configured paths are refused before deletion.
for dangerous in '' / "$root" /tmp/vss-unrelated-venv; do
  status=0
  bootstrap_env 3.14 "$dangerous" VSS_BOOTSTRAP_VENV_ONLY >"$test_dir/path.out" 2>&1 || status=$?
  (( status == 64 ))
done

# Unsupported distributions and missing sudo remain precise failures.
status=0
VSS_OS_RELEASE_FILE="$fixtures/unsupported-os-release" VSS_IS_WSL=false "$script" >"$test_dir/unsupported.out" 2>&1 || status=$?
(( status == 69 ))
grep -Fq 'unsupported operating system' "$test_dir/unsupported.out"
: >"$test_dir/commands.log"; rm -f "$test_dir/venv.available"; rm -rf "$test_dir/.venv"
status=0
VSS_SUDO_BIN=__vss_missing_sudo__ run_phase0 3.14 >"$test_dir/sudo.out" 2>&1 || status=$?
(( status == 77 ))
grep -Fq 'sudo is required for host changes' "$test_dir/sudo.out"

# The supported host path authenticates with native sudo before Ansible and
# never asks Ansible to mediate a password.
sudo_venv="$test_dir/sudo-managed-venv"
rm -rf -- "$sudo_venv"
run_install 3.14 "$sudo_venv" >/dev/null 2>&1
: >"$test_dir/commands.log"
run_host_tty >"$test_dir/host.out" 2>&1
grep -Fq 'sudo -v' "$test_dir/commands.log"
[[ $(grep -Fc 'sudo -v' "$test_dir/commands.log") -eq 1 ]]
grep -Fq 'sudo -n '"$sudo_venv"'/bin/ansible-playbook' "$test_dir/commands.log"
! grep -Fq -- '--ask-become-pass' "$test_dir/commands.log"
grep -Fq 'sudo -k' "$test_dir/commands.log"
sudo_line=$(grep -Fn 'sudo -v' "$test_dir/commands.log" | head -n1 | cut -d: -f1)
ansible_line=$(grep -Fn 'sudo -n '"$sudo_venv"'/bin/ansible-playbook' "$test_dir/commands.log" | head -n1 | cut -d: -f1)
(( sudo_line < ansible_line ))
for identity_field in user uid gid home; do
  grep -Fq "\"local_toolchain_developer_${identity_field}\"" "$test_dir/commands.log"
done
grep -Fq '"local_toolchain_project_root"' "$test_dir/commands.log"
keeper_count=$(grep -Fc 'sudo -n true' "$test_dir/commands.log")
sleep 0.1
[[ $(grep -Fc 'sudo -n true' "$test_dir/commands.log") -eq $keeper_count ]]
run_host_tty >/dev/null 2>&1

# A privileged playbook failure is generic, does not leak terminal prompts, and cleans up sudo.
: >"$test_dir/commands.log"
status=0
VSS_TEST_ANSIBLE_FAILS=1 run_host_tty >"$test_dir/ansible-failed.out" 2>&1 || status=$?
(( status == 70 ))
grep -Fq 'privileged local toolchain bootstrap failed' "$test_dir/ansible-failed.out"
grep -Fq 'sudo -k' "$test_dir/commands.log"
! grep -Eqi '(password:|become password|prompt)' "$test_dir/ansible-failed.out"

# Failed authentication, missing sudo, and a missing terminal stop before Ansible.
: >"$test_dir/commands.log"
status=0
VSS_TEST_SUDO_AUTH_FAILS=1 run_host_tty >"$test_dir/auth-failed.out" 2>&1 || status=$?
(( status == 77 ))
grep -Fq 'sudo authentication failed; bootstrap stopped before Ansible' "$test_dir/auth-failed.out"
! grep -Fq 'ansible-playbook' "$test_dir/commands.log"
status=0
host_env env VSS_BOOTSTRAP_SUDO_ONLY=1 "$script" >"$test_dir/no-terminal.out" 2>&1 || status=$?
(( status == 77 ))
grep -Fq 'bootstrap requires an interactive terminal for sudo authentication' "$test_dir/no-terminal.out"
status=0
VSS_SUDO_BIN=__vss_missing_sudo__ run_host_tty >"$test_dir/missing-host-sudo.out" 2>&1 || status=$?
(( status == 77 ))
grep -Fq 'sudo is required for host changes' "$test_dir/missing-host-sudo.out"
! grep -Eqi '(password:|become password|prompt)' "$test_dir/auth-failed.out" "$test_dir/no-terminal.out" "$test_dir/missing-host-sudo.out"

# Identity data comes from passwd/repository ownership, not caller-controlled USER variables.
: >"$test_dir/commands.log"
USER=attacker SUDO_USER=attacker run_host_tty >/dev/null 2>&1
! grep -Fq 'attacker' "$test_dir/commands.log"

# A database-only Docker group assignment requires a new login session and
# stops before bootstrap.verify. WSL prints its exact supported restart action.
developer_name=$(id -un)
: >"$test_dir/commands.log"
status=0
VSS_TEST_DOCKER_GROUP_MEMBERS="$developer_name" VSS_TEST_ACTIVE_GROUP_IDS="$(id -g)" \
  VSS_IS_WSL=true run_host_tty >"$test_dir/docker-restart.out" 2>&1 || status=$?
(( status == 24 ))
grep -Fq '"state":"RESTART_REQUIRED","reason":"docker_group"' "$test_dir/docker-restart.out"
grep -Fq 'Run from Windows PowerShell:' "$test_dir/docker-restart.out"
grep -Fq 'wsl --shutdown' "$test_dir/docker-restart.out"
! grep -Fq 'vss bootstrap verify' "$test_dir/commands.log"

# Active supplementary membership proceeds through the non-sudo Docker probe
# and verification. A second bootstrap remains idempotently successful.
: >"$test_dir/commands.log"
VSS_TEST_DOCKER_GROUP_MEMBERS="$developer_name" VSS_TEST_ACTIVE_GROUP_IDS="$(id -g) 988" \
  run_host_tty >"$test_dir/docker-active.out" 2>&1
grep -Fq '"docker_group_active":true,"docker_info_accessible":true' "$test_dir/docker-active.out"
grep -Fq 'docker info' "$test_dir/commands.log"
grep -Fq 'vss bootstrap verify' "$test_dir/commands.log"
VSS_TEST_DOCKER_GROUP_MEMBERS="$developer_name" VSS_TEST_ACTIVE_GROUP_IDS="$(id -g) 988" \
  run_host_tty >"$test_dir/docker-second.out" 2>&1
grep -Fq '"state":"COMPLETE"' "$test_dir/docker-second.out"

# Root's active docker group never stands in for the original developer's
# session, even when the group id appears in root's supplementary group list.
status=0
VSS_TEST_DOCKER_GROUP_MEMBERS="$developer_name" VSS_TEST_ACTIVE_GROUP_IDS="0 988" \
  VSS_TEST_EFFECTIVE_UID=0 run_host_tty >"$test_dir/docker-root.out" 2>&1 || status=$?
(( status == 24 ))
grep -Fq '"reason":"docker_group"' "$test_dir/docker-root.out"

# After the WSL login boundary activates docker, --resume completes normally.
status=0
VSS_TEST_DOCKER_GROUP_MEMBERS="$developer_name" VSS_TEST_ACTIVE_GROUP_IDS="$(id -g)" \
  VSS_IS_WSL=true run_host_tty >/dev/null 2>&1 || status=$?
(( status == 24 ))
VSS_TEST_DOCKER_GROUP_MEMBERS="$developer_name" VSS_TEST_ACTIVE_GROUP_IDS="$(id -g) 988" \
  VSS_IS_WSL=true host_env script -qec "$script --resume" /dev/null >"$test_dir/docker-resume.out" 2>&1
grep -Fq '"state":"COMPLETE"' "$test_dir/docker-resume.out"

# The supported path contains one sudo boundary and no nested sudo configuration.
! grep -Fq 'bootstrap local --environment development' "$script"
! grep -Fq -- '--ask-become-pass' "$script"
grep -Fq 'run_privileged "$venv_dir/bin/ansible-playbook"' "$script"

grep -Fq 'RESTART_REQUIRED' "$script"
grep -Fq 'bootstrap verify' "$script"
printf 'phase-0 bootstrap tests passed\n'
