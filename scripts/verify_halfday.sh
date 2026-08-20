#!/usr/bin/env bash
set -Eeuo pipefail

if [ ! -x gesture/.venv/bin/python ]; then
    echo "Gesture environment is missing; run 'make setup-gesture' first." >&2
    exit 1
fi

./scripts/verify_gesture_assets.sh

echo "Running gesture unit and deployment tests..."
gesture/.venv/bin/python -m pytest gesture/tests -q

echo "Building and testing the ROS 2 packages..."
docker compose run --rm --no-deps simulation bash -c \
    "cd /home/devuser/drone_landing_ws && \
     colcon build --symlink-install --packages-select \
       precision_landing_interfaces precision_landing_control_cpp px4_vision_autonomy && \
     colcon test --packages-select \
       precision_landing_interfaces precision_landing_control_cpp px4_vision_autonomy && \
     colcon test-result --verbose"

echo "Running the independent ArUco contract tests..."
docker compose run --rm --no-deps simulation \
    python3 -m pytest /home/devuser/tests/test_aruco.py -q

echo "TESTS=PASS"
