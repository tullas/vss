#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
script="$root/scripts/bootstrap-host.sh"
fixtures="$root/tests/fixtures/bootstrap"
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

[[ -x $script ]]
bash -n "$script"

bootstrap_env() {
  local version=$1 venv_path=$2 phase=$3
  shift 3
  env \
    PATH="$fixtures:$PATH" \
    VSS_OS_RELEASE_FILE="$fixtures/ubuntu-os-release" \
    VSS_IS_WSL=false \
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

# Future Python minor versions derive matching package names.
for version in 3.15 3.16; do
  : >"$test_dir/commands.log"; rm -f "$test_dir/venv.available"
  run_phase0 "$version" >/dev/null
  grep -Fq "apt-get install -y python${version}-venv" "$test_dir/commands.log"
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

grep -Fq 'RESTART_REQUIRED' "$script"
grep -Fq 'bootstrap verify' "$script"
printf 'phase-0 bootstrap tests passed\n'
