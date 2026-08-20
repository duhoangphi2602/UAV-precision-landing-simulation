#!/usr/bin/env bash
set -Eeuo pipefail

readonly CONTAINERS=(
    px4_sitl ros_bridge aruco viewer mission cpp_control platform_controller
    gesture_px4_sitl gesture_ros_bridge gesture_viewer gesture_mission gesture_operator
    final_px4_sitl final_ros_bridge final_platform_controller final_aruco
    final_viewer final_cpp_control final_mission final_gesture_operator
)

echo "Stopping only known project demo containers..."
docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
echo "DEMO_CONTAINERS_STOPPED=YES"
