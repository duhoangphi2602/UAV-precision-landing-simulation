# Hand-Gesture-Guided UAV Precision Landing Simulation

This repository combines two accepted, independently validated subsystems:

- a PX4 SITL, Gazebo Harmonic and ROS 2 autonomous precision-landing baseline;
- a CPU-only hand-gesture perception pipeline using MediaPipe landmarks and a
  compact ONNX Runtime classifier.

The intended final demo lets an operator guide the UAV with seven static hand
gestures, then hand control to the existing autonomous landing stack. The
landing stack tracks an ArUco target on a physically moving platform, aligns
with the native C++ PID controller, descends, confirms contact, stops the
platform and waits for telemetry-confirmed disarm.

Gesture-to-mission integration is the next implementation step. The accepted
landing and gesture subsystems remain separate until that safety boundary is
implemented and tested.

## Accepted capabilities

### Autonomous landing

- PX4 SITL and Gazebo Harmonic simulation;
- ROS 2 Humble camera and typed landing interfaces;
- fixed and moving ArUco landing targets;
- C++ XY PID control with deadband, saturation, integral clamping, stale-input
  handling and non-finite input protection;
- Python Mission Commander as the sole MAVSDK/PX4 command owner;
- moving-platform pose, motion and contact evidence from Gazebo;
- touchdown, platform stop, disarm and mission-complete handling;
- OpenCV dashboard and runtime metrics.

Run the accepted landing demos with:

```bash
make demo-cpp
make demo-moving-aruco
```

### Gesture perception

The production perception path is:

```text
webcam
→ MediaPipe Hand Landmarker (CPU)
→ frozen wrist/palm canonical 63D feature
→ ONNX Runtime classifier (CPU)
→ confidence
→ AUTO_LAND thumb-extension veto
→ gesture or NO_COMMAND
```

The frozen gesture vocabulary is:

| Gesture | Static hand topology |
|---|---|
| `HOLD` | Open palm |
| `TAKEOFF` | Four fingers extended, thumb folded |
| `FORWARD` | Index finger extended |
| `BACKWARD` | Index and middle fingers extended |
| `LEFT` | Thumb extended |
| `RIGHT` | Pinky extended |
| `AUTO_LAND` | Thumb and pinky extended |

The accepted live smoke recognized all seven gestures, produced `NO_COMMAND`
when no hand was present, passed pose transitions and exercised the ambiguous
`RIGHT`/`AUTO_LAND` safety veto. The measured live rate was approximately
17.13 FPS, with about 20.23 ms MediaPipe latency and 0.089 ms classifier
latency. See [gesture/README.md](gesture/README.md) for reproducible commands.

## Safety ownership

Gesture perception does not publish ROS flight commands. During the upcoming
integration, gestures will be requests to a guarded mission policy; Mission
Commander will remain the only MAVSDK owner. `NO_COMMAND`, stale perception,
rejected `AUTO_LAND` and invalid mission state must never reuse an actionable
gesture.

## Repository layout

```text
.
├── docker/                  # PX4/Gazebo/ROS container environment
├── drone_landing_ws/        # ROS 2 interfaces, landing control and simulation
├── gesture/                 # Gesture source, contracts, configs and tests
├── scripts/                 # Build, validation and demo entrypoints
├── docs/                    # Maintained architecture and acceptance context
├── docker-compose.yml
└── Makefile
```

Local gesture datasets, environments, model binaries and generated experiment
reports are intentionally ignored. Their accepted hashes and artifact policy
are recorded in
[SLICE_5_GESTURE_PERCEPTION_FREEZE.md](docs/context/SLICE_5_GESTURE_PERCEPTION_FREEZE.md).

## Validation

Bounded source tests:

```bash
gesture/.venv/bin/python -m pytest gesture/tests -q
```

The authoritative model generalization evidence is grouped cross-hand 2-fold
cross-validation. Final all-data training accuracy and numerical export parity
are optimization/deployment evidence, not held-out accuracy.

## Limitations

- simulation only; no real-aircraft validation;
- gesture-to-mission control is not integrated yet;
- concurrent gesture webcam and Gazebo/PX4 performance is not yet accepted;
- gesture dataset v1 contains one left-hand and one right-hand session per
  class from one subject;
- the final landing target remains ArUco ID 0.

## License and notices

The root project license is not yet selected. Upstream attribution and package
licenses are preserved in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
the ROS package license files.
