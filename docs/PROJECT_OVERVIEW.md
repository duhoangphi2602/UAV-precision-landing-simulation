# HỒ SƠ KIẾN TRÚC & TỔNG QUAN DỰ ÁN
**UAV Precision Landing Simulation (Hạ cánh chính xác bằng Thị giác máy tính)**

---

## 1. GIỚI THIỆU CHUNG (INTRODUCTION)

**UAV Precision Landing Simulation** là một hệ thống phần mềm mô phỏng toàn diện (Software-in-the-Loop / SITL) dành cho phương tiện bay không người lái (UAV/Drone). Dự án này được thiết kế và mở rộng dựa trên nền tảng cốt lõi của **PX4-Autopilot** và các hệ sinh thái **ROS 2 Offboard control**.

Mục tiêu cốt lõi của dự án là thiết kế một hệ thống tự trị hoàn toàn, cho phép drone cất cánh, bay đến một khu vực chỉ định, sử dụng camera gắn dưới bụng (downward-facing camera) để quét tìm bãi đáp (được đánh dấu bằng mã ArUco), tự động căn chỉnh vị trí (align) và hạ cánh chính xác xuống tâm bãi đáp đó.

Dự án này được thiết kế theo **chuẩn công nghiệp** và kiến trúc **Microservices** của robot, sử dụng các công nghệ tiên tiến nhất như ROS 2, PX4 Autopilot và Gazebo. Nhờ kiến trúc cô lập bằng Docker, toàn bộ thuật toán điều khiển và thị giác máy tính có thể được chuyển thẳng từ môi trường mô phỏng sang phần cứng thực tế (Companion Computer như Raspberry Pi) mà không cần thay đổi cấu trúc code.

---

## 2. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Hệ thống được chia thành 3 mảng chính: **Mô phỏng (Simulation)**, **Giao tiếp (Bridge)**, và **Điều khiển (ROS 2 Nodes)**. Tất cả được đóng gói và cô lập trong các Docker containers.

```mermaid
graph TD
    subgraph "Mô phỏng (Gazebo & PX4 SITL)"
        GZ[Gazebo Harmonic\nMôi trường vật lý 3D & Cảm biến]
        PX4[PX4 Autopilot\nThuật toán bay cấp thấp]
        GZ <-->|gz-bridge| PX4
    end

    subgraph "Giao tiếp (ROS 2 Bridge)"
        XRCE[Micro XRCE-DDS Agent]
        ROS_BRIDGE[ros_gz_image\nImage Bridge]
        PX4 <-->|uORB messages| XRCE
        GZ -->|Camera Stream| ROS_BRIDGE
    end

    subgraph "ROS 2 Workspace (Thuật toán bậc cao)"
        CV[ArUco Detector Node\n(Python/OpenCV)]
        PID[Precision Control Node\n(C++ rclcpp)]
        MC[Mission Commander Node\n(Python rclpy)]
        VIEW[Camera Viewer Node\n(Debug UI)]
        
        ROS_BRIDGE -->|/camera/image_raw| CV
        ROS_BRIDGE -->|/camera/image_raw| VIEW
        CV -->|/landing_pad_pose\n(err_x, err_y)| PID
        XRCE <-->|/fmu/in/*\n/fmu/out/*| PID
        XRCE <-->|Telemetry & State| MC
        MC -->|Trạng thái Mission| PID
    end
```

---

## 3. CHI TIẾT CÁC THÀNH PHẦN CỐT LÕI (CORE COMPONENTS)

### 3.1. Firmware & Simulation (Cấp thấp)
*   **PX4 Autopilot (SITL):** Firmware điều khiển bay thực tế, chịu trách nhiệm cho các tác vụ bay cơ bản (giữ thăng bằng, quay motor, định vị GPS, IMU).
*   **Gazebo:** Engine vật lý mô phỏng trọng lực, quán tính, ánh sáng và dữ liệu cảm biến (camera, GPS).

### 3.2. Thuật toán Xử lý ảnh (Computer Vision)
*   **`aruco_detector` (Python):** Bắt luồng ảnh (Image stream) từ camera mô phỏng. Sử dụng thư viện OpenCV để phát hiện mã ArUco. Nếu tìm thấy mã, nó tính toán độ lệch tâm (err_x, err_y) của mã so với tâm camera và xuất (publish) ra topic `/landing_pad_pose`.

### 3.3. Thuật toán Điều khiển (Control Logic)
Hệ thống sử dụng một kiến trúc **Lai (Hybrid Control Pipeline)** kết hợp giữa C++ và Python. Sự phối hợp này là bắt buộc và hai node này liên tục giao tiếp với nhau qua ROS 2 (chúng không phải là 2 tiến trình chạy song song độc lập).

*   **`precision_landing_control_cpp` (C++):** Đóng vai trò là "Bộ não tính toán" trong quá trình hạ cánh.
    *   Sử dụng **PID Controllers** (Proportional-Integral-Derivative) độc lập cho hai trục X và Y.
    *   Nhận độ lệch (err_x, err_y) từ camera, tính toán với tần số cao (100Hz+) để ra được vector vận tốc (Velocity Setpoint) giúp kéo drone về đúng tâm bãi đáp.
    *   Gửi (publish) các lệnh vận tốc này sang cho node Python để thực thi.
    *   Tự động tính toán tốc độ giảm độ cao (`descend`) tỷ lệ thuận với mức độ căn chỉnh chính xác.

### 3.4. Quản lý Vòng đời (State Machine & MAVSDK Wrapper)
*   **`mission_commander` (Python):** Đóng vai trò là "Người chỉ huy chiến thuật" và "Cầu nối thực thi lệnh".
    *   **Quản lý State Machine:** Quyết định khi nào drone được Cất cánh, Navigate, Quét tìm, hay Hạ cánh.
    *   **MAVSDK Wrapper:** Đây là node **duy nhất** trực tiếp ra lệnh điều khiển bay (velocity command) xuống PX4 Autopilot.
    *   **Giao tiếp với C++:** Khi drone bước vào trạng thái Căn chỉnh (ALIGN) hoặc Hạ cánh (DESCEND), node Python này sẽ **dừng tính toán** và "mở cổng" (subscribe) nhận các lệnh vận tốc được tính ra từ node C++. Nếu node C++ bị crash hoặc không gửi dữ liệu, node Python sẽ báo lỗi ("C++ command stale") và lập tức hủy bỏ quá trình hạ cánh để đảm bảo an toàn. Tương tự, nếu không có node Python, node C++ sẽ không thể ra lệnh cho drone cất cánh hay gửi tín hiệu xuống PX4.

---

## 4. VÒNG ĐỜI BAY (STATE MACHINE)

Quy trình bay của drone là tự động hoàn toàn và trải qua các trạng thái (states) nghiêm ngặt sau:

1.  **ARM:** Mở khóa các motor. Đợi tín hiệu GPS ổn định.
2.  **TAKEOFF:** Tự động cất cánh lên một độ cao an toàn.
3.  **NAVIGATE:** Chuyển sang chế độ Offboard, bay theo đường thẳng từ điểm cất cánh đến khu vực nghi ngờ có bãi đáp (Inspection Point).
4.  **SCAN:** Dừng lại trên không (Hover) và bật camera tìm kiếm mã ArUco.
5.  **ALIGN:** Khi tìm thấy ArUco, nhường quyền điều khiển cho **C++ PID Controller**. Drone di chuyển ngang (pitch/roll) để đưa tâm bãi đáp vào chính giữa màn hình camera.
6.  **DESCEND:** Khi đã căn giữa, drone vừa giữ vị trí tâm vừa từ từ giảm độ cao. Nếu bị lệch do gió, hệ thống sẽ chững lại để căn giữa trước khi tiếp tục hạ.
7.  **LAND / TOUCHDOWN:** Khi độ cao chạm ngưỡng tối thiểu (ví dụ 0.3m), drone tắt offboard và ra lệnh Land cưỡng bức để chạm đất an toàn.
8.  **DISARMED / MISSION COMPLETE:** Khóa motor, kết thúc nhiệm vụ.

---

## 5. CẤU TRÚC MÃ NGUỒN (PROJECT STRUCTURE)

Dự án được tổ chức rất chặt chẽ, tách biệt rõ ràng giữa Infrastructure (Docker), Scripts (Vận hành) và Source Code (ROS 2 Workspace).

```text
UAV-precision-landing-simulation/
├── docker/                 # File cấu hình Docker (Dockerfile, compose, env) đảm bảo môi trường đồng nhất.
├── docs/                   # Tài liệu dự án, bằng chứng test, và nhật ký kỹ thuật.
├── scripts/                # Các script tự động hóa (chạy demo, dọn dẹp, kiểm tra X11).
└── drone_landing_ws/       # Không gian làm việc của ROS 2 (Chứa toàn bộ Source Code).
    └── src/
        ├── px4_vision_autonomy/        # Cụm package Python (Mission Commander, ArUco, Viewer).
        └── precision_landing_control_cpp/ # Cụm package C++ (PID Controller tốc độ cao & GTest).
```

---

## 6. TECH STACK CHI TIẾT
*   **Hệ điều hành / Container:** Ubuntu 22.04 (Jammy) / Docker Engine.
*   **Middleware:** ROS 2 Humble Hawksbill.
*   **Giao tiếp:** Micro XRCE-DDS (eProsima).
*   **Flight Stack:** PX4 Autopilot (v1.14 hoặc tương đương SITL).
*   **Ngôn ngữ lập trình:** C++17 (Hiệu năng cao), Python 3.10 (Thuật toán linh hoạt).
*   **Thư viện CV:** OpenCV 4.x, cv_bridge.
*   **Build & Test:** CMake, Colcon, Google Test (GTest).

---

> [!NOTE]
> **Tóm lược dành cho Độc giả (Reader Summary):**
> Nhìn vào dự án này, bạn có thể hiểu rằng đây không chỉ là một đoạn script điều khiển drone bay lên và hạ xuống đơn giản. Đây là một hệ thống **Software-in-the-Loop** được thiết kế nguyên khối theo chuẩn công nghiệp, áp dụng Lý thuyết Điều khiển tự động (Control Theory - PID), Thị giác Máy tính (Computer Vision), và Kiến trúc Phân tán (ROS 2). Mọi dòng code ở đây đều sẵn sàng để biên dịch và nạp lên một thiết bị bay thực tế.
