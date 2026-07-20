# Upstream Baseline Audit

## Upstream Repository
- **URL**: https://github.com/Tinny-Robot/px4_vision_autonomy
- **Exact Commit SHA**: `62e5b6222043c90a49ed3aca58f039c8980528e1`
- **PX4 Pinned Commit**: `TBD`

## README Claims vs. Actual Source
| Claim in README | Actual Source | Mismatch Found | Action Taken |
| :--- | :--- | :--- | :--- |
| Mentions `vision_controller` and `mavsdk_bridge` nodes. | `setup.py` lists `aruco_detector`, `camera_viewer`, and `mission_commander`. | Yes. The P-controller and MAVSDK logic are combined in `mission_commander.py`. | Document the mismatch. Use `mission_commander.py` as the orchestrator and add `control_source` param to switch between its internal Python PID and our external C++ PID. |
| Mentions Gazebo Classic or Garden/Harmonic. | Relies on `gz_x500_mono_cam_down`. | Gazebo version depends on PX4. | Use Gazebo Harmonic (GZ) with a compatible PX4 version since the user specified Gazebo Harmonic in Docker env. |

