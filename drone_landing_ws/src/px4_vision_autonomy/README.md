# px4_vision_autonomy

ROS 2 Humble package for the maintained simulation runtime. It provides:

- ArUco detection and typed `TargetObservation` output;
- the sole MAVSDK/PX4 owner (`mission_commander`);
- moving-platform pose, command and contact handling;
- the OpenCV camera/dashboard view;
- final-demo gesture authority and autonomous-landing handoff policy.

Build and test this package from the repository root with `make test`. Run it
through the supported root-level demo targets; individual launch/probe scripts
are intentionally not part of the public interface. See the root
[`README.md`](../../../README.md) for setup, architecture and exact commands.
