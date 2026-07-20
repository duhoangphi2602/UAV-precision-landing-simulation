# UAV Precision Landing Simulation

A fully containerised simulation of **vision-based precision landing** for a PX4
quadrotor using an ArUco marker, ROS 2 Humble, Gazebo Harmonic and MAVSDK.

![ROS2](https://img.shields.io/badge/ROS2-Humble-blue)
![Gazebo](https://img.shields.io/badge/Gazebo-Harmonic-orange)
![PX4](https://img.shields.io/badge/PX4-Autopilot-green)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Overview

The drone takes off, navigates to a pre-defined waypoint, detects a ground-level
**ArUco marker** (DICT_4X4_50, ID 0) through a downward-facing monocular camera,
aligns itself above the marker using visual-servoing, and descends for a
precision landing — all in offboard mode without manual intervention.

### Key Features

- **One-command demo** — `make demo-python` brings up PX4 SITL, Gazebo, the ROS 2
  perception stack and the mission commander inside Docker containers.
- **No GPU required** — software rendering via OGRE 2 (CPU) out of the box.
- **Modular architecture** — detector, controller and mission logic are separate
  ROS 2 nodes that communicate through standard topics.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Docker container  (osrf/ros:humble-desktop)             │
│                                                          │
│  ┌─────────────┐   ┌────────────┐   ┌────────────────┐  │
│  │  PX4 SITL   │◄──│  Gazebo    │──►│ ROS-GZ Bridge  │  │
│  │  (x500 mono │   │  Harmonic  │   │ (image_bridge) │  │
│  │   cam down) │   │            │   └───────┬────────┘  │
│  └──────┬──────┘   └────────────┘           │           │
│         │ MAVLink (UDP 14540)        /camera│           │
│         ▼                                   ▼           │
│  ┌──────────────┐                  ┌────────────────┐   │
│  │   Mission    │                  │ ArUco Detector │   │
│  │  Commander   │◄─── /aruco/pose ─│ (cv2.aruco)    │   │
│  │  (MAVSDK)    │                  └────────────────┘   │
│  └──────────────┘                                       │
└──────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Dependency       | Version          |
| ---------------- | ---------------- |
| Docker Engine    | ≥ 24.0           |
| Docker Compose   | ≥ 2.20 (v2 CLI) |
| X11 server       | any (for GUI)    |
| OS               | Ubuntu 22.04+    |

> **Note:** A dedicated GPU is **not** required. The simulation uses
> `LIBGL_ALWAYS_SOFTWARE=1` for CPU-based rendering.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/duhoangphi2602/UAV-precision-landing-simulation.git
cd UAV-precision-landing-simulation

# 2. Build the Docker image (first time only, ~15-20 min)
make build

# 3. Run the Python baseline demo
make demo-python

# 4. Stop all containers
make stop
```

---

## Project Structure

```
.
├── Dockerfile                        # Multi-stage Docker image (ROS 2 + Gazebo + PX4)
├── docker-compose.yml                # Container orchestration
├── Makefile                          # Top-level commands
├── scripts/
│   ├── run_demo_python_baseline.sh   # Python baseline entry-point
│   ├── run_demo_cpp_control.sh       # C++ controller variant
│   ├── run_camera_only_gate.sh       # Camera-only sanity check
│   ├── build_workspace.sh            # colcon build inside container
│   ├── stop_demo.sh                  # docker compose down
│   └── allow_x11.sh                  # xhost permissions
├── docker/
│   └── entrypoint.sh                 # Container entrypoint (sources ROS 2)
├── drone_landing_ws/
│   └── src/
│       └── px4_vision_autonomy/      # Main ROS 2 package
│           ├── px4_vision_autonomy/
│           │   └── nodes/
│           │       ├── aruco_detector.py       # ArUco detection node
│           │       ├── mission_commander.py    # MAVSDK mission logic
│           │       └── camera_viewer.py        # Debug camera viewer
│           ├── models/
│           │   └── aruco_landing_pad/          # Gazebo marker model
│           │       ├── model.sdf
│           │       ├── model.config
│           │       └── aruco_marker_0.png
│           ├── worlds/
│           │   └── inspection.sdf              # Custom Gazebo world
│           ├── config/
│           │   └── params.yaml
│           └── setup.py
└── tests/                            # Unit / integration tests
```

---

## Makefile Targets

| Command           | Description                                       |
| ----------------- | ------------------------------------------------- |
| `make build`      | Build the ROS 2 workspace inside Docker           |
| `make demo-python`| Run the full Python baseline mission               |
| `make demo-cpp`   | Run the C++ controller variant                     |
| `make stop`       | Stop and remove all running containers             |
| `make verify`     | Run verification / integration checks              |

---

## ROS 2 Nodes

### `aruco_detector`

Subscribes to `/camera`, detects ArUco markers (DICT_4X4_50) using OpenCV, and
publishes the marker pose.

| Interface   | Topic              | Type                            |
| ----------- | ------------------ | ------------------------------- |
| Subscribes  | `/camera`          | `sensor_msgs/msg/Image`         |
| Publishes   | `/aruco/pose`      | `geometry_msgs/msg/PoseStamped` |

### `mission_commander`

Autonomous mission sequencer using MAVSDK. Handles arm → takeoff → navigate →
search → align → descend → land.

| Interface   | Topic              | Type                            |
| ----------- | ------------------ | ------------------------------- |
| Subscribes  | `/aruco/pose`      | `geometry_msgs/msg/PoseStamped` |
| Control     | PX4 via MAVLink    | UDP `14540`                     |

### `camera_viewer`

Debug GUI that displays the raw camera feed.

| Interface   | Topic              | Type                            |
| ----------- | ------------------ | ------------------------------- |
| Subscribes  | `/camera`          | `sensor_msgs/msg/Image`         |

---

## Simulation World

The **inspection** world (`worlds/inspection.sdf`) contains:

- **Ground plane** — 500 × 500 m, earthy beige, low specular
- **ArUco landing pad** — 0.5 × 0.5 m, placed at ENU (5.8, 0, 0.011)
- **Directional sun light**
- **Spherical coordinates** — WGS84, ENU frame (Zurich reference point)

The drone model `x500_mono_cam_down` features a downward-facing monocular camera
(`640 × 480`, 1.047 rad HFOV).

---

## Mission Sequence

1. **Startup** — PX4 SITL launches with the `gz_x500_mono_cam_down` airframe.
2. **Health check** — Script waits for Gazebo camera topic, ROS bridge, and
   ArUco detector to be alive.
3. **Arm & Takeoff** — MAVSDK arms the vehicle and takes off to 3 m AGL.
4. **Navigate to waypoint** — Offboard velocity commands fly the drone towards
   the marker area (NED: north ≈ 0, east ≈ 5.8).
5. **Search & detect** — Drone searches for ArUco ID 0 in the camera feed.
6. **Align** — Visual-servoing centers the drone above the marker.
7. **Descend & land** — Controlled descent until landing is detected.

---

## Configuration

Edit `drone_landing_ws/src/px4_vision_autonomy/config/params.yaml`:

```yaml
aruco_detector:
  ros__parameters:
    marker_size: 0.5          # physical marker size in metres
    marker_id: 0              # expected ArUco ID
    dictionary: DICT_4X4_50   # OpenCV ArUco dictionary

mission_commander:
  ros__parameters:
    takeoff_altitude: 3.0
    control_source: internal_python
```

---

## Troubleshooting

| Symptom                                  | Fix                                                       |
| ---------------------------------------- | --------------------------------------------------------- |
| `No valid data from Accel 0`             | PX4 is still initialising — wait 30–60 s                  |
| Camera topic 0 Hz                        | Check `Sensors` plugin has `<render_engine>ogre2</render_engine>` |
| ArUco not detected                       | Verify marker material has `metalness=0`, `roughness=1`   |
| `LIBGL error: failed to open /dev/dri`   | Expected on CPU — safe to ignore                          |
| Container name conflict                  | Run `make stop` then retry                                |

---

## License

This project is released under the **MIT License**. See
[LICENSE](drone_landing_ws/src/px4_vision_autonomy/LICENSE) for details.
