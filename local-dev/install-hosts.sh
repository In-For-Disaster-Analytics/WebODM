#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env.local ]; then
  set -a
  . ./.env.local
  set +a
fi

bind_ip="${LOCAL_DEV_BIND_IP:-127.0.0.1}"
hosts_line="${bind_ip} webodm.local.test clusterodm.local.test nodeodm.local.test webodm.local clusterodm.local nodeodm.local"

existing_line="$(grep -E '(^|[[:space:]])webodm\.local\.test([[:space:]]|$)' /etc/hosts || true)"
if [ -n "${existing_line}" ]; then
  if printf '%s\n' "${existing_line}" | grep -Eq "^${bind_ip}[[:space:]]"; then
    echo "Local WebODM host aliases already exist in /etc/hosts"
    exit 0
  fi

  echo "Updating existing local WebODM host aliases in /etc/hosts:"
  printf '%s\n' "${existing_line}"
  tmp_hosts="$(mktemp)"
  awk '!/(^|[[:space:]])(webodm|clusterodm|nodeodm)\.local(\.test)?([[:space:]]|$)/' /etc/hosts > "${tmp_hosts}"
  printf '\n%s\n' "${hosts_line}" >> "${tmp_hosts}"
  sudo cp "${tmp_hosts}" /etc/hosts
  rm -f "${tmp_hosts}"
  exit 0
fi

echo "Adding local WebODM host aliases to /etc/hosts:"
echo "  ${hosts_line}"
printf '\n%s\n' "${hosts_line}" | sudo tee -a /etc/hosts >/dev/null
