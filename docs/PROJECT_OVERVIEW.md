# Project Overview

## Product direction

The project is a simulation-first demonstration of a hand-gesture-guided UAV
that can transition into autonomous precision landing on a moving ArUco
platform. It is composed of two accepted subsystems and one pending integration
boundary.

```text
Operator webcam
  → gesture perception
  → guarded mission request                  (integration pending)
  → Mission Commander, sole MAVSDK owner
  → PX4 SITL / Gazebo
  → downward camera / ArUco tracking
  → C++ PID alignment and descent
  → Gazebo contact / platform stop / disarm
```

## Gesture subsystem

MediaPipe produces 21 three-dimensional landmarks. The frozen preprocessing
centres at the wrist, scales by the palm, canonicalizes handedness and rotates
the palm axis before flattening to 63 values. A `63→128→64→7` MLP runs through
ONNX Runtime on CPU. `AUTO_LAND` additionally requires deterministic extended
thumb geometry; a contradictory prediction becomes `NO_COMMAND` rather than
being relabelled.

The production runtime has no PyTorch dependency. PyTorch remains a training
and offline parity dependency only.

## Landing subsystem

Gazebo supplies vehicle dynamics, the downward camera, moving-platform pose and
contact. ROS 2 carries typed observations, controller commands, platform state
and mission status. The C++ controller owns XY PID calculations. Mission
Commander owns mission state, MAVSDK, altitude/descent policy and all commands
sent to PX4.

The accepted moving-platform demo requires measured platform motion, valid
ArUco tracking, C++ PID follow/alignment, descent, Gazebo contact, platform
stop, disarm and mission completion.

## Integration boundary

The next slice will map effective gesture outputs to guarded mission requests.
It must preserve these invariants:

- perception never talks directly to PX4 or MAVSDK;
- no hand, stale inference and vetoed landing requests are non-actionable;
- `AUTO_LAND` requires both the thumb topology gate and valid mission state;
- autonomous landing continues to use ArUco and the accepted control stack;
- Mission Commander remains the sole flight-command owner.

## Accepted evidence

- autonomous fixed and moving-platform landing baselines: accepted before the
  product pivot;
- gesture grouped cross-hand CV mean macro F1: approximately `0.8703` raw;
- safety-filtered command macro F1: approximately `0.8842`;
- all-data PyTorch model and dynamic-batch ONNX export: load/parity PASS;
- full 2,786-sample PyTorch/ONNX argmax agreement: `1.0`;
- live gesture smoke: seven gestures, no-hand, transition and thumb veto PASS;
- live rate: approximately `17.13 FPS` without concurrent Gazebo acceptance.

## Artifact policy

Track source, configuration, contracts, tests and maintained documentation.
Keep datasets, virtual environments, MediaPipe binaries, trained checkpoints,
ONNX binaries and generated reports local under ignored paths. The exact local
deployment hashes are recorded in the Slice 5 freeze manifest.
