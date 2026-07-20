#!/bin/bash
set -Eeuo pipefail

# Ensure no two builds are running in parallel
exec 9> /tmp/build_workspace.lock
if ! flock -n 9; then
    echo "Another build is already running. Exiting."
    exit 1
fi

mkdir -p artifacts/logs

# Source PX4 version
set -a
source docker/versions.env
set +a

export HOST_UID=$(id -u)
export HOST_GID=$(id -g)

echo "Building Docker image..."
docker compose build --progress=plain --build-arg PX4_VERSION=${PX4_VERSION} 2>&1 | tee artifacts/logs/docker_build.log

echo "Building ROS workspace inside Docker..."
docker compose run --rm simulation bash -c "cd /home/devuser/drone_landing_ws && colcon build --symlink-install" 2>&1 | tee artifacts/logs/colcon_build.log
echo "Build complete."
