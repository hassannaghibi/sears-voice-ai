#!/bin/bash
# Server-side deploy script — called by GitHub Actions or manually on the dev host.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sears-voice-ai}"
cd "$APP_DIR"

echo "==> Building and starting containers..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up --build -d

echo "==> Waiting for API health check..."
for i in $(seq 1 36); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "==> Deploy successful — health check passed."
    curl -s http://localhost:8000/health
    exit 0
  fi
  echo "   attempt $i/36 — not ready yet..."
  sleep 5
done

echo "==> ERROR: health check failed after 3 minutes"
docker compose logs api --tail 50
exit 1
