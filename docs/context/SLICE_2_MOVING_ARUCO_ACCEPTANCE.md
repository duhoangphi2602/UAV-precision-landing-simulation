# Slice 2 Acceptance: Moving ArUco Platform

## Objective
Thực hiện hạ cánh chính xác (precision landing) lên nền tảng ArUco di chuyển một chiều (0.10 m/s), sử dụng lại 100% Typed ROS 2, C++ PID, Dashboard, và Metrics từ Slice 1.

## Result
**STATUS: PASS**

### Moving Landing
- Entrypoint: `make demo-moving-aruco`
- Chế độ (`mission_mode`): `moving`
- Tracking: C++ PID (legacy parameters từ Slice 1). 
- Descent Safety Gates: 
  - `ALIGN` -> `DESCEND`: Center error <= 25 px
  - `DESCEND` -> `ALIGN`: Center error > 30 px for 2 consecutive valid observations
  - Re-align đếm số lần fallback.
- Platform: Di chuyển với vận tốc 0.10 m/s (ENU Y). Được điều khiển bởi Gazebo `VelocityControl`. State phát qua `/precision_landing/platform_state` ở 10Hz. Latching logic cho terminal state.
- **Metric Report (Moving)**:
  - Final Error (px): ~89.08 px (thể hiện tracking lag do không có feed-forward, đúng kỳ vọng)
  - Horizontal Touchdown Error (m): ~0.067 m (Hoàn toàn thành công nằm trong marker)
  - Re-align Count: 1
  - Đánh giá: Mission Completed, Touchdown Detected, Precision Verified.

### Fixed Landing Regression (Smoke Test)
- Entrypoint: `make demo-cpp`
- Chế độ (`mission_mode`): `fixed`
- **Metric Report (Fixed)**:
  - Final Error (px): ~85.8 px
  - Horizontal Touchdown Error (m): ~0.025 m
  - Đánh giá: PASS, không bị ảnh hưởng.

## Documentation
- `MovingPlatformState.msg` đã được tạo để truyền trạng thái (đã chuyển đổi ENU->NED).
- Dashboard tự động hiển thị `MODE: MOVING`, `PLATFORM: MOVING (0.10 m/s)`, và đếm số lần Re-Align.
- `mission_commander.py` đọc cấu hình `mission_mode` để lấy thông tin toạ độ động cho pad_N và pad_E.
- Không áp dụng YOLO, TensorRT, Feed-Forward, hay Kalman Filter theo đúng quy định chống scope creep.
