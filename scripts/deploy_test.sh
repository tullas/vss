#!/usr/bin/bash -x

set -euo pipefail

echo "Starting deployment"

echo "Deploying version 1.0.0"

echo "Health check"

curl -f https://example.com

echo "Deployment successful"
