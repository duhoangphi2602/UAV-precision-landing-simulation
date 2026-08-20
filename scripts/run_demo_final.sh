#!/bin/bash
set -Eeuo pipefail

export PX4_VERSION="${PX4_VERSION:-78a44ed439ee941acd4844ff8ceaedbfe0faea56}"

readonly CAMERA_INDEX="${GESTURE_CAMERA_INDEX:-0}"
if ! [[ "$CAMERA_INDEX" =~ ^[0-9]+$ ]]; then
    echo "GESTURE_CAMERA_INDEX must be a non-negative integer." >&2
    exit 1
fi

readonly CONTAINERS=(
    final_px4_sitl
    final_ros_bridge
    final_platform_controller
    final_aruco
    final_viewer
    final_cpp_control
    final_mission
    final_gesture_operator
)

mkdir -p artifacts/logs

cleanup() {
    echo "Stopping final-demo containers..."
    docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -Fxq "$container"; then
        echo "Refusing to start: active final-demo container '$container' exists."
        exit 1
    fi
    if docker ps -a --format '{{.Names}}' | grep -Fxq "$container"; then
        docker rm "$container" >/dev/null
    fi
done

for container in px4_sitl ros_bridge aruco viewer mission cpp_control platform_controller gesture_px4_sitl gesture_ros_bridge gesture_viewer gesture_mission gesture_operator; do
    if docker ps --format '{{.Names}}' | grep -Fxq "$container"; then
        echo "Refusing to start: active regression/demo container '$container' would conflict."
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

echo "Building final integration packages..."
docker compose run --rm --no-deps simulation bash -c \
    "cd /home/devuser/drone_landing_ws && colcon build --symlink-install --packages-select precision_landing_interfaces precision_landing_control_cpp px4_vision_autonomy"

echo "Starting final moving-platform world..."
docker compose run -d --name final_px4_sitl simulation bash -c \
    "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection_moving.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && export PX4_GZ_WORLD=inspection_moving && cd /opt/PX4-Autopilot && DONT_RUN=1 make px4_sitl gz_x500_mono_cam_down && ./build/px4_sitl_default/bin/px4"
sleep 5

docker compose run -d --name final_ros_bridge simulation bash -c \
    "ros2 run ros_gz_bridge parameter_bridge /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock /model/moving_aruco_platform/pose@geometry_msgs/msg/Pose[gz.msgs.Pose /model/moving_aruco_platform/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist /world/inspection_moving/model/moving_aruco_platform/link/link/sensor/platform_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts --ros-args -r /world/inspection_moving/model/moving_aruco_platform/link/link/sensor/platform_contact/contact:=/platform_contact & ros2 run ros_gz_image image_bridge /world/inspection_moving/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection_moving/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"
sleep 2

docker compose run -d --name final_platform_controller simulation bash -c \
    "ros2 run px4_vision_autonomy moving_platform_controller --ros-args -p use_sim_time:=true"
docker compose run -d --name final_aruco simulation bash -c \
    "ros2 run px4_vision_autonomy aruco_detector --ros-args -p camera_topic:=/camera -p mission_mode:=moving"
docker compose run -d --name final_viewer simulation bash -c \
    "ros2 run px4_vision_autonomy camera_viewer --ros-args -p mission_mode:=final"
docker compose run -d --name final_cpp_control simulation bash -c \
    "ros2 launch precision_landing_control_cpp control_cpp.launch.py interface_mode:=typed mission_mode:=moving"
docker compose run -d --name final_mission simulation bash -c \
    "ros2 run px4_vision_autonomy mission_commander --ros-args -p mission_mode:=final -p control_source:=external_cpp -p wp_north:=0.0 -p wp_east:=5.8 -p wp_down:=-3.0 -p flip_x:=true -p flip_y:=true -p gesture_minimum_confidence:=0.8 -p gesture_command_ttl_sec:=0.5 -p manual_xy_speed_m_s:=0.5 -p gesture_takeoff_altitude_m:=3.0 -p target_ready_observations:=3 -p target_ready_max_age_sec:=0.5"

docker compose run -d --name final_gesture_operator \
    -e GESTURE_CAMERA_INDEX="$CAMERA_INDEX" simulation bash -c \
    'export PYTHONPATH=/home/devuser/gesture/.venv/lib/python3.10/site-packages:/home/devuser:${PYTHONPATH}; /usr/bin/python3 -m gesture.ros_operator_node --camera "$GESTURE_CAMERA_INDEX"'

echo "Final demo running: gesture flight -> TARGET READY -> AUTO_LAND."
echo "After handoff, HUMAN authority is permanently revoked and C++ PID takes over landing XY."

wait_time=0
mission_succeeded=false
failure_class=OTHER
while [ "$wait_time" -lt 420 ]; do
    if docker logs final_mission 2>&1 | grep -q "Mission Complete"; then
        mission_succeeded=true
        break
    fi
    if docker logs final_mission 2>&1 | grep -q -E "MISSION_FAILED|TAKEOFF_OR_OFFBOARD_FAILED|FAILSAFE|Landing timeout"; then
        echo "Final mission reported a terminal failure."
        break
    fi
    if ! docker ps --format '{{.Names}}' | grep -Fxq final_mission; then
        echo "Final Mission Commander exited before completion."
        break
    fi
    if ! docker ps --format '{{.Names}}' | grep -Fxq final_gesture_operator; then
        echo "Gesture operator exited before mission completion."
        failure_class=RUNNER_CLEANUP
        break
    fi
    sleep 2
    wait_time=$((wait_time + 2))
done

if [ "$mission_succeeded" = true ]; then
    echo "Mission Complete detected; preserving terminal dashboard for 5 seconds."
    sleep 5
else
    mission_log="$(docker logs final_mission 2>&1 || true)"
    if [ "$failure_class" != "RUNNER_CLEANUP" ]; then
        if ! grep -q "AUTO_LAND_AUTHORIZED" <<< "$mission_log"; then
            if grep -q "TARGET_NOT_READY" <<< "$mission_log"; then
                failure_class=TARGET_READY_GATE
            else
                failure_class=AUTO_LAND_HANDOFF
            fi
        elif grep -q -E "PLATFORM_MOTION_NOT_VERIFIED|LOW_ALTITUDE_TARGET_LOST" <<< "$mission_log"; then
            failure_class=MOVING_TRACKING
        elif grep -q -E "DISARM_FAILED|Landing timeout|FINAL_COMMIT_TIMEOUT" <<< "$mission_log"; then
            failure_class=TOUCHDOWN_TERMINATION
        fi
    fi
    echo "FINAL_DEMO_FAILURE_CLASS=$failure_class"
fi

echo "Saving final integration logs..."
docker logs final_mission > artifacts/logs/demo_final_mission.log 2>&1 || true
docker logs final_gesture_operator > artifacts/logs/demo_final_gesture.log 2>&1 || true
docker logs final_cpp_control > artifacts/logs/demo_final_cpp_control.log 2>&1 || true
docker logs final_aruco > artifacts/logs/demo_final_aruco.log 2>&1 || true
docker logs final_platform_controller > artifacts/logs/demo_final_platform.log 2>&1 || true
docker logs final_viewer > artifacts/logs/demo_final_viewer.log 2>&1 || true
docker logs final_px4_sitl > artifacts/logs/demo_final_px4.log 2>&1 || true

if [ "$mission_succeeded" != true ]; then
    exit 1
fi

echo "FINAL_DEMO=PASS"
