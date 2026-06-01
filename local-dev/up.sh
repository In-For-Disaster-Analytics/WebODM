#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

compose() {
  docker compose -f docker-compose.local.yml "$@"
}

mkdir -p \
  .local-dev/media \
  .local-dev/db \
  .local-dev/nodeodm-data \
  .local-dev/clusterodm-data

if [ ! -f .local-dev/clusterodm-data/nodes.json ]; then
  printf '[{"hostname":"node-odm","port":3000,"token":""}]\n' > .local-dev/clusterodm-data/nodes.json
fi

if [ ! -f .local-dev/clusterodm-data/routes.json ]; then
  printf '{}\n' > .local-dev/clusterodm-data/routes.json
fi

compose up -d --build

echo "Waiting for WebODM..."
for _ in $(seq 1 90); do
  if compose exec -T webapp curl -fsS http://localhost:8000/api/ >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

if ! compose exec -T webapp curl -fsS http://localhost:8000/api/ >/dev/null 2>&1; then
  echo "WebODM did not become ready. Run ./logs.sh webapp for details." >&2
  exit 1
fi

if ! compose exec -T webapp curl -fsS http://clusterodm:3000/info >/dev/null 2>&1; then
  echo "ClusterODM is not reachable from WebODM. Run ./logs.sh clusterodm for details." >&2
  exit 1
fi

if ! compose exec -T clusterodm curl -fsS http://node-odm:3000/info >/dev/null 2>&1; then
  echo "NodeODM is not reachable from ClusterODM. Run ./logs.sh node-odm for details." >&2
  exit 1
fi

compose exec -T webapp python manage.py addnode clusterodm 3000 --label clusterodm-local

echo ""
echo "Local checkpoint dev stack is running:"
echo "  WebODM:        http://localhost:8000"
echo "  ClusterODM:    http://localhost:4000"
echo "  Cluster Admin: http://localhost:10000"
echo "  NodeODM:       http://localhost:3001"
