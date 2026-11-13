#!/usr/bin/env bash
# Same configuration as compose.yaml, as plain docker CLI commands.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "Missing .env - copy .env.example and fill it in" >&2; exit 1; }
IMAGE="${IMAGE:-ghcr.io/igridz/vivosun-fetcher:latest}"

docker rm -f vivosun-fetcher >/dev/null 2>&1 || true
docker run -d --name vivosun-fetcher \
  --restart unless-stopped \
  --network media \
  --env-file .env \
  -e TZ=Europe/Berlin \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  "$IMAGE"
