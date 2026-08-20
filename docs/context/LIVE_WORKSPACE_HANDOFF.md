# Live Workspace Handoff

Updated: 2026-08-20 (Asia/Ho_Chi_Minh)

## Current product

The current project is a hand-gesture-guided UAV simulation with autonomous
ArUco precision landing on a moving platform. The former standalone vehicle
perception research workspace has been retired from the current tree.

## Accepted robotics baseline

- fixed C++ PID landing: accepted;
- moving-platform ArUco landing: accepted as the autonomous baseline to
  preserve;
- Mission Commander remains the sole MAVSDK/PX4 command owner;
- moving-platform pose, motion and touchdown contact come from Gazebo;
- dashboard, metrics, platform stop, disarm and mission completion are part of
  runtime acceptance.

Robotics source was not modified during the Slice 5 freeze/removal closure.

## Accepted Slice 5 perception

- authoritative samples: `2,786` after bounded QA remediation;
- preprocessing: frozen wrist/palm canonical 63D landmarks;
- classifier: `63→128→64→7`, 16,903 parameters;
- generalization evidence: grouped cross-hand 2-fold CV;
- final production model: trained once on all authoritative samples for
  deployment, not a new generalization metric;
- runtime: MediaPipe CPU → ONNX Runtime CPU → confidence → deterministic
  `AUTO_LAND` thumb veto → gesture or `NO_COMMAND`;
- full all-sample export parity and live seven-gesture smoke: PASS;
- no-hand stale-command violations: `0`;
- gesture perception currently publishes no ROS/UAV commands.

## Local artifact policy

The dataset, `gesture/.venv`, MediaPipe task model, final PyTorch/ONNX binaries
and generated experiment evidence remain local and ignored. Source/config/tests
are tracked. Exact hashes are in
`docs/context/SLICE_5_GESTURE_PERCEPTION_FREEZE.md`.

## Working-tree caution

The following pre-existing paths are not part of the Slice 5 freeze and must
remain unstaged unless reviewed separately:

- `docs/plans/SLICE_1_IMPLEMENTATION_PLAN.md`;
- `drone_landing_ws/src/px4_vision_autonomy/debug_frame.png`;
- `drone_landing_ws/src/px4_vision_autonomy/scripts/capture_frame.py`;
- `drone_landing_ws/src/px4_vision_autonomy/scripts/smoke_plugin.py`.

## Next action

Open the bounded Gesture → UAV Control implementation while preserving the
accepted Mission Commander ownership and autonomous landing behavior.
