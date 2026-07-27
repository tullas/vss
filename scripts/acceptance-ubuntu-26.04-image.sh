#!/usr/bin/env bash
# Exercise phase 0 in the published clean Ubuntu 26.04 container image.
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
image=${VSS_ACCEPTANCE_IMAGE:-ubuntu:26.04}
docker run --rm \
  --mount "type=bind,source=$project_root,target=/source,readonly" \
  "$image" \
  bash -ceu '
    apt-get update
    apt-get install -y git python3
    cp -a /source /tmp/vss
    cd /tmp/vss
    rm -rf .venv .local
    VSS_BOOTSTRAP_PHASE0_ONLY=1 ./scripts/bootstrap-host.sh
    version=$(python3 -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")")
    dpkg-query -W "python${version}-venv" >/dev/null
  '
printf 'Ubuntu 26.04 clean-image phase-0 acceptance passed\n'
