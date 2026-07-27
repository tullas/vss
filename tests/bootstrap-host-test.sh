#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
script="$root/scripts/bootstrap-host.sh"
fixtures="$root/tests/fixtures/bootstrap"
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

[[ -x $script ]]
bash -n "$script"

run_phase0() {
  local version=$1
  shift
  env \
    PATH="$fixtures:$PATH" \
    VSS_OS_RELEASE_FILE="$fixtures/ubuntu-os-release" \
    VSS_IS_WSL=false \
    VSS_PID1=systemd \
    VSS_PYTHON_BIN="$fixtures/fake-python" \
    VSS_PYTHON_VERSION="$version" \
    VSS_TEST_PYTHON_VERSION="$version" \
    VSS_TEST_COMMAND_LOG="$test_dir/commands.log" \
    VSS_TEST_VENV_MARKER="$test_dir/venv.available" \
    VSS_VENV_DIR="$test_dir/.venv" \
    VSS_SUDO_BIN="${VSS_SUDO_BIN:-$fixtures/fake-sudo}" \
    VSS_BOOTSTRAP_ALLOW_NONINTERACTIVE_SUDO=1 \
    VSS_BOOTSTRAP_PHASE0_ONLY=1 \
    "$@" "$script"
}

# Missing interpreter-matched package is installed and venv creation is retried.
: >"$test_dir/commands.log"
rm -f "$test_dir/venv.available"
output=$(run_phase0 3.14)
grep -Fq 'apt-get update' "$test_dir/commands.log"
grep -Fq 'apt-get install -y python3.14-venv' "$test_dir/commands.log"
[[ $(grep -Fc 'venv 3.14' "$test_dir/commands.log") -eq 2 ]]
grep -Fq '"venv_package":"python3.14-venv"' <<<"$output"

# An already usable venv implementation performs no package operation.
: >"$test_dir/commands.log"
touch "$test_dir/venv.available"
run_phase0 3.14 >/dev/null
! grep -Fq 'apt-get' "$test_dir/commands.log"
[[ $(grep -Fc 'venv 3.14' "$test_dir/commands.log") -eq 1 ]]

# The package name follows future Python minor-version changes.
for version in 3.15 3.16; do
  : >"$test_dir/commands.log"
  rm -f "$test_dir/venv.available"
  run_phase0 "$version" >/dev/null
  grep -Fq "apt-get install -y python${version}-venv" "$test_dir/commands.log"
done

# Unsupported distributions fail before Python or package operations.
status=0
VSS_OS_RELEASE_FILE="$fixtures/unsupported-os-release" VSS_IS_WSL=false "$script" >"$test_dir/unsupported.out" 2>&1 || status=$?
(( status == 69 ))
grep -Fq 'unsupported operating system' "$test_dir/unsupported.out"

# Missing sudo produces a precise safe failure when installation is required.
: >"$test_dir/commands.log"
rm -f "$test_dir/venv.available"
status=0
VSS_SUDO_BIN=__vss_missing_sudo__ run_phase0 3.14 >"$test_dir/sudo.out" 2>&1 || status=$?
(( status == 77 ))
grep -Fq 'sudo is required for host changes' "$test_dir/sudo.out"
! grep -Fq 'apt-get' "$test_dir/commands.log"

grep -Fq -- '--resume' "$script"
grep -Fq 'RESTART_REQUIRED' "$script"
grep -Fq 'wsl --shutdown' "$script"
grep -Fq 'bootstrap verify' "$script"
printf 'phase-0 bootstrap tests passed\n'
