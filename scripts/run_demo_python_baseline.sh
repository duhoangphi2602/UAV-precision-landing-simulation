#!/bin/bash
set -Eeuo pipefail

cleanup() {
    echo "Cleaning up containers..."
    docker compose down --remove-orphans || true
    echo "Cleanup complete."
}
trap cleanup EXIT

./scripts/allow_x11.sh

echo "Starting Gazebo and PX4..."
docker compose run --rm -d --name px4_sitl simulation bash -c "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && export PX4_GZ_WORLD=inspection && cd /opt/PX4-Autopilot && make px4_sitl gz_x500_mono_cam_down"

echo "Waiting for Gazebo camera topic (max 120s)..."
wait_time=0
camera_topic_found=false
while [ $wait_time -lt 120 ]; do
    if docker exec px4_sitl bash -c "gz topic -l | grep -i 'camera/image'" > /dev/null 2>&1; then
        camera_topic_found=true
        break
    fi
    sleep 2
    wait_time=$((wait_time + 2))
done

if [ "$camera_topic_found" = false ]; then
    echo "FAIL: Gazebo camera topic not found."
    exit 1
fi
echo "Gazebo camera topic is ready!"

echo "Starting ROS Bridge..."
docker compose run --rm -d --name ros_bridge simulation bash -c "ros2 run ros_gz_image image_bridge /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"

echo "Waiting for ROS /camera topic (max 30s)..."
wait_time=0
ros_topic_found=false
while [ $wait_time -lt 30 ]; do
    if docker exec ros_bridge bash -c "source /opt/ros/humble/setup.bash && ros2 topic info /camera" 2>/dev/null | grep -q "Publisher count: 1"; then
        ros_topic_found=true
        break
    fi
    sleep 2
    wait_time=$((wait_time + 2))
done

if [ "$ros_topic_found" = false ]; then
    echo "FAIL: ROS /camera topic not active."
    exit 1
fi
echo "ROS /camera topic is active!"

echo "Starting ArUco detector and viewer..."
docker compose run --rm -d --name aruco simulation bash -c "ros2 run px4_vision_autonomy aruco_detector --ros-args -p camera_topic:=/camera"
docker compose run --rm -d --name viewer simulation bash -c "ros2 run px4_vision_autonomy camera_viewer"

echo "Checking ArUco detector process..."
sleep 5
if ! docker ps | grep -q "aruco"; then
    echo "FAIL: aruco_detector process died."
    exit 1
fi
echo "ArUco detector alive!"

echo "Waiting for PX4 readiness (max 180s)..."
wait_time=0
px4_ready=false
while [ $wait_time -lt 180 ]; do
    if docker logs px4_sitl 2>&1 | grep -q -E "Ready for takeoff|home set"; then
        px4_ready=true
        break
    fi
    sleep 3
    wait_time=$((wait_time + 3))
done
if [ "$px4_ready" = false ]; then
    echo "FAIL: PX4 sensors never initialized (no 'home set' or 'Ready for takeoff')."
    echo "--- PX4 LOGS ---"
    docker logs px4_sitl 2>&1 | tail -30
    echo "--- GZ STATS ---"
    docker exec px4_sitl bash -c "gz topic -e -t /world/inspection/stats -n 1" 2>/dev/null || true
    exit 1
else
    echo "PX4 is ready!"
fi

echo "Starting Mission Commander..."
docker compose run --rm -d --name mission simulation bash -c "ros2 run px4_vision_autonomy mission_commander --ros-args -p control_source:=internal_python -p wp_north:=0.0 -p wp_east:=5.8 -p wp_down:=-3.0 -p flip_x:=true -p flip_y:=true"

echo "Polling mission status (max 300s)..."
wait_time=0
mission_done=false
while [ $wait_time -lt 300 ]; do
    if docker logs mission 2>&1 | grep -q -E "Landing detected|Failsafe|FAILSAFE|LAND|Completed|Landed"; then
        echo "Mission terminal state reached!"
        mission_done=true
        break
    fi
    if ! docker ps | grep -q "mission"; then
        echo "Mission container exited."
        mission_done=true
        break
    fi
    sleep 5
    wait_time=$((wait_time + 5))
done

if [ "$mission_done" = false ]; then
    echo "TIMEOUT: Mission did not finish in 300s."
fi

echo "================ MISSION LOGS ================"
docker logs mission || true
echo "=============================================="

echo "Demo script finished."
