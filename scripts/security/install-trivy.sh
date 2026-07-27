#!/usr/bin/env bash
set -euo pipefail

readonly version='0.72.0'
readonly archive="trivy_${version}_Linux-64bit.tar.gz"
readonly expected_sha256='bbb64b9695866ce4a7a8f5c9592002c5961cab378577fa3f8a040df362b9b2ea'
readonly url="https://github.com/aquasecurity/trivy/releases/download/v${version}/${archive}"
readonly destination=${1:?usage: install-trivy.sh DESTINATION}

mkdir -p "$destination"
curl --fail --silent --show-error --location --output "$destination/$archive" "$url"
printf '%s  %s\n' "$expected_sha256" "$destination/$archive" | sha256sum --check --status
tar --extract --gzip --file "$destination/$archive" --directory "$destination" trivy
"$destination/trivy" --version
