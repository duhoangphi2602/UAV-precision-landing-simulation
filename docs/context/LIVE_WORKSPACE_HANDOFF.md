# LIVE WORKSPACE HANDOFF

> Generated: 2026-08-20 (Asia/Ho_Chi_Minh)  
> Purpose: authoritative local handoff for continuing development after source-lineage recovery.  
> Evidence policy: current filesystem and Git evidence take priority. Historical migration documents are context only and must not be treated as proof of runtime success.

## Executive summary

The later project lineage has been substantially recovered in the live workspace:

- typed ROS 2 interfaces and the Python/C++ typed boundary are present and tracked;
- fixed and moving ArUco landing source is present and tracked;
- moving-platform world, controller, PID configuration, contact handling and demo entrypoint are present and tracked;
- dashboard and mission metrics are present and tracked;
- the ML workspace, YOLO training/evaluation scripts, ONNX tooling and Candidate A selection source are present;
- Candidate A `.pt`, Candidate A ONNX, the raw/derived datasets, FP32 TensorRT engine, parity reports and TensorRT environment are present locally;
- TensorRT builder, inference and parity source exists but is still untracked;
- ten later commits, all important feature branches and all local milestone tags are not present on the verified remote;
- a complete filesystem recovery backup has been created and verified outside the repository.

Current continuation gate: establish the official Ultralytics PyTorch metric for Candidate A on the exact 1,610-image test split, compare it with the custom `0.52415` result, and resolve metric provenance/self-consistency. FP16 remains locked until this gate is resolved.

## 1. Project purpose and canonical architecture

The project is an end-to-end UAV SITL engineering prototype combining:

- PX4 SITL and Gazebo;
- ROS 2 typed interfaces;
- Python perception and mission orchestration;
- C++ XY PID control;
- OpenCV dashboard and mission metrics;
- fixed ArUco precision landing;
- moving ArUco platform landing with contact-confirmed touchdown;
- YOLO vehicle detection and ONNX export;
- TensorRT deployment optimization.

Canonical responsibility split:

```text
Python Mission Commander
  -> mission state, MAVSDK flight control, final approach, touchdown/disarm

ROS 2 typed interfaces
  -> TargetObservation, ControlCommand, MissionStatus, MovingPlatformState

C++ precision_landing_control_cpp
  -> XY PID control

Python camera_viewer
  -> OpenCV dashboard and mission/moving-platform metrics

ML workspace
  -> dataset preparation, YOLO training/evaluation, ONNX export, TensorRT work
```

Moving-platform ground truth is telemetry/metrics only. It must not become a flight-control input.

## 2. Progress completed by milestone

### Baseline — fixed ArUco/C++ PID

Status: `COMPLETED / TRACKED`

- PX4/Gazebo/ROS 2 simulation baseline exists.
- Python fixed-ArUco landing path exists.
- C++ PID controller and fixed demo exist.
- Canonical baseline tag: `cpp-pid-baseline-v1`.

### Slice 1 — engineering interface and dashboard

Status: `COMPLETED / MERGED LOCALLY / TAGGED LOCALLY`

- Added `precision_landing_interfaces`.
- Added typed `TargetObservation`, `ControlCommand` and `MissionStatus` messages.
- Converted the C++ controller boundary to typed ROS messages.
- Added/expanded the OpenCV dashboard and mission metrics.
- Feature commit: `bdc1a4eb5dd1e3742a719239090621a05718e4d6`.
- Merge commit: `75210388258af5f9d26b0da348ef410768a0d24a`.
- Tag: `slice1-engineering-interface-v1`.

### Slice 2 — moving ArUco platform

Status: `COMPLETED / MERGED LOCALLY / TAGGED LOCALLY`

- Added `MovingPlatformState`.
- Added `moving_platform_controller.py`.
- Added `inspection_moving.sdf` with moving platform and contact sensor.
- Added `pid_moving.yaml` and moving-specific launch/control behavior.
- Added `run_demo_moving_aruco.sh`.
- Added Mission Commander moving/final-approach/contact/touchdown logic.
- Added moving-platform metrics and dashboard state.
- Feature commit: `603484f4b886d409a4176d1326d8cf4afcaa877e`.
- Merge commit: `ced5b3e9134aa62150a9cde190714abfa023b13e`.
- Tag: `slice2-moving-aruco-v1`.

### Slice 3 — YOLO/ONNX baseline

Status: `COMPLETED / MERGED LOCALLY / TAGGED LOCALLY`

- Added the `ml/` source/config structure.
- Added dataset validation, visual sanity, training and evaluation scripts.
- Added YOLO baseline configuration.
- Added ONNX export and parity tooling.
- Added tracked dataset YAML files while keeping datasets/models generated artifacts ignored.
- Feature commit: `d2d21e1bd733c1882e2fbda83d1f506d47049e4d`.
- Merge commit: `7263034e14af94af78a4dda9bfeb328fcf9ae722`.
- Tag: `slice3-vehicle-detector-v1`.

### Slice 3B — data-centric small-object optimization

Status: `COMPLETED / SOURCE PRESENT`

- Consolidated the detector target to a single `vehicle` class.
- Prepared the derived `uavdt_vehicle_v1` dataset.
- Increased Candidate A input size to `960`.
- Added Candidate A/B manual run scripts and evaluation tools.
- Candidate A became the deployment candidate.

### Slice 3C — Pareto selection

Status: `COMPLETED / MERGED LOCALLY / TAGGED LOCALLY`

- Compared Candidate A with the P2 Candidate B path.
- Preserved Candidate B as a research artifact.
- Selected Candidate A as the canonical deployment model.
- Kept SAHI out of the runtime path because of latency cost.
- Git-hygiene commit: `87d2669987c41c683d551a1ffef9adb2af870254`.
- Merge commit/current HEAD: `8e3fbd06d1ff493cc1db10143f621e1871e96726`.
- Tag: `slice3c-vehicle-detector-v1`.

### Slice 4 — TensorRT optimization

Status: `IN PROGRESS / SOURCE UNTRACKED / LOCAL ASSETS PRESENT`

Present locally:

- isolated TensorRT environment;
- Candidate A ONNX input;
- FP32 TensorRT engine;
- engine builder;
- TensorRT inference wrapper;
- shared detection/preprocessing/postprocessing contract;
- smoke and full FP32 parity scripts;
- FP32 parity reports;
- PyTorch metric self-check runner.

Not completed or not recovered:

- committed Slice 4 source lineage;
- Slice 4 branch/commit/tag closure;
- TensorRT-specific latency benchmark implementation/report;
- resolved authoritative test-metric provenance;
- FP16 and INT8 gates.

## 3. Current Git state

```text
Current branch: feature/tensorrt-optimization
HEAD:           8e3fbd06d1ff493cc1db10143f621e1871e96726
Local main:     8e3fbd06d1ff493cc1db10143f621e1871e96726
origin/main:    1a2b19687eb1ed01f2fcaa3ef9587baa949c26e9
Ahead/behind:   ahead 10, behind 0
```

Important branches:

```text
feature/typed-interface-dashboard bdc1a4e
feature/moving-aruco-platform     603484f
feature/yolo-uavdt-baseline       d2d21e1
feature/tensorrt-optimization     8e3fbd0
main                              8e3fbd0
origin/main                       1a2b196
```

Important local tags:

```text
cpp-pid-baseline-v1
slice1-engineering-interface-v1
slice2-moving-aruco-v1
slice3-vehicle-detector-v1
slice3c-vehicle-detector-v1
```

Live `git ls-remote` verification found only `refs/heads/main` at `1a2b196` and no remote tags. Therefore all later commits, feature branches and milestone tags are currently local-only.

### Ten local-only commits

```text
e622a4ce730e3ebeee732f7cc8a9644fa3d37dd1  clean up AI scratchpads/evidence and add PROJECT_OVERVIEW
1503422de459193e89a7b35e2c0701fcdfa25715  remove UPSTREAM_BASELINE audit report
bdc1a4eb5dd1e3742a719239090621a05718e4d6  typed ROS2 interfaces and landing dashboard
75210388258af5f9d26b0da348ef410768a0d24a  merge typed interfaces/dashboard slice
603484f4b886d409a4176d1326d8cf4afcaa877e  moving ArUco platform landing
ced5b3e9134aa62150a9cde190714abfa023b13e  merge moving ArUco slice
d2d21e1bd733c1882e2fbda83d1f506d47049e4d  optimized UAV vehicle detector pipeline
7263034e14af94af78a4dda9bfeb328fcf9ae722  merge vehicle detector pipeline
87d2669987c41c683d551a1ffef9adb2af870254  Slice 3C Git-hygiene update
8e3fbd06d1ff493cc1db10143f621e1871e96726  merge optimized detector slice
```

## 4. Current working tree

### Modified tracked file

```text
M  .gitignore
```

### Untracked non-TensorRT source

```text
drone_landing_ws/src/px4_vision_autonomy/scripts/capture_frame.py
drone_landing_ws/src/px4_vision_autonomy/scripts/smoke_plugin.py
```

### Untracked TensorRT source/config

```text
ml/configs/tensorrt_candidate_a_fp32.yaml
ml/scripts/build_tensorrt_engines.py
ml/scripts/fp32_full_parity.py
ml/scripts/fp32_smoke_parity.py
ml/scripts/inspect_onnx.py
ml/scripts/run_fp32_parity_full_manual.sh
ml/scripts/run_fp32_parity_smoke_manual.sh
ml/scripts/run_fp32_pytorch_metric_selfcheck_manual.sh
ml/scripts/verify_ort_preload.py
ml/scripts/verify_tensorrt_install.py
ml/tensorrt/detection_contract.py
ml/tensorrt/infer.py
```

### Important ignored content

```text
docs/context/
docs/plans/
artifacts/
ml/.venv/
ml/.venv-tensorrt/
ml/datasets/
ml/experiments/
ml/exports/
ml/reports/
```

Do not run `git clean` or any cleanup operation against this workspace. Untracked TensorRT source and ignored assets are part of the recovered project state.

## 5. Recovered source lineage inventory

| Area | Status | Current evidence |
|---|---|---|
| Typed ROS interfaces | PRESENT / TRACKED | `drone_landing_ws/src/precision_landing_interfaces/` |
| Target observation contract | PRESENT / TRACKED | `TargetObservation.msg` and Python/C++ consumers |
| Moving platform state | PRESENT / TRACKED | `MovingPlatformState.msg` and consumers |
| Moving controller | PRESENT / TRACKED | `moving_platform_controller.py` |
| Moving world/contact | PRESENT / TRACKED | `inspection_moving.sdf` |
| Moving PID/demo | PRESENT / TRACKED | `pid_moving.yaml`, launch and demo script |
| Mission contact/final approach | PRESENT / TRACKED | `mission_commander.py` |
| Dashboard/metrics | PRESENT / TRACKED | `camera_viewer.py` and mission metrics |
| ML source/config | PRESENT / TRACKED | `ml/configs/`, tracked `ml/scripts/` |
| YOLO/ONNX tooling | PRESENT / TRACKED | train/export/parity/evaluation scripts |
| Candidate A assets | PRESENT / IGNORED | exact `.pt` and ONNX |
| Historical Candidate A manifest | HISTORICAL ONLY | local branch `feature/yolo-uavdt-baseline` |
| TensorRT source | PRESENT / UNTRACKED | builder, inference, contract, parity scripts |
| TensorRT reports/engine/env | PRESENT / IGNORED | local reports, engine and venv |
| TensorRT committed lineage | MISSING | no Slice 4 commit/tag |
| TensorRT benchmark code/report | MISSING | not found in available local evidence |

## 6. Critical local assets

### Candidate A checkpoint

```text
Path:   ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt
Size:   6,297,066 bytes
SHA256: 190cd1091adae5fbfde747ce3075e4c2038e66629de0328acb66d230d6f92f71
```

### Candidate A ONNX

```text
Path:   ml/exports/yolov8n_uavdt_vehicle_960_v1.onnx
Size:   12,475,282 bytes
SHA256: ef39f723aa4dafbf7a5a31bed10bb76cba7430a77f5ab6dc24b4f12eccf48245
```

Both Candidate A hashes exactly match `ml/MODEL_MANIFEST.yaml` preserved on local branch `feature/yolo-uavdt-baseline`.

### Dataset

```text
Source archive:
  ml/datasets/Aerial Vehicles.v1i.yolov8.zip
  940,401,248 bytes
  SHA256 2ec06256d8e88600c83316d31c300b348ec180e2720e73625cb9f58a096b5ba7

Raw dataset root:
  ml/datasets/raw/uavdt/aerial_vehicles_v1
  train: 6,469 images + 6,469 labels
  valid:   547 images +   547 labels
  test:  1,610 images + 1,610 labels

Derived single-class dataset:
  ml/datasets/derived/uavdt_vehicle_v1
  train: 6,469 image symlinks + labels
  valid:   547 image symlinks + labels
  test:  1,610 image symlinks + labels
```

### FP32 TensorRT engine

```text
Path:   ml/exports/tensorrt/yolov8n_uavdt_vehicle_960_v1_fp32.engine
Size:   143,045,748 bytes
SHA256: df2f920e1caed46a489c8c1c674fb559a78c8277f22198838261321d96854f90
```

### TensorRT reports

```text
ml/reports/tensorrt_environment.json          702 bytes
ml/reports/tensorrt_fp32_smoke_parity.json   409 bytes
ml/reports/tensorrt_fp32_full_parity.json     859 bytes
```

### Environments

```text
ml/.venv/             present, ignored
ml/.venv-tensorrt/    present, ignored, approximately 10 GB
```

TensorRT environment package metadata includes TensorRT `11.2.1.2` and ONNX Runtime GPU `1.27.0`. Runtime readiness has not been revalidated during migration.

## 7. Current technical state

```text
Current phase:
  Slice 4 — TensorRT optimization

Current sub-phase:
  FP32 metric provenance / evaluator self-consistency gate

Canonical model:
  Candidate A — YOLOv8n, single-class vehicle, imgsz=960

TensorRT toolchain:
  Environment present; historically remediated; current runtime not verified

FP32 build:
  Engine present and checksum verified; historical build recorded PASS

FP32 output parity:
  Local smoke/full reports record PASS; not rerun during migration

FP32 metric state:
  Provenance/self-consistency unresolved

FP16:
  LOCKED

INT8:
  LOCKED
```

The recorded `tensorrt_environment.json` is an older blocked-toolchain snapshot and predates the later environment/engine/parity artifacts. Do not treat it as current runtime truth. Conversely, do not treat historical PASS claims as a substitute for a future authorized runtime check.

## 8. Current blocker and unresolved items

### Primary blocker

The authoritative metric contract is unresolved:

- historical Candidate A result: approximately `0.609 mAP50-95`;
- custom evaluation on the 1,610-image test path: `0.52415 mAP50-95`;
- historical context suggests validation-vs-test provenance may explain the difference, but this is not proven.

### Required unresolved items

- official Ultralytics Candidate A metric on the exact 1,610-image test split;
- provenance of `0.609` versus `0.52415`;
- evaluator self-consistency before any FP16 work;
- Git provenance and selective review of untracked TensorRT source;
- remote protection of the ten local-only commits and local tags;
- current Docker/GPU/NVIDIA runtime readiness;
- current TensorRT environment and engine runtime compatibility;
- missing `docs/context/CURRENT_STATE.md`;
- missing `docs/context/DECISION_LOG.md`;
- missing TensorRT-specific latency benchmark implementation/report.

No unresolved item should be silently converted into PASS.

## 9. Environment readiness

| Component | Status | Basis |
|---|---|---|
| Docker access | UNKNOWN | not validated during migration |
| GPU | PRESENT BUT NOT VERIFIED | historical/local metadata identifies RTX 3060 |
| NVIDIA container runtime | PRESENT BUT NOT VERIFIED | historically configured, not revalidated |
| Python ML environment | PRESENT BUT NOT VERIFIED | local ignored environment exists |
| TensorRT environment | PRESENT BUT NOT VERIFIED | venv and package metadata exist |
| Dataset availability | READY FOR ACCESS | files/counts present and backup verified |
| Candidate A availability | READY FOR ACCESS | `.pt` and ONNX checksums verified |
| FP32 engine availability | PRESENT BUT NOT VERIFIED | checksum verified; execution not revalidated |

## 10. Migration documents

```text
docs/context/CURRENT_STATE.md       MISSING
docs/context/DECISION_LOG.md        MISSING
docs/context/PROJECT_CONTINUITY.md  PRESENT / IGNORED
docs/context/MIGRATION_FILE_MANIFEST.md PRESENT / IGNORED
docs/context/REPO_CONTEXT_GAPS.md   PRESENT / IGNORED
```

The available historical documents are useful for identifying what to search for and reconstructing user-provided context. Current source, Git refs and local assets remain the evidence for what actually exists.

## 11. Verified recovery backup

```text
Path:
  /home/hoangphi/Projects/UAV-precision-landing-simulation_RECOVERY_BACKUP_20260820

Size:
  19,572,599,610 bytes (19G)

Verification:
  source/backup inventory identical
  14,333 directories
  106,079 files
  8,797 symlinks
  critical source/docs byte-identical
  four critical asset checksums identical
  Git HEAD/branch/refs identical
  reflogs present
  Git object connectivity verified
```

The backup is a safety copy. Continue development only in the live workspace unless the user explicitly chooses a different recovery procedure.

## 12. Exact continuation point

One next technical task, after explicit user permission to resume development:

> Run the official Ultralytics PyTorch evaluation of Candidate A on the exact 1,610-image test split, compare the result with the custom `0.52415` metric, and resolve metric provenance/evaluator self-consistency.

Decision gate:

```text
Official test metric approximately 0.524
  -> likely validation-vs-test provenance difference
  -> document authoritative split/metric contract
  -> close FP32 self-consistency gate if evidence supports it

Official test metric approximately 0.609
  -> custom evaluator remains suspect
  -> investigate evaluator contract without forcing agreement

Until resolved
  -> FP16 LOCKED
  -> INT8 LOCKED
```

## 13. Do-not-do list

Before explicit user authorization:

- do not run `git clean`;
- do not reset, checkout, merge or overwrite the working tree;
- do not overwrite untracked TensorRT source;
- do not delete ignored datasets, models, reports, engine or environments;
- do not replace Candidate A;
- do not retrain Candidate A or Candidate B;
- do not change the dataset split;
- do not edit the evaluator merely to force metric agreement;
- do not unlock FP16 or INT8;
- do not treat `0.609` and `0.52415` as the same metric without provenance evidence;
- do not promote historical intermediate configurations to current configuration;
- do not push or commit without selective review and user authorization;
- do not recreate missing historical documents as if they were originals.

## 14. Final handoff status

```text
WORKSPACE READY FOR CONTINUATION:
  YES WITH SAFETY RISKS

CONTEXT MIGRATION:
  COMPLETE

SOURCE LINEAGE:
  PARTIALLY RECOVERED

PRIMARY SAFETY RISKS:
  ten commits and all milestone tags are local-only
  TensorRT source/config is untracked
  critical ML/TensorRT assets are ignored

BACKUP:
  VERIFIED

NEXT TASK:
  Official Ultralytics PyTorch Candidate A evaluation on the exact
  1,610-image test split; compare with custom 0.52415 and resolve
  provenance/self-consistency before unlocking FP16.
```
