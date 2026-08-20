#!/bin/bash
set -Eeuo pipefail

readonly CAMERA_INDEX="${GESTURE_CAMERA_INDEX:-0}"
if ! [[ "$CAMERA_INDEX" =~ ^[0-9]+$ ]]; then
    echo "GESTURE_CAMERA_INDEX must be a non-negative integer." >&2
    exit 1
fi

readonly CONTAINERS=(
    gesture_px4_sitl
    gesture_ros_bridge
    gesture_viewer
    gesture_mission
    gesture_operator
)

mkdir -p artifacts/logs

cleanup() {
    echo "Stopping Slice 6 gesture-demo containers..."
    sleep 1
    docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -Fxq "$container"; then
        echo "Refusing to start: active simulation container '$container' would conflict."
        exit 1
    fi
    if docker ps -a --format '{{.Names}}' | grep -Fxq "$container"; then
        docker rm "$container" >/dev/null
    fi
done

for container in px4_sitl ros_bridge aruco viewer mission cpp_control platform_controller; do
    if docker ps --format '{{.Names}}' | grep -Fxq "$container"; then
        echo "Refusing to start: active accepted-demo container '$container' would conflict."
        exit 1
    fi
done

if pgrep -af '[b]uild/px4_sitl_default/bin/px4|[g]z sim' >/dev/null; then
    echo "Refusing to start: an existing PX4/Gazebo host process is active."
    pgrep -af '[b]uild/px4_sitl_default/bin/px4|[g]z sim' || true
    exit 1
fi

if [ ! -c "/dev/video${CAMERA_INDEX}" ]; then
    echo "Webcam /dev/video${CAMERA_INDEX} is unavailable."
    exit 1
fi

if [ ! -x gesture/.venv/bin/python ]; then
    echo "Gesture environment is missing; run 'make setup-gesture' first."
    exit 1
fi

for artifact in \
    gesture/models/hand_landmarker.task \
    gesture/deploy/model.onnx \
    gesture/deploy/preprocessing.json \
    gesture/deploy/deployment_config.json \
    gesture/deploy/class_mapping.json; do
    if [ ! -f "$artifact" ]; then
        echo "Missing frozen gesture runtime artifact: $artifact"
        exit 1
    fi
done

./scripts/verify_gesture_assets.sh

./scripts/allow_x11.sh

echo "Building only the typed interface and Python mission package..."
docker compose run --rm --no-deps simulation bash -c \
    "cd /home/devuser/drone_landing_ws && colcon build --symlink-install --packages-select precision_landing_interfaces px4_vision_autonomy"

echo "Starting PX4/Gazebo inspection world (autonomous landing nodes disabled)..."
docker compose run -d --name gesture_px4_sitl simulation bash -c \
    "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && export PX4_GZ_WORLD=inspection && cd /opt/PX4-Autopilot && DONT_RUN=1 make px4_sitl gz_x500_mono_cam_down && ./build/px4_sitl_default/bin/px4"
sleep 5

docker compose run -d --name gesture_ros_bridge simulation bash -c \
    "ros2 run ros_gz_image image_bridge /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"
sleep 2

docker compose run -d --name gesture_viewer simulation bash -c \
    "ros2 run px4_vision_autonomy camera_viewer --ros-args -p mission_mode:=gesture"

docker compose run -d --name gesture_mission simulation bash -c \
    "ros2 run px4_vision_autonomy mission_commander --ros-args -p mission_mode:=gesture -p control_source:=gesture_manual -p gesture_minimum_confidence:=0.8 -p gesture_command_ttl_sec:=0.5 -p manual_xy_speed_m_s:=0.5 -p gesture_takeoff_altitude_m:=3.0"

echo "Gesture control is ready. Hold TAKEOFF steadily; use Q/Esc to publish HOLD and exit."
echo "AUTO_LAND is perception-only in Slice 6 and will report LANDING_HANDOFF_NOT_ENABLED."

docker compose run --name gesture_operator \
    -e GESTURE_CAMERA_INDEX="$CAMERA_INDEX" simulation bash -c \
    'export PYTHONPATH=/home/devuser/gesture/.venv/lib/python3.10/site-packages:/home/devuser:${PYTHONPATH}; /usr/bin/python3 -m gesture.ros_operator_node --camera "$GESTURE_CAMERA_INDEX"'

echo "Saving bounded Slice 6 logs..."
docker logs gesture_mission > artifacts/logs/demo_gesture_mission.log 2>&1 || true
docker logs gesture_operator > artifacts/logs/demo_gesture_operator.log 2>&1 || true
docker logs gesture_viewer > artifacts/logs/demo_gesture_viewer.log 2>&1 || true
docker logs gesture_px4_sitl > artifacts/logs/demo_gesture_px4.log 2>&1 || true

echo "Gesture demo exited after publishing a safe HOLD."
