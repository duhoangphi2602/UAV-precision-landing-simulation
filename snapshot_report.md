# Snapshot Report

## 1. Git Status & Diff
**`git status --short`**
```
 M drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf
?? imu.txt
?? old_inspection.sdf
?? ps_out.txt
?? sitl_logs.txt
?? test_topics.txt
```

**`git diff --stat`**
```
 .../src/px4_vision_autonomy/worlds/inspection.sdf  | 175 ++++-----------------
 1 file changed, 34 insertions(+), 141 deletions(-)
```

## 2. Files Modified Since Camera PASS
The following files were modified since the last successful camera gate (`/camera` PASS):
- `scripts/run_camera_only_gate.sh` (Updated to kill orphans, use trap, and fix sed single quotes)
- `scripts/run_demo_python_baseline.sh` (Updated to remove background jobs and capture logs)
- `drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf` (Removed all Gazebo Fuel models like trees/cars to fix Gazebo hanging/timeout, replaced ground plane with default)

## 3. Launch Scripts

### Exact Content of `run_camera_only_gate.sh`
```bash
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
docker compose run --rm -d --name px4_sitl simulation bash -c "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && sed -i 's/<model name=.x500_mono_cam_down.>/<model name=\"x500_mono_cam_down\">\n    <static>true<\/static>/g' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500_mono_cam_down/model.sdf && export PX4_GZ_WORLD=inspection && export PX4_GZ_MODEL_POSE='5.8,0,2.5,0,0,0' && cd /opt/PX4-Autopilot && make px4_sitl gz_x500_mono_cam_down"

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
```

### Exact Content of `run_demo_python_baseline.sh`
```bash
#!/bin/bash
set -Eeuo pipefail

./scripts/allow_x11.sh

echo "Starting Python Baseline Demo..."
docker compose run --rm -d --name px4_sitl simulation bash -c "cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && export PX4_GZ_WORLD=inspection && cd /opt/PX4-Autopilot && make px4_sitl gz_x500_mono_cam_down"
echo "Container px4_sitl Created"

docker compose run --rm -d --name ros_bridge simulation bash -c "ros2 run ros_gz_image image_bridge /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image --ros-args -r /world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image:=/camera"
echo "Container ros_bridge Created"

docker compose run --rm -d --name aruco simulation bash -c "ros2 run px4_vision_autonomy aruco_detector --ros-args -p camera_topic:=/camera"
docker compose run --rm -d --name viewer simulation bash -c "ros2 run px4_vision_autonomy camera_viewer"
docker compose run --rm -d --name mission simulation bash -c "ros2 run px4_vision_autonomy mission_commander --ros-args -p control_source:=internal_python"

echo "Waiting for mission commander to finish (max 300s)..."
docker logs -f mission > mission_logs.txt 2>&1 &
MISSION_PID=$!
sleep 240
kill $MISSION_PID || true
echo "Mission Commander Logs:"
cat mission_logs.txt
./scripts/stop_demo.sh
```

### Actual PX4/Gazebo Commands Used
- **In Camera Gate:** 
  `cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && sed -i 's/<model name=.x500_mono_cam_down.>/<model name=\"x500_mono_cam_down\">\n    <static>true<\/static>/g' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500_mono_cam_down/model.sdf && export PX4_GZ_WORLD=inspection && export PX4_GZ_MODEL_POSE='5.8,0,2.5,0,0,0' && cd /opt/PX4-Autopilot && make px4_sitl gz_x500_mono_cam_down`
- **In Python Baseline:**
  `cp /home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf /opt/PX4-Autopilot/Tools/simulation/gz/worlds/ && cp -r /home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad /opt/PX4-Autopilot/Tools/simulation/gz/models/ && export PX4_GZ_WORLD=inspection && cd /opt/PX4-Autopilot && make px4_sitl gz_x500_mono_cam_down`

## 4. Environment State
- **Docker Compose Config:**
```yaml
name: uav-precision-landing-simulation
services:
  simulation:
    build:
      context: /home/hoangphi/Projects/UAV-precision-landing-simulation
      dockerfile: Dockerfile
      args:
        PX4_VERSION: ""
        USER_GID: "1000"
        USER_UID: "1000"
    environment:
      DISPLAY: :0
      LIBGL_ALWAYS_SOFTWARE: "1"
      QT_X11_NO_MITSHM: "1"
    network_mode: host
    privileged: true
    volumes:
      - type: bind
        source: /tmp/.X11-unix
        target: /tmp/.X11-unix
        bind: {}
      - type: bind
        source: /run/user/1000/.mutter-Xwaylandauth.6T9MS3
        target: /home/devuser/.Xauthority
        bind: {}
      - type: bind
        source: /home/hoangphi/Projects/UAV-precision-landing-simulation/drone_landing_ws
        target: /home/devuser/drone_landing_ws
        bind: {}
      - type: bind
        source: /home/hoangphi/Projects/UAV-precision-landing-simulation/scripts
        target: /home/devuser/scripts
        bind: {}
      - type: bind
        source: /home/hoangphi/Projects/UAV-precision-landing-simulation/tests
        target: /home/devuser/tests
        bind: {}
      - type: bind
        source: /home/hoangphi/Projects/UAV-precision-landing-simulation/artifacts
        target: /home/devuser/artifacts
        bind: {}
```
- **Exact PX4 Commit:** `78a44ed439ee941acd4844ff8ceaedbfe0faea56`
- **World File:** `/home/devuser/drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf` (Fuel models removed, ground replaced with default.sdf ground)
- **Model File:** `/home/devuser/drone_landing_ws/src/px4_vision_autonomy/models/aruco_landing_pad` (Mounted/copied into PX4 dir). Drone model is the unmodified `x500_mono_cam_down`.

## 5. Latest Proven Results
- **Gazebo Camera Topic:** `/world/inspection/model/x500_mono_cam_down_0/link/camera_link/sensor/camera/image`
- **Gazebo Hz:** Publishing (exact Hz not measured but frame was successfully bridged).
- **ROS /camera Hz:** Publishing successfully.
- **Frame Path:** `debug_frame.png`
- **Camera Pitch:** Original unmodified pitch (`x500_mono_cam_down` from PX4 repo). When spawned at `(5.8, 0, 2.5)` pointing straight down.

## 6. Classification

- **LAST_KNOWN_GOOD:** 
  The camera successfully published when `inspection.sdf` was used with a `static=true` drone at `(5.8, 0, 2.5)` (Camera Gate test).
- **CURRENT_REGRESSION:**
  When `static=false` (in `run_demo_python_baseline.sh` or standard runs), the drone spawned at `(0,0,0.2)` or `(0,0,0)` on the custom `inspection.sdf` ground. This caused extreme physics spikes/collisions on spawn, leading to `WARN [health_and_arming_checks] Preflight Fail: ekf2 missing data` and `No valid data from Accel 0`. Because EKF2 failed, MAVSDK connection failed and mission commander stalled. Additionally, `inspection.sdf` originally contained numerous Fuel models which caused Gazebo to hang downloading them in short-lived containers.
- **FILES_CAUSING_REGRESSION:**
  `drone_landing_ws/src/px4_vision_autonomy/worlds/inspection.sdf` (Fixed in the latest step by removing Fuel models and swapping the collision/friction configuration of `ground_plane` to exactly match PX4's `default.sdf`).
