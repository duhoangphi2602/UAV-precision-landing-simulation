#!/bin/bash
set -Eeuo pipefail

echo "Stopping previous simulation containers..."
docker compose down -v || true

echo "Killing any orphaned background tasks..."
pkill -f px4 || true
pkill -f gz || true
pkill -f ros2 || true
