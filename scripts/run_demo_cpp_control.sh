#!/bin/bash
set -Eeuo pipefail

./scripts/allow_x11.sh

echo "Starting C++ Control Demo..."
docker compose run --rm -d --name px4_sitl simulation bash -c "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && export PX4_GZ_WORLD=inspection && cd /opt/PX4-Autopilot && DONT_RUN=1 make px4_sitl gz_x500_mono_cam_down && ./build/px4_sitl_default/bin/px4"
sleep 5

docker compose run --rm -d --name ros_bridge simulation bash -c "ros2 run ros_gz_image image_bridge /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"
sleep 2

docker compose run --rm -d --name aruco simulation bash -c "ros2 run px4_vision_autonomy aruco_detector --ros-args -p camera_topic:=/camera"
docker compose run --rm -d --name viewer simulation bash -c "ros2 run px4_vision_autonomy camera_viewer"
docker compose run --rm -d --name cpp_control simulation bash -c "ros2 launch precision_landing_control_cpp control_cpp.launch.py"
docker compose run --rm -d --name mission simulation bash -c "ros2 run px4_vision_autonomy mission_commander --ros-args -p control_source:=external_cpp"

echo "Demo is running. Use 'make stop' to stop."
sleep 120
./scripts/stop_demo.sh
