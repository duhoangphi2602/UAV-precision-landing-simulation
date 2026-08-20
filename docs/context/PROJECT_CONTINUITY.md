# PROJECT CONTINUITY

> **Purpose:** continuity checkpoint for a new AI/Codex agent taking over the UAV precision-landing project. This document reconstructs the project from the conversation history available in this migration context. It is intentionally explicit about superseded decisions, current state, and unknowns so a new agent does not restart the reasoning process or reintroduce rejected approaches.
>
> **As-of:** 2026-08-19 (conversation migration point).  
> **Current repository/project path referenced throughout the work:** `~/Projects/UAV-precision-landing-simulation`.
>
> **Evidence rule:** where the conversation gave exact evidence, this checkpoint preserves it. Where the conversation did not expose an exact filename, commit SHA, command, or artifact, this document says `UNKNOWN` rather than inventing one.

---

# 1. PROJECT ORIGIN

## 1.1 Original idea

The project began as a practical, portfolio-oriented UAV / Computer Vision / Embedded AI project intended to demonstrate an end-to-end engineering workflow rather than a collection of disconnected tutorials or model experiments.

The initial problem was **precision landing / visual target tracking for a UAV in simulation**, using a downward-facing camera and an ArUco landing target as a deterministic ground-truth perception problem first. The desired result was a demo where a virtual drone could:

1. start PX4 SITL;
2. run Gazebo/Gazebo Sim;
3. obtain camera frames;
4. detect a landing marker with OpenCV/ArUco;
5. calculate image-center error;
6. control the drone with a PID controller;
7. descend while maintaining visual alignment;
8. land and disarm safely;
9. display the visual result and live telemetry in a user-visible GUI.

The project was deliberately built around a **real engineering boundary between perception, control, orchestration, simulation, and deployment**, rather than one monolithic script.

## 1.2 Initial technical / portfolio goal

The project was explicitly intended to be useful for an AI / Computer Vision Engineer portfolio, with relevance to UAV / embedded / edge-AI work. The project was also intended to demonstrate skills that commonly matter for that role:

- Python for AI/perception and system glue;
- C/C++ for performance-sensitive control/runtime components;
- OpenCV in Python and C++;
- ROS 2 communication and typed interfaces;
- PX4 SITL and Gazebo;
- MAVSDK for flight mission interaction;
- MAVLink/pymavlink for a future gimbal control path;
- Linux/Ubuntu and Docker;
- GPU acceleration on an RTX 3060;
- PyTorch model training;
- ONNX export;
- TensorRT FP16/INT8;
- eventual object tracking (ByteTrack);
- eventual gimbal control.

The user explicitly wanted the project to look like **one coherent engineering prototype solving real UAV perception/control problems**, not a set of unrelated technologies.

## 1.3 Initial project scope

The project evolved into a mission-driven roadmap with a stable fixed-ArUco landing core and later extensions.

Initial portfolio/demo scope became:

- **Fixed ArUco precision landing** as the deterministic baseline.
- **Moving ArUco platform landing** as the next control challenge.
- **YOLO vehicle detection + tracking** as the AI perception extension.
- **Gimbal control** as a separate control problem.
- **Edge optimization** through ONNX/TensorRT and eventually C++ runtime.

The user wanted incremental implementation and explicitly prioritized fast, demonstrable progress over broad refactors.

## 1.4 Initial architecture idea

The project initially relied on the following major pieces:

- PX4 SITL for flight control;
- Gazebo for simulated world/camera/physics;
- ROS 2 for perception/control message flow;
- Python for perception and mission orchestration;
- C++ for a performance-sensitive PID control node;
- MAVSDK for flight mission commands;
- OpenCV for image processing and visualization;
- Docker/Compose to keep the simulation environment reproducible;
- NVIDIA GPU acceleration for Gazebo and later ML/TensorRT.

The early baseline responsibility split eventually became an important invariant:

- **Python Mission Commander:** mission orchestration/state machine, MAVSDK bridge, ARM/TAKEOFF/NAVIGATE/SCAN/ALIGN/DESCEND/LAND/termination logic.
- **C++ PID controller:** XY velocity calculation only; no mission orchestration.
- **ArUco detector:** image-based target observation generation.
- **OpenCV viewer/dashboard:** visual telemetry/debug output.
- **Gazebo/PX4:** simulation and vehicle dynamics.

## 1.5 Initial assumptions

The original working assumptions included:

- No real UAV hardware; simulation first.
- SITL is the authoritative execution environment for portfolio demo.
- PC with RTX 3060 is the active compute target.
- Fixed target can be represented by ArUco ID 0.
- A downward-facing camera can provide visual feedback for landing.
- The project should work locally through Docker/Compose.
- The final demo should be visible through Gazebo plus an OpenCV camera view/dashboard.

## 1.6 Initial constraints

Major constraints that remained important throughout the work:

- **Do not break the already-working Python baseline.**
- Keep changes incremental and reversible.
- Avoid broad refactors when a targeted change solves the problem.
- Do not let the agent wander into unrelated optimization.
- Prefer evidence-driven gates before moving to the next implementation step.
- User should manually run important training and system-level commands when practical, so they can see progress and control key decisions.
- Simulation only; no claim of real-hardware validation.
- GPU target during development: RTX 3060 12 GB.
- Project should be able to run in a clean clone; reproducibility was explicitly part of Definition of Done.
- Runtime logs, datasets, model binaries, and generated evidence must not pollute the public Git repository.

## 1.7 Initial Definition of Done (evolved into final form)

The practical DoD that emerged was:

- fixed landing demo works reliably;
- moving landing demo works reliably enough for portfolio proof;
- user-visible Gazebo + OpenCV demo exists;
- typed ROS 2 interface exists between Python perception/state and C++ control;
- C++ PID works without replacing Python mission orchestration;
- metrics/evidence are captured;
- public repository is clean;
- dataset/model artifacts are ignored and not tracked;
- security hygiene is applied;
- Docker user is non-root at runtime;
- clean-clone gate passes;
- limitations are documented honestly;
- each Slice is closed with Git hygiene, commit, merge, tag, and clean working tree before opening the next Slice.

---

# 2. EVOLUTION OF THE PROJECT

## 2.1 Early simulation stabilization

### Decision: simplify Gazebo inspection world

**Problem:** Gazebo startup hung/timeouts because `inspection.sdf` repeatedly downloaded many heavy Fuel models (trees, cars, etc.) in short-lived containers.

**Options:** keep the original rich Fuel world; remove heavy external entities; redesign the world later.

**Decision:** remove the heavy Fuel dependencies so the world loads deterministically and quickly.

**Why:** the goal was a stable demo and reproducible startup, not realism at the cost of reliability.

**Status:** CURRENT.

**Impact:** fast world load became a prerequisite for all later testing.

---

### Decision: correct static landing plane physics

**Problem:** PX4 EKF2 / acceleration failures were traced to spawning the drone over a custom ground plane that did not match PX4's expected friction/bounce setup.

**Decision:** replace the custom plane with a plane matching PX4 `default.sdf` behavior.

**Why:** eliminate a physics regression rather than compensate in flight code.

**Status:** CURRENT.

**Impact:** drone spawn became stable.

---

## 2.2 Camera / coordinate debugging

### Decision: do not keep a destructive camera-pitch `sed` hack

**Problem:** camera pitch patching repeatedly caused crashes / singularity issues and confused the root cause of the perception failure.

Approaches tried:

- patching camera SDF with `sed` from `1.5707` to `-1.57`;
- changing exact `-90°` values.

**Why rejected:** exact `-1.5707` hit a Gazebo gimbal-lock-like singularity and generated NaNs; editing a running shell script also corrupted bash execution once.

**Decision:** preserve the original PX4 camera model and stop patching it from the run script.

**Status:** REJECTED/SUPERSEDED.

**Impact:** camera model became a protected upstream asset instead of an ad-hoc runtime mutation.

---

### Decision: fix NED/ENU waypoint mapping

**Problem:** marker was at Gazebo ENU `X=5.8, Y=0`, while PX4 NED mapping required `North=0.0, East=5.8`.

**Decision:** lock mission waypoint to `N=0.0, E=5.8, Down=-3.0` for the fixed demo.

**Why:** coordinate mismatch caused the drone to fly several meters away from the marker.

**Status:** CURRENT for fixed baseline.

**Impact:** deterministic navigation directly above the marker.

---

## 2.3 GPU acceleration / visualization

### Decision: NVIDIA Container Toolkit + hardware rendering

**Problem:** Gazebo performance and rendering were initially poor.

**Decision:** install NVIDIA Container Toolkit and expose RTX 3060 to relevant containers; configure Compose for NVIDIA hardware rendering.

**Why:** the user explicitly wanted hardware-accelerated Gazebo and smoother visual demo.

**Status:** CURRENT.

**Impact:** Gazebo reached approximately real-time factor ~1.0 in the accepted GPU configuration.

---

## 2.4 Python baseline first

### Decision: preserve Python baseline as Golden Reference

**Problem:** the project needed an authoritative behavior contract before switching control implementation.

**Decision:** keep `make demo-python` as the Golden baseline and later tag it as `python-baseline-v1`.

**Why:** C++ changes could then be compared against something known-good.

**Status:** CURRENT.

**Impact:** fixed landing behavior became the regression reference for C++ control.

---

## 2.5 C++ PID transition

### Decision: use C++ for XY control, keep Python for orchestration

**Problem:** a real engineering prototype should demonstrate a meaningful C++/Python boundary without making the control system needlessly complex.

**Options:** replace all Python with C++; keep all control in Python; use C++ only for the performance-sensitive velocity calculation.

**Decision:** C++ handles pure XY velocity calculation; Python remains responsible for mission state and MAVSDK flight orchestration.

**Why:** this gives a realistic division of responsibility and preserves the working Python mission logic.

**Status:** CURRENT.

**Impact:** `precision_landing_control_cpp` became the main control node while Python remains the mission commander.

---

### Decision: use ROS 2 as the Python/C++ interface

**Problem:** user explicitly rejected weak integration patterns such as JSON files, global files, subprocess stdout, and unschematized UDP.

**Decision:** ROS 2 is the architectural interface between Python and C++.

**Why:** typed, timestamped, versionable contracts are appropriate for a multi-node robotics system.

**Status:** CURRENT.

**Impact:** Slice 1 introduced `precision_landing_interfaces` with typed messages.

---

## 2.6 Slice 1 — typed interfaces + dashboard + metrics

### Decision: create typed ROS 2 contracts while retaining legacy compatibility

**Problem:** moving directly to typed messages could break the known-good Python/C++ flow.

**Decision:** dual-publish typed and legacy messages during Slice 1.

Typed interfaces introduced:

- `TargetObservation.msg`
- `ControlCommand.msg`
- `MissionStatus.msg`

**Why:** preserve backward compatibility while introducing an engineering-grade contract.

**Status:** CURRENT architecture.

**Impact:** `precision_landing_interfaces` became foundational.

---

### Decision: one OpenCV dashboard window

**Problem:** the user wanted a more impressive, readable demo than a raw camera window.

**Decision:** one OpenCV window combining the camera feed with a telemetry side panel.

Panel includes/was planned to include:

- mode;
- mission status;
- controller;
- target status/ID;
- pixel error;
- velocity commands;
- re-align count;
- platform state in moving mode;
- post-mission summary.

**Status:** CURRENT.

**Impact:** dashboard became a visible engineering feature.

---

### Discovery: camera stream FPS ≠ UI refresh rate

**Problem:** early metrics reported ~30 FPS because the UI was refreshed at 30 Hz even though fresh camera frames arrived at only ~4 Hz in the slow simulation environment.

**Decision:** distinguish `CAM FPS` / fresh-frame rate from `UI HZ`.

**Why:** the user explicitly noticed that the camera feed itself was choppy even when Gazebo's world ran smoothly.

**Status:** CURRENT.

**Impact:** metrics became more honest; no false claim of camera 30 FPS.

---

### Decision: do not over-optimize the camera GUI at this stage

The camera stream was observed to be low-FPS in the simulator while Gazebo world rendering was much smoother. This was treated as a simulation/runtime limitation, not a reason to redesign the perception architecture mid-Slice.

**Status:** CURRENT limitation.

---

## 2.7 Slice 1 termination / precision stabilization

Several targeted safety/termination corrections were made:

- wait for actual disarm before reporting `Mission Complete`;
- prevent runner from terminating just because `LAND` appeared in logs;
- maintain exact termination contract;
- use touchdown coordinates with corrected ENU↔NED mapping;
- corrected touchdown metric so fixed pad is `North=0.0, East=5.8`.

Final fixed regression evidence included approximately `0.0472 m` touchdown horizontal error at one correction point and later `0.025 m` fixed regression in Slice 2 documentation.

**Status:** CURRENT fixed baseline behavior.

---

## 2.8 Slice 1 closure

Slice 1 was merged and tagged as:

`slice1-engineering-interface-v1`

The working tree was cleaned and whitespace/source hygiene was fixed without broad auto-formatting.

---

## 2.9 Slice 2 — moving ArUco platform

### Decision: moving ArUco before YOLO

**Problem:** user wanted a higher-value UAV control extension before adding a full AI detector/tracker stack.

**Decision:** use a single moving ArUco platform first as a deterministic moving-target ground truth; defer YOLO until later.

**Why:** easier to prove the moving-control loop independently of AI detector uncertainty.

**Status:** CURRENT milestone completed.

---

### Decision: one-dimensional, constant-speed platform

**Decision:** move landing platform at approximately `0.10 m/s` in one direction.

**Why:** user explicitly selected a simple, low-speed motion profile to keep Slice 2 tractable.

**Status:** CURRENT.

---

### Discovery: smoke motion PASS but full demo platform stayed still

**Problem:** platform moved in isolated smoke test but not during full demo.

**Root cause:** `moving_platform_controller.py` crashed on a wrong state constant (`STATE_LANDED` instead of `STATE_LAND`), so continuous `cmd_vel` publishing stopped and the Gazebo platform halted.

**Decision:** fix controller state constant; harden motion latch; add full-demo physical motion gate.

**Status:** FIXED.

**Impact:** full demo eventually showed continuous physical motion.

---

### Decision: do not use platform ground truth as flight-control input

Ground-truth moving-platform pose was used for:

- telemetry;
- dashboard;
- metrics;
- touchdown mapping.

It was deliberately **not** used to generate flight control commands.

**Why:** the intended moving demo is reactive visual tracking, not ground-truth feed-forward.

**Status:** CURRENT invariant.

---

### Failed/superseded moving-control approaches

#### P2/PID tuning exploration

Several moving PID variants were tried. A key discovery was that the fixed-mode controller configuration was not directly transferable to moving mode because:

- camera updates were slow;
- moving platform required steady-state horizontal velocity;
- a deadband could freeze integral behavior;
- wrong flip settings could cause divergence.

A moving-specific profile was therefore created.

**Status:** current moving profile exists; exact final values should be read from repository/config rather than inferred from history alone.

---

### Decision: reject Kalman + long blind descent for Slice 2

**Problem:** at low altitude the camera FOV became tight and pixel error could spike; an agent proposed a Kalman filter plus a blind descent using the last XY velocity.

**Decision:** reject the Kalman prediction path and reject treating predicted measurements as `valid=true`; prefer bounded low-altitude logic and physical touchdown confirmation.

**Why:** predicted observations would blur the observation contract, and holding an unknown last XY velocity near touchdown was judged unsafe/unnecessary.

**Status:** REJECTED / DO NOT REPEAT unless a later scope explicitly reopens estimation work.

---

### Decision: use scale-aware error in low-altitude moving mode

**Problem:** fixed `30 px` thresholds became too strict as the marker grew in the image at low altitude.

**Decision:** normalize center error by observed marker size for low-altitude moving final approach.

**Why:** a fixed pixel threshold is not physically scale-invariant.

**Status:** CURRENT moving-mode logic.

---

### Discovery: platform continued moving after apparent landing

**Problem:** drone could appear to contact the moving pad, but if mission state did not latch touchdown, the platform continued moving, pixel error grew, and state machine could push the drone back toward ALIGN/SCAN.

**Decision:** touchdown-priority + touchdown latch + platform stop.

**Why:** once physical touchdown is confirmed, vision tracking should no longer be allowed to command a relaunch.

**Status:** CURRENT.

---

### Decision: no `action.kill()` for normal landing termination

**Problem:** one interim agent implementation used `action.kill()` after a final-commit timeout. The container terminated cleanly, but this was not considered a proper landing contract.

**Decision:** remove `action.kill()` from normal mission flow; use contact confirmation plus a standard landing/disarm sequence.

**Why:** `kill()` is an emergency motor-stop, not an evidence-backed touchdown/disarm flow.

**Status:** REJECTED / SUPERSEDED.

---

### Final Slice 2 result

Moving platform landing was accepted with:

- physical platform motion verified;
- stable visual tracking;
- scale-aware low-altitude logic;
- Gazebo contact-confirmed touchdown;
- platform stop at touchdown;
- graceful disarm;
- horizontal touchdown error around `0.127 m` in the final reported moving run;
- fixed regression around `0.025 m` in the final report.

Slice 2 was considered functionally PASS with documented SITL limitations.

Slice 2 was intended to be merged/tagged using the end-of-Slice Git gate. The exact tag name was planned as `slice2-moving-aruco-v1`; the conversation explicitly says Slice 2 was merged and current state proceeds from it.

---

## 2.10 Slice 3 — YOLO baseline

### Dataset decision

The user supplied a local Roboflow export:

`/home/hoangphi/Projects/UAV-precision-landing-simulation/ml/datasets/Aerial Vehicles.v1i.yolov8.zip`

Dataset information provided by the user:

- 4 classes: `car`, `truck`, `bus`, `van`;
- YOLOv8 format;
- train/valid/test image counts: `6469 / 547 / 1610`;
- Auto-Orient applied;
- Stretch resize to `960x720`.

The source URL given in the conversation was:

`https://universe.roboflow.com/uavdt/aerial-vehicles-hjarh`

License stated by the user: `CC BY 4.0`.

The explicit rule was: `data.yaml` and archive contents are the source of truth; do not assume the class IDs without reading them.

---

### Decision: YOLOv8n baseline first

**Problem:** needed a reproducible AI detector before optimization.

**Decision:** train YOLOv8n at `imgsz=640` as a baseline, export ONNX, and validate ONNX parity.

**Why:** baseline first, then measured optimization.

**Status:** PASS / MERGED.

---

## 2.11 Slice 3B — data-centric optimization

### Decision: add a dedicated AI-engineering diagnosis phase

**Problem:** user explicitly wanted to see what an AI engineer does to improve model quality rather than blindly retraining.

**Decision:** analyze:

- class-aware vs class-agnostic performance;
- class imbalance;
- bbox-size distributions;
- small-object limitations;
- preprocessing/augmentation implications;
- latency budget;
- technique-to-problem mapping.

**Status:** CURRENT methodology.

---

### Decision: keep a 4-class research baseline but use single-class `vehicle` for deployment candidate

**Problem:** class confusion among `car`, `van`, `truck`, `bus` was not essential to generic vehicle tracking for the gimbal use case.

**Decision:** keep the 4-class baseline as a research artifact; derive a single-class `vehicle` dataset for deployment-oriented tracking.

**Why:** reduces class confusion and class imbalance while preserving the original dataset/labels as an audit reference.

**Status:** CURRENT.

---

### Candidate A

Single-class `vehicle`, YOLOv8n, `imgsz=960`.

Reported outcome:

- mAP50 ≈ `0.877`;
- mAP50-95 ≈ `0.609`;
- precision ≈ `0.901`;
- recall ≈ `0.792`;
- PyTorch model inference around `2.4 ms` in one benchmark context.

Candidate A became the main deployment candidate.

---

### Decision: defer SAHI for runtime

**Problem:** sliced inference increased latency substantially.

**Decision:** benchmark SAHI, but do not use it as the default runtime path.

**Why:** reported SAHI end-to-end latency was approximately `90.98 ms`, unsuitable for the desired ~30 FPS gimbal loop.

**Status:** DEFERRED / REJECTED for current runtime.

---

### Candidate B: YOLOv8n-P2

**Problem:** possible need for small-object feature resolution.

**Decision:** train a controlled P2 candidate and compare by Pareto criteria.

**Result:** P2 gained only about `+0.006` mAP50-95, tiny-object recall improved by about `+2.4 percentage points`, but larger-object recall fell and latency increased significantly.

Reported fair benchmark later showed approximately:

- Candidate A total ≈ `6.8 ms`, inference ≈ `4.4 ms`;
- Candidate B total ≈ `10.1 ms`, inference ≈ `7.3 ms`.

Operating-point evaluation also showed A ahead (F1 about `0.807` vs `0.798`).

**Decision:** Candidate A wins the Pareto comparison.

**Status:** Candidate B = RESEARCH ARTIFACT / SUPERSEDED for deployment selection.

---

### Decision: defer knowledge distillation

**Problem:** user suggested distillation for further optimization.

**Decision:** do not do distillation yet.

**Why:** there was no sufficiently stronger teacher justified by evidence; Candidate A already had a strong accuracy/latency trade-off.

**Status:** DEFERRED.

---

### Candidate A / B learning-curve explanation

A critical discovery: Candidate A started at a very high early validation score because it was initialized from the UAVDT baseline checkpoint (`best.pt`) and benefited from domain transfer. Candidate B P2 started much lower because its architecture had additional/new components and was not initialized identically.

**Invariant:** do not interpret “beautiful learning curve” as proof of better final model quality. Initialization and architecture matter.

---

## 2.12 Slice 3 Git closure

The user explicitly introduced a new permanent process rule:

**Every Slice must end with a full Git hygiene closure before the next Slice starts.**

The rule includes:

- acceptance PASS;
- audit tracked/untracked/ignored files;
- ensure datasets/models/generated reports are not tracked;
- selective staging only;
- commit;
- merge into `main`;
- annotated tag;
- clean working tree;
- do not push remote unless requested.

Slice 3 was reported as:

- merged;
- Candidate A selected;
- dataset not tracked;
- model binary not tracked;
- generated ML report not tracked;
- secrets/absolute paths none;
- working tree clean;
- tag: `slice3c-vehicle-detector-v1`.

---

## 2.13 Slice 4 — TensorRT

### Decision: TensorRT only after model is frozen

**Problem:** user wanted to reduce deployment latency and learn practical Edge AI optimization.

**Decision:** ONNX Candidate A is the frozen model entering Slice 4.

**Status:** CURRENT.

---

### Toolchain discovery

Initial audit found:

- `trtexec` missing;
- `nvcc` missing;
- Python `tensorrt` missing;
- ONNX Runtime GPU initially could not find `libcudart.so.13`.

The agent first reported the purpose of each missing component and the user explicitly requested this reporting behavior going forward.

### Decision: isolated TensorRT environment

The user manually installed an isolated environment:

`ml/.venv-tensorrt`

with TensorRT/CUDA 13 stack.

Verification output:

- `TENSORRT_IMPORT=PASS`;
- TensorRT `11.2.1.2`;
- `TENSORRT_BUILDER=PASS`;
- `CUDA_RUNTIME=PASS`;
- `ORT_CUDA_EP=PASS`;
- `ONNX_INFERENCE=PASS`.

**Status:** CURRENT.

---

### FP32 TensorRT engine

A strict FP32 engine was built successfully.

Key evidence:

- TensorRT version `11.2.1.2`;
- ONNX opset `20`;
- engine build about `44.77 s`;
- engine size `136.42 MB`;
- SHA-256:
  `df2f920e1caed46a489c8c1c674fb559a78c8277f22198838261321d96854f90`.

Runtime deserialize contract was verified:

- 2 I/O tensors total;
- input `images`, `FLOAT`, shape `(1,3,960,960)`;
- output `output0`, `FLOAT`, shape `(1,5,18900)`.

Output interpretation:

- 4 bbox values + 1 vehicle score;
- 18,900 predictions = `120x120 + 60x60 + 30x30` from P3/P4/P5.

**Status:** FP32 engine build + deserialize PASS.

---

### FP32 parity

Output parity smoke on 10 images:

- 296 vs 296 detections;
- 0 missing / 0 extra;
- mean matched IoU ≈ `0.998862`;
- mean confidence drift ≈ `0.000222`;
- finite outputs.

Full test output parity on 1,610 images:

- PyTorch detections: `37,950`;
- TensorRT detections: `37,952`;
- matched: `37,944`;
- missing: `6`;
- extra: `8`;
- mean matched IoU ≈ `0.999906`;
- mean confidence drift ≈ `0.000103`;
- all outputs finite;
- PyTorch FPS ≈ `114.30`;
- TensorRT FPS ≈ `145.16` in that evaluator context.

**Status:** OUTPUT PARITY = PASS.

---

### FP32 metric-provenance issue — current blocker

A custom evaluator initially returned:

- PyTorch mAP50-95 `0.49908`;
- TensorRT mAP50-95 `0.49906`;
- delta `0.00002`;
- recall delta `0.00044`.

Backend parity was excellent, but the value was much lower than the Candidate A reported `0.609`.

The next self-check changed the custom PyTorch test metric to `0.52415`, still below `0.609`.

Current conclusion: **the project must distinguish validation metrics from test metrics before opening FP16**. The reported `0.609` may be the validation metric from training, while the 1,610-image test evaluator reports a lower value. This is not yet proven; it is the current provenance hypothesis to verify using the official Ultralytics validator on the same 1,610-image test split.

Current blocker is therefore **metric provenance / evaluator self-consistency**, not TensorRT output correctness.

FP16 remains LOCKED until the official test-set reference is established.

---

# 3. CURRENT ARCHITECTURE

## 3.1 System-level architecture

The current project is a layered UAV simulation/AI engineering prototype.

### Flight / simulation

```text
Gazebo / Gazebo Sim
        │
        ├── camera / world / moving platform
        │
        ▼
PX4 SITL  ⇄  MAVSDK Python
        │
        ▼
Python Mission Commander
```

### Perception / control

```text
Camera frame
    │
    ▼
ROS 2 image pipeline
    │
    ▼
ArUco detector (current landing path)
    │
    ├── TargetObservation (typed)
    └── legacy center-error topic (compatibility)
            │
            ▼
C++ precision_landing_control_cpp
    │
    ├── XY PID
    └── typed ControlCommand + legacy Twist
            │
            ▼
Python Mission Commander
    │
    └── MAVSDK flight commands / state machine
```

### Mission ownership

**Python Mission Commander owns:**

- mission state machine;
- ARM;
- TAKEOFF;
- NAVIGATE;
- SCAN;
- ALIGN/descend orchestration;
- final-approach gating;
- touchdown detection/termination logic;
- MAVSDK interactions;
- metric aggregation;
- mission success/failure semantics.

**C++ PID node owns:**

- converting target observation error into XY velocity command;
- PID state;
- saturation;
- deadband / anti-windup behavior as configured;
- stale/invalid observation handling.

C++ does **not** own mission orchestration.

## 3.2 Typed ROS 2 boundary

A typed ROS 2 interface package exists:

`precision_landing_interfaces`

Known messages:

- `TargetObservation.msg`;
- `ControlCommand.msg`;
- `MissionStatus.msg`;
- `MovingPlatformState.msg`.

Slice 1 initially dual-published typed and legacy topics to preserve baseline compatibility.

## 3.3 Fixed landing

Fixed target:

- ArUco ID 0;
- fixed pad in the inspection world;
- PX4 local NED target for fixed navigation: approximately `North=0.0`, `East=5.8`.

The final fixed flow includes graceful disarm and touchdown metrics.

## 3.4 Moving landing

Moving platform:

- Gazebo platform driven at approximately `0.10 m/s` one-dimensional motion;
- platform controller uses Gazebo ground-truth pose only for telemetry/metrics;
- flight controller remains vision-reactive.

The moving landing flow includes:

- motion latch;
- actual platform motion gate;
- moving-specific PID profile;
- low-altitude scale-aware error;
- final commit;
- Gazebo contact confirmation;
- platform stop at touchdown;
- disarm without `action.kill()` in the accepted path.

## 3.5 AI detector path

Current frozen deployment candidate:

`YOLOv8n` single-class `vehicle`, input `960`.

Model artifacts:

- local `.pt` and `.onnx` are intentionally ignored/untracked;
- ONNX is the artifact entering TensorRT.

## 3.6 TensorRT path (current in-progress)

```text
Candidate A ONNX
    │
    ▼
TensorRT 11.2.1.2
    │
    └── FP32 reference engine   ← build PASS, parity PASS
             │
             ├── FP16           ← LOCKED pending metric gate
             └── INT8           ← LOCKED
```

## 3.7 Future gimbal/ByteTrack path

Only the direction agreed in the conversation is authoritative:

```text
YOLO detector
→ ByteTrack
→ user selects Track ID in OpenCV dashboard
→ target error
→ C PID gimbal module
→ pymavlink
```

This is future scope; it is not currently implemented in the canonical current architecture.

## 3.8 Visualization

The OpenCV GUI is a single window that combines:

- camera image;
- side telemetry panel;
- mode indicator (`FIXED` / `MOVING` / `GIMBAL` planned);
- mission/controller state;
- target information;
- errors;
- velocity;
- moving-platform state;
- mission summary/metrics.

The user noticed that the camera feed can be choppy even when Gazebo world FPS/RTF is stable. This is treated as a known simulator/runtime limitation rather than a reason to destabilize the whole architecture.

## 3.9 Containers / infrastructure

Docker/Compose is used for simulation components.

NVIDIA Container Toolkit is configured so the RTX 3060 is visible to containers. Earlier accepted evidence showed GPU-backed Gazebo rendering and real-time factor around 1.0.

Runtime Docker user was hardened to a non-root `devuser` (UID 1000 was reported during final acceptance). Passwordless `NOPASSWD:ALL` was removed from the final security path.

---

# 4. CURRENT CANONICAL STATE

## 4.1 Current phase

**Slice 4 — TensorRT optimization.**

## 4.2 Last completed milestone

**Slice 3/3B/3C completed, merged, Git hygiene closed, Candidate A selected as final detector candidate.**

The last completed TensorRT milestone is the successful strict FP32 engine build + deserialize + output parity.

## 4.3 Last known working state

### Fixed demo

`make demo-cpp` is the fixed C++ control demo and remained a known-good regression after Slice 1/2 work.

### Moving demo

`make demo-moving-aruco` was accepted as a functional moving-platform landing demo with approximate final touchdown error `0.127 m` in the final reported run and graceful disarm/contact confirmation.

### AI detector

Candidate A is the selected deployment model:

- YOLOv8n;
- single-class vehicle;
- `imgsz=960`;
- baseline/export artifacts local/ignored;
- Candidate B P2 is research-only.

### TensorRT

The following are PASS:

- TensorRT toolchain setup;
- TensorRT Python import;
- builder;
- CUDA runtime;
- ONNX Runtime GPU execution;
- ONNX inference;
- FP32 engine build;
- FP32 serialization;
- FP32 engine deserialize;
- FP32 output parity;
- FP32 backend metric delta parity.

## 4.4 Features currently working

- PX4 SITL + Gazebo simulation;
- hardware-accelerated Gazebo rendering using RTX 3060;
- Python mission orchestration;
- C++ PID XY controller;
- typed ROS 2 interface layer;
- OpenCV telemetry dashboard;
- fixed ArUco precision landing;
- moving ArUco platform landing;
- moving-platform telemetry/metrics;
- graceful touchdown/disarm path;
- YOLOv8n single-class vehicle training pipeline;
- ONNX export;
- TensorRT FP32 engine build and inference parity.

## 4.5 Features partially working / in progress

- TensorRT FP32 metric-level comparison against an authoritative test-set reference.
- TensorRT FP16.
- TensorRT INT8.
- final deployment-engine selection.
- future Python YOLO + ByteTrack integration.
- future gimbal control.
- future C++ TensorRT/OpenCV runtime integration.

## 4.6 Features not currently implemented in canonical state

- ByteTrack integration.
- full GIMBAL mode.
- C-only PID gimbal module integration.
- pymavlink gimbal command path.
- C++ TensorRT/OpenCV inference runtime.
- INT8 QAT.
- real hardware testing.
- Jetson/onboard deployment validation.

## 4.7 Current blocker

**FP32 metric provenance / evaluator self-consistency.**

Current custom PyTorch test-set metric:

`mAP50-95 = 0.52415`

Original Candidate A reported metric:

`mAP50-95 = 0.609`

The conversation strongly suggests, but has not yet proven, that `0.609` is a validation metric while `0.52415` is a test-set metric. The official Ultralytics test evaluator on the same 1,610-image test split must be run once to establish the authoritative test reference.

Do not open FP16 until this provenance question is resolved.

## 4.8 Current technical debt

- exact final documentation split between validation and test metrics needs to be corrected if provenance mismatch is confirmed;
- TensorRT benchmark/evaluation reports are local and must remain untracked;
- some earlier walkthrough/report files contain historical intermediate results and need careful status wording if revisited;
- source repository has evolved with many narrowly targeted fixes; avoid broad refactors;
- final C++ TensorRT runtime has not been implemented yet.

## 4.9 Known limitations

- SITL only; no real flight hardware validation.
- Gazebo contact sensor is SITL-specific.
- Camera fresh-frame rate may be much lower than Gazebo UI/RTF.
- TensorRT engine is environment/GPU/TensorRT-version specific and must be rebuilt on other hardware.
- RTX 3060 latency does not represent onboard/Jetson performance.
- The current YOLO detector is single-class vehicle; fine-grained `car/van/truck/bus` classification is preserved only in the research baseline.
- INT8 accuracy is not yet verified.
- No real rangefinder/sonar/lidar hardware was added to the SITL drone.

## 4.10 Current environment assumptions

- Ubuntu/Linux desktop environment;
- project root `~/Projects/UAV-precision-landing-simulation`;
- active PC GPU: NVIDIA RTX 3060 12 GB;
- CUDA/TensorRT environment isolated in `ml/.venv-tensorrt`;
- TensorRT `11.2.1.2` verified;
- ONNX Runtime GPU verified;
- Python training environment kept separate from TensorRT environment.

## 4.11 Work immediately in progress before migration

The last concrete task was **not feature development**; it was validating the metric provenance for FP32 TensorRT parity.

The latest command executed by the user was:

```bash
bash ml/scripts/run_fp32_pytorch_metric_selfcheck_manual.sh
```

Latest output:

```text
PYTORCH_AUTHORITATIVE_MAP50_95=0.609
PYTORCH_CUSTOM_MAP50_95=0.52415
PYTORCH_SELF_CONSISTENCY_DROP=0.08485
PYTORCH_EVALUATOR_SELF_CONSISTENCY=FAIL
```

This means the project is currently waiting for the **official Ultralytics PyTorch test reference on the same 1,610-image test split**. The next expected manual step is to run the prepared official test-reference script, not to start FP16.

---

# 5. NEXT INTENDED DIRECTION

This section only reconstructs directions already agreed in the conversation.

## 5.1 Immediate next task

Run an official Ultralytics PyTorch evaluation of Candidate A on the **test split (1,610 images)** to establish the authoritative test metric.

Then compare that metric with the custom evaluator's `0.52415`.

Possible outcomes already agreed:

- if official test is around `0.524`, the `0.609` metric is validation vs test, and the custom evaluator is likely self-consistent;
- if official test is around `0.609`, the custom evaluator still has a bug and should be corrected before FP16.

## 5.2 Next milestone

Unlock **TensorRT FP16** only after FP32 metric provenance/self-consistency passes.

Then:

```text
FP16 build
→ FP16 output/metric parity
→ latency benchmark
→ decide FP16 vs INT8
```

## 5.3 Later planned work

The agreed roadmap after TensorRT:

1. **Slice 5 — Python YOLO + ByteTrack.**
2. **Slice 6 — simulated gimbal + C PID + pymavlink.**
3. **Slice 7 — C++ TensorRT/OpenCV runtime.**

The user wanted the project to continue toward a coherent `GIMBAL` mode where YOLO detects vehicles, ByteTrack provides stable IDs, the user can click/lock a target in the OpenCV dashboard, a C PID module computes gimbal corrections, and `pymavlink` communicates with the simulated gimbal.

## 5.4 Optional work

- More model optimization such as distillation or pruning may be revisited only if evidence shows a real need.
- P2 remains a research artifact unless a later experiment demonstrates a meaningful deployment benefit.
- SAHI is deferred for runtime because the measured end-to-end latency was too high for the intended gimbal loop.

## 5.5 Explicitly out of scope unless reopened

- real hardware UAV flight;
- uncontrolled architecture refactor;
- Kalman filter for Slice 2 moving landing;
- long blind descent using predicted target observations;
- feed-forward from platform ground truth to flight controller;
- using platform ground truth as the flight-control input;
- replacing Python mission orchestration with C++;
- combining ByteTrack/gimbal/TensorRT all in one Slice;
- pushing artifacts to GitHub without an explicit request.

---

# 6. CRITICAL INVARIANTS

These are the constraints the new agent must not casually violate.

## 6.1 Component ownership

- Python Mission Commander owns mission orchestration and MAVSDK flight logic.
- C++ precision landing control owns XY PID/velocity calculation.
- ROS 2 is the canonical Python/C++ communication boundary.
- Do not replace this with JSON files, shared global files, subprocess stdout, or unschematized UDP.
- Do not let C++ PID take over entire mission orchestration unless a future explicit decision says so.

## 6.2 Fixed baseline

- Keep `make demo-python` as the Python fallback/reference path.
- Keep `make demo-cpp` as the fixed C++ regression/demo path.
- Do not break the accepted fixed landing flow while extending moving/AI functionality.

## 6.3 Moving platform

- Moving platform nominal speed is approximately `0.10 m/s`.
- Platform ground truth is for telemetry/metrics/touchdown mapping, not flight control.
- Do not reintroduce ground-truth feed-forward unless explicitly requested later.
- Touchdown priority/latch prevents vision feedback from causing a relaunch after physical contact.
- `action.kill()` is not the normal accepted landing termination path.

## 6.4 Coordinate conventions

Known fixed mapping:

- Gazebo ENU pad position: `X=5.8`, `Y=0`.
- PX4 NED fixed pad coordinate: `North=0.0`, `East=5.8`.

Do not casually swap these axes.

For moving platform telemetry, preserve the explicitly documented ENU↔NED mapping in the current source of truth.

## 6.5 Detection/control semantics

- A real visual observation must not be silently replaced with a prediction and marked `valid=true`.
- Do not reintroduce a long Kalman-prediction takeover without reopening the observation contract.
- Low-altitude moving control is scale-aware, not based solely on a fixed absolute pixel threshold.

## 6.6 Model selection

- Candidate A is the selected deployment candidate.
- Candidate B P2 is research-only unless reopened by evidence.
- SAHI is deferred for runtime because of latency.
- Do not retrain simply to reduce latency before trying TensorRT optimization.

## 6.7 TensorRT

- Candidate A ONNX is frozen entering Slice 4.
- FP32 is the reference precision.
- FP16 is unlocked only after FP32 parity/provenance gate.
- INT8 acceptance was pre-agreed at **mAP drop no more than 2 percentage points**.
- TensorRT engine binaries stay local and ignored.

## 6.8 Git / repository hygiene

Every Slice must end with:

1. acceptance pass;
2. tracked/untracked/ignored artifact audit;
3. dataset/model/report/secret scan;
4. selective staging;
5. commit;
6. merge to `main`;
7. annotated tag;
8. clean working tree;
9. only then open the next Slice.

Never use `git add .` blindly for a Slice closure.

## 6.9 Training control

For major training runs, the user prefers to run the training manually in the foreground so they can observe each epoch, GPU use, losses and validation metrics.

Agent responsibilities:

- prepare scripts/configs;
- explain important parameters and new libraries;
- run lightweight syntax/synthetic checks;
- ask the user to run expensive training/benchmark gates manually.

Do not silently launch long background training.

## 6.10 Scope discipline

Always prioritize:

- current blocker;
- current Slice acceptance;
- minimum necessary changes;
- evidence before tuning;
- no speculative refactor.

The user explicitly wants progress accelerated and does not want broad or tangential implementation.

---

# 7. DO NOT REPEAT

## 7.1 Do not recreate the original camera-pitch `sed` patch

It caused singularity/crash issues and made diagnosis harder. The original PX4 camera model was restored and protected.

## 7.2 Do not replace fixed coordinates with the old incorrect mapping

The fixed landing pad is `N=0, E=5.8`, not `N=5.8, E=0`.

## 7.3 Do not make Gazebo world realism the main task

Heavy Fuel entities were removed for startup determinism. Some visual polish was deliberately deferred. World decoration must not displace core demo progress.

## 7.4 Do not treat Gazebo world RTF as camera FPS

Earlier dashboard metrics confused UI refresh with fresh camera frames. Current terminology distinguishes world/GUI rate from fresh camera FPS.

## 7.5 Do not add Kalman just because moving landing got difficult

A Kalman + predicted-valid-observation path was explicitly rejected for Slice 2. It would alter observation semantics and was not needed for the accepted moving landing path.

## 7.6 Do not use `action.kill()` as normal touchdown termination

It was an interim solution and was superseded by contact-confirmed touchdown + platform stop + graceful disarm.

## 7.7 Do not use platform ground truth to drive the flight controller

Ground truth is an evidence/telemetry source only.

## 7.8 Do not use SAHI as the default gimbal runtime

The measured end-to-end latency was about `90.98 ms`, too slow for the intended ~30 FPS control loop.

## 7.9 Do not make YOLOv8n-P2 the default because its learning curve looks prettier

Its learning curve started lower because it had a less transferable initialization. Candidate A was better on the final accuracy/latency Pareto comparison.

## 7.10 Do not assume retraining lowers latency

Changing weights does not materially reduce graph compute if architecture/input stay the same. TensorRT FP16/INT8 and actual architecture/input changes are the legitimate latency levers.

## 7.11 Do not call mAP50 “accuracy”

mAP50 is one detection metric, not a simple accuracy percentage.

## 7.12 Do not compare validation and test metrics as if they are the same

This is the current active issue. The `0.609` Candidate A metric may be validation; the `0.52415` custom metric is currently from the 1,610-image test path. Confirm before drawing conclusions.

## 7.13 Do not confuse TensorRT build success with TensorRT accuracy parity

Engine creation, engine deserialization, output parity, and metric parity are separate gates.

## 7.14 Do not commit training/data artifacts

Dataset ZIPs, image/label datasets, `.pt`, `.onnx`, `.engine`, training runs, TensorBoard outputs, local evaluation reports and runtime-generated artifacts are local/ignored unless an explicit future decision changes the policy.

## 7.15 Do not start multiple future Slices at once

The agreed sequence is to close the current Slice before opening the next.

---

# 8. WORKING STYLE

## 8.1 User preference: focused progress

The user repeatedly asked for:

- focused execution;
- minimal but sufficient changes;
- no unnecessary refactor;
- no scope creep;
- no long-running agent background tasks when the user can run them manually.

## 8.2 Explain new technical concepts when they matter

The user does want the agent to explain important new definitions/technologies when they enter the project, especially:

- what a missing tool/library is for;
- why a dependency is required;
- why a technique was chosen;
- what a key parameter controls;
- what evidence determines a technique's acceptance or rejection.

But explanations should stay scoped to the current Slice.

## 8.3 Manual gates for important engineering decisions

User explicitly prefers to make or observe key manual decisions such as:

- training runs and epochs;
- meaningful parameter tuning;
- toolchain installation/configuration;
- calibration-set choices;
- final model/engine selection;
- final Git closure.

Agent should prepare exact commands and decision criteria, then stop for user execution where appropriate.

## 8.4 Foreground execution for expensive tasks

For training/benchmark tasks, user wants terminal-visible progress. Do not use hidden background execution for long jobs unless explicitly requested.

## 8.5 Evidence-first debugging

Preferred pattern:

```text
observe
→ isolate blocker
→ identify minimal hypothesis
→ change one thing
→ verify
→ record result
→ stop
```

Avoid changing PID, camera, world, and state machine simultaneously.

## 8.6 Preserve known-good baselines

When a regression appears:

- keep the known-good path;
- isolate the new path;
- compare outputs;
- do not overwrite the Golden baseline.

## 8.7 Report format preference

At the end of each Slice, the user wants a short project-progress checkpoint such as:

```text
Slice 1 — PASS / MERGED
Slice 2 — PASS / MERGED
Slice 3 — PASS / MERGED
Slice 4 — CURRENT BLOCKER: ...
Slice 5 — PENDING
Slice 6 — PENDING
Slice 7 — PENDING
```

This should be appended to future Slice reports to prevent context drift.

## 8.8 Honest status over impressive wording

Do not claim:

- production-ready;
- hardware validated;
- perfectly stable;
- flawless;

unless evidence explicitly supports it. The project is a **SITL engineering prototype** with documented limitations.

---

# 9. SOURCE FILE MANIFEST

> **Important:** The conversation did not provide a complete machine-readable attachment inventory. The entries below include artifacts explicitly named or pasted in the conversation and project screenshots that materially affected decisions. Where the exact local filename or repository status was not visible, the status is marked `UNKNOWN`. A new agent should search the repository for exact current paths rather than assuming every named historical artifact still exists.

## 9.1 Repository files explicitly referenced / known

### `README.md`
- **Type:** Markdown
- **Purpose:** public project documentation, architecture, prerequisites, quick start, limitations, attribution.
- **Where used:** repeatedly updated during project cleanup and Slice 1 documentation.
- **Still relevant:** YES.
- **Equivalent in Git:** YES.
- **Original file needed:** NO, current Git version is authoritative.
- **Status:** CURRENT.

### `.gitignore`
- **Type:** Git config
- **Purpose:** prevent datasets, models, runtime logs, ML reports, caches and environments from entering Git.
- **Where used:** repeated Git hygiene phases; final Slice 3 closure.
- **Still relevant:** YES.
- **Equivalent in Git:** YES.
- **Original file needed:** NO.
- **Status:** CURRENT / CRITICAL.

### `THIRD_PARTY_NOTICES.md`
- **Type:** Markdown
- **Purpose:** preserve upstream MIT notice/attribution for `px4_vision_autonomy`.
- **Where used:** Slice C license/attribution phase.
- **Still relevant:** YES.
- **Equivalent in Git:** YES.
- **Original file needed:** NO.
- **Status:** CURRENT.

### `drone_landing_ws/src/px4_vision_autonomy/LICENSE`
- **Type:** MIT license text
- **Purpose:** preserve upstream package license.
- **Where used:** license/attribution review.
- **Still relevant:** YES.
- **Equivalent in Git:** YES (reported).
- **Original file needed:** NO if present in current repo.
- **Status:** CURRENT.

### `docker-compose.yml`
- **Type:** Compose configuration
- **Purpose:** PX4/Gazebo/ROS2/container orchestration, GPU exposure, IPC configuration.
- **Still relevant:** YES.
- **Equivalent in Git:** YES.
- **Original file needed:** NO.
- **Status:** CURRENT.

### `Dockerfile`
- **Type:** Docker build configuration
- **Purpose:** project/simulation image build; later hardened to remove passwordless sudo and use a non-root runtime user.
- **Still relevant:** YES.
- **Equivalent in Git:** YES.
- **Status:** CURRENT.

### `Makefile`
- **Type:** build/run entrypoint
- **Purpose:** canonical commands such as `make demo-python`, `make demo-cpp`, `make demo-moving-aruco`, tests/build/stop.
- **Still relevant:** YES.
- **Equivalent in Git:** YES.
- **Status:** CURRENT.

### `scripts/run_demo_python_baseline.sh`
- **Type:** Bash
- **Purpose:** Golden Python baseline demo.
- **Where used:** baseline, termination fixes, regression runs.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `scripts/run_demo_cpp_control.sh`
- **Type:** Bash
- **Purpose:** fixed C++ demo.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `scripts/run_demo_moving_aruco.sh`
- **Type:** Bash
- **Purpose:** moving platform demo entrypoint.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `drone_landing_ws/src/px4_vision_autonomy/px4_vision_autonomy/nodes/mission_commander.py`
- **Type:** Python
- **Purpose:** mission state machine, MAVSDK flight control, final approach, touchdown/disarm, metrics.
- **Still relevant:** YES / CRITICAL.
- **Status:** CURRENT.

### `aruco_detector.py`
- **Type:** Python
- **Purpose:** ArUco perception, center error, target observation publishing.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `camera_viewer.py`
- **Type:** Python/OpenCV
- **Purpose:** live dashboard and mission summary/metrics visualization.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `moving_platform_controller.py`
- **Type:** Python
- **Purpose:** moving platform command/telemetry, motion latch, stop at touchdown.
- **Still relevant:** YES.
- **Status:** CURRENT for moving demo.

### `drone_landing_ws/src/precision_landing_interfaces/`
- **Type:** ROS 2 interface package
- **Purpose:** typed ROS 2 contracts.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `drone_landing_ws/src/precision_landing_control_cpp/`
- **Type:** C++ ROS 2 package
- **Purpose:** C++ PID XY controller.
- **Still relevant:** YES / CRITICAL.
- **Status:** CURRENT.

### `precision_landing_control_cpp/config/pid.yaml`
- **Type:** YAML
- **Purpose:** fixed/control PID configuration.
- **Still relevant:** YES.
- **Status:** CURRENT, with moving mode using a separate config during Slice 2.

### `precision_landing_control_cpp/config/pid_moving.yaml`
- **Type:** YAML
- **Purpose:** moving-platform-specific controller settings.
- **Still relevant:** YES.
- **Status:** CURRENT if still present; verify exact values from repository.

### `inspection.sdf`
- **Type:** Gazebo SDF
- **Purpose:** fixed inspection world.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `inspection_moving.sdf`
- **Type:** Gazebo SDF
- **Purpose:** moving landing platform world.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `precision_landing_control_cpp/src/control_node.cpp`
- **Type:** C++
- **Purpose:** typed ROS2 observation → XY PID command.
- **Still relevant:** YES.
- **Status:** CURRENT.

### `control_cpp.launch.py`
- **Type:** ROS 2 launch Python
- **Purpose:** launch/control mode passing including typed/moving mode.
- **Still relevant:** YES.
- **Status:** CURRENT.

---

## 9.2 Evidence / reports explicitly referenced

### `artifacts/logs/REPORT_C1.md`
- **Purpose:** early C++ unit-test evidence.
- **Status:** historical/local; generated reports were intentionally ignored from Git.
- **Current relevance:** historical reference only.

### `artifacts/logs/REPORT_C2.md`
- **Purpose:** shadow mode / moving-control evidence and later FP32 context also used the name `REPORT_C2.md` in a different phase.
- **Status:** historical/local; exact current meaning depends on repository version.
- **Warning:** filename reused conceptually; search current repo before interpreting.

### `artifacts/logs/REPORT_C3.md`
- **Purpose:** C++ runtime/repeatability evidence.
- **Status:** historical/local.

### `docs/evidence/FINAL_TERMINATION_REPORT.md`
- **Purpose:** final mission termination evidence for Slice 1.
- **Status:** historical but relevant for regression/termination rationale.

### `docs/evidence/REPOSITORY_INVENTORY.md`
- **Purpose:** pre-cleanup repository inventory.
- **Status:** historical/local; may be ignored depending on final Git policy.

### `docs/evidence/LICENSE_ATTRIBUTION_REPORT.md`
- **Purpose:** upstream license/attribution decision record.
- **Status:** historical/local.

### `docs/evidence/README_DOCUMENTATION_REPORT.md`
- **Purpose:** README restructuring/verification evidence.
- **Status:** historical/local.

### `docs/evidence/EVIDENCE_CURATION_REPORT.md`
- **Purpose:** engineering evidence curation.
- **Status:** historical/local.

### `docs/evidence/CLEANUP_MANIFEST.md`
- **Purpose:** cleanup candidate inventory.
- **Status:** historical/local.

### `docs/evidence/PHASE_F_CLEANUP_REPORT.md`
- **Purpose:** safe scratch/redundant-file cleanup evidence.
- **Status:** historical/local.

### `docs/evidence/GITIGNORE_REVIEW_REPORT.md`
- **Purpose:** Git ignore rule review.
- **Status:** historical/local.

### `docs/evidence/STATIC_VALIDATION_REPORT.md`
- **Purpose:** static validation of Bash/Python/Compose/package/YAML/Makefile/security checks.
- **Status:** historical/local.

### `docs/evidence/FINAL_ACCEPTANCE_REPORT.md`
- **Purpose:** final repository acceptance, Docker security, clean-clone evidence.
- **Status:** high-value historical evidence.

### `docs/evidence/SLICE_2_MOVING_ARUCO_ACCEPTANCE.md`
- **Purpose:** moving ArUco landing acceptance evidence.
- **Status:** historical/current milestone reference.

### `docs/evidence/SLICE_3_YOLO_ONNX_ACCEPTANCE.md`
- **Purpose:** YOLO baseline training/export acceptance.
- **Status:** historical/local.

### `docs/evidence/SLICE_3B_SMALL_OBJECT_OPTIMIZATION.md`
- **Purpose:** data-centric model optimization, Candidate A/B/SAHI decisions.
- **Status:** high-value historical/current model-selection evidence.

### `docs/evidence/SLICE_3C_PARETO_OPTIMIZATION.md`
- **Purpose:** Candidate A vs P2 causal/latency audit and final model selection.
- **Status:** high-value historical/current model-selection evidence.

### `docs/evidence/SLICE_4_TENSORRT_ACCEPTANCE.md`
- **Purpose:** planned local TensorRT Slice 4 acceptance report.
- **Status:** current Slice 4 artifact but not yet final; verify exact file presence.

### `ml/reports/yolov8n_uavdt_baseline_v1.md`
- **Purpose:** YOLO baseline evaluation.
- **Status:** local/generated; relevant for historical baseline metrics.

### `ml/reports/tensorrt_environment.json`
- **Purpose:** TensorRT environment audit.
- **Status:** local, ignored.

### `ml/reports/tensorrt_fp32_smoke_parity.json`
- **Purpose:** FP32 TensorRT 10-image parity.
- **Status:** local, ignored.

### `ml/reports/tensorrt_fp32_full_parity.json`
- **Purpose:** FP32 TensorRT full 1,610-image parity/metrics.
- **Status:** local, ignored; current blocker context.

### `ml/reports/candidate_a_ultralytics_test_reference.json`
- **Purpose:** planned authoritative official Ultralytics test reference.
- **Status:** planned/current blocker artifact; may not yet exist.

---

## 9.3 ML files / artifacts explicitly referenced

### `ml/datasets/Aerial Vehicles.v1i.yolov8.zip`
- **Type:** dataset archive
- **Purpose:** source Roboflow export for YOLO baseline.
- **Status:** LOCAL ONLY / IGNORED.
- **Relevant:** YES.
- **New agent needs original:** YES if local dataset is needed and available, but can also use a matching local copy with verified metadata/checksum.

### `ml/datasets/derived/uavdt_vehicle_v1/`
- **Purpose:** derived single-class `vehicle` dataset.
- **Status:** LOCAL ONLY / IGNORED.
- **Relevant:** YES.
- **New agent needs original:** YES for retraining/evaluation unless reproducible from raw archive.

### `ml/configs/uavdt_vehicle_v1.yaml`
- **Purpose:** resolved single-class dataset configuration.
- **Status:** SHOULD be tracked if repository policy permits; exact current Git status UNKNOWN.
- **Relevant:** YES.

### `ml/exports/yolov8n_uavdt_vehicle_960_v1.onnx`
- **Purpose:** Candidate A deployment artifact / TensorRT input.
- **Status:** LOCAL ONLY / IGNORED.
- **Relevant:** CRITICAL to Slice 4.
- **New agent needs original:** YES for exact engine reproduction unless regenerated from checkpoint.

### Candidate A `.pt` (`best.pt`)
- **Type:** PyTorch checkpoint
- **Purpose:** final detector candidate training weight.
- **Status:** LOCAL ONLY / IGNORED.
- **Exact path:** repository-relative path not consistently exposed in conversation; likely under `ml/experiments/.../weights/best.pt` — **verify, do not assume**.
- **New agent needs original:** YES for exact evaluation/retraining parity.

### Candidate B P2 `.pt`
- **Purpose:** P2 research experiment.
- **Status:** LOCAL ONLY / IGNORED.
- **Relevant:** historical research artifact only.

### `ml/MODEL_MANIFEST.yaml`
- **Purpose:** model/checksum/environment metadata.
- **Status:** was created and updated; final Git tracking status for current version should be checked.
- **Important:** some final Git hygiene phases indicated the real manifest was intentionally ignored to avoid leaking local artifact metadata; an example/template may be preferred.

---

## 9.4 Generated/debug/scratch artifacts explicitly referenced

These were cleanup candidates or runtime outputs and should not be reintroduced into Git:

- `tmp_upstream/` — removed/redundant upstream clone.
- `fix_waypoint.py` — scratch fix; removed.
- `old_inspection.sdf` — scratch world; removed.
- `transpose_texture.py` — scratch utility; removed.
- `test_topics.txt` — scratch diagnostic.
- `imu.txt` — scratch diagnostic.
- `ps_out.txt` — scratch diagnostic.
- `sitl_logs.txt` — scratch diagnostic.
- `mission_logs.txt` — scratch diagnostic.
- root-level random PNG/JPG debug frames — scratch.
- `debug_frame.png` — tracked once, later removed from Git.
- `snapshot_report.md` — tracked once, later removed from Git.

Exact historical existence/commit details of each cleanup file are documented in conversation reports but may differ from current repository state. New agent should use `git status`, `git log`, and `find` rather than trusting this list as a current inventory.

---

## 9.5 Screenshots/images referenced in conversation

Project-relevant images were shown for:

- OpenCV dashboard readability;
- Gazebo moving platform visual evidence;
- moving platform start/5-second motion evidence;
- final visual-demo screenshots.

Exact source filenames for those chat images are **UNKNOWN** from the accessible conversation context. Some report files referenced paths such as `moving_scan_start.jpg` and `moving_scan_5s.jpg`; those should be treated as historical evidence/local runtime artifacts unless present in current Git.

Unrelated personal ID-photo images from earlier conversation context are **NOT project artifacts** and must not be imported into this project checkpoint.

---

# 10. MIGRATION RISKS

## 10.1 Biggest risk: treating old reports as current source of truth

Many historical reports contain intermediate FAIL states that were later superseded.

Examples:

- C++ FP32 parity intermediate metrics before evaluator fixes;
- moving landing runs before motion latch/contact confirmation;
- P2 candidate that looked good by learning curve but lost on final Pareto;
- interim `action.kill()` termination.

Always prefer the current repository/source and the latest explicit decision over older walkthrough prose.

## 10.2 Biggest TensorRT risk: mixing metric contracts

The current active issue is a difference between:

- Candidate A's reported validation metric (`~0.609` mAP50-95);
- custom 1,610-image test evaluation (`~0.52415`).

Do not call this a TensorRT accuracy problem until the official Ultralytics test reference is established.

## 10.3 Biggest architecture risk: collapsing Python orchestration into C++

The project intentionally demonstrates a Python/C++ boundary. C++ PID is a control component, not the mission state machine.

## 10.4 Biggest control risk: reintroducing ground-truth control

Moving-platform ground truth is telemetry/metrics only.

## 10.5 Biggest perception risk: confusing output parity with metric parity

A TensorRT engine can produce nearly identical detections to PyTorch and still have a faulty evaluator. Keep these gates separate.

## 10.6 Biggest repository risk: uploading artifacts

The user explicitly wants dataset/model/training/report artifacts kept local. A new agent must not use `git add .` when closing a Slice.

## 10.7 Biggest workflow risk: hidden background jobs

The user wants expensive operations visible in their terminal. Do not start long training/benchmark tasks in the background without explicit permission.

## 10.8 Biggest scope risk

The user has repeatedly asked not to broaden the project. Do not re-open rejected techniques (Kalman, SAHI runtime, large architecture sweeps, gimbal/ByteTrack before the TensorRT gate) merely because they are technically interesting.

---

# 11. FINAL CONTINUITY SNAPSHOT

```text
PROJECT:
UAV-precision-landing-simulation — an end-to-end UAV SITL engineering prototype
combining PX4, Gazebo, ROS 2, OpenCV, Python mission orchestration, C++ PID
control, and an optimized YOLO vehicle detector, with an eventual gimbal/ByteTrack
extension.

GOAL:
Demonstrate a coherent Computer Vision + robotics engineering workflow:
fixed ArUco precision landing → moving ArUco platform landing → vehicle detection /
tracking → gimbal control → edge optimization, while keeping Python and C++ roles
clean and using ROS 2 as the interface.

CURRENT PHASE:
Slice 4 — TensorRT optimization.

CURRENT ARCHITECTURE:
PX4 SITL + Gazebo + Docker/Compose; ROS 2 typed interfaces; Python ArUco/mission
orchestration; C++ XY PID; MAVSDK for flight control; OpenCV dashboard; Candidate A
YOLOv8n single-class vehicle model at 960 input; TensorRT 11.2.1.2 FP32 engine
currently built and verified.

LAST VERIFIED SUCCESS:
FP32 TensorRT engine built, serialized, deserialized and showed extremely close
output parity to PyTorch on the full 1,610-image run (mean matched IoU ~0.999906,
mean confidence drift ~0.000103, outputs finite).

CURRENT BLOCKER:
Metric provenance / self-consistency. Custom test-set mAP50-95 is ~0.52415, while
Candidate A's previously reported ~0.609 metric may be validation rather than test.
Need official Ultralytics test evaluation on the same 1,610-image split before FP16.

CURRENT WORK:
Preparing/running the official Ultralytics test-set reference to determine whether
0.609 is a validation metric and 0.52415 is the correct test metric.

NEXT ACTION:
Run the prepared official Ultralytics Candidate A test reference in the foreground.
If its test mAP50-95 ≈ 0.524, close the provenance mismatch, mark FP32 metric
self-consistency PASS, then unlock FP16. If it ≈0.609, continue debugging the custom
metric implementation. Do not build FP16 before this gate.

MOST IMPORTANT DECISIONS:
- Python Mission Commander owns orchestration; C++ PID owns XY control.
- ROS 2 typed interfaces are the Python/C++ boundary.
- Fixed ArUco is the Golden regression baseline.
- Moving platform ground truth is telemetry-only, not flight control.
- Kalman/long blind descent were rejected for Slice 2.
- Candidate A (YOLOv8n single-class vehicle, 960) is the selected detector.
- Candidate B P2 is research-only after Pareto comparison.
- SAHI is deferred for runtime because of high latency.
- TensorRT FP32 is the current reference engine; FP16/INT8 remain gated.
- Every Slice must end with Git hygiene, selective commit, merge, tag and clean tree.
- Dataset/model/generated report artifacts must not be tracked or pushed.

MOST IMPORTANT DO-NOT-REPEAT:
- Do not reintroduce camera-pitch sed hacks.
- Do not use wrong NED/ENU mapping.
- Do not use platform ground truth as flight-control input.
- Do not use action.kill() as normal landing termination.
- Do not re-add long Kalman-predicted `valid=true` observations.
- Do not use SAHI as default gimbal runtime.
- Do not choose P2 merely because its learning curve looks better.
- Do not treat mAP50 as accuracy.
- Do not compare validation and test metrics as one metric.
- Do not treat TensorRT output parity as metric parity.
- Do not silently run long training jobs in the background.
- Do not commit dataset/model/training/report artifacts.

FILES NEW AGENT MUST HAVE:
1. Current Git repository checkout.
2. `README.md` and `.gitignore`.
3. Current PX4/ROS2/Gazebo source tree.
4. `precision_landing_interfaces` package.
5. `precision_landing_control_cpp` package.
6. `mission_commander.py`, `aruco_detector.py`, `camera_viewer.py`,
   `moving_platform_controller.py`.
7. `inspection.sdf` and `inspection_moving.sdf`.
8. Candidate A ONNX artifact locally (ignored) for TensorRT continuation.
9. Candidate A `.pt` artifact locally if exact PyTorch evaluation is needed.
10. `ml/.venv-tensorrt` or an equivalent verified TensorRT environment.
11. Local dataset / derived dataset if evaluation requires local image+label data.
12. Historical evidence reports are helpful but must not override current source;
    if absent, continuity decisions above remain the guide.
```

---

## CONTINUITY HANDOFF RULE

A new agent should begin by reading this file **before proposing any implementation change**, then verify current repository state with:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -10
git tag --list
```

It should then verify the **current blocker only**. It must not restart the roadmap, retrain Candidate A, re-run Slice 2, reintroduce rejected methods, or propose new architecture unless evidence from the current repository shows the checkpoint is stale or incorrect.
