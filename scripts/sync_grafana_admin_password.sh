#!/bin/bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-12}
SLEEP_SECONDS=${SLEEP_SECONDS:-5}

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if docker compose -f "$COMPOSE_FILE" exec -T grafana \
    sh -c 'grafana cli admin reset-admin-password "$GF_SECURITY_ADMIN_PASSWORD"'; then
    exit 0
  fi

  if [ "$attempt" -eq "$MAX_ATTEMPTS" ]; then
    echo "failed to sync Grafana admin password after $MAX_ATTEMPTS attempts" >&2
    exit 1
  fi

  sleep "$SLEEP_SECONDS"
done
