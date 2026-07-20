#!/bin/bash
set -Eeuo pipefail

echo "Running tests..."
# Run Python mock tests
docker compose run --rm simulation bash -c "pytest /home/devuser/tests/test_aruco.py"

# Run C++ GTests
docker compose run --rm simulation bash -c "cd /home/devuser/drone_landing_ws && colcon test --packages-select precision_landing_control_cpp && colcon test-result --verbose"

echo "Unit test verification complete"
