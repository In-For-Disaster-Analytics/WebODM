#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env.local ]; then
  set -a
  . ./.env.local
  set +a
fi

compose() {
  docker compose -f docker-compose.local.yml "$@"
}

bind_ip="${LOCAL_DEV_BIND_IP:-127.0.0.1}"
webodm_port="${LOCAL_DEV_WEBODM_PORT:-18000}"
clusterodm_port="${LOCAL_DEV_CLUSTERODM_PORT:-14000}"
clusterodm_admin_port="${LOCAL_DEV_CLUSTERODM_ADMIN_PORT:-11000}"
nodeodm_port="${LOCAL_DEV_NODEODM_PORT:-13001}"

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
echo "  WebODM:        http://webodm.local.test:${webodm_port}    (or http://${bind_ip}:${webodm_port})"
echo "  ClusterODM:    http://clusterodm.local.test:${clusterodm_port} (or http://${bind_ip}:${clusterodm_port})"
echo "  Cluster Admin: http://clusterodm.local.test:${clusterodm_admin_port} (or http://${bind_ip}:${clusterodm_admin_port})"
echo "  NodeODM:       http://nodeodm.local.test:${nodeodm_port}    (or http://${bind_ip}:${nodeodm_port})"
