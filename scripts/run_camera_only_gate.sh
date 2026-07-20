#!/bin/bash
set -Eeuo pipefail

# Cleanup function to kill ONLY containers started by this script
cleanup() {
    echo "Cleaning up camera gate containers..."
    docker rm -f px4_sitl ros_bridge >/dev/null 2>&1 || true
    echo "Cleanup complete."
}
trap cleanup EXIT

./scripts/allow_x11.sh

echo "Starting Gazebo (static drone at z=2.5 above marker)..."
docker compose run --rm -d --name px4_sitl simulation bash -c "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && sed -i 's/<model name=.x500_mono_cam_down.>/<model name=\"x500_mono_cam_down\">\\n    <static>true<\\/static>/g' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500_mono_cam_down/model.sdf && export PX4_GZ_WORLD=inspection && export PX4_GZ_MODEL_POSE='5.8,0,2.5,0,0,0' && cd /opt/PX4-Autopilot && make px4_sitl gz_x500_mono_cam_down"

echo "Waiting for Gazebo camera topic (max 120s)..."
for i in {1..60}; do
    if docker exec px4_sitl bash -c "gz topic -l" 2>/dev/null | grep -q "/world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image"; then
        echo "Gazebo camera topic is ready!"
        break
    fi
    sleep 2
    if [ $i -eq 60 ]; then
        echo "Timeout waiting for Gazebo camera topic."
        exit 1
    fi
done

echo "Starting ROS Bridge..."
docker compose run --rm -d --name ros_bridge simulation bash -c "ros2 run ros_gz_image image_bridge /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"

echo "Waiting for ROS /camera topic (max 30s)..."
for i in {1..15}; do
    if docker exec ros_bridge bash -c "source /opt/ros/humble/setup.bash && ros2 topic info /camera" 2>/dev/null | grep -q "Publisher count: 1"; then
        echo "ROS /camera topic is ready!"
        break
    fi
    sleep 2
    if [ $i -eq 15 ]; then
        echo "Timeout waiting for ROS /camera topic."
        exit 1
    fi
done

echo "Saving frame..."
docker exec ros_bridge bash -c "source /opt/ros/humble/setup.bash && python3 /home/devuser/drone_landing_ws/src/px4_vision_autonomy/scripts/save_frame.py"

echo "Extracting frame to host..."
docker cp ros_bridge:/home/devuser/drone_landing_ws/debug_frame.png ./debug_frame.png

echo "Running marker detection..."
docker compose run --rm simulation bash -c "python3 drone_landing_ws/check_marker.py"

echo "Camera Gate Done."
