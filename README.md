# 1. Project Title
UAV Precision Landing Simulation

# 2. Project Overview
Portfolio-ready, reproducible PX4 SITL precision-landing prototype with native C++ PID control, ROS 2 vision integration and a GPU-accelerated Gazebo simulation.
This project is a PX4 SITL simulation and is not deployed on real drone hardware. It simulates a downward-facing camera to perform precision landing onto a fixed ArUco-based target, serving as an engineering prototype and portfolio piece.

# 3. Demo Capabilities
- PX4 SITL
- Gazebo Harmonic
- ROS 2 Humble
- OpenCV ArUco DICT_4X4_50, marker ID 0
- Live debug overlay
- Python Mission Commander
- Native C++ PID for XY alignment
- Deadband
- Output saturation
- Integral clamping
- Stale-observation timeout
- NaN/Inf protection
- Python baseline fallback
- C++ Shadow Mode
- GPU-accelerated simulation
- Two-window visual demo
- Automatic touchdown, disarm and cleanup

# 4. Final Demo Flow
The mission follows this explicit sequence: `INIT` -> `ARM` -> `TAKEOFF` -> `OFFBOARD` -> `NAVIGATE` -> `SCAN` -> `ALIGN` -> `DESCEND` -> `LAND` -> `DISARMED` -> `MISSION COMPLETE`

- Drone cất cánh.
- Bay đến waypoint NED đã khóa.
- Tìm ArUco ID 0.
- C++ PID căn tâm.
- Tiếp tục hiệu chỉnh XY khi hạ độ cao.
- Gọi PX4 landing.
- Chờ telemetry xác nhận disarm.
- Cleanup container.

# 5. System Architecture
- **Gazebo/PX4**: simulation; vehicle dynamics; downward camera; vehicle telemetry.
- **ROS image bridge**: chuyển camera image từ Gazebo sang ROS 2.
- **ArUco detector**: nhận camera frame; phát hiện marker ID 0; publish signed center error; publish debug image.
- **C++ PID node**: nhận signed center error; tạo velocity XY; publish C++ velocity command; xử lý deadband, saturation, timeout và invalid input.
- **Python Mission Commander**: kết nối MAVSDK; quản lý mission state; arm; takeoff; offboard; waypoint navigation; nhận velocity XY từ C++; quản lý descent Z; gửi command tới PX4; gọi landing; chờ disarm; ghi Mission Complete.
- **OpenCV viewer**: hiển thị live debug image và overlay.

# 6. Python Baseline vs C++ PID
- `make demo-python`: verified Python control baseline; fallback implementation; giữ nguyên để comparison và rollback.
- `make demo-cpp`: primary final demo; C++ PID là nguồn velocity XY; Python vẫn quản lý mission orchestration và MAVSDK.

# 7. Technology Stack
- ROS 2 Humble
- PX4 Autopilot SITL
- Gazebo Harmonic
- C++17
- Python 3.10
- Docker & Docker Compose
- OpenCV
- NVIDIA Container Toolkit

# 8. Prerequisites
**Host Requirements**:
- Linux host
- Docker Engine
- Docker Compose plugin
- NVIDIA GPU và driver cho GPU path
- NVIDIA Container Toolkit (yêu cầu quyền sudo trên host để cài đặt)
- X11 display access
- Git
- Đủ disk/RAM cho simulation.

**Container Environment** (Do not install these on host):
- ROS 2 Humble
- PX4
- Gazebo Harmonic
- OpenCV
- MAVSDK
- C++ build tools

# 9. GPU and Display Requirements
- Kiểm tra host bằng lệnh `nvidia-smi`.
- Kiểm tra Docker GPU bằng command: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`.
- Cách xác minh simulation container thấy GPU: Kiểm tra logs của Gazebo container hoặc chạy `gz topic -e -t /world/inspection/stats` trong container.
- **Lưu ý**: Hành vi khi GPU không khả dụng là Gazebo sẽ fallback về software rendering, điều này có thể làm simulation chậm đáng kể và rớt frames. X11 là bắt buộc để hiển thị GUI.

# 10. Quick Start
```bash
git clone <YOUR_REPOSITORY_URL>
cd <REPOSITORY_DIRECTORY>
docker compose build
make demo-cpp
```
To stop the demo manually and cleanup containers:
```bash
make stop
```

# 11. Available Make Targets
- `make build`: Build the ROS 2 workspace (drone_landing_ws).
- `make test`: Run functional unit tests.
- `make demo-python`: Verified Python control baseline (mở GUI và thực hiện flight).
- `make shadow-cpp`: C++ Shadow Mode (C++ PID chạy ngầm, Python baseline bay thực).
- `make demo-cpp`: Primary final demo (C++ PID là nguồn velocity XY, mở GUI và thực hiện flight).
- `make verify`: Automated tests suite.
- `make stop`: Stop containers and cleanup.

# 12. Expected Runtime Behaviour
Two-window visual demo sẽ xuất hiện:
- **Window 1 — Gazebo**: world 3D; drone; landing marker; lightweight visual-polish entities; quá trình bay và đáp.
- **Window 2 — OpenCV**: live downward camera; ArUco polygon; marker ID; tâm ảnh; tâm marker; signed dx/dy; velocity vx/vy nếu hiện có; FPS; mission state; CONTROL: C++ PID hoặc CONTROL: PYTHON.

# 13. ROS Topics and Control Contracts
- `/camera` (sensor_msgs/Image): Camera feed bridge từ Gazebo.
- `/aruco/center_error` (geometry_msgs/Point): Signed error dx/dy được detector xuất ra.
- `/precision_landing/cmd_vel` (geometry_msgs/Twist): Vận tốc tính toán bởi C++ PID.
- `/mission/status` (std_msgs/String): Trạng thái mission cho OpenCV overlay.

# 14. Project Structure
```text
.
├── docker/
├── docker-compose.yml
├── docs/
│   └── evidence/
├── drone_landing_ws/
│   └── src/
│       ├── precision_landing_control_cpp/
│       │   └── config/
│       └── px4_vision_autonomy/
│           └── models/ (world/model assets)
├── Makefile
├── scripts/
└── THIRD_PARTY_NOTICES.md
```

# 15. Validation Results
- Python baseline verified.
- C++ functional GTests: 10 PASS.
- C++ shadow sign matching verified.
- C++ repeatability 3/3.
- 0 NaN/Inf encountered in validation.
- Final touchdown confirmed.
- PX4 disarm confirmed.
- Mission Complete state confirmed.

Three consecutive verified SITL landing runs passed under the tested configuration.

# 16. Engineering Evidence
All validation reports and repository states are stored in the `docs/evidence/` directory:
- [FINAL_TERMINATION_REPORT.md](docs/evidence/FINAL_TERMINATION_REPORT.md)
- [REPOSITORY_INVENTORY.md](docs/evidence/REPOSITORY_INVENTORY.md)
- [LICENSE_ATTRIBUTION_REPORT.md](docs/evidence/LICENSE_ATTRIBUTION_REPORT.md)

# 17. Troubleshooting
- **Docker không thấy GPU**: Kiểm tra lại NVIDIA Container Toolkit trên host.
- **Gazebo dùng software renderer**: Kiểm tra quyền passthrough GPU hoặc OpenGL trong docker-compose.
- **X11/OpenCV window không mở**: Chạy `xhost +local:root` trên host.
- **Camera topic không publish**: Restart lại simulation, PX4 có thể boot chậm.
- **ROS 2 image bị drop do shared-memory configuration**: Xảy ra trên một số kernel nếu `--ipc=host` không được set.
- **MAVSDK connection timeout**: Port UDP có vấn đề routing.
- **Port 14540 bị container/process cũ chiếm**: Chạy `make stop` trước khi thử lại.
- **`PX4_VERSION` chưa được load**: Nếu thiếu env variable, `docker-compose` sẽ hiện warning. Đã cấu hình cứng trong `.env` hoặc `versions.env`.
- **Cleanup container không hoàn tất**: Có container bị kẹt, dùng `docker compose down -v --remove-orphans`.

# 18. Known Limitations
- SITL only; chưa kiểm thử trên real drone.
- Chỉ fixed ArUco marker ID 0.
- Phụ thuộc downward camera và marker visibility.
- Chưa xử lý điều kiện thời tiết/ánh sáng thực.
- Hiện target waypoint/world được cấu hình trước.
- C++ lint/format có thể còn limitation.
- NVIDIA/X11 host setup vẫn cần thao tác ngoài container.
- Second-host verification chưa PASS cho tới Phase N.

# 19. Acknowledgements
Parts of this repository are derived from and modified from the upstream `px4_vision_autonomy` project.
The upstream source is used under the MIT License.
For full third-party legal notices, please see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) in the root of this repository.
The original upstream package license is preserved in its entirety at `drone_landing_ws/src/px4_vision_autonomy/LICENSE`.

# 20. License and Third-Party Notices
The root project license is currently **NOT_SELECTED**.
Please see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for full licensing information regarding third-party code from `px4_vision_autonomy`.
