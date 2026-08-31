#!/usr/bin/env bash
# Exercise phase 0 in the published clean Ubuntu 26.04 container image.
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
readonly image='ghcr.io/tullas/vss/ubuntu-26.04-acceptance@sha256:a4693923c263447a4a63e8a2c5920d0ebbfe29428e83c5971e749bf5ee06a0ee'
docker run --rm \
  --user 0:0 \
  --mount "type=bind,source=$project_root,target=/source,readonly" \
  "$image" \
  bash -ceu '
    apt-get update
    apt-get install -y git python3 util-linux
    cp -a /source /tmp/vss
    cd /tmp/vss
    rm -rf .venv .local
    version=$(python3 -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")")
    if python3 -m venv .venv >/tmp/initial-venv.log 2>&1; then
      echo "expected initial venv creation to fail without python${version}-venv" >&2
      exit 1
    fi
    test -d .venv
    apt-get install -y "python${version}-venv"
    before_partial=$(find .venv -mindepth 1 -maxdepth 2 | wc -l)
    test "$before_partial" -gt 0
    VSS_IS_WSL=false VSS_PID1=systemd VSS_BOOTSTRAP_VENV_ONLY=1 ./scripts/bootstrap-host.sh
    .venv/bin/python -m pip --version
    before_inode=$(stat -c %i .venv)
    VSS_IS_WSL=false VSS_PID1=systemd VSS_BOOTSTRAP_VENV_ONLY=1 ./scripts/bootstrap-host.sh
    after_inode=$(stat -c %i .venv)
    test "$before_inode" = "$after_inode"
    test -z "$(command -v ansible-playbook || true)"
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
      VSS_IS_WSL=false VSS_PID1=systemd VSS_BOOTSTRAP_INSTALL_ONLY=1 ./scripts/bootstrap-host.sh
    test -x .venv/bin/ansible-playbook
    test "$(.venv/bin/python -c "from ansible.release import __version__; print(__version__)")" = 2.21.2
    .venv/bin/ansible-playbook --version
    useradd --create-home vssdev
    chown -R vssdev:vssdev /tmp/vss
    developer_uid=$(id -u vssdev)
    developer_gid=$(id -g vssdev)
    developer_home=$(getent passwd vssdev | cut -d: -f6)
    developer_vars=$(.venv/bin/python -c \
      "import json,sys; print(json.dumps(dict(zip((\"local_toolchain_developer_user\", \"local_toolchain_developer_uid\", \"local_toolchain_developer_gid\", \"local_toolchain_developer_home\", \"local_toolchain_project_root\"), sys.argv[1:]))))" \
      vssdev "$developer_uid" "$developer_gid" "$developer_home" /tmp/vss)
    .venv/bin/ansible-playbook \
      -i ansible/inventories/development/hosts.yml \
      ansible/playbooks/bootstrap-local.yml \
      --tags local_directories \
      --extra-vars "$developer_vars"
    test -z "$(find .local -user root -print)"
    VSS_IS_WSL=false VSS_PID1=systemd VSS_BOOTSTRAP_SUDO_ONLY=1 ./scripts/bootstrap-host.sh >/tmp/root-sudo-preflight.json
    grep -Fq "\"preauthenticated\":false" /tmp/root-sudo-preflight.json
    mkdir -p /tmp/fake-bin
    ln -s /tmp/vss/tests/fixtures/bootstrap/fake-interactive-ansible /tmp/fake-bin/ansible-playbook
    VSS_TEST_INTERACTIVE_MARKER=/tmp/interactive-ran \
      script -qec "PATH=/tmp/fake-bin:\$PATH .venv/bin/vss bootstrap local --environment development --ask-become-pass" \
      /tmp/interactive-transcript
    test -e /tmp/interactive-ran
    grep -Fq "\"status\":\"success\"" /tmp/interactive-transcript
  '
printf 'Ubuntu 26.04 clean-image phase-0 acceptance passed\n'
