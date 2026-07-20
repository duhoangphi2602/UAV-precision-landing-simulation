#!/bin/bash
set -Eeuo pipefail

./scripts/allow_x11.sh

echo "Starting Gazebo and ROS Bridge..."
docker compose run --rm -d --name px4_sitl simulation bash -c "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && sed -i 's/ 1.5707 / -1.5707 /g' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500_mono_cam_down/model.sdf && export PX4_GZ_WORLD=inspection && export PX4_GZ_MODEL_POSE='0,0,2.5,0,0,0' && cd /opt/PX4-Autopilot && DONT_RUN=1 make px4_sitl gz_x500_mono_cam_down && ./build/px4_sitl_default/bin/px4"
echo "Container px4_sitl Created"

docker compose run --rm -d --name ros_bridge simulation bash -c "ros2 run ros_gz_image image_bridge /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"
echo "Container ros_bridge Created"

sleep 20



echo "1. Gazebo camera topic thật:"
docker exec px4_sitl bash -c "gz topic -l | grep -i camera" || true

echo "2. Type của topic camera:"
docker exec px4_sitl bash -c "gz topic -i -t /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image" || true

echo "3. Đo Gazebo Hz trong 10 giây:"
docker exec px4_sitl bash -c "timeout 10 gz topic -f -t /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image" || true

echo "5. Xác minh ROS 2 topic:"
docker exec ros_bridge bash -c "source /opt/ros/humble/setup.bash && ros2 topic info /camera -v" || true
docker exec ros_bridge bash -c "source /opt/ros/humble/setup.bash && timeout 10 ros2 topic hz /camera" || true

echo "6. Lưu ngay một frame từ /camera:"
docker exec ros_bridge bash -c "source /opt/ros/humble/setup.bash && python3 /home/devuser/drone_landing_ws/src/px4_vision_autonomy/scripts/save_frame.py" || true

docker cp ros_bridge:/home/devuser/drone_landing_ws/debug_frame.png ./debug_frame.png || true
ls -la debug_frame.png || true

./scripts/stop_demo.sh
