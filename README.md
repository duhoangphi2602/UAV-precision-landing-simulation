# UAV Precision Landing Simulation

This repository contains a full ROS 2 and PX4 SITL (Gazebo Harmonic) simulation for a UAV performing autonomous precision landing using an ArUco marker.

## Features

- **ROS 2 Humble**: Integrates with PX4 using microRTPS/microXRCE-DDS.
- **Gazebo Harmonic**: Modern hardware-accelerated 3D simulation environment.
- **ArUco Marker Detection**: A downward-facing camera on the UAV streams images to an OpenCV-based ArUco detector node to identify and track `ID 0`.
- **Mission Commander**: A Python-based state machine that orchestrates the mission: `ARM` -> `TAKEOFF` -> `NAVIGATE` -> `SCAN` -> `ALIGN` -> `DESCEND` -> `LAND`.
- **GPU Acceleration**: Supports NVIDIA GPU pass-through to the Docker containers for real-time physics and rendering performance.

## Prerequisites

- Docker
- Docker Compose v2
- NVIDIA Container Toolkit (for GPU support)
- NVIDIA Drivers

## Quick Start

You can run the full baseline demo using the provided Makefile. This will build the necessary Docker images (if not already built) and launch the entire simulation pipeline.

```bash
make demo-python
```

### What this does:
1. Starts the `px4_sitl` container running PX4 and Gazebo.
2. Starts the `ros_bridge` container to connect PX4's internal DDS topics to the ROS 2 space.
3. Starts the `aruco` detector container, processing the camera feed.
4. Starts the `viewer` container, rendering an OpenCV debug window to your host display showing the camera feed, detected marker, bounding box, offsets, and mission state.
5. Starts the `mission_commander` node, which initiates takeoff, navigates to the marker area, aligns itself with the marker, and descends to a safe landing.

## Project Structure

- `docker-compose.yml`: Defines the microservice architecture for the simulation components.
- `drone_landing_ws/`: ROS 2 workspace containing the `px4_vision_autonomy` package (ArUco detector and Mission Commander nodes).
- `scripts/`: Shell scripts for orchestrating the demo and configuring the environment.
- `Makefile`: Convenient entrypoints for building, cleaning, and running the simulation.

## Debugging

If you want to run only the static camera/vision pipeline without flying the drone (to test camera and detector functionality):

```bash
./scripts/run_test_gui.sh
```

## Troubleshooting

- **No GUI / OpenCV Window not showing**: Make sure your `xhost` permissions are set correctly. The `run_demo_python_baseline.sh` script attempts to set `xhost +local:root` automatically.
- **Slow Performance**: Ensure you have configured Docker to use your NVIDIA GPU correctly (`docker run --rm --gpus all nvidia/cuda:12.9.0-base-ubuntu22.04 nvidia-smi`).
