#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "Checking frontend_deps..."
if ! docker compose ps frontend_deps 2>/dev/null | grep -q "Exited (0)"; then
  echo "Running frontend_deps (first time or after package changes)..."
  docker compose up -d frontend_deps
  echo "Wait for frontend_deps to complete (exited 0), then run: docker compose up -d"
  exit 0
fi

echo "Starting stack..."
docker compose up -d
echo "Done. Check: docker compose ps"
