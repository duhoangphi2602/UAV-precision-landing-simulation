# PRE-PIVOT BASELINE AUDIT

Audit date: 2026-08-20 (Asia/Ho_Chi_Minh)  
Repository: `/home/hoangphi/Projects/UAV-precision-landing-simulation`

## 1. Executive verdict

`PIVOT_READINESS=READY`

`FINAL_AUTONOMOUS_LANDING_BASELINE_TO_PRESERVE=YES`

The fixed and moving autonomous ArUco landing paths are current, end-to-end demonstrated, and ready to preserve. Docker, PX4, Gazebo, ROS 2, typed interfaces, C++ XY control, Mission Commander, touchdown/disarm semantics, the camera-performance correction, compact dashboard, and current metrics all have positive runtime evidence.

The bounded baseline-freeze closure also resolved the remaining repository-quality gates without changing runtime semantics: all six ArUco compatibility tests pass against image OpenCV 4.5.4, all 10 C++ PID GTests pass, all registered package tests pass, and the aggregate result is 41 tests with 0 errors, 0 failures, and 4 skipped checks. The accepted worktree is ready for selective preservation review.

## 2. Current Git / workspace safety state

### Branch and history

- Current branch: `feature/tensorrt-optimization`
- HEAD: `8e3fbd06d1ff493cc1db10143f621e1871e96726`
- No upstream is configured for the current branch.
- Local `main` and `feature/tensorrt-optimization` both point to HEAD.
- Live remote query, performed with `git ls-remote --heads --tags origin` without fetching, returned only:
  - `refs/heads/main` at `1a2b19687eb1ed01f2fcaa3ef9587baa949c26e9`
  - no remote tags
- Relative to the live remote main commit, HEAD is 10 commits ahead and 0 behind.
- The local feature branches have no live remote counterparts.
- Local-only tags:
  - `cpp-pid-baseline-v1`
  - `slice1-engineering-interface-v1`
  - `slice2-moving-aruco-v1`
  - `slice3-vehicle-detector-v1`
  - `slice3c-vehicle-detector-v1`

### Tracked modifications

- `.gitignore`
- `drone_landing_ws/src/precision_landing_control_cpp/CMakeLists.txt`
- `drone_landing_ws/src/precision_landing_control_cpp/include/precision_landing_control_cpp/pid_controller.hpp`
- `drone_landing_ws/src/precision_landing_control_cpp/launch/control_cpp.launch.py`
- `drone_landing_ws/src/precision_landing_control_cpp/src/control_node.cpp`
- `drone_landing_ws/src/precision_landing_control_cpp/src/pid_controller.cpp`
- `drone_landing_ws/src/precision_landing_control_cpp/test/test_pid_controller.cpp`
- `drone_landing_ws/src/px4_vision_autonomy/px4_vision_autonomy/nodes/aruco_detector.py`
- `drone_landing_ws/src/px4_vision_autonomy/px4_vision_autonomy/nodes/camera_viewer.py`
- `drone_landing_ws/src/px4_vision_autonomy/px4_vision_autonomy/nodes/mission_commander.py`
- `drone_landing_ws/src/px4_vision_autonomy/px4_vision_autonomy/nodes/moving_platform_controller.py`
- `drone_landing_ws/src/px4_vision_autonomy/tests/unit/test_aruco_detection.py`
- `scripts/run_demo_cpp_control.sh`
- `tests/test_aruco.py`

The `.gitignore` closure change explicitly rejects the earlier broad `docs/` rule. Maintained documentation and evidence source remain visible to Git; only the three named generated Slice 3 evidence-report paths remain ignored. Runtime `artifacts/` and existing ML datasets, experiments, exports, reports, manifests, environments, and caches remain ignored.

### Untracked source/evidence paths

- `drone_landing_ws/src/px4_vision_autonomy/debug_frame.png`
- `drone_landing_ws/src/px4_vision_autonomy/scripts/capture_frame.py`
- `drone_landing_ws/src/px4_vision_autonomy/scripts/smoke_plugin.py`
- `docs/context/` continuity, handoff, and Slice 2/3/3B/3C historical documents
- `docs/plans/` local planning documents
- `ml/configs/tensorrt_candidate_a_fp32.yaml`
- `ml/scripts/build_tensorrt_engines.py`
- `ml/scripts/fp32_full_parity.py`
- `ml/scripts/fp32_smoke_parity.py`
- `ml/scripts/inspect_onnx.py`
- `ml/scripts/run_candidate_a_ultralytics_test_reference.py`
- `ml/scripts/run_fp32_parity_full_manual.sh`
- `ml/scripts/run_fp32_parity_smoke_manual.sh`
- `ml/scripts/run_fp32_pytorch_metric_selfcheck_manual.sh`
- `ml/scripts/verify_ort_preload.py`
- `ml/scripts/verify_tensorrt_install.py`
- `ml/tensorrt/`

### Ignored heavy/runtime state

- `.venv/`: approximately 13 MB
- `ml/.venv/`: approximately 5.7 GB
- `ml/.venv-tensorrt/`: approximately 10 GB
- `ml/datasets/`: approximately 1.9 GB
- `ml/experiments/`: approximately 60 MB
- `ml/exports/`: approximately 161 MB
- `ml/reports/`: approximately 1 MB
- ROS build/install/log trees: approximately 47 MB combined
- `artifacts/`: current runtime logs, dashboard image, and metrics

The worktree is intentionally dirty and is not yet Git-frozen. Closure did not stage, commit, push, fetch, clean, reset, delete, or modify refs.

## 3. Environment / Docker readiness

`SIMULATION_DOCKER_IMAGE=PASS`

| Item | Current evidence | Status |
|---|---|---|
| Docker client/daemon | Client 29.7.2; server 29.7.2 | READY |
| Docker Compose | v5.4.0 | READY |
| Compose topology | Sole service: `simulation` | READY |
| Resolved service hash | `404280a6a38e3266ac2757414530ec02cfb86dee4c4540366738358f311d5368` | READY |
| Simulation image | `uav-precision-landing-simulation-simulation`, image `sha256:7a475b94bf0c83b1fdccbf8e9109b282f6ee0726951e08317b7213f16c42272b`, 3,916,077,387 bytes | READY |
| Container state | No residual demo/audit containers after inspection | READY |
| Host GPU | NVIDIA GeForce RTX 3060, 12,288 MiB, driver 595.84 | READY |
| NVIDIA runtime | `nvidia-container-runtime` registered; disposable image probe saw the RTX 3060 | READY |
| PX4 | Commit `78a44ed439ee941acd4844ff8ceaedbfe0faea56`; SITL binary present | READY |
| Gazebo | Gazebo Sim 8.15.0 (Harmonic generation) | READY |
| ROS 2 | Humble; `rclpy` import passes | READY |
| Vision/control Python | OpenCV 4.5.4 with ArUco; MAVSDK and NumPy imports pass | READY |
| `ml/.venv` | Python 3.14.4, Torch 2.13.0+cu130, Ultralytics 8.4.108, CUDA visible outside sandbox | READY / HISTORICAL ML |
| `ml/.venv-tensorrt` | Python 3.14.4, Torch 2.13.0+cu130, TensorRT 11.2.1.2, CUDA visible outside sandbox | READY / HISTORICAL ML |

The image used for the final fixed and moving runs was not rebuilt during report closure. The unset `PX4_VERSION` warning in the current Compose environment affects only a future build argument; the existing image contains the required pinned PX4 commit and passed both final demos.

### Build and test evidence

- ROS packages `precision_landing_interfaces`, `precision_landing_control_cpp`, and `px4_vision_autonomy`: build PASS during this audit.
- Post-dashboard targeted `px4_vision_autonomy` build: PASS.
- Relevant shell/Python syntax checks: PASS.
- C++ PID GTests: 10 tests, 0 failures, 0 errors.
- Current aggregate `colcon test-result --verbose`: 41 tests, 0 errors, 0 failures, 4 skipped.
- Current ArUco pytest suites in the simulation image:
  - `tests/test_aruco.py`: 5 passed;
  - `drone_landing_ws/src/px4_vision_autonomy/tests/unit/test_aruco_detection.py`: 1 passed.
  - The tests now use the same old/new ArUco API compatibility principle as the runtime detector.
- Ament copyright, cpplint, flake8, lint-cmake, uncrustify, cppcheck, pep257, and xmllint gates: PASS.

## 4. Baseline / Slice 1

`STATUS=DEMO_READY`

Original objective: fixed ArUco precision landing with typed ROS 2 interfaces, C++ PID control, and an operational dashboard.

Current demonstrated chain:

`camera -> ArUco -> TargetObservation -> C++ XY PID -> ControlCommand -> alignment -> descent -> touchdown -> telemetry-confirmed disarm -> Mission Complete -> clean runner exit`

Final fixed-run evidence:

- active Gazebo camera and valid ArUco acquisition;
- typed target observations and `controller=CPP PID` control;
- alignment and descent completed;
- physical landing completed;
- touchdown confirmed with source `fixed_altitude`;
- touchdown horizontal error: `0.0287772736 m`;
- final-commit duration: `6.012713 s`, without timeout;
- `armed_after_contact=false`, `disarmed=true`, `mission_complete=true`;
- Mission Commander log: `Disarmed. Mission Complete.`;
- C++ control log: terminal landing state received and output stopped;
- dashboard remained alive, wrote a fresh descent screenshot and metrics, and logged no runtime exception;
- runner exited successfully with no post-touchdown relaunch.

Regressions found and corrected during the audit:

1. Invalid low-altitude ArUco observations could force a repeated `DESCEND -> ALIGN` loop. The low-altitude/final-approach handling was corrected and the current end-to-end fixed regression passes.
2. Terminal state handling could permit landing/relaunch behavior after touchdown. Terminal/control-output latching and runner success handling were corrected; the current run lands, disarms, stays terminal, reports Mission Complete, and exits cleanly.

## 5. Slice 2 — Moving Platform

`STATUS=DEMO_READY`

`FINAL_AUTONOMOUS_LANDING_BASELINE_TO_PRESERVE=YES`

The current moving demonstration provides:

- continuous physical platform motion commanded at `0.10 m/s`;
- flight control based on visual ArUco observations only;
- Gazebo platform pose/state used for telemetry and acceptance evidence, not control feedback;
- the moving C++ PID/profile;
- visual follow, descent, and one accepted re-alignment;
- contact-confirmed touchdown from `gazebo_contact`;
- touchdown latch and terminal control stop;
- platform stop command at touchdown;
- graceful real disarm, Mission Complete, no delayed relaunch, and clean exit.

Latest final-run metrics:

| Metric | Value |
|---|---:|
| Mission result | `SUCCESS_PRECISION_UNVERIFIED` in dashboard evidence; Mission Commander result `PASS` |
| Mode | `MOVING` |
| Controller | `CPP PID` |
| Mission duration | 105.5722 s |
| Alignment duration | 54.1900 s |
| Descent duration | 11.8445 s |
| Re-align count | 1 |
| Platform command | 0.1000000 m/s |
| Physical moving duration | 68.0109 s |
| Physical displacement | 6.77498 m |
| Displacement-derived mean speed | 0.0996161 m/s |
| Expected displacement | 6.80109 m |
| Displacement ratio | 0.996161 |
| Platform motion verified | `true` |
| Touchdown source | `gazebo_contact` |
| Touchdown horizontal error | 0.0537754 m |
| Platform stop latency | 0.0 s |
| Armed after contact | `false` |
| Disarmed / mission complete | `true` / `true` |

The log's `final_commit_timeout=true` records the transition that stopped platform/XY motion and entered landing; it did not prevent contact-confirmed touchdown, disarm, Mission Commander PASS, or clean completion.

## 6. Camera / dashboard performance

`CAMERA_PIPELINE_ACCEPTABLE=YES`

The Gazebo camera sensor is configured for 30 Hz at 1280x960. Direct Gazebo sampling remained near 30 Hz and simulation real-time factor remained approximately 1.0. ROS raw image delivery varied approximately 19–25 Hz depending on bridge and subscriber/probe load.

The primary bottleneck was synchronous Python serialization and reliable publication of a full 1280x960 debug image inside the ArUco callback. The dashboard then depended on that slow debug topic. The accepted local correction:

- keeps `/camera` on sensor-data QoS;
- has the dashboard consume `/camera` directly;
- performs annotated debug-image serialization/publication only when an explicit debug subscriber exists;
- leaves detection, PID, Mission Commander, and camera sensor resolution unchanged.

| Pipeline measurement | Before | After |
|---|---:|---:|
| ArUco observations | ~4.07 Hz | ~21.9 Hz |
| Viewer fresh frames | ~4.25 Hz | ~19.9 Hz baseline; 22.51 Hz latest moving run |
| UI render | ~4.25 Hz | ~19.1 Hz baseline; 21.18 Hz latest moving run |
| ArUco process CPU | ~109% | ~57% during isolated comparison |

Dashboard presentation changed from a 1280x720 composition (960x720 camera plus 320 px panel) to an 890x480 composition (640x480 4:3 camera plus 250 px panel). It now presents only `FIXED | MOVING`; the obsolete GIMBAL dashboard choice is absent. The underlying 1280x960 sensor is unchanged.

Final evidence-defect verification:

- moving JSON reports `mode=MOVING`;
- successful physical motion reports `platform_motion_verified=true`, not `PLATFORM_MOTION_FAIL`;
- displacement-derived speed is `0.0996161 m/s`, not approximately doubled;
- correct fresh-camera evidence is present in `fresh_camera_fps=22.5127`.

The legacy redundant `average_fresh_frame_fps` field remains `0.0`; `fresh_camera_fps` is the populated authoritative field. This is a small schema/evidence cleanup item and does not reopen flight acceptance.

## 7. Old Slice 3 / 3B / 3C

These slices are reclassified away from the final UAV runtime path.

### Slice 3 — `HISTORICAL_RESEARCH`

- YOLOv8n four-class baseline: bus, car, truck, van;
- frozen dataset counts: 6,469 train, 547 validation, 1,610 test images and matching labels;
- baseline training, ONNX export, configs, scripts, plots, and weights remain locally available;
- baseline best checkpoint SHA-256: `011521a2ada35e4d7270ca57e1c2560bf99e8f8b13a40c2dc7875a1e2fe2027d`.

### Slice 3B — `HISTORICAL_RESEARCH`

- derived single-class vehicle dataset has the same 6,469/547/1,610 split counts, with intact image symlinks and labels;
- Candidate A: YOLOv8n, single-class vehicle, `imgsz=960`;
- Candidate A checkpoint SHA-256: `190cd1091adae5fbfde747ce3075e4c2038e66629de0328acb66d230d6f92f71`;
- Candidate A ONNX SHA-256: `ef39f723aa4dafbf7a5a31bed10bb76cba7430a77f5ab6dc24b4f12eccf48245`;
- these Candidate A hashes match the preserved historical manifest evidence;
- SAHI remains deferred because its measured end-to-end latency was unsuitable for the intended real-time loop.

### Slice 3C — `HISTORICAL_RESEARCH`

- Candidate B/P2 checkpoint SHA-256: `4d2e966e5ff23b9a47ede8cef27d76359f902ca3eba02254566f71f1f9740459`;
- Candidate B's gain did not satisfy the predefined accuracy/recall Pareto gate;
- Candidate A won the historical Candidate A versus Candidate B/P2 selection;
- Candidate A/B configs, weights, raw result CSVs, reports, and decision rationale remain available for documentation.

The historical `~0.609` Candidate A value is validation/training evidence, not the authoritative frozen test metric. No ML retraining was performed during this audit, and no historical ML training is claimed as a current UAV runtime demo.

## 8. Old Slice 4

`STATUS=CLOSED_BY_SCOPE_PIVOT_AFTER_FP32_ACCEPTANCE`

Original Slice 4 is not called fully complete.

### Candidate A TensorRT FP32

- build: PASS;
- current deserialize: PASS;
- exact engine contract: input `images`, FP32, `(1,3,960,960)`; output `output0`, FP32, `(1,5,18900)`;
- output parity: PASS;
- metric provenance: PASS;
- engine size: 143,045,748 bytes;
- engine SHA-256: `df2f920e1caed46a489c8c1c674fb559a78c8277f22198838261321d96854f90`.

Stored smoke parity covers 10 images with 296/296 detections, no missing/extra detections, mean matched IoU `0.998862`, and finite outputs. Stored full parity reports 37,944 matched detections with 6 missing and 7 extra, mean matched IoU `0.999894`, and FP32 metric parity PASS. The stored full-parity report predates the current script schema and is preserved as historical evidence rather than silently represented as a freshly generated current-schema report.

Authoritative frozen test comparison:

- split: `test`;
- images/labels: 1,610 / 1,610;
- official Ultralytics Candidate A mAP50-95: `0.5244729223`;
- custom evaluator reference mAP50-95: `0.5241500000`;
- delta, official minus custom: `+0.0003229223`;
- decision: accepted evaluator/provenance consistency.

The official JSON's `comparison.gate` still says `PENDING_REVIEW`, despite the accepted numerical comparison. The older `tensorrt_environment.json` also records the pre-install blocked toolchain and is superseded by current TensorRT 11.2.1.2/CUDA import and engine evidence. Both stale fields are evidence-quality issues, not FP32 acceptance failures.

- FP16: not completed.
- INT8: not completed.
- final vehicle engine: not selected for the new runtime roadmap.

## 9. VERIFIED CURRENT DEMOS

- `FIXED_ARUCO_LANDING=DEMO_READY`
- `MOVING_ARUCO_LANDING=DEMO_READY`

No historical ML training, ONNX export, or TensorRT research artifact is listed as a current UAV runtime demo.

## 10. FINAL BASELINE TO PRESERVE

`FINAL_AUTONOMOUS_LANDING_BASELINE_TO_PRESERVE=YES`

Preserve as the foundation for the gesture roadmap:

- Docker/PX4/Gazebo simulation infrastructure and the pinned working image;
- ROS 2 typed messages and topic contracts;
- Python Mission Commander and MAVSDK ownership model;
- C++ XY PID and fixed/moving profiles;
- OpenCV ArUco detector and valid/stale observation semantics;
- fixed autonomous landing behavior;
- moving autonomous landing behavior;
- contact/touchdown latching and terminal control stop;
- platform physical-motion command, telemetry-only ground truth, and touchdown stop;
- real disarm and Mission Complete semantics;
- camera pipeline performance correction;
- compact FIXED/MOVING dashboard;
- runtime logs, dashboard frames, and metrics infrastructure.

Gesture perception must integrate on top of these components without reopening accepted landing behavior or making historical vehicle detection part of the new runtime critical path.

## 11. CLEANUP INVENTORY

Nothing was deleted. Every classification below is advisory and must be reviewed before action.

| Material | Classification | Rationale |
|---|---|---|
| Current robotics source, configs, worlds, models, interfaces, tests, runners | KEEP | Final fixed/moving baseline |
| Dockerfile, Compose config, entrypoint, pinned version files | KEEP | Reproducible simulation foundation |
| Current final fixed/moving logs, `latest_metrics.json`, descent dashboard | KEEP | Acceptance evidence |
| Candidate A `best.pt`, ONNX, FP32 engine, hashes, official test and parity reports | ARCHIVE | Historical ML/TensorRT engineering provenance |
| Candidate B/P2 `best.pt`, result CSV, and Pareto report | ARCHIVE | Preserves the rejected-alternative decision |
| Four-class baseline `best.pt`, ONNX, config, result CSV, and acceptance report | ARCHIVE | Preserves Slice 3 research lineage |
| Derived dataset labels/symlink structure and dataset configs | ARCHIVE | Reproducibility evidence; not new runtime critical path |
| Raw extracted dataset | ARCHIVE | Needed only to reproduce historical research |
| `ml/datasets/Aerial Vehicles.v1i.yolov8.zip` (~940 MB) | DELETE_CANDIDATE | Likely duplicates the intact extracted raw dataset; verify archive checksum first |
| Experiment `last.pt` files when corresponding `best.pt` is archived | DELETE_CANDIDATE | Training-resume artifacts, not selected checkpoints |
| Generated train batches, validation previews, plots duplicated by archived reports | DELETE_CANDIDATE | Reproducible generated research output |
| Python `__pycache__`, pytest caches, ROS `build/`, `install/`, and `log/` | DELETE_CANDIDATE | Generated caches/build products; rebuildable after baseline freeze |
| Old shadow/recovery/REPORT_C2/REPORT_C3 runtime logs | ARCHIVE | Historical troubleshooting evidence; consolidate before deletion |
| `ml/.venv/` (~5.7 GB) | UNKNOWN | Historical ML environment; remove only after environment lock/rebuild path is proven |
| `ml/.venv-tensorrt/` (~10 GB) | UNKNOWN | Large but contains the accepted TensorRT toolchain; preserve until reproducibility is frozen |
| Root `.venv/` (~13 MB) | UNKNOWN | Current ownership/use not established by this audit |
| `debug_frame.png`, `capture_frame.py`, `smoke_plugin.py` untracked paths | UNKNOWN | Provenance and ongoing diagnostic use require owner review |
| Ignored continuity/planning documents under `docs/context/` and `docs/plans/` | ARCHIVE | Useful migration/history context, but not runtime source |

## 12. Remaining issues

No remaining issue invalidates the demonstrated fixed or moving landing baseline.

Issues that affect baseline freeze or the next roadmap's engineering hygiene:

1. **Unfrozen dirty worktree:** accepted robotics changes, TensorRT evidence source, tests, and this audit report are not yet committed/tagged. Review the selective freeze manifest before choosing the preservation commit.
2. **Small evidence-schema debt:** `average_fresh_frame_fps` remains a redundant zero-valued field while `fresh_camera_fps` is correct; the official ML JSON still says `PENDING_REVIEW`; the old TensorRT environment JSON still describes the pre-install toolchain. These do not block flight, baseline freeze, or the gesture architecture, but should be normalized when evidence schemas are next maintained.

## 13. PIVOT READINESS

`PIVOT_READINESS=READY`

Robotics, camera runtime, functional tests, C++ GTests, registered package tests, and the aggregate ament gate are green. The autonomous landing baseline is ready to preserve. No gesture implementation should begin until the accepted worktree and cleanup disposition are reviewed and selectively frozen.

## 14. EXACT NEXT ACTION

Review the cleanup inventory and freeze the accepted baseline before opening the Gesture Perception slice.
