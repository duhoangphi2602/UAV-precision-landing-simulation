# UAV Precision Landing Simulation

This repository contains a full ROS 2 and PX4 SITL (Gazebo Harmonic) simulation for a UAV performing autonomous precision landing using an ArUco marker.

## Features

- **ROS 2 Humble**: Integrates with PX4 using microRTPS/microXRCE-DDS.
- **Gazebo Harmonic**: Modern hardware-accelerated 3D simulation environment.
- **ArUco Marker Detection**: A downward-facing camera on the UAV streams images to an OpenCV-based ArUco detector node to identify and track `ID 0`.
- **Golden C++ PID Controller**: A highly robust, production-ready C++ node for precision landing with deadband, anti-windup, saturation, and stale observation protection.
- **Mission Commander**: A state machine that orchestrates the mission (`ARM` -> `TAKEOFF` -> `NAVIGATE` -> `SCAN` -> `ALIGN` -> `DESCEND` -> `LAND`), capable of interfacing with either the Python baseline or the C++ PID.
- **GPU Acceleration**: Supports NVIDIA GPU pass-through to Docker containers for real-time physics and OpenCV hardware rendering.

## Prerequisites

- Docker
- Docker Compose v2
- NVIDIA Drivers
- NVIDIA Container Toolkit (Mandatory for GPU support in Gazebo / OpenCV rendering)

## Quick Start

You can run the precision landing simulation using the provided Makefile. This builds the Docker images and launches the entire simulation pipeline.

### Golden C++ Precision Landing (Recommended)
This uses the robust C++ PID controller for alignment and landing:
```bash
make demo-cpp
```

### Python Baseline
This uses the Python-based controller (useful for comparison or rapid prototyping):
```bash
make demo-python
```

### What this does:
1. Starts `px4_sitl` running PX4 and Gazebo Harmonic.
2. Starts `ros_bridge` to connect PX4's internal DDS topics to ROS 2.
3. Starts `aruco` detector processing the camera feed.
4. Starts `viewer` rendering an OpenCV debug window to your host display.
5. Starts the controllers (`cpp_control` or Python internal PID).
6. Starts `mission_commander`, orchestrating takeoff, navigation, alignment, and landing.

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

## Attribution

This project is built upon the foundational work from the `px4_vision_autonomy` package. 
We have significantly refactored and expanded the original source to incorporate a Golden C++ PID controller, Gazebo Harmonic integration, NVIDIA GPU containerization, automated multi-node orchestration, and advanced state machine safety checks.

The original codebase was provided under the MIT License by its respective authors.
