# WALKTHROUGH

## 1. Project Objective
This prototype demonstrates a highly-reproducible, Docker-based PX4 SITL drone performing a precision landing on an ArUco marker using a native C++ PID controller and Python mission orchestration.

## 2. Runtime Architecture
The system employs a hybrid architecture:
- **C++ PID Node**: Consumes signed center errors from the OpenCV ArUco detector and computes XY velocity commands.
- **Python Mission Commander**: Manages the overarching state machine via MAVSDK, orchestrating the takeoff, navigation, Z-descent, and final landing logic.

## 3. Two-Window User Experience
When running the simulation, the user sees:
- **Window 1 (Gazebo Harmonic)**: 3D hardware-accelerated rendering of the drone, the world, and the visual marker.
- **Window 2 (OpenCV)**: A live downward-camera feed overlaying the marker bounding box, signed dx/dy errors, calculated velocity commands, and the current active controller.

## 4. Mission Sequence
The drone follows a strict sequence:
1. `ARM`
2. `TAKEOFF`
3. `OFFBOARD`
4. `NAVIGATE` (fly to marker GPS location)
5. `SCAN` (search for marker)
6. `ALIGN` (C++ PID logic activates)
7. `DESCEND` (descent while aligning)
8. `LAND`
9. `DISARMED`
10. `MISSION COMPLETE`

## 5. Python Baseline Role
The Python baseline acts as the original Golden reference. It remains in the source code as a fallback and for exact behavior comparison during shadow testing.

## 6. C++ PID Transition
The C++ PID logic exactly replicates the Python logic, adding performance and robustness (deadband, saturation, integral clamping, NaN/Inf protection).

## 7. Shadow Validation
Before integrating the C++ controller, a Shadow Mode ran it in parallel with the Python baseline, silently comparing outputs. We observed a 100% sign match and identical deadband handling (see [REPORT_C2](REPORT_C2.md)).

## 8. Repeatability Result
The C++ controller completed 3 consecutive successful landings in pre-polish configuration, followed by a final post-polish verification run without regressions (see [REPORT_C3](REPORT_C3.md)).

## 9. Final Termination Behavior
Upon touchdown, the Mission Commander explicitly waits for PX4 telemetry to broadcast a disarmed state before declaring the mission complete and triggering automatic Docker cleanup (see [FINAL_TERMINATION_REPORT](FINAL_TERMINATION_REPORT.md)).

## 10. How to Run
To run the primary C++ demo:
```bash
make demo-cpp
```
To run the fallback Python baseline:
```bash
make demo-python
```

## 11. What Is and Is Not Verified
- **Verified**: PX4 SITL flight, marker detection, XY alignment, safe touchdown, automated cleanup.
- **Not Verified**: Second-host reproducibility (Phase N), real-world wind/lighting conditions, real hardware deployment.

## 12. Known Limitations
- SITL simulation only.
- Relies on pre-configured waypoint and specific marker ID.
- Root project license NOT_SELECTED.
