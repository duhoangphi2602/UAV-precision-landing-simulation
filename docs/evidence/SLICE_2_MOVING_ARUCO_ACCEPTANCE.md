# Slice 2 Acceptance: Moving ArUco Platform

## Objective
Thực hiện hạ cánh chính xác (precision landing) lên nền tảng ArUco di chuyển một chiều (0.10 m/s), sử dụng lại 100% Typed ROS 2, C++ PID, Dashboard, và Metrics từ Slice 1.

## Result
**PLUGIN-ONLY MOTION SMOKE: PASS**
**FULL-DEMO PHYSICAL MOTION: PASS**
- Start Y (ENU): -0.75 m
- Moving speed command: 0.10 m/s
- Evidence of measured motion:
  `[INFO] [moving_platform_controller]: PLATFORM_COMMAND mission_state=4 latched=True cmd_enu_y=0.10 measured_enu_y=5.87 measured_speed=0.20`
**LANDING RESULT: PRECISION_FAIL**
**SLICE 2 FINAL STATUS: PRECISION_FAIL**

### Issue Details
- **Tracking-only PASS**: Verified with `flip_x=true, flip_y=true`, drone follows platform smoothly.
- **Previous full run**: Physically touched platform but failed termination (bounced).
- **Current Run (Touchdown Latch Implementation)**: 
  - **Touchdown signal source**: MAVSDK `telemetry.in_air()` and `telemetry.landed_state()`.
  - **Touchdown latch evidence**: Implemented `touchdown_latched` logic that overrides all vision states.
  - **Platform stop latency**: Configured to stop immediately upon `STATE_LAND`.
  - **No relaunch after touchdown**: Prevented by latch.
  - **Final termination result**: **PRECISION_FAIL**. The drone descended to `0.66 m` relative altitude (approx 0.24m above the pad), but the `30px` error threshold was breached because pixel resolution is extremely high at close range, while physical error was still small. 
  - Since `touchdown_latched == false` (it had not touched the pad yet), the strict `30px` threshold correctly forced a re-alignment. Because of the narrow FOV at `0.66m`, the marker was immediately lost, resulting in the drone aborting the landing before the touchdown latch could be engaged.
