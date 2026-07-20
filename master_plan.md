# MASTER ACTION PLAN

## Half-Day Dockerized PX4 Vision Precision Landing

## 1. Mục tiêu

Trong tối đa một nửa ngày kỹ thuật, tạo được một fork hoạt động của:

`Tinny-Robot/px4_vision_autonomy`

Kết quả cuối phải thể hiện được:

1. PX4 SITL chạy trong môi trường cô lập.
2. Gazebo hiển thị drone X500 với camera hướng xuống.
3. Camera Gazebo được bridge sang ROS 2.
4. Python/OpenCV phát hiện ArUco.
5. Cửa sổ OpenCV hiển thị:

   * khung xanh quanh marker;
   * tâm marker;
   * tâm ảnh;
   * vector sai lệch;
   * giá trị `dx`, `dy`;
   * FPS;
   * trạng thái nhiệm vụ.
6. Một ROS 2 node C++ dùng PID nhận sai lệch ảnh và tạo velocity command.
7. Python Mission Commander sử dụng command từ C++ để gửi xuống PX4 bằng MAVSDK.
8. Drone thực hiện:

   * arm;
   * takeoff;
   * chuyển Offboard;
   * bay đến khu vực landing;
   * tìm ArUco;
   * căn chỉnh;
   * hạ cánh.
9. Có unit test C++ và mock test Python.
10. Có script chạy demo và script verification.

---

# 2. Định nghĩa phạm vi nửa ngày

## 2.1 Bắt buộc hoàn thành

* Fork source của repo gốc.
* Ghi lại upstream commit SHA.
* Docker environment chạy được ROS 2 Humble.
* PX4 SITL và Gazebo chạy được.
* Camera topic nhận được frame.
* ArUco detector hoạt động.
* OpenCV debug window hoạt động.
* C++ PID package build được bằng CMake/ament_cmake.
* C++ PID có unit test.
* C++ PID phát lệnh điều khiển thật.
* Python Mission Commander nhận lệnh C++ và gửi bằng MAVSDK.
* Có chế độ quay về controller Python gốc để không phá baseline.
* Có one-command hoặc số lượng command tối thiểu để chạy demo.
* Có log xác nhận từng acceptance gate.

## 2.2 Không bắt buộc trong nửa ngày

* Viết lại toàn bộ MAVSDK bridge bằng C++.
* CUDA OpenCV.
* AprilTag.
* Camera pose estimation 6DoF.
* ROS 2 custom messages.
* QGroundControl.
* CI chạy full Gazebo.
* PID autotuning.
* Multi-drone.
* Real drone deployment.
* Production-grade Docker image tối ưu dung lượng.

## 2.3 Stretch goals

Chỉ triển khai khi toàn bộ MVP đã PASS:

* MAVSDK C++ adapter.
* Closed-loop PID overshoot plot.
* Fault injection target loss.
* Docker GPU profile riêng.
* Video recording tự động.
* GitHub Actions cho unit tests.

---

# 3. Kiến trúc MVP

```text
Gazebo Harmonic
   │ gz camera image
   ▼
ros_gz_bridge
   │ sensor_msgs/msg/Image
   │ topic: /camera
   ▼
aruco_detector.py
   ├── /aruco/center_error
   ├── /aruco/debug_image
   └── /aruco/marker_visible
            │
            ▼
precision_landing_control_cpp
   ├── PID X/Y
   ├── deadband
   ├── saturation
   ├── stale-data timeout
   ├── target-loss reset
   ├── /precision_landing/cmd_vel
   └── /precision_landing/control_debug
            │
            ▼
mission_commander.py
   ├── arm
   ├── takeoff
   ├── navigate
   ├── scan
   ├── align
   ├── descend
   ├── land
   └── MAVSDK Python
            │
            ▼
PX4 SITL
```

## Quyền sở hữu chức năng

### Python Vision Node

Chịu trách nhiệm:

* Nhận frame.
* Phát hiện ArUco.
* Lọc đúng marker ID.
* Tính `dx`, `dy`.
* Vẽ overlay.
* Đo FPS.
* Publish observation.

Không được:

* Tính PID.
* Gửi velocity xuống PX4.
* Arm hoặc takeoff.

### C++ Control Node

Chịu trách nhiệm:

* Nhận `dx`, `dy`.
* Mapping trục camera sang body velocity.
* PID.
* Deadband.
* Clamp velocity.
* Stale timeout.
* Reset PID khi mất marker.
* Publish `geometry_msgs/msg/Twist`.

Không được:

* Arm.
* Takeoff.
* Chuyển Offboard trong MVP.
* Gọi trực tiếp Gazebo.

### Python Mission Commander

Chịu trách nhiệm:

* MAVSDK connection.
* Mission state machine.
* Arm.
* Takeoff.
* Navigation.
* Offboard.
* Gửi command C++ xuống PX4.
* Landing/failsafe.
* Giữ fallback controller Python.

---

# 4. Cấu trúc thư mục đích

```text
project-root/
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── README.md
├── LICENSE
├── UPSTREAM_BASELINE.md
│
├── docker/
│   ├── entrypoint.sh
│   └── versions.env
│
├── scripts/
│   ├── bootstrap_upstream.sh
│   ├── build_workspace.sh
│   ├── allow_x11.sh
│   ├── run_demo.sh
│   ├── run_demo_python_baseline.sh
│   ├── run_demo_cpp_control.sh
│   ├── stop_demo.sh
│   └── verify_halfday.sh
│
├── drone_landing_ws/
│   └── src/
│       ├── px4_vision_autonomy/
│       │   ├── config/
│       │   ├── launch/
│       │   ├── models/
│       │   ├── worlds/
│       │   ├── px4_vision_autonomy/
│       │   │   └── nodes/
│       │   ├── package.xml
│       │   ├── setup.py
│       │   └── setup.cfg
│       │
│       └── precision_landing_control_cpp/
│           ├── CMakeLists.txt
│           ├── package.xml
│           ├── include/
│           │   └── precision_landing_control_cpp/
│           │       └── pid_controller.hpp
│           ├── src/
│           │   ├── pid_controller.cpp
│           │   └── control_node.cpp
│           ├── config/
│           │   └── pid.yaml
│           ├── launch/
│           │   └── control_cpp.launch.py
│           └── test/
│               └── test_pid_controller.cpp
│
├── tests/
│   ├── mock_aruco_test.py
│   ├── mock_control_input.py
│   └── integration_contract_test.py
│
└── artifacts/
    ├── logs/
    ├── metrics/
    └── screenshots/
```

`PX4-Autopilot` có thể được đặt trong image tại `/opt/PX4-Autopilot` hoặc một named Docker volume. Không commit source PX4 vào repository chính.

---

# 5. Phase 0 — Reality Audit và Upstream Freeze

## Timebox

20 phút.

## Mục tiêu

Không tin tuyệt đối vào README. Xác định source thật đang có gì và tạo baseline có thể truy vết.

## Công việc

1. Kiểm tra project blank:

   * `pwd`;
   * `find`;
   * `git status`;
   * dung lượng đĩa;
   * Docker;
   * NVIDIA runtime;
   * X11.

2. Clone upstream vào thư mục tạm.

3. Ghi lại:

   * repository URL;
   * branch;
   * commit SHA;
   * ngày clone;
   * license;
   * danh sách node;
   * launch file;
   * model;
   * world;
   * topic;
   * dependency.

4. Copy source upstream vào:

```text
drone_landing_ws/src/px4_vision_autonomy
```

Không giữ nested `.git`.

5. Tạo `UPSTREAM_BASELINE.md`.

6. Không refactor source trong Phase 0.

## Phải kiểm tra đặc biệt

* Launch file nào thật sự tồn tại.
* `setup.py` đăng ký executable nào.
* Camera topic thật là `/camera` hay topic khác.
* ArUco dictionary và marker ID.
* Mission Commander dùng MAVSDK như thế nào.
* Frame mapping:

  * `swap_axes`;
  * `flip_x`;
  * `flip_y`.
* World và model được launch sử dụng.
* PX4 target `gz_x500_mono_cam_down` có tồn tại trong PX4 version đang dùng hay không.

## Gate P0

PASS khi:

* Upstream source đã được import.
* Commit SHA được ghi lại.
* License được giữ.
* Có báo cáo mismatch giữa README và source.
* Không có nested `.git`.

---

# 6. Phase 1 — Docker, ROS 2, PX4 và GPU Sanity

## Timebox

70 phút.

## Mục tiêu

Tạo môi trường đủ chạy repo, không tối ưu quá mức.

## Docker base

* Ubuntu 22.04.
* ROS 2 Humble.
* Gazebo Harmonic.
* `ros_gz_bridge`.
* `cv_bridge`.
* OpenCV có ArUco.
* Python MAVSDK.
* colcon.
* CMake.
* GCC/G++.
* GTest.
* PX4 build dependencies.

## Docker Compose bắt buộc

```text
network_mode: host
DISPLAY
XAUTHORITY
/tmp/.X11-unix
UID/GID mapping
non-root user
workspace bind mount
/dev/dri fallback
```

## RTX 3060

Thứ tự xử lý:

1. Kiểm tra host `nvidia-smi`.
2. Kiểm tra Docker có truy cập NVIDIA runtime hay không.
3. Nếu sẵn sàng, dùng `gpus: all`.
4. Nếu chưa sẵn sàng, không được dừng toàn bộ project để cài CUDA/OpenCV CUDA.
5. Cho phép Gazebo chạy bằng `/dev/dri` hoặc software rendering.
6. Không compile OpenCV CUDA trong MVP.

GPU 3060 chủ yếu được dùng để render Gazebo mượt hơn. ArUco vẫn chạy CPU để giảm thời gian setup.

## PX4

* Không dùng một nhánh không pin trong kết quả cuối.
* Có thể thử một ref tương thích để tìm baseline.
* Sau khi target chạy được, ghi exact commit SHA vào `docker/versions.env`.
* Không update PX4 sau khi baseline đã PASS.
* Build đúng target camera hướng xuống.

## Sanity checks

```text
ros2 --help
gz sim --version
python3 -c "import rclpy"
python3 -c "import cv2; assert hasattr(cv2, 'aruco')"
python3 -c "from cv_bridge import CvBridge"
python3 -c "from mavsdk import System"
colcon --help
cmake --version
g++ --version
```

## Gate P1

PASS khi:

* Docker image build thành công.
* Container chạy non-root.
* Files tạo từ container thuộc UID người dùng.
* ROS 2 hoạt động.
* OpenCV ArUco import được.
* Python MAVSDK import được.
* Gazebo có thể khởi động.
* PX4 SITL build được.
* GPU được ghi `AVAILABLE` hoặc `FALLBACK`; GPU không phải điều kiện bắt buộc để PASS.

---

# 7. Phase 2 — Reproduce Golden Python Baseline

## Timebox

80 phút.

## Mục tiêu

Chạy repo gần nguyên bản trước khi đưa C++ vào.

## Công việc

1. Build workspace:

```text
colcon build --symlink-install
```

2. Kiểm tra ROS executable.

3. Sửa tối thiểu các lỗi portability:

   * hard-coded `~/PX4-Autopilot`;
   * camera topic;
   * model path;
   * world path;
   * X11;
   * package install rules;
   * launch ordering.

4. Không đổi thuật toán điều khiển trước khi baseline chạy.

5. Chạy theo thứ tự:

```text
PX4/Gazebo
→ camera bridge
→ camera viewer
→ ArUco detector
→ Mission Commander
```

6. Trước khi arm:

   * camera phải có frame;
   * detector node phải hoạt động;
   * MAVSDK phải discovery được PX4;
   * marker topic phải có dữ liệu khi marker trong view.

7. Chạy baseline Python một lần.

## Baseline evidence

Ghi:

* PX4 connection.
* Arm result.
* Takeoff result.
* Offboard result.
* Marker detected.
* State transitions.
* Landing result.
* Camera FPS.
* Command dùng để chạy.
* Các patch cần thiết so với upstream.

## Gate P2

PASS khi:

* Gazebo mở.
* Drone xuất hiện.
* Camera viewer mở.
* Frame camera nhận liên tục.
* ArUco được phát hiện.
* Mission Commander kết nối PX4.
* Drone ít nhất thực hiện được arm, takeoff và Offboard.
* Mục tiêu ưu tiên là hoàn thành landing Python baseline.

Nếu landing chưa thành công nhưng toàn bộ pipeline đã chạy, trạng thái là `PARTIALLY_VERIFIED`, không được tuyên bố PASS.

---

# 8. Phase 3 — OpenCV Visual Upgrade và Python Tests

## Timebox

70 phút.

## Mục tiêu

Tạo phần visual rõ ràng cho portfolio mà không thay đổi giao thức đang chạy.

## Overlay bắt buộc

Trên debug image phải có:

* Bounding polygon màu xanh quanh ArUco.
* Marker ID.
* Tâm marker.
* Tâm ảnh.
* Đường nối từ tâm ảnh tới tâm marker.
* Mũi tên chỉ hướng.
* `dx`.
* `dy`.
* FPS.
* Detection latency nếu đo được.
* Trạng thái:

  * SEARCH;
  * ALIGN;
  * DESCEND;
  * LAND.
* Dòng `CONTROL: PYTHON` hoặc `CONTROL: C++ PID`.

## Camera Viewer

Viewer phải ưu tiên subscribe `/aruco/debug_image`.

Chỉ dùng raw `/camera` làm fallback.

## Marker rules

* Dùng đúng dictionary được world cung cấp.
* Dùng đúng marker ID.
* Không chấp nhận marker ID khác.
* Không publish center error khi marker đúng không tồn tại.
* Có trạng thái target lost.

## Python mock test

Tạo frame tổng hợp:

1. Marker ở giữa.
2. Marker lệch trái.
3. Marker lệch phải.
4. Marker lệch trên.
5. Marker lệch dưới.
6. Sai marker ID.
7. Không có marker.

Kiểm tra:

* Marker đúng được phát hiện.
* Marker sai bị từ chối.
* Dấu `dx`, `dy` đúng.
* Center error gần 0 khi marker ở giữa.
* Overlay output không rỗng.

## Gate P3

PASS khi:

* OpenCV window hiển thị overlay đầy đủ.
* Mock test PASS.
* Wrong-marker acceptance bằng 0 trong test.
* Viewer không làm detector bị block.
* Baseline Python vẫn hoạt động.

---

# 9. Phase 4 — C++ PID Control Migration

## Timebox

80 phút.

## Mục tiêu

Đưa C++ vào đường điều khiển thật mà không viết lại MAVSDK.

## Package

Tạo package:

```text
precision_landing_control_cpp
```

Build type:

```text
ament_cmake
```

C++ standard:

```text
C++17 hoặc C++20, khai báo rõ trong CMakeLists.txt
```

## PID library

Tách khỏi ROS:

```text
PIDController
```

API tối thiểu:

```text
constructor/configure
reset
compute(error, dt)
```

Hỗ trợ:

* `kp`;
* `ki`;
* `kd`;
* integral limit;
* output limit;
* deadband;
* derivative low-pass filter;
* first-sample derivative protection;
* invalid `dt`;
* reset.

## ROS 2 control node

Subscribe:

```text
/aruco/center_error
```

Publish:

```text
/precision_landing/cmd_vel
/precision_landing/control_debug
```

Dùng:

```text
geometry_msgs/msg/Point
geometry_msgs/msg/Twist
std_msgs/msg/String
```

Không tạo custom message trong MVP.

## Parameters

```text
kp_x
ki_x
kd_x
kp_y
ki_y
kd_y
deadband_px
max_velocity_xy
stale_timeout_sec
control_rate_hz
swap_axes
flip_x
flip_y
shadow_mode
```

## Safety

* Khi observation stale: publish zero velocity.
* Khi mất marker: reset PID.
* Clamp velocity.
* Không publish NaN/Inf.
* Không gửi descent command từ C++ trong phiên bản đầu.
* Mission Commander vẫn quản lý descend và landing.
* C++ chỉ chịu trách nhiệm căn chỉnh XY.

## Mission Commander patch

Thêm parameter:

```text
control_source: internal_python | external_cpp
```

### `internal_python`

Giữ nguyên baseline gốc.

### `external_cpp`

* Subscribe `/precision_landing/cmd_vel`.
* Dùng `linear.x` và `linear.y` làm velocity body.
* Không tính lại P controller trong Python.
* Có command timeout.
* Nếu command stale:

  * gửi zero XY;
  * không tiếp tục descend;
  * quay lại ALIGN hoặc SCAN.
* State machine và MAVSDK vẫn thuộc Python.

## Migration sequence

### Bước 1 — Unit test

Chạy GTest cho PID.

### Bước 2 — Shadow mode

C++ nhận error và tính command nhưng Mission Commander vẫn dùng Python internal control.

So sánh:

* dấu velocity;
* magnitude;
* saturation;
* stale handling.

### Bước 3 — External mode

Chuyển:

```text
control_source:=external_cpp
```

C++ command trở thành command XY thật.

### Bước 4 — Bounded flight

* Một lần takeoff.
* Một lần alignment.
* Không chạy lặp vô hạn.
* Có timeout tổng.
* Có emergency stop script.

## Unit tests C++

Bắt buộc kiểm tra:

1. Zero error → zero output.
2. Positive error → output đúng dấu.
3. Negative error → output đúng dấu.
4. Deadband → zero.
5. Saturation.
6. Integral limit.
7. Reset.
8. First derivative sample không kick.
9. Invalid `dt`.
10. Output finite.

## Gate P4

PASS khi:

* CMake configure PASS.
* Package build PASS.
* GTest PASS.
* Shadow comparison hợp lý.
* Mission Commander chạy external mode.
* Command C++ thật sự được dùng để gửi xuống PX4.
* Baseline Python vẫn còn chạy được bằng parameter.

---

# 10. Phase 5 — End-to-End Demo, Verification và Packaging

## Timebox

40 phút.

## Demo flow

```text
make demo-cpp
```

hoặc một script tương đương phải:

1. Kiểm tra X11.
2. Khởi động container.
3. Source ROS 2.
4. Source workspace.
5. Khởi động PX4/Gazebo.
6. Chờ simulation ready.
7. Chờ camera topic.
8. Khởi động detector.
9. Khởi động viewer.
10. Khởi động C++ PID.
11. Khởi động Mission Commander external mode.
12. Ghi log.
13. Có timeout và cleanup.

## Các command bắt buộc

```text
make build
make test
make demo-python
make demo-cpp
make verify
make stop
```

## Verification script

`verify_halfday.sh` phải kiểm tra:

* Docker image.
* ROS imports.
* OpenCV ArUco.
* MAVSDK Python.
* PX4 build.
* colcon build.
* C++ unit tests.
* Python mock tests.
* Camera topic.
* ArUco topic.
* C++ cmd_vel topic.
* Mission status topic.

Mỗi gate phải có:

```text
PASS
FAIL
BLOCKED
NOT_RUN
```

## Artifact tối thiểu

```text
artifacts/logs/docker_build.log
artifacts/logs/colcon_build.log
artifacts/logs/python_tests.log
artifacts/logs/cpp_tests.log
artifacts/logs/demo_python.log
artifacts/logs/demo_cpp.log
artifacts/metrics/run_summary.json
```

## README tối thiểu

* Project overview.
* Upstream attribution.
* Architecture diagram.
* Tech stack.
* Build instructions.
* Demo instructions.
* Test instructions.
* Control mode comparison.
* Known limitations.
* Safety statement.
* Không có real-drone validation.

## Gate P5 — Final Definition of Done

Dự án hoàn thành MVP khi:

* `make build` PASS.
* `make test` PASS.
* Gazebo và OpenCV window cùng hiển thị.
* Marker có overlay.
* Drone takeoff.
* Drone chuyển Offboard.
* Drone tìm marker.
* C++ PID điều khiển XY.
* Drone căn chỉnh.
* Drone descend và land.
* Log chứng minh `CONTROL: C++ PID`.
* Python fallback vẫn tồn tại.
* Không có tiến trình PX4/Gazebo treo sau cleanup.

---

# 11. Quy tắc timebox và fallback

## Không dành quá 20 phút cho một blocker đơn lẻ

Nếu quá thời gian:

1. Ghi blocker.
2. Dùng fallback nhỏ nhất.
3. Tiếp tục tới gate tiếp theo.
4. Không refactor rộng.

## GPU blocker

Dùng CPU/software render. Không cài CUDA toolkit trong buổi MVP.

## MAVSDK C++ blocker

Không triển khai trong MVP. Giữ Python MAVSDK.

## PX4 version blocker

Chọn ref tương thích với `gz_x500_mono_cam_down`, sau đó pin exact SHA.

## Camera topic blocker

Dùng `gz topic -l` và `ros2 topic list` để tìm topic thật, sau đó remap bằng config.

## C++ PID instability

Quay về shadow mode, giữ Python baseline hoạt động, sửa sign/mapping trước khi cấp quyền điều khiển.

## Landing instability

Giảm:

* `kp`;
* max velocity;
* descent speed.

Tăng:

* deadband;
* hold time trước descent.

Không thêm thuật toán mới trong nửa ngày.

---

# 12. Những điều agent không được làm

* Không viết lại repo từ đầu.
* Không thay ArUco bằng AprilTag.
* Không đổi simulator khi chưa chứng minh cần thiết.
* Không refactor toàn bộ Mission Commander.
* Không bắt buộc MAVSDK C++ trong MVP.
* Không compile OpenCV CUDA.
* Không tạo custom ROS interface không cần thiết.
* Không dùng QGroundControl làm dependency bắt buộc.
* Không xóa fallback Python.
* Không tuyên bố PASS dựa trên file tồn tại.
* Không arm trước khi camera và MAVSDK readiness được xác minh.
* Không chạy flight test không timeout.
* Không dùng `xhost +`.
* Không để container ghi file root-owned.
* Không để script chạy vô hạn.