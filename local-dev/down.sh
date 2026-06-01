#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env.local ]; then
  set -a
  . ./.env.local
  set +a
fi

docker compose -f docker-compose.local.yml down "$@"
